# main.py (라즈베리파이 환경 최적화 - 무인 자동화)
import os
import sys
import uuid
import time
import signal
import threading
import traceback
import subprocess
from pathlib import Path
from utils.qr_display import show_qr_code
from utils.server_request import is_muid_registered, health_check
from utils.serial_reader import read_uid, read_uid_simulation
from utils.server_request import verify_rfid_uid, get_dispense_list, report_dispense_result
from core.state_controller import StateController
from dispenser_gui import show_main_screen
from utils.voice_feedback import VoiceFeedbackManager, announce_welcome, announce_error
from utils.system_monitor import SystemMonitor
from utils.raspberry_pi_helper import RaspberryPiHelper
from config import (
    SIMULATION_MODE, MONITORING_CONFIG, HARDWARE_CONFIG, 
    RASPBERRY_PI_CONFIG, AUTOSTART_CONFIG, NETWORK_CONFIG
)
from utils.logger import (
    log_info, log_error, log_warning, log_debug, 
    log_hardware_event, performance_timer, logger
)

class RaspberryPiDispenserSystem:
    """라즈베리파이용 스마트 약 디스펜서 메인 시스템"""
    
    def __init__(self):
        self.state_controller = StateController()
        self.current_muid = None
        self.system_running = True
        self.gui_thread = None
        self.rfid_thread = None
        self.monitoring_thread = None
        self.watchdog_thread = None
        self.startup_time = time.time()
        
        # 라즈베리파이 특화 컴포넌트들
        self.rpi_helper = RaspberryPiHelper()
        self.voice_manager = None
        self.system_monitor = None
        
        # 시스템 통계
        self.stats = {
            'total_rfid_scans': 0,
            'successful_authentications': 0,
            'failed_authentications': 0,
            'total_dispenses': 0,
            'system_errors': 0,
            'last_dispense_time': None,
            'uptime_start': time.time(),
            'restart_count': 0,
            'network_failures': 0,
            'hardware_failures': 0
        }
        
        # 자동 복구 설정
        self.recovery_state = {
            'consecutive_errors': 0,
            'last_error_time': None,
            'recovery_mode': False,
            'maintenance_mode': False
        }
        
        log_info("RaspberryPiDispenserSystem 초기화 완료", "SYSTEM")
    
    def setup_signal_handlers(self):
        """시스템 신호 처리기 설정"""
        def signal_handler(signum, frame):
            log_info(f"종료 신호 수신: {signum}", "SYSTEM")
            self.graceful_shutdown()
            sys.exit(0)
        
        def usr1_handler(signum, frame):
            log_info("SIGUSR1 수신 - 시스템 상태 출력", "SYSTEM")
            self.print_system_status()
        
        def usr2_handler(signum, frame):
            log_info("SIGUSR2 수신 - 강제 새로고침", "SYSTEM")
            self.force_system_refresh()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGUSR1, usr1_handler)
        signal.signal(signal.SIGUSR2, usr2_handler)
    
    def initialize_raspberry_pi_environment(self):
        """라즈베리파이 환경 초기화"""
        try:
            log_info("라즈베리파이 환경 초기화 시작", "SYSTEM")
            
            # 시스템 정보 수집
            system_info = self.rpi_helper.get_system_info()
            log_info(f"시스템 정보: {system_info}", "SYSTEM")
            
            # GPU 메모리 분할 확인
            gpu_mem = self.rpi_helper.get_gpu_memory()
            if gpu_mem < 64:
                log_warning(f"GPU 메모리가 부족할 수 있습니다: {gpu_mem}MB", "SYSTEM")
            
            # 필수 디렉토리 생성
            self.create_system_directories()
            
            # 하드웨어 초기화
            if not SIMULATION_MODE:
                self.initialize_hardware()
            
            # 네트워크 설정 확인
            self.check_network_configuration()
            
            # 오디오 시스템 초기화
            if RASPBERRY_PI_CONFIG['audio_enabled']:
                self.initialize_audio_system()
            
            # 시스템 모니터링 시작
            if MONITORING_CONFIG['enabled']:
                self.system_monitor = SystemMonitor()
                self.system_monitor.start_monitoring()
            
            # 음성 피드백 초기화
            if RASPBERRY_PI_CONFIG['voice_feedback']:
                self.voice_manager = VoiceFeedbackManager()
                self.voice_manager.test_audio()
            
            # 자동 시작 설정 적용
            if AUTOSTART_CONFIG['enabled']:
                self.setup_autostart()
            
            log_info("라즈베리파이 환경 초기화 완료", "SYSTEM")
            
        except Exception as e:
            log_error(f"라즈베리파이 환경 초기화 실패: {e}", "SYSTEM", exc_info=True)
            raise
    
    def create_system_directories(self):
        """시스템 디렉토리 생성"""
        try:
            from config import SYSTEM_PATHS
            
            for path_name, path_value in SYSTEM_PATHS.items():
                path = Path(path_value)
                path.mkdir(parents=True, exist_ok=True)
                log_debug(f"디렉토리 생성/확인: {path}", "SYSTEM")
            
            # 권한 설정
            os.chmod(SYSTEM_PATHS['logs_dir'], 0o755)
            os.chmod(SYSTEM_PATHS['config_dir'], 0o755)
            
        except Exception as e:
            log_error(f"시스템 디렉토리 생성 실패: {e}", "SYSTEM")
            raise
    
    def initialize_hardware(self):
        """하드웨어 초기화"""
        try:
            log_info("하드웨어 초기화 시작", "HARDWARE")
            
            # GPIO 초기화
            self.rpi_helper.init_gpio()
            
            # 릴레이 핀 설정
            for slot, pins in HARDWARE_CONFIG['relay_pins'].items():
                self.rpi_helper.setup_relay_pins(slot, pins['forward'], pins['backward'])
            
            # RFID 리더 초기화
            rfid_pins = HARDWARE_CONFIG['rfid_pins']
            self.rpi_helper.setup_rfid_pins(rfid_pins)
            
            # 하드웨어 자가진단
            self.run_hardware_selftest()
            
            log_info("하드웨어 초기화 완료", "HARDWARE")
            
        except Exception as e:
            log_error(f"하드웨어 초기화 실패: {e}", "HARDWARE")
            self.stats['hardware_failures'] += 1
            raise
    
    def check_network_configuration(self):
        """네트워크 설정 확인"""
        try:
            log_info("네트워크 설정 확인 중", "NETWORK")
            
            # 네트워크 인터페이스 확인
            interfaces = self.rpi_helper.get_network_interfaces()
            log_info(f"네트워크 인터페이스: {interfaces}", "NETWORK")
            
            # 인터넷 연결 테스트
            if AUTOSTART_CONFIG['wait_for_network']:
                self.wait_for_network_connection()
            
            # DNS 설정 확인
            dns_servers = self.rpi_helper.get_dns_servers()
            log_info(f"DNS 서버: {dns_servers}", "NETWORK")
            
        except Exception as e:
            log_error(f"네트워크 설정 확인 실패: {e}", "NETWORK")
            self.stats['network_failures'] += 1
    
    def wait_for_network_connection(self):
        """네트워크 연결 대기"""
        max_wait = AUTOSTART_CONFIG['max_network_wait']
        start_time = time.time()
        
        log_info(f"네트워크 연결 대기 중 (최대 {max_wait}초)", "NETWORK")
        
        while time.time() - start_time < max_wait:
            if self.rpi_helper.test_internet_connection():
                log_info("네트워크 연결 확인됨", "NETWORK")
                return True
            
            log_debug("네트워크 연결 대기 중...", "NETWORK")
            time.sleep(5)
        
        log_warning("네트워크 연결 대기 시간 초과", "NETWORK")
        return False
    
    def initialize_audio_system(self):
        """오디오 시스템 초기화"""
        try:
            log_info("오디오 시스템 초기화", "AUDIO")
            
            # HDMI 오디오 활성화
            if RASPBERRY_PI_CONFIG['audio_device'] == 'HDMI':
                subprocess.run(['amixer', 'cset', 'numid=3', '2'], check=False)
            
            # 오디오 장치 확인
            audio_devices = self.rpi_helper.get_audio_devices()
            log_info(f"오디오 장치: {audio_devices}", "AUDIO")
            
            # 볼륨 설정
            self.rpi_helper.set_system_volume(80)  # 80% 볼륨
            
        except Exception as e:
            log_error(f"오디오 시스템 초기화 실패: {e}", "AUDIO")
    
    def setup_autostart(self):
        """자동 시작 설정"""
        try:
            log_info("자동 시작 설정 적용", "SYSTEM")
            
            # systemd 서비스 파일 생성
            service_content = self.create_systemd_service()
            service_path = Path('/etc/systemd/system/dispenser.service')
            
            with open(service_path, 'w') as f:
                f.write(service_content)
            
            # 서비스 활성화
            subprocess.run(['systemctl', 'daemon-reload'], check=False)
            subprocess.run(['systemctl', 'enable', 'dispenser.service'], check=False)
            
            log_info("자동 시작 설정 완료", "SYSTEM")
            
        except Exception as e:
            log_error(f"자동 시작 설정 실패: {e}", "SYSTEM")
    
    def create_systemd_service(self):
        """systemd 서비스 파일 내용 생성"""
        from config import SYSTEM_PATHS
        
        return f"""[Unit]
Description=Smart Medicine Dispenser
After=network.target sound.target
Wants=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory={SYSTEM_PATHS['base_dir']}
Environment=DISPLAY=:0
Environment=PYTHONPATH={SYSTEM_PATHS['base_dir']}
ExecStart=/usr/bin/python3 {SYSTEM_PATHS['base_dir']}/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# 리소스 제한
MemoryLimit=512M
CPUQuota=80%

# 보안 설정
NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
"""
    
    def run_hardware_selftest(self):
        """하드웨어 자가진단"""
        try:
            log_info("하드웨어 자가진단 시작", "HARDWARE")
            
            selftest_results = {
                'gpio': False,
                'relays': False,
                'rfid': False,
                'audio': False
            }
            
            # GPIO 테스트
            selftest_results['gpio'] = self.rpi_helper.test_gpio()
            
            # 릴레이 테스트
            if not SIMULATION_MODE:
                selftest_results['relays'] = self.test_relay_system()
            else:
                selftest_results['relays'] = True
            
            # RFID 테스트
            selftest_results['rfid'] = self.test_rfid_system()
            
            # 오디오 테스트
            if RASPBERRY_PI_CONFIG['audio_enabled']:
                selftest_results['audio'] = self.test_audio_system()
            else:
                selftest_results['audio'] = True
            
            # 결과 로깅
            failed_tests = [test for test, result in selftest_results.items() if not result]
            
            if failed_tests:
                log_warning(f"하드웨어 자가진단 실패: {failed_tests}", "HARDWARE")
                if self.voice_manager:
                    self.voice_manager.speak_async('system_error')
            else:
                log_info("하드웨어 자가진단 통과", "HARDWARE")
                if self.voice_manager:
                    self.voice_manager.speak_async('smart_dispenser_ready')
            
            return all(selftest_results.values())
            
        except Exception as e:
            log_error(f"하드웨어 자가진단 오류: {e}", "HARDWARE")
            return False
    
    def test_relay_system(self):
        """릴레이 시스템 테스트"""
        try:
            for slot in HARDWARE_CONFIG['relay_pins']:
                # 각 릴레이 짧게 테스트
                if not self.rpi_helper.test_relay(slot):
                    return False
            return True
        except Exception as e:
            log_error(f"릴레이 테스트 실패: {e}", "HARDWARE")
            return False
    
    def test_rfid_system(self):
        """RFID 시스템 테스트"""
        try:
            # RFID 리더 통신 테스트
            return self.rpi_helper.test_rfid_reader()
        except Exception as e:
            log_error(f"RFID 테스트 실패: {e}", "HARDWARE")
            return False
    
    def test_audio_system(self):
        """오디오 시스템 테스트"""
        try:
            return self.rpi_helper.test_audio_output()
        except Exception as e:
            log_error(f"오디오 테스트 실패: {e}", "AUDIO")
            return False
    
    def get_or_create_muid(self):
        """기기 UID 생성 또는 로드"""
        from config import SECURITY_CONFIG
        
        muid_file = Path(SECURITY_CONFIG['device_id_file'])
        
        if not muid_file.exists():
            # 라즈베리파이 시리얼 번호 기반 UID 생성
            rpi_serial = self.rpi_helper.get_serial_number()
            if rpi_serial:
                muid = f"RPI_{rpi_serial[-8:].upper()}"
            else:
                muid = str(uuid.uuid4())[:8].upper()
            
            try:
                muid_file.parent.mkdir(parents=True, exist_ok=True)
                with open(muid_file, 'w') as f:
                    f.write(muid)
                os.chmod(muid_file, 0o600)  # 읽기 전용
                log_info(f"새로운 m_uid 생성: {muid}", "SYSTEM")
            except IOError as e:
                log_error(f"m_uid 파일 생성 실패: {e}", "SYSTEM")
                return None
        else:
            try:
                with open(muid_file, 'r') as f:
                    muid = f.read().strip()
                log_info(f"기존 m_uid 로드: {muid}", "SYSTEM")
            except IOError as e:
                log_error(f"m_uid 파일 읽기 실패: {e}", "SYSTEM")
                return None
        
        return muid
    
    def wait_for_registration(self, muid):
        """QR 코드 표시하고 등록 대기"""
        log_info(f"기기 등록 대기 중... m_uid: {muid}", "SYSTEM")
        
        qr_data = {
            "type": "register",
            "m_uid": muid,
            "model": "RaspberryPi",
            "version": "2.0",
            "serial": self.rpi_helper.get_serial_number(),
            "createdAt": time.strftime("%Y-%m-%d %H:%M:%S"),
            "capabilities": {
                "voice_feedback": RASPBERRY_PI_CONFIG['voice_feedback'],
                "audio_enabled": RASPBERRY_PI_CONFIG['audio_enabled'],
                "slots": len(HARDWARE_CONFIG['relay_pins'])
            }
        }
        
        # QR 코드 표시 (별도 스레드)
        qr_thread = threading.Thread(
            target=show_qr_code, 
            args=(qr_data,),
            name="QRDisplayThread"
        )
        qr_thread.daemon = True
        qr_thread.start()
        
        # 음성 안내
        if self.voice_manager:
            self.voice_manager.speak_async('user_not_registered')
        
        # 등록 확인 루프
        retry_count = 0
        max_retries = 120  # 10분 (5초 * 120회)
        
        while self.system_running and retry_count < max_retries:
            try:
                if is_muid_registered(muid):
                    log_info("✅ 기기 등록 완료!", "SYSTEM")
                    if self.voice_manager:
                        self.voice_manager.speak_async('connection_restored')
                    return True
                
                retry_count += 1
                if retry_count % 12 == 0:  # 1분마다 로그
                    elapsed = retry_count * 5
                    log_info(f"등록 대기 중... ({elapsed}초 경과)", "SYSTEM")
                    
                    # 주기적 음성 안내
                    if self.voice_manager and retry_count % 24 == 0:  # 2분마다
                        self.voice_manager.speak_async('user_not_registered')
                
                time.sleep(5)
                
            except Exception as e:
                log_error(f"등록 확인 중 오류: {e}", "SYSTEM")
                self.stats['network_failures'] += 1
                time.sleep(10)
        
        if retry_count >= max_retries:
            log_error("등록 대기 시간 초과", "SYSTEM")
            return False
        
        return False
    
    def process_rfid_authentication(self):
        """RFID 인증 및 약 배출 처리 메인 루프"""
        log_info("RFID 인증 처리 시작", "RFID")
        
        if SIMULATION_MODE:
            log_info("🔍 시뮬레이션 모드 - 콘솔에 UID 입력", "RFID")
            log_info("테스트용 UID: K001, K002, K003, K004", "RFID")
        else:
            log_info("🔍 RFID 인증 대기 중...", "RFID")
            if self.voice_manager:
                self.voice_manager.speak_async('welcome')
        
        consecutive_errors = 0
        max_consecutive_errors = 10
        last_uid_time = {}  # UID별 마지막 처리 시간
        uid_cooldown = 5  # 5초 쿨다운
        
        while self.system_running:
            try:
                # RFID UID 읽기
                uid = None
                with performance_timer("rfid_read"):
                    if SIMULATION_MODE:
                        uid = read_uid_simulation()
                    else:
                        uid = read_uid()
                
                if not uid:
                    time.sleep(0.5)
                    continue
                
                # 쿨다운 체크
                current_time = time.time()
                if uid in last_uid_time:
                    if current_time - last_uid_time[uid] < uid_cooldown:
                        log_debug(f"UID 쿨다운 중: {uid}", "RFID")
                        continue
                
                last_uid_time[uid] = current_time
                self.stats['total_rfid_scans'] += 1
                log_info(f"📡 RFID 감지: {uid}", "RFID")
                
                # GUI에 RFID 활동 알림
                if hasattr(self, 'gui_instance'):
                    self.gui_instance.data_queue.put(('rfid_detected', {'uid': uid}))
                
                # 중복 처리 방지
                if self.state_controller.is_processing(uid):
                    log_warning(f"이미 처리 중인 UID: {uid}", "RFID")
                    continue
                
                # 음성 피드백
                if self.voice_manager:
                    self.voice_manager.speak_async('rfid_detected')
                
                # 인증 및 배출 처리
                success = self.process_single_rfid(uid)
                
                if success:
                    self.stats['successful_authentications'] += 1
                    consecutive_errors = 0
                else:
                    self.stats['failed_authentications'] += 1
                    consecutive_errors += 1
                
                # 너무 많은 연속 에러 시 복구 모드
                if consecutive_errors >= max_consecutive_errors:
                    log_warning(f"연속 {consecutive_errors}회 오류 - 복구 모드 진입", "RFID")
                    self.enter_recovery_mode()
                    consecutive_errors = 0
                
            except Exception as e:
                self.stats['system_errors'] += 1
                log_error(f"RFID 처리 중 심각한 오류: {e}", "RFID", exc_info=True)
                consecutive_errors += 1
                
                if self.voice_manager:
                    self.voice_manager.speak_async('system_error')
                
                time.sleep(5)
            finally:
                self.state_controller.clear()
                time.sleep(1)
    
    def process_single_rfid(self, uid):
        """단일 RFID 처리"""
        try:
            self.state_controller.set_processing(uid)
            
            # 사용자 인증
            with performance_timer("user_authentication"):
                auth_result = verify_rfid_uid(uid)
            
            if not auth_result or auth_result.get('status') != 'ok':
                log_warning(f"인증 실패: {uid}", "RFID")
                
                if auth_result and auth_result.get('status') == 'unregistered':
                    log_info("미등록 사용자 - 앱에서 등록 필요", "RFID")
                    if self.voice_manager:
                        self.voice_manager.speak_async('user_not_registered')
                else:
                    if self.voice_manager:
                        self.voice_manager.speak_async('access_denied')
                
                return False
            
            user = auth_result.get('user', {})
            log_info(f"✅ 인증 성공: {user.get('name')} ({user.get('role')})", "RFID")
            
            if self.voice_manager:
                self.voice_manager.speak_async('user_authenticated', user_name=user.get('name', '사용자'))
            
            # 배출할 약 목록 조회
            with performance_timer("dispense_list_fetch"):
                dispense_list = get_dispense_list(uid)
            
            if not dispense_list:
                log_info("현재 시간에 배출할 약이 없음", "RFID")
                if self.voice_manager:
                    self.voice_manager.speak_async('no_medicine_scheduled')
                return True
            
            log_info(f"📋 배출 대상: {len(dispense_list)}개 약", "RFID")
            for item in dispense_list:
                log_debug(f"  - {item.get('medicine_name')} ({item.get('dose')}개)", "RFID")
            
            if self.voice_manager:
                self.voice_manager.speak_async('dispensing_start')
            
            # 약 배출 처리
            success_list = self.execute_dispense(dispense_list)
            
            # 결과 보고
            if success_list:
                with performance_timer("dispense_result_report"):
                    result = report_dispense_result(uid, success_list)
                
                if result:
                    log_info("📊 배출 결과 전송 완료", "RFID")
                    self.log_dispense_result(result)
                    self.stats['total_dispenses'] += len(success_list)
                    self.stats['last_dispense_time'] = time.time()
                    
                    # GUI에 배출 완료 알림
                    if hasattr(self, 'gui_instance'):
                        self.gui_instance.data_queue.put(('dispense_complete', {
                            'count': len(success_list),
                            'medicines': [item.get('medicine_name') for item in dispense_list if item.get('medi_id') in [s.get('medi_id') for s in success_list]]
                        }))
                    
                    if self.voice_manager:
                        self.voice_manager.speak_async('dispense_complete')
                        self.voice_manager.play_sound_async('success')
            
            log_info(f"🎉 약 배출 완료: {len(success_list)}개", "RFID")
            return True
            
        except Exception as e:
            log_error(f"RFID 처리 오류: {e}", "RFID", exc_info=True)
            if self.voice_manager:
                self.voice_manager.speak_async('dispense_failed')
            return False
    
    def execute_dispense(self, dispense_list):
        """약 배출 실행"""
        success_list = []
        
        try:
            if SIMULATION_MODE:
                log_info("🔧 시뮬레이션 모드 - 하드웨어 제어 생략", "HARDWARE")
                # 시뮬레이션에서는 모든 배출이 성공한 것으로 처리
                for item in dispense_list:
                    success_list.append({
                        "medi_id": item.get('medi_id'),
                        "dose": item.get('dose', 1)
                    })
                    time.sleep(0.2)  # 시뮬레이션 지연
            else:
                # 실제 하드웨어 제어
                for item in dispense_list:
                    medi_id = item.get('medi_id')
                    dose = item.get('dose', 1)
                    slot_num = item.get('slot', 1)
                    medicine_name = item.get('medicine_name', medi_id)
                    
                    log_hardware_event("약 배출 시작", slot_num, f"{medicine_name} ({dose}개)")
                    
                    try:
                        with performance_timer("hardware_dispense", f"slot_{slot_num}_{medicine_name}"):
                            # 하드웨어 약 배출
                            dispense_success = self.rpi_helper.dispense_medicine(slot_num, dose)
                        
                        if dispense_success:
                            success_list.append({"medi_id": medi_id, "dose": dose})
                            log_hardware_event("약 배출 완료", slot_num, medicine_name)
                        else:
                            log_error(f"약 배출 실패: {medicine_name}", "HARDWARE")
                            if self.voice_manager:
                                self.voice_manager.speak_async('dispense_failed')
                        
                    except Exception as e:
                        log_error(f"약 배출 중 오류: {medicine_name} - {e}", "HARDWARE")
                        self.stats['hardware_failures'] += 1
                        continue
                        
        except Exception as e:
            log_error(f"배출 처리 중 오류: {e}", "HARDWARE", exc_info=True)
        
        return success_list
    
    def log_dispense_result(self, result):
        """배출 결과 로깅"""
        processed = result.get('processed', [])
        insufficient = result.get('insufficient', [])
        
        if processed:
            log_info(f"✅ 처리 완료: {', '.join(processed)}", "DISPENSE")
        if insufficient:
            log_warning(f"⚠️ 부족한 약: {', '.join(insufficient)}", "DISPENSE")
            if self.voice_manager:
                for medicine in insufficient:
                    self.voice_manager.speak_async('low_medicine_warning', medicine_name=medicine)
    
    def enter_recovery_mode(self):
        """복구 모드 진입"""
        try:
            log_warning("시스템 복구 모드 진입", "RECOVERY")
            self.recovery_state['recovery_mode'] = True
            self.recovery_state['consecutive_errors'] = 0
            
            if self.voice_manager:
                self.voice_manager.speak_async('maintenance_mode')
            
            # 30초 대기 후 정상 모드 복귀
            def exit_recovery():
                time.sleep(30)
                self.recovery_state['recovery_mode'] = False
                log_info("복구 모드 종료", "RECOVERY")
            
            threading.Thread(target=exit_recovery, daemon=True).start()
            
        except Exception as e:
            log_error(f"복구 모드 진입 오류: {e}", "RECOVERY")
    
    def start_system_monitoring(self):
        """시스템 모니터링 시작"""
        if not MONITORING_CONFIG['enabled']:
            return
        
        def monitoring_loop():
            log_info("시스템 모니터링 시작", "MONITOR")
            
            while self.system_running:
                try:
                    # 헬스체크
                    health_status = health_check()
                    
                    # 시스템 리소스 모니터링
                    if self.system_monitor:
                        system_summary = self.system_monitor.get_system_summary()
                        
                        # 위험 상태 체크
                        if not system_summary['is_healthy']:
                            log_warning("시스템 건강 상태 불량", "MONITOR")
                            if system_summary['cpu_temp'] > 75:
                                log_warning(f"높은 CPU 온도: {system_summary['cpu_temp']:.1f}°C", "MONITOR")
                    
                    # 성능 통계 주기적 로그
                    if self.stats['total_rfid_scans'] % 10 == 0 and self.stats['total_rfid_scans'] > 0:
                        self.log_system_stats()
                    
                    # 메모리 사용량 체크
                    self.check_system_resources()
                    
                    time.sleep(MONITORING_CONFIG['health_check_interval'])
                    
                except Exception as e:
                    log_error(f"모니터링 오류: {e}", "MONITOR")
                    time.sleep(60)
        
        self.monitoring_thread = threading.Thread(target=monitoring_loop, name="MonitoringThread")
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
    
    def start_watchdog(self):
        """워치독 시작 (자동 복구)"""
        if not RASPBERRY_PI_CONFIG['watchdog_enabled']:
            return
        
        def watchdog_loop():
            log_info("워치독 시작", "WATCHDOG")
            last_activity = time.time()
            
            while self.system_running:
                try:
                    current_time = time.time()
                    
                    # GUI 응답성 체크
                    if hasattr(self, 'gui_instance') and self.gui_instance:
                        if current_time - last_activity > 300:  # 5분간 활동 없음
                            log_warning("GUI 응답 없음 - 재시작 고려", "WATCHDOG")
                    
                    # 메모리 리크 체크
                    if self.system_monitor:
                        memory_usage = self.system_monitor.get_memory_usage()
                        if memory_usage > 95:
                            log_warning(f"높은 메모리 사용량: {memory_usage:.1f}%", "WATCHDOG")
                            self.trigger_memory_cleanup()
                    
                    # 연속 오류 체크
                    if self.recovery_state['consecutive_errors'] > 20:
                        log_error("연속 오류 임계치 초과 - 시스템 재시작 필요", "WATCHDOG")
                        if RASPBERRY_PI_CONFIG['auto_restart_on_crash']:
                            self.trigger_system_restart("연속 오류 임계치 초과")
                    
                    time.sleep(60)  # 1분마다 체크
                    
                except Exception as e:
                    log_error(f"워치독 오류: {e}", "WATCHDOG")
                    time.sleep(60)
        
        self.watchdog_thread = threading.Thread(target=watchdog_loop, name="WatchdogThread")
        self.watchdog_thread.daemon = True
        self.watchdog_thread.start()
    
    def check_system_resources(self):
        """시스템 리소스 체크"""
        try:
            if not self.system_monitor:
                return
            
            # CPU 온도 체크
            cpu_temp = self.system_monitor.get_cpu_temperature()
            if cpu_temp > 75:
                log_warning(f"높은 CPU 온도: {cpu_temp:.1f}°C", "RESOURCE")
                # 열 보호 조치
                self.rpi_helper.enable_thermal_protection()
            
            # 메모리 사용량 체크
            memory_usage = self.system_monitor.get_memory_usage()
            if memory_usage > 90:
                log_warning(f"높은 메모리 사용량: {memory_usage:.1f}%", "RESOURCE")
                self.trigger_memory_cleanup()
            
            # 디스크 사용량 체크
            disk_usage = self.system_monitor.get_disk_usage()
            if disk_usage > 90:
                log_warning(f"높은 디스크 사용량: {disk_usage:.1f}%", "RESOURCE")
                self.cleanup_old_logs()
                
        except Exception as e:
            log_debug(f"리소스 체크 오류: {e}", "RESOURCE")
    
    def trigger_memory_cleanup(self):
        """메모리 정리 실행"""
        try:
            log_info("메모리 정리 실행", "CLEANUP")
            
            # 시스템 캐시 정리
            subprocess.run(['sync'], check=False)
            subprocess.run(['sudo', 'sysctl', 'vm.drop_caches=3'], check=False)
            
            # Python 가비지 컬렉션
            import gc
            collected = gc.collect()
            log_info(f"가비지 컬렉션 완료: {collected}개 객체", "CLEANUP")
            
        except Exception as e:
            log_error(f"메모리 정리 오류: {e}", "CLEANUP")
    
    def cleanup_old_logs(self):
        """오래된 로그 파일 정리"""
        try:
            from config import SYSTEM_PATHS
            
            log_dir = Path(SYSTEM_PATHS['logs_dir'])
            current_time = time.time()
            
            for log_file in log_dir.glob('*.log'):
                if current_time - log_file.stat().st_mtime > 7 * 24 * 3600:  # 7일 이상
                    log_file.unlink()
                    log_info(f"오래된 로그 파일 삭제: {log_file.name}", "CLEANUP")
            
        except Exception as e:
            log_error(f"로그 정리 오류: {e}", "CLEANUP")
    
    def trigger_system_restart(self, reason):
        """시스템 재시작 실행"""
        try:
            log_warning(f"시스템 재시작 실행: {reason}", "RESTART")
            
            self.stats['restart_count'] += 1
            
            if self.voice_manager:
                self.voice_manager.speak_async('system_shutdown')
            
            # 정상 종료 후 재시작
            self.graceful_shutdown()
            subprocess.run(['sudo', 'reboot'], check=False)
            
        except Exception as e:
            log_error(f"시스템 재시작 오류: {e}", "RESTART")
    
    def log_system_stats(self):
        """시스템 통계 로깅"""
        uptime = time.time() - self.stats['uptime_start']
        
        stats_message = (
            f"시스템 통계 - "
            f"가동시간: {uptime/3600:.1f}시간, "
            f"RFID 스캔: {self.stats['total_rfid_scans']}회, "
            f"인증 성공: {self.stats['successful_authentications']}회, "
            f"인증 실패: {self.stats['failed_authentications']}회, "
            f"약 배출: {self.stats['total_dispenses']}회, "
            f"시스템 에러: {self.stats['system_errors']}회, "
            f"재시작 횟수: {self.stats['restart_count']}회"
        )
        
        log_info(stats_message, "STATS")
        
        # 성능 요약도 함께 로그
        perf_summary = logger.get_performance_summary()
        if perf_summary != "성능 메트릭 없음":
            log_debug(f"성능 요약:\n{perf_summary}", "PERFORMANCE")
    
    def print_system_status(self):
        """시스템 상태 출력 (SIGUSR1 핸들러)"""
        try:
            print("\n" + "="*50)
            print("📊 시스템 상태 요약")
            print("="*50)
            
            # 기본 정보
            uptime = time.time() - self.stats['uptime_start']
            print(f"가동 시간: {uptime/3600:.1f}시간")
            print(f"기기 ID: {self.current_muid}")
            print(f"시뮬레이션 모드: {'ON' if SIMULATION_MODE else 'OFF'}")
            
            # 통계
            print(f"RFID 스캔: {self.stats['total_rfid_scans']}회")
            print(f"인증 성공률: {self.stats['successful_authentications']}/{self.stats['total_rfid_scans']} ({(self.stats['successful_authentications']/max(1,self.stats['total_rfid_scans']))*100:.1f}%)")
            print(f"약 배출: {self.stats['total_dispenses']}회")
            
            # 시스템 상태
            if self.system_monitor:
                summary = self.system_monitor.get_system_summary()
                print(f"CPU 온도: {summary['cpu_temp']:.1f}°C")
                print(f"메모리 사용: {summary['memory_usage']:.1f}%")
                print(f"시스템 건강: {'양호' if summary['is_healthy'] else '불량'}")
            
            # 연결 상태
            print(f"복구 모드: {'ON' if self.recovery_state['recovery_mode'] else 'OFF'}")
            print(f"오류 카운트: {self.stats['system_errors']}")
            
            print("="*50)
            
        except Exception as e:
            print(f"상태 출력 오류: {e}")
    
    def force_system_refresh(self):
        """강제 시스템 새로고침 (SIGUSR2 핸들러)"""
        try:
            log_info("강제 시스템 새로고침 실행", "SYSTEM")
            
            # 캐시 정리
            if hasattr(self, 'gui_instance'):
                self.gui_instance.cached_data = {key: None for key in self.gui_instance.cached_data}
            
            # 메모리 정리
            self.trigger_memory_cleanup()
            
            # 하드웨어 재초기화
            if not SIMULATION_MODE:
                self.rpi_helper.reset_hardware()
            
            log_info("강제 새로고침 완료", "SYSTEM")
            
        except Exception as e:
            log_error(f"강제 새로고침 오류: {e}", "SYSTEM")
    
    def start_gui(self):
        """GUI 시작"""
        def gui_thread_func():
            try:
                log_info("GUI 스레드 시작", "GUI")
                
                # GUI 인스턴스 저장 (워치독용)
                from dispenser_gui import RaspberryPiDispenserGUI
                self.gui_instance = RaspberryPiDispenserGUI(self.current_muid)
                self.gui_instance.show()
                
            except Exception as e:
                log_error(f"GUI 오류: {e}", "GUI", exc_info=True)
                self.stats['system_errors'] += 1
            finally:
                log_info("GUI 스레드 종료", "GUI")
                self.system_running = False
        
        self.gui_thread = threading.Thread(target=gui_thread_func, name="GUIThread")
        self.gui_thread.start()
    
    def start_rfid_processing(self):
        """RFID 처리 시작"""
        self.rfid_thread = threading.Thread(
            target=self.process_rfid_authentication,
            name="RFIDThread"
        )
        self.rfid_thread.daemon = True
        self.rfid_thread.start()
    
    def graceful_shutdown(self):
        """정상 종료 처리"""
        log_info("시스템 종료 시작", "SYSTEM")
        
        self.system_running = False
        
        try:
            # 음성 안내
            if self.voice_manager:
                self.voice_manager.speak_async('system_shutdown')
                time.sleep(2)  # 음성 출력 대기
                self.voice_manager.cleanup()
            
            # 하드웨어 정리
            if not SIMULATION_MODE and HARDWARE_CONFIG['gpio_cleanup_on_exit']:
                log_info("GPIO 정리 중...", "HARDWARE")
                self.rpi_helper.cleanup_gpio()
            
            # 시스템 모니터링 정지
            if self.system_monitor:
                self.system_monitor.stop_monitoring()
            
            # 최종 통계 로그
            self.log_system_stats()
            
            # 스레드 종료 대기
            threads_to_join = [
                (self.rfid_thread, "RFID"),
                (self.monitoring_thread, "Monitoring"),
                (self.watchdog_thread, "Watchdog")
            ]
            
            for thread, name in threads_to_join:
                if thread and thread.is_alive():
                    log_info(f"{name} 스레드 종료 대기 중...", "SYSTEM")
                    thread.join(timeout=5)
            
            # GUI 스레드는 마지막에
            if self.gui_thread and self.gui_thread.is_alive():
                log_info("GUI 스레드 종료 대기 중...", "SYSTEM")
                self.gui_thread.join(timeout=10)
            
            log_info("시스템 정상 종료 완료", "SYSTEM")
            
        except Exception as e:
            log_error(f"종료 처리 중 오류: {e}", "SYSTEM", exc_info=True)
    
    def run(self):
        """메인 시스템 실행"""
        try:
            log_info("=" * 60, "SYSTEM")
            log_info("🏥 스마트 약 디스펜서 시작 (라즈베리파이)", "SYSTEM")
            if SIMULATION_MODE:
                log_info("🔧 시뮬레이션 모드 (하드웨어 없음)", "SYSTEM")
            log_info("=" * 60, "SYSTEM")
            
            # 신호 처리기 설정
            self.setup_signal_handlers()
            
            # 라즈베리파이 환경 초기화
            self.initialize_raspberry_pi_environment()
            
            # 스플래시 화면 표시
            if AUTOSTART_CONFIG['display_splash_screen']:
                self.show_splash_screen()
            
            # 시작 지연
            if AUTOSTART_CONFIG['startup_delay'] > 0:
                log_info(f"시작 지연: {AUTOSTART_CONFIG['startup_delay']}초", "SYSTEM")
                time.sleep(AUTOSTART_CONFIG['startup_delay'])
            
            # 1. 기기 UID 생성/로드
            self.current_muid = self.get_or_create_muid()
            if not self.current_muid:
                log_error("기기 UID 생성/로드 실패", "SYSTEM")
                return False
            
            # 2. 시스템 체크 실행
            if AUTOSTART_CONFIG['run_system_check']:
                if not self.run_hardware_selftest():
                    log_warning("하드웨어 자가진단 일부 실패 - 계속 진행", "SYSTEM")
            
            # 3. 기기 등록 확인
            if not is_muid_registered(self.current_muid):
                log_info("📱 기기 미등록 상태 - QR 코드 표시", "SYSTEM")
                if not self.wait_for_registration(self.current_muid):
                    log_error("기기 등록 실패", "SYSTEM")
                    return False
            else:
                log_info("✅ 기기 이미 등록됨", "SYSTEM")
            
            # 4. 시스템 모니터링 시작
            self.start_system_monitoring()
            
            # 5. 워치독 시작
            self.start_watchdog()
            
            # 6. RFID 처리 시작
            self.start_rfid_processing()
            
            # 7. GUI 시작 (메인 스레드)
            log_info("🖥️ GUI 및 시스템 서비스 시작", "SYSTEM")
            
            # 시작 완료 음성 안내
            if self.voice_manager:
                self.voice_manager.speak_async('smart_dispenser_ready')
            
            self.start_gui()
            
            # GUI 스레드 종료 대기
            if self.gui_thread:
                self.gui_thread.join()
            
            return True
            
        except KeyboardInterrupt:
            log_info("사용자에 의한 종료 요청", "SYSTEM")
            return True
        except Exception as e:
            log_error(f"시스템 실행 중 심각한 오류: {e}", "SYSTEM", exc_info=True)
            self.stats['system_errors'] += 1
            
            # 자동 재시작 시도
            if (RASPBERRY_PI_CONFIG['auto_restart_on_crash'] and 
                self.stats['restart_count'] < RASPBERRY_PI_CONFIG['max_restart_attempts']):
                
                log_warning("자동 재시작 시도", "SYSTEM")
                time.sleep(10)
                self.trigger_system_restart("시스템 크래시")
            
            return False
        finally:
            self.graceful_shutdown()
    
    def show_splash_screen(self):
        """스플래시 화면 표시"""
        try:
            # 간단한 콘솔 스플래시
            print("\n" + "="*60)
            print("🏥 SMART MEDICINE DISPENSER")
            print("   Raspberry Pi Edition v2.0")
            print("-"*60)
            print(f"Device ID: {self.current_muid or 'Loading...'}")
            print(f"Mode: {'Simulation' if SIMULATION_MODE else 'Hardware'}")
            print(f"Audio: {'Enabled' if RASPBERRY_PI_CONFIG['audio_enabled'] else 'Disabled'}")
            print("="*60)
            print("System Starting...")
            print()
            
        except Exception as e:
            log_error(f"스플래시 화면 오류: {e}", "SYSTEM")


def main():
    """메인 진입점"""
    # 작업 디렉토리 설정
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # 루트 권한 체크 (GPIO 사용시 필요)
    if not SIMULATION_MODE and os.geteuid() != 0:
        print("[ERROR] 하드웨어 모드에서는 sudo 권한이 필요합니다.")
        print("sudo python3 main.py 로 실행해주세요.")
        sys.exit(1)
    
    # 필수 디렉토리 생성
    try:
        from config import SYSTEM_PATHS
        for path in SYSTEM_PATHS.values():
            Path(path).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[ERROR] 디렉토리 생성 실패: {e}")
        sys.exit(1)
    
    try:
        system = RaspberryPiDispenserSystem()
        success = system.run()
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"[CRITICAL] 시스템 시작 실패: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()