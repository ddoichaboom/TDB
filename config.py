# config.py (라즈베리파이 환경 최적화)
import os

# 아두이노와 연결된 시리얼 포트
SERIAL_PORT = '/dev/ttyACM0'
BAUD_RATE = 9600

# 서버 주소 (AWS EC2 연동 대비)
BASE_API_URL = os.getenv('DISPENSER_API_URL', 'http://localhost:3000/dispenser')
AWS_EC2_URL = os.getenv('AWS_EC2_URL', 'https://your-ec2-instance.amazonaws.com/dispenser')

# 하드웨어 시뮬레이션 모드 (Arduino 없이 테스트할 때 True)
SIMULATION_MODE = os.getenv('SIMULATION_MODE', 'True').lower() == 'true'

# 라즈베리파이 환경 설정
RASPBERRY_PI_CONFIG = {
    # 디스플레이 설정
    'fullscreen': True,
    'hide_cursor': True,  # 마우스 커서 숨김
    'disable_screensaver': True,
    'auto_start_gui': True,
    
    # 터치스크린 없는 모니터 설정
    'touch_enabled': False,
    'keyboard_input': False,
    'mouse_input': False,
    
    # 스피커 설정 (모니터 내장 스피커)
    'audio_device': 'HDMI',  # HDMI 오디오 출력
    'audio_enabled': True,
    'voice_feedback': True,
    'sound_effects': True,
    
    # 자동 복구 설정
    'auto_restart_on_crash': True,
    'watchdog_enabled': True,
    'max_restart_attempts': 3
}

# GUI 설정 (라즈베리파이 최적화)
GUI_CONFIG = {
    # 업데이트 주기 (라즈베리파이 성능 고려)
    'update_interval': 15,  # 15초로 늘림
    'time_update_interval': 5,  # 시간 업데이트도 5초로
    
    # 네트워크 설정 (AWS EC2 연동 고려)
    'request_timeout': 15,  # 타임아웃 늘림
    'max_retry_count': 5,
    'retry_delay': 10,
    'connection_check_interval': 30,
    
    # 성능 설정 (라즈베리파이)
    'max_workers': 2,  # 스레드 수 줄임
    'cache_duration': 60,  # 캐시 시간 늘림
    'memory_limit_mb': 256,
    
    # UI 설정 (터치/키보드 없는 환경)
    'animation_speed': 1000,  # 애니메이션 느리게
    'loading_timeout': 30,
    'auto_transition_time': 10000,  # 10초 후 자동 전환
    
    # 색상 테마 (모니터 가독성 최적화)
    'colors': {
        'primary': '#2563eb',
        'success': '#16a34a', 
        'warning': '#ea580c',
        'danger': '#dc2626',
        'background': '#f8fafc',
        'card_bg': '#ffffff',
        'text_primary': '#1e293b',
        'text_secondary': '#64748b',
        'text_muted': '#94a3b8'
    },
    
    # 폰트 설정 (라즈베리파이 디스플레이)
    'fonts': {
        'family': 'DejaVu Sans',  # 라즈베리파이 기본 폰트
        'sizes': {
            'title': 32,
            'header': 20,
            'body': 16,
            'small': 14,
            'tiny': 12
        }
    }
}

# 음성 피드백 설정
VOICE_CONFIG = {
    'enabled': True,
    'language': 'ko',
    'volume': 0.8,
    'speech_rate': 180,
    'voice_engine': 'espeak',  # 라즈베리파이용
    
    # 음성 메시지 설정
    'welcome_message': True,
    'rfid_feedback': True,
    'dispense_announcement': True,
    'error_notification': True,
    
    # 사운드 효과
    'sound_effects': {
        'beep': True,
        'success_chime': True,
        'error_buzzer': True,
        'notification_ping': True
    }
}

