# core/dispenser.py (핵심 약 배출 기능에 집중)
import time
from config import SIMULATION_MODE, HARDWARE_CONFIG

# GPIO 라이브러리 안전 임포트
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    print("[WARNING] RPi.GPIO 모듈이 없습니다. 시뮬레이션 모드에서만 동작합니다.")
    GPIO_AVAILABLE = False
    # 시뮬레이션용 더미 GPIO 클래스
    class DummyGPIO:
        BCM = 'BCM'
        OUT = 'OUT'
        HIGH = True
        LOW = False
        
        @staticmethod
        def setmode(mode): pass
        @staticmethod
        def setwarnings(flag): pass
        @staticmethod
        def setup(pin, mode): pass
        @staticmethod
        def output(pin, state): pass
        @staticmethod
        def cleanup(): pass
    
    GPIO = DummyGPIO()

class MedicineDispenser:
    """약 배출 하드웨어 제어 클래스"""
    
    def __init__(self):
        self.gpio_initialized = False
        self.simulation_mode = SIMULATION_MODE or not GPIO_AVAILABLE
        
        # 슬롯별 릴레이 핀 매핑 (config에서 가져오기)
        self.relay_pins = HARDWARE_CONFIG.get('relay_pins', {
            1: {'forward': 17, 'backward': 18},
            2: {'forward': 22, 'backward': 23}, 
            3: {'forward': 24, 'backward': 25}
        })
        
        # 배출 타이밍 설정
        self.pulse_duration = HARDWARE_CONFIG.get('servo_pulse_duration', 1.0)
        self.slot_delay = HARDWARE_CONFIG.get('slot_delay', 0.5)
        
        print(f"[DISPENSER] 초기화 완료 - 시뮬레이션 모드: {self.simulation_mode}")
        if self.simulation_mode:
            print(f"[DISPENSER] 설정된 슬롯: {list(self.relay_pins.keys())}")
    
    def initialize_gpio(self):
        """GPIO 초기화"""
        if self.simulation_mode:
            print("[DISPENSER] 시뮬레이션 모드 - GPIO 초기화 생략")
            self.gpio_initialized = True
            return True
        
        try:
            # GPIO 모드 설정
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            # 모든 릴레이 핀 초기화
            for slot, pins in self.relay_pins.items():
                forward_pin = pins['forward']
                backward_pin = pins['backward']
                
                GPIO.setup(forward_pin, GPIO.OUT)
                GPIO.setup(backward_pin, GPIO.OUT)
                
                # 초기 상태: 모든 릴레이 OFF
                GPIO.output(forward_pin, GPIO.LOW)
                GPIO.output(backward_pin, GPIO.LOW)
                
                print(f"[DISPENSER] 슬롯 {slot} 핀 초기화: {forward_pin}(전진), {backward_pin}(후진)")
            
            self.gpio_initialized = True
            print("[DISPENSER] GPIO 초기화 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] GPIO 초기화 실패: {e}")
            self.gpio_initialized = False
            return False
    
    def dispense_medicine(self, slot_num, dose=1):
        """약 배출 실행
        
        Args:
            slot_num (int): 슬롯 번호 (1, 2, 3...)
            dose (int): 배출할 알약 개수
            
        Returns:
            bool: 배출 성공 여부
        """
        if not self.gpio_initialized:
            print("[ERROR] GPIO가 초기화되지 않았습니다")
            return False
        
        if slot_num not in self.relay_pins:
            print(f"[ERROR] 잘못된 슬롯 번호: {slot_num}")
            return False
        
        if dose <= 0:
            print(f"[ERROR] 잘못된 배출 개수: {dose}")
            return False
        
        print(f"[DISPENSE] 슬롯 {slot_num}에서 {dose}개 약 배출 시작")
        
        try:
            if self.simulation_mode:
                return self._simulate_dispense(slot_num, dose)
            else:
                return self._hardware_dispense(slot_num, dose)
                
        except Exception as e:
            print(f"[ERROR] 슬롯 {slot_num} 배출 중 오류: {e}")
            return False
    
    def _simulate_dispense(self, slot_num, dose):
        """시뮬레이션 모드 배출"""
        pins = self.relay_pins[slot_num]
        
        for i in range(dose):
            print(f"[SIMULATION] 슬롯 {slot_num} - {i+1}/{dose}개 배출 중...")
            print(f"[SIMULATION] 전진 릴레이 ON (핀 {pins['forward']})")
            time.sleep(self.pulse_duration)
            print(f"[SIMULATION] 전진 릴레이 OFF")
            
            time.sleep(self.slot_delay)
            
            print(f"[SIMULATION] 후진 릴레이 ON (핀 {pins['backward']})")
            time.sleep(self.pulse_duration)
            print(f"[SIMULATION] 후진 릴레이 OFF")
            
            if i < dose - 1:  # 마지막 배출이 아니면 대기
                time.sleep(self.slot_delay)
                
        print(f"[SIMULATION] 슬롯 {slot_num} 배출 완료")
        return True
    
    def _hardware_dispense(self, slot_num, dose):
        """실제 하드웨어 배출"""
        pins = self.relay_pins[slot_num]
        forward_pin = pins['forward']
        backward_pin = pins['backward']
        
        try:
            for i in range(dose):
                print(f"[HARDWARE] 슬롯 {slot_num} - {i+1}/{dose}개 배출 중...")
                
                # 1단계: 전진 동작 (약 진입)
                GPIO.output(forward_pin, GPIO.HIGH)
                time.sleep(self.pulse_duration)
                GPIO.output(forward_pin, GPIO.LOW)
                
                # 중간 대기
                time.sleep(self.slot_delay)
                
                # 2단계: 후진 동작 (약 배출)
                GPIO.output(backward_pin, GPIO.HIGH)
                time.sleep(self.pulse_duration)
                GPIO.output(backward_pin, GPIO.LOW)
                
                # 다음 배출 전 대기 (마지막 제외)
                if i < dose - 1:
                    time.sleep(self.slot_delay)
                    
            print(f"[HARDWARE] 슬롯 {slot_num} 배출 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] 하드웨어 배출 실패: {e}")
            # 에러 발생시 모든 릴레이 OFF
            try:
                GPIO.output(forward_pin, GPIO.LOW)
                GPIO.output(backward_pin, GPIO.LOW)
            except:
                pass
            return False
    
    def emergency_stop(self):
        """비상 정지 - 모든 릴레이 즉시 OFF"""
        if self.simulation_mode:
            print("[SIMULATION] 비상 정지 - 모든 동작 중단")
            return
        
        if not self.gpio_initialized:
            return
        
        try:
            print("[EMERGENCY] 비상 정지 실행")
            for slot, pins in self.relay_pins.items():
                GPIO.output(pins['forward'], GPIO.LOW)
                GPIO.output(pins['backward'], GPIO.LOW)
            print("[EMERGENCY] 모든 릴레이 OFF 완료")
        except Exception as e:
            print(f"[ERROR] 비상 정지 실패: {e}")
    
    def test_slot(self, slot_num):
        """특정 슬롯 테스트 (1개 배출)"""
        print(f"[TEST] 슬롯 {slot_num} 테스트 시작")
        success = self.dispense_medicine(slot_num, 1)
        
        if success:
            print(f"[TEST] ✅ 슬롯 {slot_num} 테스트 성공")
        else:
            print(f"[TEST] ❌ 슬롯 {slot_num} 테스트 실패")
        
        return success
    
    def test_all_slots(self):
        """모든 슬롯 테스트"""
        print("[TEST] 전체 슬롯 테스트 시작")
        results = {}
        
        for slot_num in self.relay_pins.keys():
            results[slot_num] = self.test_slot(slot_num)
            time.sleep(2)  # 슬롯 간 대기시간
        
        # 결과 요약
        success_count = sum(results.values())
        total_count = len(results)
        
        print(f"\n[TEST] 테스트 완료: {success_count}/{total_count} 성공")
        for slot, success in results.items():
            status = "✅" if success else "❌"
            print(f"  슬롯 {slot}: {status}")
        
        return results
    
    def cleanup(self):
        """GPIO 정리"""
        if self.simulation_mode:
            print("[DISPENSER] 시뮬레이션 모드 - 정리 완료")
            return
        
        if self.gpio_initialized:
            try:
                # 모든 릴레이 OFF
                for slot, pins in self.relay_pins.items():
                    GPIO.output(pins['forward'], GPIO.LOW)
                    GPIO.output(pins['backward'], GPIO.LOW)
                
                # GPIO 정리
                GPIO.cleanup()
                self.gpio_initialized = False
                print("[DISPENSER] GPIO 정리 완료")
                
            except Exception as e:
                print(f"[ERROR] GPIO 정리 실패: {e}")

