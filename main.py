# main.py (핵심 기능 중심의 간소화 버전 - 들여쓰기 수정)
import os
import sys
import time
import signal
import threading
import argparse
import subprocess

from pathlib import Path

# 프로젝트 모듈 임포트
from config import SIMULATION_MODE
from utils.serial_reader import read_uid
from utils.server_request import verify_rfid_uid, get_dispense_list, report_dispense_result, confirm_user_intake, get_user_slot_mapping
from core.dispenser import trigger_slot_dispense, init_gpio, cleanup_gpio
from core.state_controller import StateController

try:
    from dispenser_gui import show_main_screen
    GUI_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] GUI 모듈 로드 실패: {e}")
    GUI_AVAILABLE = False

class SimpleMedicineDispenser:
    """간소화된 약 디스펜서 메인 시스템"""
    
    def __init__(self, enable_gui=False):
        self.running = True
        self.state_controller = StateController()
        self.device_id = self.load_device_id()
        
        # ✅ GUI 관련 설정 추가
        self.enable_gui = enable_gui and GUI_AVAILABLE
        self.gui_thread = None
        self.gui_message_queue = None
        
        # ✅ 슬롯 매핑 캐시 추가
        self.slot_mapping_cache = {}
        self.slot_mapping_last_update = 0
        self.slot_mapping_cache_duration = 300  # 5분 캐시
        
        # 통계 정보 (간단하게)
        self.stats = {
            'total_scans': 0,
            'successful_auth': 0,
            'failed_auth': 0,
            'medicines_dispensed': 0,
            'intake_confirmations': 0,
            'duplicate_attempts': 0  # ✅ 중복 시도 추가
        }
        
        print(f"[SYSTEM] 디스펜서 초기화 완료 - Device ID: {self.device_id}")
        print(f"[SYSTEM] 시뮬레이션 모드: {'ON' if SIMULATION_MODE else 'OFF'}")
        print(f"[SYSTEM] GUI 모드: {'ON' if self.enable_gui else 'OFF'}")
    
    def start_gui(self):
            """GUI 시작 (별도 스레드에서)"""
            if not self.enable_gui:
                return
            
            try:
                print("[GUI] GUI 시작 중...")

                # ✅ 라즈베리파이 환경에서 DISPLAY 환경변수 자동 설정
                self._setup_display_environment()
                
                # GUI 메시지 큐 초기화 (추후 GUI와 통신용)
                import queue
                self.gui_message_queue = queue.Queue()
                
                # GUI를 별도 스레드에서 실행
                def run_gui():
                    try:
                        show_main_screen(self.device_id)
                    except Exception as e:
                        print(f"[ERROR] GUI 실행 오류: {e}")
                        self.enable_gui = False
                
                self.gui_thread = threading.Thread(target=run_gui, daemon=True)
                self.gui_thread.start()
                
                print("[GUI] ✅ GUI 스레드 시작 완료")
                
                # GUI 초기화 대기 (약간의 지연)
                time.sleep(2)
                
            except Exception as e:
                print(f"[ERROR] GUI 시작 실패: {e}")
                self.enable_gui = False

    def _setup_display_environment(self):
        """디스플레이 환경 설정 (라즈베리파이용)"""
        try:
            current_display = os.environ.get('DISPLAY')
            
            if not current_display:
                # DISPLAY 환경변수가 없으면 기본값 설정
                os.environ['DISPLAY'] = ':0'
                print(f"[GUI] DISPLAY 환경변수 설정: :0")
            else:
                print(f"[GUI] 기존 DISPLAY 환경변수 사용: {current_display}")
            
            # X11 권한 설정 시도
            try:
                subprocess.run(['xhost', '+local:'], 
                             check=False, capture_output=True, timeout=5)
                print("[GUI] X11 접근 권한 설정 완료")
            except:
                print("[GUI] X11 권한 설정 건너뛰기")
            
            # 화면 보호기 비활성화 시도
            try:
                subprocess.run(['xset', 's', 'off'], 
                             check=False, capture_output=True, timeout=5)
                subprocess.run(['xset', '-dpms'], 
                             check=False, capture_output=True, timeout=5)
                print("[GUI] 화면 보호기 비활성화 완료")
            except:
                print("[GUI] 화면 보호기 설정 건너뛰기")
                
        except Exception as e:
            print(f"[WARNING] 디스플레이 환경 설정 오류: {e}")
            # 기본값 강제 설정
            os.environ['DISPLAY'] = ':0'

    def send_gui_message(self, message_type, data=None):
        """GUI에 메시지 전송"""
        if not self.enable_gui or not self.gui_message_queue:
            return
        
        try:
            message = {
                'type': message_type,
                'data': data,
                'timestamp': time.time()
            }
            self.gui_message_queue.put_nowait(message)
        except Exception as e:
            print(f"[ERROR] GUI 메시지 전송 오류: {e}")

    def load_device_id(self):
        """디바이스 ID 로드 또는 생성"""
        try:
            # muid.txt에서 로드
            muid_file = Path('muid.txt')
            if muid_file.exists():
                device_id = muid_file.read_text().strip()
                print(f"[SYSTEM] 기존 Device ID 로드: {device_id}")
                return device_id
            else:
                # 새로 생성 (간단한 형태)
                import uuid
                device_id = str(uuid.uuid4())[:8].upper()
                muid_file.write_text(device_id)
                print(f"[SYSTEM] 새 Device ID 생성: {device_id}")
                return device_id
        except Exception as e:
            print(f"[ERROR] Device ID 처리 오류: {e}")
            return "UNKNOWN"
    
    def get_slot_mapping(self):
        """슬롯 매핑 정보 조회 (캐시 적용)"""
        current_time = time.time()
        
        # 캐시가 유효한 경우 재사용
        if (self.slot_mapping_cache and 
            current_time - self.slot_mapping_last_update < self.slot_mapping_cache_duration):
            return self.slot_mapping_cache
        
        print("[MAPPING] 슬롯 매핑 정보 업데이트 중...")
        
        try:
            slot_mapping = get_user_slot_mapping(self.device_id)
            
            if slot_mapping:
                self.slot_mapping_cache = slot_mapping
                self.slot_mapping_last_update = current_time
                print(f"[MAPPING] ✅ 슬롯 매핑 업데이트 완료: {slot_mapping}")
                return slot_mapping
            else:
                print("[MAPPING] ⚠️ 슬롯 매핑 정보를 가져올 수 없습니다. 기본값 사용")
                # 기본값 반환 (호환성 유지)
                return {
                    'M001': 1,
                    'M002': 2, 
                    'M003': 3
                }
                
        except Exception as e:
            print(f"[ERROR] 슬롯 매핑 조회 오류: {e}")
            return {}
    
    def setup_signal_handlers(self):
        """시스템 종료 신호 처리"""
        def signal_handler(signum, frame):
            print(f"\n[SYSTEM] 종료 신호 수신 ({signum})")
            self.shutdown()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def initialize_hardware(self):
        """하드웨어 초기화"""
        if SIMULATION_MODE:
            print("[HARDWARE] 시뮬레이션 모드 - 하드웨어 초기화 생략")
            return True
        
        try:
            success = init_gpio()
            if success:
                print("[HARDWARE] GPIO 초기화 완료")
                return True
            else:
                print("[ERROR] GPIO 초기화 실패")
                return False
        except Exception as e:
            print(f"[ERROR] 하드웨어 초기화 오류: {e}")
            return False
    
    def process_rfid_scan(self, uid):
        """RFID 스캔 처리 - took_today 체크 로직 수정"""
        print(f"\n[RFID] 카드 스캔: {uid}")
        self.stats['total_scans'] += 1
        
        # 1단계: 사용자 인증
        print("[AUTH] 사용자 인증 중...")
        auth_result = verify_rfid_uid(uid)
        
        if not auth_result or auth_result.get('status') != 'ok':
            print("[AUTH] ❌ 인증 실패")
            self.stats['failed_auth'] += 1
            
            if auth_result and auth_result.get('status') == 'unregistered':
                print("[INFO] 미등록 사용자 - 앱에서 등록이 필요합니다")
            
            return False
        
        # 인증 성공
        user = auth_result.get('user', {})
        user_name = user.get('name', '사용자')
        user_id = user.get('user_id', 'unknown')
        print(f"[AUTH] ✅ 인증 성공: {user_name} (ID: {user_id})")
        self.stats['successful_auth'] += 1
        
        # ✅ 2단계: took_today 체크 (수정된 부분)
        took_today = user.get('took_today', 0)
        print(f"[CHECK] took_today 상태 확인: {took_today}")
        
        if took_today == 1:
            print(f"[CHECK] ⚠️ {user_name}님은 이미 오늘 약을 받으셨습니다")
            print("[CHECK] 🚫 중복 배출을 방지합니다")
            
            # 통계 업데이트 (중복 시도)
            if 'duplicate_attempts' not in self.stats:
                self.stats['duplicate_attempts'] = 0
            self.stats['duplicate_attempts'] += 1
            
            # 사용자에게 알림 (GUI가 있다면 표시)
            self._show_already_taken_message(user_name)
            
            # ✅ 중요: 여기서 바로 리턴하여 배출 로직을 실행하지 않음
            return True  # 성공으로 처리하되 배출은 하지 않음
        
        print(f"[CHECK] ✅ {user_name}님 오늘 첫 약 수령 - 배출 진행")
        
        # 3단계: 배출할 약 목록 조회 (슬롯 정보 포함)
        print("[MEDICINE] 배출 대상 약 조회 중...")
        dispense_list = get_dispense_list(uid)
        
        if not dispense_list:
            print("[MEDICINE] 현재 시간에 복용할 약이 없습니다")
            return True
        
        print(f"[MEDICINE] 배출 대상: {len(dispense_list)}개")
        for item in dispense_list:
            med_name = item.get('medicine_name', 'Unknown')
            dose = item.get('dose', 1)
            slot = item.get('slot', 'Unknown')
            time_of_day = item.get('time_of_day', '')
            print(f"  - {med_name} ({dose}개) [슬롯 {slot}] [{time_of_day}]")
        
        # 4단계: 약 배출 실행
        print("[DISPENSE] 약 배출 시작...")
        success_list = self.execute_medicine_dispense(dispense_list)
        
        if success_list:
            print(f"[DISPENSE] ✅ 배출 완료: {len(success_list)}개")
            self.stats['medicines_dispensed'] += len(success_list)
            
            # 5단계: 결과 서버 전송
            print("[SERVER] 배출 결과 전송 중...")
            result = report_dispense_result(uid, success_list)
            if result:
                print("[SERVER] ✅ 결과 전송 완료")
            else:
                print("[SERVER] ⚠️ 결과 전송 실패")
            
            # ✅ 6단계: 복용 완료 처리 (took_today = 1로 설정)
            print("[CONFIRM] 복용 완료 처리 중...")
            try:
                confirm_result = confirm_user_intake(uid)
                
                if confirm_result and confirm_result.get('status') in ['confirmed', 'already_confirmed']:
                    print(f"[CONFIRM] ✅ 복용 완료: {confirm_result.get('message', '')}")
                    self.stats['intake_confirmations'] += 1
                else:
                    print("[CONFIRM] ⚠️ 복용 완료 처리 실패")
                    
            except Exception as e:
                print(f"[ERROR] 복용 완료 처리 오류: {e}")
        else:
            print("[DISPENSE] ❌ 약 배출 실패")
        
        return len(success_list) > 0

    def _show_already_taken_message(self, user_name):
        """이미 약을 받은 사용자에게 메시지 표시 (GUI 통합)"""
        try:
            # 콘솔 메시지
            print("="*50)
            print(f"🔔 {user_name}님께 알림")
            print("오늘 이미 약을 받으셨습니다.")
            print("내일 다시 이용해주세요.")
            print("="*50)
            
            # ✅ GUI에도 메시지 전송
            if self.enable_gui:
                self.send_gui_message('show_already_taken', {
                    'user_name': user_name,
                    'message': '오늘 이미 약을 받으셨습니다.'
                })
            
            # 간단한 대기 시간 (사용자가 메시지를 읽을 수 있도록)
            time.sleep(3)
            
        except Exception as e:
            print(f"[ERROR] 알림 메시지 표시 오류: {e}")
    
    def execute_medicine_dispense(self, dispense_list):
        """약 배출 실행 (개선된 슬롯 매핑 사용)"""
        success_list = []
        
        # ✅ 서버에서 실제 슬롯 매핑 정보 가져오기
        slot_mapping = self.get_slot_mapping()
        
        if not slot_mapping:
            print("[ERROR] 슬롯 매핑 정보를 가져올 수 없습니다")
            return success_list
        
        for item in dispense_list:
            medi_id = item.get('medi_id')
            dose = item.get('dose', 1)
            medicine_name = item.get('medicine_name', medi_id)
            
            # ✅ 서버 응답에 slot 정보가 있으면 우선 사용
            if 'slot' in item and item['slot']:
                slot_num = item['slot']
                print(f"[DISPENSE] 서버 슬롯 정보 사용: {medicine_name} -> 슬롯 {slot_num}")
            else:
                # 슬롯 매핑에서 조회
                slot_num = slot_mapping.get(medi_id)
                if not slot_num:
                    print(f"[ERROR] {medi_id}에 대한 슬롯 정보 없음")
                    continue
                print(f"[DISPENSE] 매핑 테이블 사용: {medicine_name} -> 슬롯 {slot_num}")
            
            print(f"[DISPENSE] {medicine_name} 배출 중... (슬롯 {slot_num}, {dose}개)")
            
            try:
                if SIMULATION_MODE:
                    # 시뮬레이션: 성공으로 처리
                    print(f"[SIMULATION] {medicine_name} 배출 시뮬레이션 완료")
                    time.sleep(1)  # 배출 시간 시뮬레이션
                    success = True
                else:
                    # 실제 하드웨어 제어
                    success = trigger_slot_dispense(slot_num, dose)
                
                if success:
                    success_list.append({
                        "medi_id": medi_id,
                        "dose": dose
                    })
                    print(f"[DISPENSE] ✅ {medicine_name} 배출 성공")
                else:
                    print(f"[DISPENSE] ❌ {medicine_name} 배출 실패")
                    
            except Exception as e:
                print(f"[ERROR] {medicine_name} 배출 중 오류: {e}")
                continue
        
        return success_list
    
    def main_loop(self):
        """메인 실행 루프 (GUI 통합)"""
        print("\n" + "="*50)
        print("🏥 Smart Medicine Dispenser 시작")
        if self.enable_gui:
            print("🖥️  GUI 모드 활성화")
        print("="*50)
        
        if SIMULATION_MODE:
            print("\n📋 시뮬레이션 모드 사용법:")
            print("  - UID를 콘솔에 입력하세요 (예: K001, K002)")
            print("  - 'quit' 입력시 종료")
            print("  - 테스트용 UID: K001, K002, K003")
        else:
            print("\n🔍 RFID 카드를 대기 중...")
        
        print()
        
        consecutive_errors = 0
        max_errors = 5
        
        while self.running:
            try:
                # RFID UID 읽기
                uid = read_uid()
                
                if uid:
                    # 시뮬레이션 모드에서 'quit' 명령 처리
                    if SIMULATION_MODE and uid.lower() == 'quit':
                        print("[SYSTEM] 사용자 종료 요청")
                        break
                    
                    # 중복 처리 방지
                    if self.state_controller.is_processing(uid):
                        print(f"[WARNING] {uid} 이미 처리 중...")
                        continue
                    
                    # ✅ GUI에 RFID 감지 알림
                    if self.enable_gui:
                        self.send_gui_message('rfid_detected', {'uid': uid})
                    
                    # RFID 처리
                    self.state_controller.set_processing(uid)
                    try:
                        success = self.process_rfid_scan(uid)
                        consecutive_errors = 0  # 성공시 에러 카운트 리셋
                        
                        # ✅ GUI에 처리 결과 알림
                        if self.enable_gui:
                            self.send_gui_message('rfid_processed', {
                                'uid': uid,
                                'success': success
                            })
                            
                    finally:
                        self.state_controller.clear()
                    
                    # 처리 완료 후 잠시 대기
                    time.sleep(1)
                else:
                    # UID가 없을 때는 짧게 대기
                    time.sleep(0.5)
                
            except KeyboardInterrupt:
                print("\n[SYSTEM] 키보드 인터럽트 - 종료")
                break
            except Exception as e:
                consecutive_errors += 1
                print(f"[ERROR] 메인 루프 오류: {e}")
                
                if consecutive_errors >= max_errors:
                    print(f"[CRITICAL] 연속 {max_errors}회 오류 - 시스템 종료")
                    break
                
                time.sleep(2)  # 오류 발생시 2초 대기
    
    def print_stats(self):
        """통계 정보 출력 (개선)"""
        print("\n" + "="*30)
        print("📊 시스템 통계")
        print("="*30)
        print(f"총 스캔 수: {self.stats['total_scans']}")
        print(f"인증 성공: {self.stats['successful_auth']}")
        print(f"인증 실패: {self.stats['failed_auth']}")
        print(f"약 배출 수: {self.stats['medicines_dispensed']}")
        print(f"복용 완료 처리: {self.stats['intake_confirmations']}")  # ✅ 추가
        
        if self.stats['total_scans'] > 0:
            success_rate = (self.stats['successful_auth'] / self.stats['total_scans']) * 100
            print(f"인증 성공률: {success_rate:.1f}%")
        
        # ✅ 슬롯 매핑 캐시 정보
        if self.slot_mapping_cache:
            print(f"현재 슬롯 매핑: {self.slot_mapping_cache}")
        
        print("="*30)
    
    def shutdown(self):
        """시스템 종료"""
        if not self.running:  # 이미 종료 중이면 중복 실행 방지
            return
            
        print("\n[SYSTEM] 시스템 종료 중...")
        self.running = False
        
        # 통계 출력
        self.print_stats()
        
        # 하드웨어 정리
        if not SIMULATION_MODE:
            try:
                cleanup_gpio()
                print("[HARDWARE] GPIO 정리 완료")
            except Exception as e:
                print(f"[ERROR] GPIO 정리 오류: {e}")
        
        print("[SYSTEM] 종료 완료")
    
    def run(self):
        """시스템 실행 (GUI 통합)"""
        try:
            # 신호 처리기 설정
            self.setup_signal_handlers()
            
            # GUI 시작 (활성화된 경우)
            if self.enable_gui:
                self.start_gui()
            
            # 하드웨어 초기화
            if not self.initialize_hardware():
                print("[CRITICAL] 하드웨어 초기화 실패 - 종료")
                return False
            
            # 메인 루프 실행
            self.main_loop()
            
            return True
            
        except Exception as e:
            print(f"[CRITICAL] 시스템 실행 오류: {e}")
            return False
        finally:
            self.shutdown()



