# utils/serial_reader.py (향상된 RFID 리더 - 라즈베리파이 최적화)
import serial
import time
import threading
import queue
import re
import select
import sys
from config import SERIAL_PORT, BAUD_RATE, SIMULATION_MODE, HARDWARE_CONFIG
from utils.logger import log_info, log_error, log_warning, log_debug

class RFIDReader:
    """향상된 RFID 리더 클래스"""
    
    def __init__(self):
        self.serial_port = SERIAL_PORT
        self.baud_rate = BAUD_RATE
        self.timeout = 1.0
        self.connection = None
        self.is_connected = False
        self.read_thread = None
        self.running = False
        
        # UID 큐 및 필터링
        self.uid_queue = queue.Queue(maxsize=10)
        self.last_uid = None
        self.last_uid_time = 0
        self.uid_debounce_time = 1.0  # 1초 디바운스
        
        # UID 검증 패턴
        self.uid_patterns = [
            re.compile(r'^[A-F0-9]{8,12}$'),  # 8-12자리 16진수
            re.compile(r'^K[0-9]{3,4}$'),     # K001, K0001 형식
            re.compile(r'^[0-9]{8,12}$'),     # 숫자만
        ]
        
        # 통계
        self.stats = {
            'total_reads': 0,
            'valid_reads': 0,
            'invalid_reads': 0,
            'connection_errors': 0,
            'last_read_time': None
        }
        
        log_info("RFID 리더 초기화 완료", "RFID")
    
    def connect(self):
        """RFID 리더 연결"""
        if SIMULATION_MODE:
            log_info("RFID 리더 시뮬레이션 모드", "RFID")
            self.is_connected = True
            return True
        
        try:
            # 시리얼 포트 연결 시도
            self.connection = serial.Serial(
                port=self.serial_port,
                baudrate=self.baud_rate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            
            # 연결 확인
            if self.connection.is_open:
                self.is_connected = True
                log_info(f"RFID 리더 연결 성공: {self.serial_port}", "RFID")
                
                # 초기화 명령 전송 (리더 종류에 따라 다름)
                self.initialize_reader()
                
                return True
            else:
                log_error("RFID 리더 연결 실패", "RFID")
                return False
                
        except serial.SerialException as e:
            log_error(f"시리얼 포트 오류: {e}", "RFID")
            self.stats['connection_errors'] += 1
            return False
        except Exception as e:
            log_error(f"RFID 리더 연결 중 오류: {e}", "RFID")
            return False
    
    def initialize_reader(self):
        """RFID 리더 초기화"""
        try:
            if not self.connection or SIMULATION_MODE:
                return
            
            # 버퍼 비우기
            self.connection.reset_input_buffer()
            self.connection.reset_output_buffer()
            
            # 리더 타입별 초기화 명령
            # (실제 사용하는 RFID 리더 모델에 맞게 수정 필요)
            init_commands = [
                b'\x02\x00\x01\x03',  # 예시 명령
            ]
            
            for cmd in init_commands:
                try:
                    self.connection.write(cmd)
                    time.sleep(0.1)
                except:
                    pass
            
            log_info("RFID 리더 초기화 완료", "RFID")
            
        except Exception as e:
            log_error(f"RFID 리더 초기화 오류: {e}", "RFID")
    
    def start_reading(self):
        """읽기 스레드 시작"""
        if self.running:
            log_warning("RFID 리더가 이미 실행 중입니다", "RFID")
            return
        
        if not self.connect():
            log_error("RFID 리더 연결 실패로 읽기 시작 불가", "RFID")
            return
        
        self.running = True
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()
        
        log_info("RFID 읽기 스레드 시작", "RFID")
    
    def stop_reading(self):
        """읽기 스레드 중지"""
        self.running = False
        
        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=3)
        
        self.disconnect()
        log_info("RFID 읽기 스레드 중지", "RFID")
    
    def _read_loop(self):
        """읽기 메인 루프"""
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        while self.running:
            try:
                if SIMULATION_MODE:
                    # 시뮬레이션 모드
                    uid = self._read_simulation()
                else:
                    # 실제 하드웨어 모드
                    uid = self._read_hardware()
                
                if uid:
                    self._process_uid(uid)
                    consecutive_errors = 0
                else:
                    time.sleep(0.1)  # UID가 없을 때 짧은 대기
                
            except Exception as e:
                consecutive_errors += 1
                log_error(f"RFID 읽기 오류: {e}", "RFID")
                
                if consecutive_errors >= max_consecutive_errors:
                    log_error("연속 읽기 오류 - 재연결 시도", "RFID")
                    self._reconnect()
                    consecutive_errors = 0
                
                time.sleep(1)  # 오류 시 1초 대기
    
    def _read_hardware(self):
        """하드웨어에서 UID 읽기"""
        try:
            if not self.connection or not self.connection.is_open:
                return None
            
            # 데이터 대기 확인
            if self.connection.in_waiting == 0:
                return None
            
            # 데이터 읽기
            raw_data = self.connection.readline()
            
            if not raw_data:
                return None
            
            # 문자열 변환 및 정리
            try:
                uid_str = raw_data.decode('utf-8', errors='ignore').strip()
            except:
                uid_str = raw_data.decode('ascii', errors='ignore').strip()
            
            # 공백 및 특수문자 제거
            uid_str = re.sub(r'[^\w]', '', uid_str).upper()
            
            if len(uid_str) < 3:  # 너무 짧은 데이터 무시
                return None
            
            self.stats['total_reads'] += 1
            
            # UID 검증
            if self._validate_uid(uid_str):
                self.stats['valid_reads'] += 1
                self.stats['last_read_time'] = time.time()
                return uid_str
            else:
                self.stats['invalid_reads'] += 1
                log_debug(f"잘못된 UID 형식: {uid_str}", "RFID")
                return None
                
        except serial.SerialException as e:
            log_error(f"시리얼 읽기 오류: {e}", "RFID")
            self.stats['connection_errors'] += 1
            return None
        except Exception as e:
            log_error(f"하드웨어 읽기 오류: {e}", "RFID")
            return None
    
    def _read_simulation(self):
        """시뮬레이션 모드 UID 읽기"""
        try:
            # 논블로킹 키보드 입력 확인
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                line = sys.stdin.readline().strip()
                if line:
                    uid_str = line.upper()
                    
                    self.stats['total_reads'] += 1
                    
                    # 시뮬레이션 UID 검증
                    if self._validate_uid(uid_str):
                        self.stats['valid_reads'] += 1
                        self.stats['last_read_time'] = time.time()
                        log_debug(f"시뮬레이션 UID 입력: {uid_str}", "RFID")
                        return uid_str
                    else:
                        self.stats['invalid_reads'] += 1
                        log_debug(f"잘못된 시뮬레이션 UID: {uid_str}", "RFID")
                        return None
            
            return None
            
        except Exception as e:
            log_error(f"시뮬레이션 읽기 오류: {e}", "RFID")
            return None
    
    def _validate_uid(self, uid_str):
        """UID 유효성 검증"""
        if not uid_str or len(uid_str) < 3:
            return False
        
        # 패턴 매칭
        for pattern in self.uid_patterns:
            if pattern.match(uid_str):
                return True
        
        # 추가 검증 규칙
        if len(uid_str) >= 6 and uid_str.isalnum():
            return True
        
        return False
    
    def _process_uid(self, uid):
        """UID 처리 및 디바운싱"""
        current_time = time.time()
        
        # 디바운싱: 같은 UID가 짧은 시간 내에 반복되면 무시
        if (self.last_uid == uid and 
            current_time - self.last_uid_time < self.uid_debounce_time):
            return
        
        self.last_uid = uid
        self.last_uid_time = current_time
        
        # 큐에 UID 추가
        try:
            self.uid_queue.put_nowait(uid)
            log_info(f"새 UID 감지: {uid}", "RFID")
        except queue.Full:
            # 큐가 가득 찬 경우 오래된 항목 제거
            try:
                self.uid_queue.get_nowait()
                self.uid_queue.put_nowait(uid)
            except queue.Empty:
                pass
    
    def get_uid(self):
        """큐에서 UID 가져오기 (논블로킹)"""
        try:
            return self.uid_queue.get_nowait()
        except queue.Empty:
            return None
    
    def wait_for_uid(self, timeout=None):
        """UID 대기 (블로킹)"""
        try:
            return self.uid_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def _reconnect(self):
        """재연결 시도"""
        try:
            log_info("RFID 리더 재연결 시도", "RFID")
            
            self.disconnect()
            time.sleep(2)  # 2초 대기
            
            if self.connect():
                log_info("RFID 리더 재연결 성공", "RFID")
            else:
                log_error("RFID 리더 재연결 실패", "RFID")
                
        except Exception as e:
            log_error(f"재연결 중 오류: {e}", "RFID")
    
    def disconnect(self):
        """연결 해제"""
        try:
            if self.connection and self.connection.is_open:
                self.connection.close()
            
            self.is_connected = False
            log_info("RFID 리더 연결 해제", "RFID")
            
        except Exception as e:
            log_error(f"연결 해제 오류: {e}", "RFID")
    
    def get_stats(self):
        """통계 정보 반환"""
        stats = self.stats.copy()
        stats['is_connected'] = self.is_connected
        stats['is_running'] = self.running
        stats['queue_size'] = self.uid_queue.qsize()
        
        if stats['total_reads'] > 0:
            stats['success_rate'] = (stats['valid_reads'] / stats['total_reads']) * 100
        else:
            stats['success_rate'] = 0
        
        return stats
    
    def test_connection(self):
        """연결 테스트"""
        if SIMULATION_MODE:
            log_info("RFID 연결 테스트 - 시뮬레이션 모드", "RFID")
            return True
        
        try:
            if not self.is_connected:
                return self.connect()
            
            # 간단한 통신 테스트
            if self.connection and self.connection.is_open:
                # 테스트 명령 전송 (리더 타입에 따라 다름)
                test_cmd = b'\x02\x00\x00\x02'  # 예시 명령
                self.connection.write(test_cmd)
                
                # 응답 대기
                time.sleep(0.5)
                if self.connection.in_waiting > 0:
                    response = self.connection.read(self.connection.in_waiting)
                    log_info(f"RFID 테스트 응답: {response.hex()}", "RFID")
                
                return True
            
            return False
            
        except Exception as e:
            log_error(f"RFID 연결 테스트 실패: {e}", "RFID")
            return False