# 전역 디스펜서 인스턴스
_dispenser = None

def get_dispenser():
    """전역 디스펜서 인스턴스 반환"""
    global _dispenser
    if _dispenser is None:
        _dispenser = MedicineDispenser()
    return _dispenser

# main.py에서 사용할 인터페이스 함수들
def init_gpio():
    """GPIO 초기화 (main.py 인터페이스)"""
    dispenser = get_dispenser()
    return dispenser.initialize_gpio()

def trigger_slot_dispense(slot_num, dose=1):
    """약 배출 실행 (main.py 인터페이스)"""
    dispenser = get_dispenser()
    return dispenser.dispense_medicine(slot_num, dose)

def cleanup_gpio():
    """GPIO 정리 (main.py 인터페이스)"""
    dispenser = get_dispenser()
    dispenser.cleanup()

def emergency_stop():
    """비상 정지 (main.py 인터페이스)"""
    dispenser = get_dispenser()
    dispenser.emergency_stop()

def test_hardware():
    """하드웨어 테스트 (main.py 인터페이스)"""
    dispenser = get_dispenser()
    if not dispenser.gpio_initialized:
        print("[TEST] GPIO 초기화 먼저 실행...")
        if not dispenser.initialize_gpio():
            return False
    
    return dispenser.test_all_slots()

