# config.py (핵심 설정만 포함 - 단계별 확장 가능)
import os

# ============================================================================
# 기본 시스템 설정
# ============================================================================

# 시뮬레이션 모드 (하드웨어 없이 테스트 가능)
SIMULATION_MODE = os.getenv('SIMULATION_MODE', 'True').lower() == 'true'

# 시리얼 포트 설정 (RFID 리더 연결)
SERIAL_PORT = os.getenv('SERIAL_PORT', '/dev/ttyACM0')
BAUD_RATE = int(os.getenv('BAUD_RATE', '9600'))

# 서버 URL 설정  
BASE_API_URL = os.getenv('DISPENSER_API_URL', 'http://192.168.59.208:3000/dispenser')

# ============================================================================
# 하드웨어 설정 (약 배출 시스템)
# ============================================================================

HARDWARE_CONFIG = {
    # 릴레이 핀 매핑 (슬롯번호: {전진핀, 후진핀})
    'relay_pins': {
        1: {'forward': 17, 'backward': 18},  # 슬롯 1
        2: {'forward': 22, 'backward': 23},  # 슬롯 2  
        3: {'forward': 24, 'backward': 25}   # 슬롯 3
    },
    
    # 배출 타이밍 설정 (초)
    'servo_pulse_duration': 1.0,  # 릴레이 ON 시간
    'slot_delay': 0.5,            # 전진->후진 사이 대기시간
    
    # GPIO 기본 설정
    'gpio_mode': 'BCM',           # GPIO 번호 모드
    'gpio_warnings': False,       # GPIO 경고 메시지 끄기
    'gpio_cleanup_on_exit': True  # 종료시 GPIO 정리
}

# ============================================================================
# GUI 및 네트워크 설정 (기본값)
# ============================================================================

GUI_CONFIG = {
    # 데이터 업데이트 주기 (초)
    'update_interval': 15,
    'time_update_interval': 5,
    
    # 네트워크 요청 설정
    'request_timeout': 10,
    'max_retry_count': 3,
    'retry_delay': 5,
    
    # 성능 설정
    'max_workers': 2,
    'cache_duration': 60,
    
    # UI 색상 테마
    'colors': {
        'primary': '#2563eb',
        'success': '#16a34a', 
        'warning': '#ea580c',
        'danger': '#dc2626',
        'background': '#f8fafc',
        'card_bg': '#ffffff',
        'text_primary': '#1e293b',
        'text_secondary': '#64748b'
    }
}

# ============================================================================
# 음성 피드백 설정 (기본값)
# ============================================================================

VOICE_CONFIG = {
    'enabled': False,  # 현재 단계에서는 비활성화
    'language': 'ko',
    'volume': 0.8,
    'speech_rate': 180
}

# ============================================================================
# 라즈베리파이 설정 (기본값)
# ============================================================================

RASPBERRY_PI_CONFIG = {
    # 디스플레이 설정
    'fullscreen': False,  # 개발 단계에서는 창모드
    'hide_cursor': False,
    'auto_start_gui': False,
    
    # 오디오 설정
    'audio_enabled': False,  # 현재 단계에서는 비활성화
    'audio_device': 'HDMI',
    'voice_feedback': False
}

# ============================================================================
# 로깅 설정 (간소화)
# ============================================================================

LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '[%(levelname)s] %(asctime)s - %(message)s',
    'file_enabled': True,
    'file_path': 'logs/dispenser.log',
    'max_file_size': 5 * 1024 * 1024,  # 5MB
    'backup_count': 3
}

# ============================================================================
# 시스템 모니터링 설정 (기본값)
# ============================================================================

MONITORING_CONFIG = {
    'enabled': False,  # 현재 단계에서는 비활성화
    'metrics_interval': 120,
    'health_check_interval': 60,
    'memory_threshold': 85,
    'cpu_threshold': 90,
    'temperature_threshold': 70,
    'auto_recovery': False
}

# ============================================================================
# 네트워크 설정 (간소화)
# ============================================================================

NETWORK_CONFIG = {
    'primary_server': BASE_API_URL,
    'fallback_mode': True,
    'ssl_verify': True,
    'auto_reconnect': True,
    'reconnect_interval': 30,
    'max_reconnect_attempts': 5
}

# ============================================================================
# 보안 설정 (기본값)
# ============================================================================

SECURITY_CONFIG = {
    'device_id_file': 'muid.txt',
    'encryption_enabled': False,  # 현재 단계에서는 단순화
    'session_timeout': 300,
    'max_failed_attempts': 3
}

# ============================================================================
# 자동 시작 설정 (개발용)
# ============================================================================

AUTOSTART_CONFIG = {
    'enabled': False,  # 개발 단계에서는 수동 시작
    'startup_delay': 5,
    'wait_for_network': True,
    'max_network_wait': 30,
    'run_system_check': False,
    'display_splash_screen': False
}

# ============================================================================
# 디버그 설정
# ============================================================================

DEBUG_CONFIG = {
    'enabled': SIMULATION_MODE,
    'verbose_api_logs': True,
    'show_performance_metrics': False,
    'save_debug_screenshots': False
}

# ============================================================================
# 시스템 경로 (간소화)
# ============================================================================

SYSTEM_PATHS = {
    'base_dir': os.getcwd(),
    'logs_dir': 'logs',
    'config_dir': 'config',
    'assets_dir': 'assets',
    'temp_dir': 'temp'
}

# ============================================================================
# 설정 검증 및 디렉토리 생성
# ============================================================================

def validate_config():
    """설정값 검증 및 필수 디렉토리 생성"""
    import pathlib
    
    # 필수 디렉토리 생성
    for path_name, path_value in SYSTEM_PATHS.items():
        pathlib.Path(path_value).mkdir(parents=True, exist_ok=True)
    
    # 하드웨어 설정 검증
    if not SIMULATION_MODE:
        required_pins = []
        for slot, pins in HARDWARE_CONFIG['relay_pins'].items():
            required_pins.extend([pins['forward'], pins['backward']])
        
        # 핀 번호 중복 체크
        if len(required_pins) != len(set(required_pins)):
            print("[WARNING] 릴레이 핀 번호가 중복됩니다!")
        
        print(f"[CONFIG] 하드웨어 핀 설정: {required_pins}")
    
    print(f"[CONFIG] 설정 로드 완료 - 시뮬레이션 모드: {SIMULATION_MODE}")

# 설정 검증 실행
if __name__ == "__main__":
    validate_config()
    print("\n=== 현재 설정 요약 ===")
    print(f"시뮬레이션 모드: {SIMULATION_MODE}")
    print(f"시리얼 포트: {SERIAL_PORT}")
    print(f"서버 URL: {BASE_API_URL}")
    print(f"릴레이 슬롯 수: {len(HARDWARE_CONFIG['relay_pins'])}")
    print(f"GUI 활성화: {not RASPBERRY_PI_CONFIG['auto_start_gui']}")
    print(f"음성 피드백: {VOICE_CONFIG['enabled']}")
    print(f"시스템 모니터링: {MONITORING_CONFIG['enabled']}")
else:
    # 모듈 import시 자동 검증
    validate_config()