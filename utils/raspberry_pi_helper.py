# utils/raspberry_pi_helper.py (라즈베리파이 하드웨어 제어 및 시스템 유틸리티)
import time
import subprocess
import os
import json
import socket
from pathlib import Path
from config import HARDWARE_CONFIG, SIMULATION_MODE

# GPIO 라이브러리 안전하게 임포트
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("[WARNING] RPi.GPIO가 설치되지 않음. 시뮬레이션 모드로만 동작합니다.")

class RaspberryPiHelper:
    """라즈베리파이 하드웨어 제어 및 시스템 관리 클래스"""
    
    def __init__(self):
        self.gpio_initialized = False
        self.relay_pins = {}
        self.rfid_pins = {}
        self.thermal_protection_active = False
        
        # 시스템 정보 캐시
        self.system_info_cache = {}
        self.last_system_info_update = 0
        
        print("[INFO] RaspberryPiHelper 초기화")
    
    def get_system_info(self):
        """라즈베리파이 시스템 정보 수집"""
        try:
            # 캐시된 정보가 있고 5분 이내라면 반환
            current_time = time.time()
            if (self.system_info_cache and 
                current_time - self.last_system_info_update < 300):
                return self.system_info_cache
            
            system_info = {}
            
            # 라즈베리파이 모델 정보
            try:
                with open('/proc/device-tree/model', 'r') as f:
                    system_info['model'] = f.read().strip().replace('\x00', '')
            except:
                system_info['model'] = 'Unknown'
            
            # CPU 정보
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    cpuinfo = f.read()
                    for line in cpuinfo.split('\n'):
                        if 'Hardware' in line:
                            system_info['hardware'] = line.split(':')[1].strip()
                        elif 'Revision' in line:
                            system_info['revision'] = line.split(':')[1].strip()
                        elif 'Serial' in line:
                            system_info['serial'] = line.split(':')[1].strip()
            except:
                pass
            
            # 메모리 정보
            try:
                with open('/proc/meminfo', 'r') as f:
                    meminfo = f.read()
                    for line in meminfo.split('\n'):
                        if 'MemTotal' in line:
                            system_info['total_memory'] = int(line.split()[1]) * 1024  # bytes
                            break
            except:
                system_info['total_memory'] = 0
            
            # OS 정보
            try:
                with open('/etc/os-release', 'r') as f:
                    os_info = f.read()
                    for line in os_info.split('\n'):
                        if line.startswith('PRETTY_NAME='):
                            system_info['os'] = line.split('=')[1].strip('"')
                            break
            except:
                system_info['os'] = 'Unknown'
            
            # 커널 버전
            try:
                result = subprocess.run(['uname', '-r'], capture_output=True, text=True)
                system_info['kernel'] = result.stdout.strip()
            except:
                system_info['kernel'] = 'Unknown'
            
            # 부팅 시간
            try:
                with open('/proc/uptime', 'r') as f:
                    uptime = float(f.read().split()[0])
                    system_info['uptime'] = uptime
            except:
                system_info['uptime'] = 0
            
            # GPU 정보
            system_info['gpu_memory'] = self.get_gpu_memory()
            system_info['gpu_temp'] = self.get_gpu_temperature()
            
            # 전압 정보
            system_info['voltages'] = self.get_all_voltages()
            
            # 스로틀링 상태
            system_info['throttling'] = self.get_throttling_info()
            
            # 캐시 업데이트
            self.system_info_cache = system_info
            self.last_system_info_update = current_time
            
            return system_info
            
        except Exception as e:
            print(f"[ERROR] 시스템 정보 수집 오류: {e}")
            return {'error': str(e)}
    
    def get_serial_number(self):
        """라즈베리파이 시리얼 번호 반환"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        return line.split(':')[1].strip()
            return None
        except:
            return None
    
    def get_gpu_memory(self):
        """GPU 메모리 할당량 확인"""
        try:
            result = subprocess.run(['vcgencmd', 'get_mem', 'gpu'], 
                                  capture_output=True, text=True, check=True)
            # gpu=64M 형식에서 숫자 추출
            gpu_mem = int(result.stdout.strip().split('=')[1].rstrip('M'))
            return gpu_mem
        except:
            return 0
    
    def get_gpu_temperature(self):
        """GPU 온도 확인"""
        try:
            result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                  capture_output=True, text=True, check=True)
            # temp=42.8'C 형식에서 숫자 추출
            temp = float(result.stdout.strip().split('=')[1].split("'")[0])
            return temp
        except:
            return 0.0
    
    def get_all_voltages(self):
        """모든 전압 정보 수집"""
        voltages = {}
        voltage_types = ['core', 'sdram_c', 'sdram_i', 'sdram_p']
        
        for volt_type in voltage_types:
            try:
                result = subprocess.run(['vcgencmd', 'measure_volts', volt_type], 
                                      capture_output=True, text=True, check=True)
                # volt=1.2000V 형식에서 숫자 추출
                voltage = float(result.stdout.strip().split('=')[1].rstrip('V'))
                voltages[volt_type] = voltage
            except:
                voltages[volt_type] = 0.0
        
        return voltages
    
    def get_throttling_info(self):
        """스로틀링 정보 수집"""
        try:
            result = subprocess.run(['vcgencmd', 'get_throttled'], 
                                  capture_output=True, text=True, check=True)
            throttled_hex = result.stdout.strip().split('=')[1]
            throttled_int = int(throttled_hex, 16)
            
            # 스로틀링 상태 비트 분석
            throttling_info = {
                'currently_throttled': bool(throttled_int & 0x1),
                'arm_frequency_capped': bool(throttled_int & 0x2),
                'under_voltage': bool(throttled_int & 0x4),
                'soft_temp_limit': bool(throttled_int & 0x8),
                'throttling_occurred': bool(throttled_int & 0x10000),
                'arm_frequency_capping_occurred': bool(throttled_int & 0x20000),
                'under_voltage_occurred': bool(throttled_int & 0x40000),
                'soft_temp_limit_occurred': bool(throttled_int & 0x80000)
            }
            
            return throttling_info
        except:
            return {}
    
    def get_network_interfaces(self):
        """네트워크 인터페이스 정보"""
        try:
            interfaces = {}
            result = subprocess.run(['ip', 'addr', 'show'], 
                                  capture_output=True, text=True, check=True)
            
            current_interface = None
            for line in result.stdout.split('\n'):
                if line and not line.startswith(' '):
                    # 인터페이스 이름 추출
                    parts = line.split(':')
                    if len(parts) >= 2:
                        current_interface = parts[1].strip()
                        interfaces[current_interface] = {'addresses': []}
                
                elif line.strip().startswith('inet ') and current_interface:
                    # IP 주소 추출
                    ip_info = line.strip().split()
                    if len(ip_info) >= 2:
                        interfaces[current_interface]['addresses'].append(ip_info[1])
            
            return interfaces
        except:
            return {}
    
    def get_dns_servers(self):
        """DNS 서버 정보"""
        try:
            dns_servers = []
            with open('/etc/resolv.conf', 'r') as f:
                for line in f:
                    if line.startswith('nameserver'):
                        dns_servers.append(line.split()[1])
            return dns_servers
        except:
            return []
    
    def test_internet_connection(self):
        """인터넷 연결 테스트"""
        try:
            # Google DNS에 연결 테스트
            socket.create_connection(("8.8.8.8", 53), timeout=5)
            return True
        except:
            try:
                # 대체 서버 테스트
                socket.create_connection(("1.1.1.1", 53), timeout=5)
                return True
            except:
                return False
    
    def get_audio_devices(self):
        """오디오 장치 목록"""
        try:
            devices = []
            result = subprocess.run(['aplay', '-l'], 
                                  capture_output=True, text=True, check=False)
            
            for line in result.stdout.split('\n'):
                if 'card' in line and ':' in line:
                    devices.append(line.strip())
            
            return devices
        except:
            return []
    
    def set_system_volume(self, volume_percent):
        """시스템 볼륨 설정"""
        try:
            subprocess.run(['amixer', 'set', 'Master', f'{volume_percent}%'], 
                          check=False, capture_output=True)
            return True
        except:
            return False
    
    def test_audio_output(self):
        """오디오 출력 테스트"""
        try:
            # 간단한 비프음 생성 및 재생
            result = subprocess.run(['speaker-test', '-t', 'sine', '-f', '1000', '-l', '1', '-s', '1'], 
                                  timeout=3, capture_output=True, check=False)
            return result.returncode == 0
        except:
            try:
                # sox를 사용한 대체 테스트
                subprocess.run(['play', '-n', 'synth', '0.1', 'sin', '1000'], 
                              timeout=2, capture_output=True, check=False)
                return True
            except:
                return False
    
    # GPIO 관련 메서드들
    def init_gpio(self):
        """GPIO 초기화"""
        if not GPIO_AVAILABLE or SIMULATION_MODE:
            print("[INFO] GPIO 시뮬레이션 모드")
            self.gpio_initialized = True
            return True
        
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            self.gpio_initialized = True
            print("[INFO] GPIO 초기화 완료")
            return True
        except Exception as e:
            print(f"[ERROR] GPIO 초기화 실패: {e}")
            return False
    
    def setup_relay_pins(self, slot, forward_pin, backward_pin):
        """릴레이 핀 설정"""
        if not self.gpio_initialized:
            print("[WARNING] GPIO가 초기화되지 않음")
            return False
        
        try:
            if not SIMULATION_MODE and GPIO_AVAILABLE:
                GPIO.setup(forward_pin, GPIO.OUT)
                GPIO.setup(backward_pin, GPIO.OUT)
                GPIO.output(forward_pin, GPIO.LOW)
                GPIO.output(backward_pin, GPIO.LOW)
            
            self.relay_pins[slot] = {
                'forward': forward_pin,
                'backward': backward_pin
            }
            
            print(f"[INFO] 릴레이 핀 설정 완료 - 슬롯 {slot}: {forward_pin}, {backward_pin}")
            return True
            
        except Exception as e:
            print(f"[ERROR] 릴레이 핀 설정 실패: {e}")
            return False
    
    def setup_rfid_pins(self, rfid_pin_config):
        """RFID 핀 설정"""
        if not self.gpio_initialized:
            print("[WARNING] GPIO가 초기화되지 않음")
            return False
        
        try:
            self.rfid_pins = rfid_pin_config
            
            if not SIMULATION_MODE and GPIO_AVAILABLE:
                # RFID 리더의 전원 핀 설정
                if 'power' in rfid_pin_config:
                    GPIO.setup(rfid_pin_config['power'], GPIO.OUT)
                    GPIO.output(rfid_pin_config['power'], GPIO.HIGH)
                
                # 데이터 핀 설정
                if 'data' in rfid_pin_config:
                    GPIO.setup(rfid_pin_config['data'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
                
                # 클럭 핀 설정
                if 'clock' in rfid_pin_config:
                    GPIO.setup(rfid_pin_config['clock'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            print("[INFO] RFID 핀 설정 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] RFID 핀 설정 실패: {e}")
            return False
    
    def test_gpio(self):
        """GPIO 기능 테스트"""
        if not self.gpio_initialized:
            return False
        
        if SIMULATION_MODE:
            print("[INFO] GPIO 테스트 - 시뮬레이션 모드")
            return True
        
        try:
            if not GPIO_AVAILABLE:
                return False
            
            # 간단한 GPIO 테스트 (사용하지 않는 핀으로)
            test_pin = 21  # 일반적으로 사용하지 않는 핀
            
            GPIO.setup(test_pin, GPIO.OUT)
            GPIO.output(test_pin, GPIO.HIGH)
            time.sleep(0.1)
            GPIO.output(test_pin, GPIO.LOW)
            GPIO.cleanup(test_pin)
            
            print("[INFO] GPIO 테스트 통과")
            return True
            
        except Exception as e:
            print(f"[ERROR] GPIO 테스트 실패: {e}")
            return False
    
    def test_relay(self, slot):
        """특정 슬롯의 릴레이 테스트"""
        if slot not in self.relay_pins:
            print(f"[ERROR] 슬롯 {slot}이 설정되지 않음")
            return False
        
        if SIMULATION_MODE:
            print(f"[INFO] 릴레이 테스트 - 슬롯 {slot} (시뮬레이션)")
            time.sleep(0.1)
            return True
        
        try:
            if not GPIO_AVAILABLE:
                return False
            
            pins = self.relay_pins[slot]
            forward_pin = pins['forward']
            backward_pin = pins['backward']
            
            # 짧은 테스트 펄스
            GPIO.output(forward_pin, GPIO.HIGH)
            time.sleep(0.1)
            GPIO.output(forward_pin, GPIO.LOW)
            
            time.sleep(0.1)
            
            GPIO.output(backward_pin, GPIO.HIGH)
            time.sleep(0.1)
            GPIO.output(backward_pin, GPIO.LOW)
            
            print(f"[INFO] 릴레이 테스트 통과 - 슬롯 {slot}")
            return True
            
        except Exception as e:
            print(f"[ERROR] 릴레이 테스트 실패 - 슬롯 {slot}: {e}")
            return False
    
    def test_rfid_reader(self):
        """RFID 리더 테스트"""
        if SIMULATION_MODE:
            print("[INFO] RFID 리더 테스트 - 시뮬레이션 모드")
            return True
        
        try:
            if not GPIO_AVAILABLE or not self.rfid_pins:
                return False
            
            # RFID 리더의 전원 상태 확인
            if 'power' in self.rfid_pins:
                power_pin = self.rfid_pins['power']
                power_state = GPIO.input(power_pin)
                if not power_state:
                    print("[WARNING] RFID 리더 전원이 꺼져있음")
                    return False
            
            # 데이터 핀 상태 확인
            if 'data' in self.rfid_pins:
                data_pin = self.rfid_pins['data']
                data_state = GPIO.input(data_pin)
                print(f"[INFO] RFID 데이터 핀 상태: {data_state}")
            
            print("[INFO] RFID 리더 테스트 통과")
            return True
            
        except Exception as e:
            print(f"[ERROR] RFID 리더 테스트 실패: {e}")
            return False
    
    def dispense_medicine(self, slot, dose=1):
        """약 배출 실행"""
        if slot not in self.relay_pins:
            print(f"[ERROR] 슬롯 {slot}이 설정되지 않음")
            return False
        
        if SIMULATION_MODE:
            print(f"[INFO] 약 배출 시뮬레이션 - 슬롯 {slot}, {dose}개")
            time.sleep(dose * 0.5)  # 시뮬레이션 지연
            return True
        
        try:
            if not GPIO_AVAILABLE:
                return False
            
            pins = self.relay_pins[slot]
            forward_pin = pins['forward']
            backward_pin = pins['backward']
            
            pulse_duration = HARDWARE_CONFIG['servo_pulse_duration']
            slot_delay = HARDWARE_CONFIG['slot_delay']
            
            print(f"[INFO] 약 배출 시작 - 슬롯 {slot}, {dose}개")
            
            for i in range(dose):
                # 전진 (약 진입)
                GPIO.output(forward_pin, GPIO.HIGH)
                time.sleep(pulse_duration)
                GPIO.output(forward_pin, GPIO.LOW)
                
                time.sleep(slot_delay)
                
                # 후진 (약 배출)
                GPIO.output(backward_pin, GPIO.HIGH)
                time.sleep(pulse_duration)
                GPIO.output(backward_pin, GPIO.LOW)
                
                if i < dose - 1:  # 마지막이 아니면 대기
                    time.sleep(slot_delay)
                
                print(f"[INFO] 약 배출 진행 - {i+1}/{dose}")
            
            print(f"[INFO] 약 배출 완료 - 슬롯 {slot}")
            return True
            
        except Exception as e:
            print(f"[ERROR] 약 배출 실패 - 슬롯 {slot}: {e}")
            return False
    
    def reset_hardware(self):
        """하드웨어 리셋"""
        try:
            print("[INFO] 하드웨어 리셋 시작")
            
            if not SIMULATION_MODE and GPIO_AVAILABLE:
                # 모든 릴레이 핀을 LOW로
                for slot, pins in self.relay_pins.items():
                    GPIO.output(pins['forward'], GPIO.LOW)
                    GPIO.output(pins['backward'], GPIO.LOW)
                    print(f"[INFO] 슬롯 {slot} 리셋 완료")
            
            print("[INFO] 하드웨어 리셋 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] 하드웨어 리셋 실패: {e}")
            return False
    
    def cleanup_gpio(self):
        """GPIO 정리"""
        try:
            if not SIMULATION_MODE and GPIO_AVAILABLE and self.gpio_initialized:
                GPIO.cleanup()
                print("[INFO] GPIO 정리 완료")
            
            self.gpio_initialized = False
            self.relay_pins = {}
            self.rfid_pins = {}
            
        except Exception as e:
            print(f"[ERROR] GPIO 정리 실패: {e}")
    
    def enable_thermal_protection(self):
        """열 보호 모드 활성화"""
        if self.thermal_protection_active:
            return
        
        try:
            print("[INFO] 열 보호 모드 활성화")
            
            # CPU 주파수 제한
            subprocess.run(['echo', 'powersave', '>', '/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'], 
                          shell=True, check=False)
            
            self.thermal_protection_active = True
            
            # 30초 후 자동 해제
            def disable_thermal_protection():
                time.sleep(30)
                try:
                    subprocess.run(['echo', 'ondemand', '>', '/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'], 
                                  shell=True, check=False)
                    self.thermal_protection_active = False
                    print("[INFO] 열 보호 모드 해제")
                except:
                    pass
            
            import threading
            threading.Thread(target=disable_thermal_protection, daemon=True).start()
            
        except Exception as e:
            print(f"[ERROR] 열 보호 모드 활성화 실패: {e}")
    
    def get_hardware_status(self):
        """하드웨어 상태 요약"""
        try:
            status = {
                'gpio_initialized': self.gpio_initialized,
                'relay_slots': list(self.relay_pins.keys()),
                'rfid_configured': bool(self.rfid_pins),
                'thermal_protection': self.thermal_protection_active,
                'simulation_mode': SIMULATION_MODE,
                'gpio_available': GPIO_AVAILABLE
            }
            
            # 온도 정보 추가
            status['temperatures'] = {
                'cpu': self.get_cpu_temperature(),
                'gpu': self.get_gpu_temperature()
            }
            
            # 전압 정보 추가
            status['voltages'] = self.get_all_voltages()
            
            # 스로틀링 정보 추가
            status['throttling'] = self.get_throttling_info()
            
            return status
            
        except Exception as e:
            print(f"[ERROR] 하드웨어 상태 수집 오류: {e}")
            return {'error': str(e)}
    
    def get_cpu_temperature(self):
        """CPU 온도 반환"""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp_millidegree = int(f.read().strip())
                return temp_millidegree / 1000.0
        except:
            return 0.0
    
    def save_hardware_config(self, config_path='/home/pi/dispenser/config/hardware.json'):
        """하드웨어 설정 저장"""
        try:
            config = {
                'relay_pins': self.relay_pins,
                'rfid_pins': self.rfid_pins,
                'gpio_initialized': self.gpio_initialized,
                'timestamp': time.time()
            }
            
            Path(config_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            print(f"[INFO] 하드웨어 설정 저장: {config_path}")
            return True
            
        except Exception as e:
            print(f"[ERROR] 하드웨어 설정 저장 실패: {e}")
            return False
    
    def load_hardware_config(self, config_path='/home/pi/dispenser/config/hardware.json'):
        """하드웨어 설정 로드"""
        try:
            if not Path(config_path).exists():
                print("[INFO] 하드웨어 설정 파일이 없음")
                return False
            
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            self.relay_pins = config.get('relay_pins', {})
            self.rfid_pins = config.get('rfid_pins', {})
            
            print(f"[INFO] 하드웨어 설정 로드: {config_path}")
            return True
            
        except Exception as e:
            print(f"[ERROR] 하드웨어 설정 로드 실패: {e}")
            return False