# 직접 실행시 테스트 모드
if __name__ == "__main__":
    print("=== 약 배출 시스템 테스트 ===")
    
    dispenser = MedicineDispenser()
    
    try:
        # 초기화
        if dispenser.initialize_gpio():
            print("\n사용 가능한 명령:")
            print("  test [슬롯번호] - 특정 슬롯 테스트")
            print("  testall - 모든 슬롯 테스트")
            print("  dispense [슬롯번호] [개수] - 약 배출")
            print("  quit - 종료")
            
            while True:
                try:
                    cmd = input("\n명령 입력: ").strip().split()
                    
                    if not cmd:
                        continue
                    
                    if cmd[0].lower() == 'quit':
                        break
                    elif cmd[0].lower() == 'testall':
                        dispenser.test_all_slots()
                    elif cmd[0].lower() == 'test' and len(cmd) > 1:
                        slot = int(cmd[1])
                        dispenser.test_slot(slot)
                    elif cmd[0].lower() == 'dispense' and len(cmd) > 2:
                        slot = int(cmd[1])
                        dose = int(cmd[2])
                        dispenser.dispense_medicine(slot, dose)
                    else:
                        print("잘못된 명령입니다.")
                        
                except ValueError:
                    print("숫자를 올바르게 입력해주세요.")
                except KeyboardInterrupt:
                    print("\n종료 중...")
                    break
                except Exception as e:
                    print(f"오류: {e}")
        
    finally:
        dispenser.cleanup()
        print("테스트 완료")