# 전역 RFID 리더 인스턴스
_rfid_reader = None

def get_rfid_reader():
    """전역 RFID 리더 반환"""
    global _rfid_reader
    if _rfid_reader is None:
        _rfid_reader = RFIDReader()
    return _rfid_reader

def start_rfid_reader():
    """RFID 리더 시작"""
    reader = get_rfid_reader()
    reader.start_reading()

def stop_rfid_reader():
    """RFID 리더 중지"""
    global _rfid_reader
    if _rfid_reader:
        _rfid_reader.stop_reading()
        _rfid_reader = None

# 기존 함수들 (호환성 유지)
def read_uid():
    """RFID UID 읽기 (기존 인터페이스)"""
    try:
        reader = get_rfid_reader()
        
        # 리더가 실행 중이 아니면 시작
        if not reader.running:
            reader.start_reading()
            time.sleep(1)  # 초기화 대기
        
        return reader.get_uid()
        
    except Exception as e:
        log_error(f"UID 읽기 오류: {e}", "RFID")
        return None

def read_uid_simulation():
    """시뮬레이션 모드 UID 읽기 (기존 인터페이스)"""
    try:
        reader = get_rfid_reader()
        return reader._read_simulation()
    except Exception as e:
        log_error(f"시뮬레이션 UID 읽기 오류: {e}", "RFID")
        return None

