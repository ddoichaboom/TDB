# main.py (핵심 기능 중심의 간소화 버전)
import os
import sys
import time
import signal
import threading
from pathlib import Path

# 프로젝트 모듈 임포트
from config import SIMULATION_MODE
from utils.serial_reader import read_uid
from utils.server_request import verify_rfid_uid, get_dispense_list, report_dispense_result
from core.dispenser import trigger_slot_dispense, init_gpio, cleanup_gpio
from core.state_controller import StateController

class SimpleMedicineDispenser:
    """간소화된 약 디스펜서 메인 시스템"""
    
    def __init__(self):
        self.running = True
        self.state_controller = StateController()
        self.device_id = self.load_device_id()
        
        # 통계 정보 (간단하게)
        self.stats = {
            'total_scans': 0,
            'successful_auth': 0,
            'failed_auth': 0,
            'medicines_dispensed': 0
        }
        
        print(f"[SYSTEM] 디스펜서 초기화 완료 - Device ID: {self.device_id}")
        print(f"[SYSTEM] 시뮬레이션 모드: {'ON' if SIMULATION_MODE else 'OFF'}")
    
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
        """RFID 스캔 처리 - 핵심 비즈니스 로직"""
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
        print(f"[AUTH] ✅ 인증 성공: {user_name}")
        self.stats['successful_auth'] += 1
        
        # 2단계: 배출할 약 목록 조회
        print("[MEDICINE] 배출 대상 약 조회 중...")
        dispense_list = get_dispense_list(uid)
        
        if not dispense_list:
            print("[MEDICINE] 현재 시간에 복용할 약이 없습니다")
            return True
        
        print(f"[MEDICINE] 배출 대상: {len(dispense_list)}개")
        for item in dispense_list:
            med_name = item.get('medicine_name', 'Unknown')
            dose = item.get('dose', 1)
            time_of_day = item.get('time_of_day', '')
            print(f"  - {med_name} ({dose}개) [{time_of_day}]")
        
        # 3단계: 약 배출 실행
        print("[DISPENSE] 약 배출 시작...")
        success_list = self.execute_medicine_dispense(dispense_list)
        
        if success_list:
            print(f"[DISPENSE] ✅ 배출 완료: {len(success_list)}개")
            self.stats['medicines_dispensed'] += len(success_list)
            
            # 4단계: 결과 서버 전송
            print("[SERVER] 배출 결과 전송 중...")
            result = report_dispense_result(uid, success_list)
            if result:
                print("[SERVER] ✅ 결과 전송 완료")
            else:
                print("[SERVER] ⚠️ 결과 전송 실패")
        else:
            print("[DISPENSE] ❌ 약 배출 실패")
        
        return len(success_list) > 0
    
    def execute_medicine_dispense(self, dispense_list):
        """약 배출 실행"""
        success_list = []
        
        # 슬롯 매핑 (서버에서 슬롯 정보가 없으므로 기본 매핑 사용)
        # 실제 환경에서는 약품별 슬롯 정보를 별도로 관리해야 함
        default_slot_mapping = {
            'M001': 1,  # 첫 번째 약은 슬롯 1
            'M002': 2,  # 두 번째 약은 슬롯 2  
            'M003': 3,  # 세 번째 약은 슬롯 3
        }
        
        for item in dispense_list:
            medi_id = item.get('medi_id')
            dose = item.get('dose', 1)
            medicine_name = item.get('medicine_name', medi_id)
            
            # 슬롯 번호 결정 (서버 응답에 없으므로 매핑 사용)
            slot_num = default_slot_mapping.get(medi_id, 1)  # 기본값 1
            
            print(f"[DISPENSE] {medicine_name} 배출 중... (슬롯 {slot_num}, {dose}개)")
            
            try:
                if SIMULATION_MODE:
                    # 시뮬레이션: 단순히 성공으로 처리
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
        """메인 실행 루프"""
        print("\n" + "="*50)
        print("🏥 Smart Medicine Dispenser 시작")
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
                    
                    # RFID 처리
                    self.state_controller.set_processing(uid)
                    try:
                        success = self.process_rfid_scan(uid)
                        consecutive_errors = 0  # 성공시 에러 카운트 리셋
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
        """통계 정보 출력"""
        print("\n" + "="*30)
        print("📊 시스템 통계")
        print("="*30)
        print(f"총 스캔 수: {self.stats['total_scans']}")
        print(f"인증 성공: {self.stats['successful_auth']}")
        print(f"인증 실패: {self.stats['failed_auth']}")
        print(f"약 배출 수: {self.stats['medicines_dispensed']}")
        
        if self.stats['total_scans'] > 0:
            success_rate = (self.stats['successful_auth'] / self.stats['total_scans']) * 100
            print(f"인증 성공률: {success_rate:.1f}%")
        
        print("="*30)
    
    def shutdown(self):
        """시스템 종료"""
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
        """시스템 실행"""
        try:
            # 신호 처리기 설정
            self.setup_signal_handlers()
            
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
    """메인 진입점"""
    try:
        # 작업 디렉토리 설정
        script_dir = Path(__file__).parent
        os.chdir(script_dir)
        
        # 시스템 생성 및 실행
        dispenser = SimpleMedicineDispenser()
        success = dispenser.run()
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"[CRITICAL] 시스템 시작 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()