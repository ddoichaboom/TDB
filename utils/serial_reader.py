# utils/serial_reader.py (간소화 및 안정화 버전)
import serial
import time
import re
import sys
import select
from config import SERIAL_PORT, BAUD_RATE, SIMULATION_MODE

class SimpleRFIDReader:
    """간소화된 RFID 리더 - 핵심 기능에 집중"""
    
    def __init__(self):
        self.port = SERIAL_PORT
        self.baud_rate = BAUD_RATE
        self.connection = None
        self.last_uid = None
        self.last_read_time = 0
        self.debounce_time = 2.0  # 2초 디바운스
        
        print(f"[RFID] 초기화 - 시뮬레이션 모드: {SIMULATION_MODE}")
    
    def connect(self):
        """RFID 리더 연결"""
        if SIMULATION_MODE:
            print("[RFID] 시뮬레이션 모드 - 콘솔 입력 대기")
            return True
        
        try:
            self.connection = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=1.0
            )
            print(f"[RFID] 하드웨어 연결 성공: {self.port}")
            return True
            
        except Exception as e:
            print(f"[RFID] 연결 실패: {e}")
            return False
    
    def read_uid(self):
        """UID 읽기 - 메인 함수"""
        current_time = time.time()
        
        # 디바운싱: 같은 카드가 너무 빨리 재인식되는 것 방지
        if (self.last_uid and 
            current_time - self.last_read_time < self.debounce_time):
            return None
        
        if SIMULATION_MODE:
            uid = self._read_simulation()
        else:
            uid = self._read_hardware()
        
        if uid and self._validate_uid(uid):
            self.last_uid = uid
            self.last_read_time = current_time
            print(f"[RFID] 유효한 UID 감지: {uid}")
            return uid
        
        return None
    
    def _read_simulation(self):
        """시뮬레이션 모드에서 콘솔 입력 읽기"""
        try:
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                line = sys.stdin.readline().strip()
                if line:
                    return line.upper()
        except:
            pass
        return None
    
    def _read_hardware(self):
        """실제 하드웨어에서 UID 읽기"""
        try:
            if not self.connection or not self.connection.is_open:
                return None
                
            if self.connection.in_waiting > 0:
                raw_data = self.connection.readline()
                if raw_data:
                    # 바이트를 문자열로 변환하고 정리
                    uid_str = raw_data.decode('utf-8', errors='ignore').strip()
                    # 특수문자 제거하고 대문자로 변환
                    uid_str = re.sub(r'[^\w]', '', uid_str).upper()
                    return uid_str if uid_str else None
        except Exception as e:
            print(f"[RFID] 하드웨어 읽기 오류: {e}")
        
        return None
    
    def _validate_uid(self, uid):
        """UID 유효성 검증"""
        if not uid or len(uid) < 3:
            return False
        
        # 기본 패턴들: 16진수, K+숫자, 숫자만
        patterns = [
            r'^[A-F0-9]{6,12}$',  # 16진수 6-12자리
            r'^K[0-9]{3,4}$',     # K001, K0001 형식
            r'^[0-9]{6,12}$'      # 숫자 6-12자리
        ]
        
        for pattern in patterns:
            if re.match(pattern, uid):
                return True
        
        return False
    
    def close(self):
        """연결 종료"""
        if self.connection:
            self.connection.close()
            print("[RFID] 연결 종료")

# 전역 리더 인스턴스
_rfid_reader = None

def get_rfid_reader():
    """전역 RFID 리더 인스턴스 반환"""
    global _rfid_reader
    if _rfid_reader is None:
        _rfid_reader = SimpleRFIDReader()
        _rfid_reader.connect()
    return _rfid_reader

# 기존 호환성 유지를 위한 함수들
def read_uid():
    """UID 읽기 (메인 인터페이스)"""
    reader = get_rfid_reader()
    return reader.read_uid()

def read_uid_simulation():
    """시뮬레이션 UID 읽기 (기존 호환성)"""
    reader = get_rfid_reader()
    if SIMULATION_MODE:
        return reader._read_simulation()
    return None