def main():
    """메인 진입점 (명령행 인자 처리 추가)"""
    try:
        # ✅ 명령행 인자 파싱
        parser = argparse.ArgumentParser(description='Smart Medicine Dispenser')
        parser.add_argument('--gui', action='store_true', 
                          help='GUI 모드로 실행 (라즈베리파이 모니터 출력)')
        parser.add_argument('--console', action='store_true',
                          help='콘솔 모드로 실행 (기본값)')
        parser.add_argument('--auto-gui', action='store_true',
                          help='라즈베리파이에서 자동으로 GUI 모드 실행')
        
        args = parser.parse_args()
        
        # GUI 모드 결정
        enable_gui = False
        
        if args.gui:
            enable_gui = True
            print("[SYSTEM] GUI 모드로 시작")
        elif args.auto_gui and RASPBERRY_PI_CONFIG.get('auto_start_gui', False):
            enable_gui = True
            print("[SYSTEM] 자동 GUI 모드로 시작")
        elif args.console:
            enable_gui = False
            print("[SYSTEM] 콘솔 모드로 시작")
        else:
            # 기본값: 라즈베리파이이고 모니터가 연결되어 있으면 GUI 모드
            try:
                import platform
                is_raspberry_pi = 'arm' in platform.machine().lower()
                has_display = os.environ.get('DISPLAY') is not None
                
                if is_raspberry_pi and has_display:
                    enable_gui = True
                    print("[SYSTEM] 라즈베리파이 환경 감지 - GUI 모드로 시작")
                else:
                    enable_gui = False
                    print("[SYSTEM] 콘솔 모드로 시작")
            except:
                enable_gui = False
                print("[SYSTEM] 기본 콘솔 모드로 시작")
        
        # 작업 디렉토리 설정
        script_dir = Path(__file__).parent
        os.chdir(script_dir)
        
        # 시스템 생성 및 실행
        dispenser = SimpleMedicineDispenser(enable_gui=enable_gui)
        success = dispenser.run()
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"[CRITICAL] 시스템 시작 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()