def wait_for_card(timeout=None):
    """카드 대기 (새로운 함수)"""
    try:
        reader = get_rfid_reader()
        
        if not reader.running:
            reader.start_reading()
        
        return reader.wait_for_uid(timeout)
        
    except Exception as e:
        log_error(f"카드 대기 오류: {e}", "RFID")
        return None

def get_rfid_stats():
    """RFID 리더 통계 반환"""
    try:
        reader = get_rfid_reader()
        return reader.get_stats()
    except Exception as e:
        log_error(f"RFID 통계 조회 오류: {e}", "RFID")
        return {}

def test_rfid_connection():
    """RFID 연결 테스트"""
    try:
        reader = get_rfid_reader()
        return reader.test_connection()
    except Exception as e:
        log_error(f"RFID 연결 테스트 오류: {e}", "RFID")
        return False

# 고급 UID 처리 함수들
def validate_uid_format(uid):
    """UID 형식 검증"""
    if not uid:
        return False
    
    # 기본 검증 패턴들
    patterns = [
        r'^[A-F0-9]{8,12}$',  # 8-12자리 16진수
        r'^K[0-9]{3,4}$',     # K001, K0001 형식  
        r'^[0-9]{8,12}$',     # 숫자만
        r'^[A-Z][0-9]{3,6}$', # 문자+숫자 조합
    ]
    
    for pattern in patterns:
        if re.match(pattern, uid.upper()):
            return True
    
    return False