# 로깅 설정 (라즈베리파이 SD카드 고려)
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '[%(levelname)s] %(asctime)s - %(message)s',
    'file_enabled': True,
    'file_path': '/home/pi/dispenser/logs/dispenser.log',
    'max_file_size': 5 * 1024 * 1024,  # 5MB로 줄임
    'backup_count': 3,
    'rotate_on_startup': True
}

# 시스템 모니터링 설정
MONITORING_CONFIG = {
    'enabled': True,
    'metrics_interval': 120,  # 2분으로 늘림
    'health_check_interval': 60,
    'memory_threshold': 85,  # 메모리 임계값
    'cpu_threshold': 90,
    'temperature_threshold': 70,  # 라즈베리파이 온도 모니터링
    'disk_threshold': 90,
    
    # 자동 복구 설정
    'auto_recovery': True,
    'restart_on_memory_limit': True,
    'restart_on_temperature_limit': True
}

# 하드웨어 설정 (라즈베리파이 GPIO)
HARDWARE_CONFIG = {
    'gpio_cleanup_on_exit': True,
    'servo_pulse_duration': 1.0,
    'slot_delay': 0.5,
    'max_dispense_retries': 3,
    'dispense_timeout': 15,
    
    # 라즈베리파이 특화 설정
    'gpio_mode': 'BCM',
    'gpio_warnings': False,
    'servo_frequency': 50,  # 50Hz PWM
    
    # 릴레이 핀 매핑
    'relay_pins': {
        1: {'forward': 17, 'backward': 18},
        2: {'forward': 22, 'backward': 23}, 
        3: {'forward': 24, 'backward': 25}
    },
    
    # 센서 핀
    'rfid_pins': {
        'power': 2,
        'ground': 6,
        'data': 14,
        'clock': 15
    }
}

# 개발/디버그 설정
DEBUG_CONFIG = {
    'enabled': SIMULATION_MODE,
    'verbose_api_logs': True,
    'show_performance_metrics': True,
    'mock_data_enabled': SIMULATION_MODE,
    'gui_debug_mode': False,
    'save_debug_screenshots': True,
    'debug_log_path': '/home/pi/dispenser/logs/debug.log'
}

# 네트워크 설정 (AWS EC2 연동)
NETWORK_CONFIG = {
    'primary_server': BASE_API_URL,
    'backup_server': AWS_EC2_URL,
    'fallback_mode': True,  # 서버 연결 실패 시 오프라인 모드
    
    # 연결 테스트
    'ping_test_hosts': [
        '8.8.8.8',  # Google DNS
        'amazonaws.com'  # AWS 연결 테스트
    ],
    
    # SSL/TLS 설정
    'ssl_verify': True,
    'ssl_cert_path': '/home/pi/dispenser/certs/',
    
    # 재연결 설정
    'auto_reconnect': True,
    'reconnect_interval': 30,
    'max_reconnect_attempts': 10
}

# 보안 설정
SECURITY_CONFIG = {
    'device_id_file': '/home/pi/dispenser/device_id.txt',
    'encryption_enabled': True,
    'api_key_file': '/home/pi/dispenser/api_key.txt',
    
    # RFID 보안
    'rfid_encryption': True,
    'session_timeout': 300,  # 5분
    'max_failed_attempts': 3,
    'lockout_duration': 600  # 10분
}

# 시스템 경로
SYSTEM_PATHS = {
    'base_dir': '/home/pi/dispenser',
    'logs_dir': '/home/pi/dispenser/logs',
    'config_dir': '/home/pi/dispenser/config',
    'assets_dir': '/home/pi/dispenser/assets',
    'sounds_dir': '/home/pi/dispenser/assets/sounds',
    'temp_dir': '/tmp/dispenser',
    'backup_dir': '/home/pi/dispenser/backup'
}

# 자동 시작 설정
AUTOSTART_CONFIG = {
    'enabled': True,
    'startup_delay': 30,  # 30초 후 시작
    'wait_for_network': True,
    'max_network_wait': 120,  # 최대 2분 대기
    'run_system_check': True,
    'display_splash_screen': True
}