def sanitize_uid(raw_uid):
    """UID 정리 및 표준화"""
    if not raw_uid:
        return None
    
    # 문자열 변환
    if isinstance(raw_uid, bytes):
        try:
            uid_str = raw_uid.decode('utf-8', errors='ignore')
        except:
            uid_str = raw_uid.decode('ascii', errors='ignore')
    else:
        uid_str = str(raw_uid)
    
    # 공백 및 특수문자 제거
    uid_str = re.sub(r'[^\w]', '', uid_str).upper().strip()
    
    # 길이 검증
    if len(uid_str) < 3 or len(uid_str) > 20:
        return None
    
    # 형식 검증
    if validate_uid_format(uid_str):
        return uid_str
    
    return None

def debug_rfid_reader():
    """RFID 리더 디버깅 정보 출력"""
    try:
        reader = get_rfid_reader()
        stats = reader.get_stats()
        
        print("\n" + "="*50)
        print("🔍 RFID 리더 디버깅 정보")
        print("="*50)
        print(f"연결 상태: {'연결됨' if stats['is_connected'] else '연결 안됨'}")
        print(f"실행 상태: {'실행 중' if stats['is_running'] else '중지됨'}")
        print(f"시리얼 포트: {reader.serial_port}")
        print(f"보드레이트: {reader.baud_rate}")
        print(f"시뮬레이션 모드: {'ON' if SIMULATION_MODE else 'OFF'}")
        print()
        print("📊 통계 정보:")
        print(f"총 읽기 시도: {stats['total_reads']}")
        print(f"유효한 읽기: {stats['valid_reads']}")
        print(f"무효한 읽기: {stats['invalid_reads']}")
        print(f"연결 오류: {stats['connection_errors']}")
        print(f"성공률: {stats['success_rate']:.1f}%")
        print(f"큐 크기: {stats['queue_size']}")
        
        if stats['last_read_time']:
            last_read = time.time() - stats['last_read_time']
            print(f"마지막 읽기: {last_read:.1f}초 전")
        else:
            print("마지막 읽기: 없음")
        
        print("="*50)
        
    except Exception as e:
        print(f"디버깅 정보 조회 오류: {e}")

if __name__ == "__main__":
    # 직접 실행 시 테스트 모드
    print("RFID 리더 테스트 모드")
    print("'debug'를 입력하면 디버깅 정보를 표시합니다.")
    print("'quit'를 입력하면 종료합니다.")
    print("시뮬레이션 모드에서는 UID를 직접 입력하세요 (예: K001)")
    print()
    
    try:
        start_rfid_reader()
        
        while True:
            try:
                if SIMULATION_MODE:
                    user_input = input("UID 입력 (또는 명령): ").strip()
                    
                    if user_input.lower() == 'quit':
                        break
                    elif user_input.lower() == 'debug':
                        debug_rfid_reader()
                        continue
                    elif user_input:
                        # 시뮬레이션 UID 처리
                        sanitized = sanitize_uid(user_input)
                        if sanitized:
                            print(f"✅ 유효한 UID: {sanitized}")
                        else:
                            print(f"❌ 잘못된 UID 형식: {user_input}")
                else:
                    # 하드웨어 모드
                    uid = wait_for_card(timeout=1)
                    if uid:
                        print(f"📡 카드 감지: {uid}")
                
            except KeyboardInterrupt:
                print("\n종료 중...")
                break
            except Exception as e:
                print(f"오류: {e}")
    
    finally:
        stop_rfid_reader()
        print("RFID 리더 테스트 종료")