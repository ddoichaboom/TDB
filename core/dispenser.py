# core/dispenser.py (GPIO 설정 및 약 배출 로직 개선)
import time
import RPi.GPIO as GPIO
from utils.logger import log_info, log_error

# 릴레이 핀 번호 정의 (슬롯별 서보모터 제어)
RELAY_PINS = {
    1: (17, 18),  # slot1: forward, backward
    2: (22, 23),  # slot2
    3: (24, 25),  # slot3
}

# GPIO 초기화
def init_gpio():
    """GPIO 초기화"""
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        for pin_pair in RELAY_PINS.values():
            for pin in pin_pair:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)
        
        log_info("GPIO 초기화 완료")
    except Exception as e:
        log_error(f"GPIO 초기화 실패: {e}")

def trigger_slot_dispense(slot_num, dose=1):
    """특정 슬롯에서 약 배출"""
    if slot_num not in RELAY_PINS:
        raise ValueError(f"잘못된 슬롯 번호: {slot_num}")
    
    try:
        init_gpio()  # GPIO 초기화 확인
        
        forward_pin, backward_pin = RELAY_PINS[slot_num]
        
        log_info(f"슬롯 {slot_num}에서 {dose}개 약 배출 시작")
        
        for i in range(dose):
            # Step 1: 약 진입 (forward)
            GPIO.output(forward_pin, GPIO.HIGH)
            time.sleep(0.8)  # 약 진입 시간
            GPIO.output(forward_pin, GPIO.LOW)
            
            # 잠시 대기
            time.sleep(0.3)
            
            # Step 2: 약 배출 (backward)  
            GPIO.output(backward_pin, GPIO.HIGH)
            time.sleep(0.8)  # 약 배출 시간
            GPIO.output(backward_pin, GPIO.LOW)
            
            # 다음 약 배출 전 대기
            if i < dose - 1:
                time.sleep(0.5)
                
        log_info(f"슬롯 {slot_num} 약 배출 완료")
        
    except Exception as e:
        log_error(f"슬롯 {slot_num} 배출 실패: {e}")
        raise

def cleanup_gpio():
    """GPIO 정리"""
    try:
        GPIO.cleanup()
        log_info("GPIO 정리 완료")
    except Exception as e:
        log_error(f"GPIO 정리 실패: {e}")

# utils/qr_display.py (개선된 QR 코드 표시)
import qrcode
import tkinter as tk
from PIL import Image, ImageTk
import json
import threading
import time

def show_qr_code(data: dict):
    """QR 코드를 화면에 표시"""
    try:
        # QR 코드 생성
        qr_data = json.dumps(data, ensure_ascii=False)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        img.save("assets/qr_temp.png")
        
        # Tkinter 창 생성
        window = tk.Tk()
        window.title("🏥 스마트 약 디스펜서 등록")
        window.geometry("500x600")
        window.configure(bg='#f0f0f0')
        
        # 상단 제목
        title_label = tk.Label(
            window, 
            text="📱 기기 등록", 
            font=("Arial", 20, "bold"),
            bg='#f0f0f0',
            fg='#2c3e50'
        )
        title_label.pack(pady=20)
        
        # 설명 텍스트
        desc_label = tk.Label(
            window,
            text="스마트폰 앱으로 아래 QR 코드를 스캔해주세요",
            font=("Arial", 12),
            bg='#f0f0f0',
            fg='#7f8c8d'
        )
        desc_label.pack(pady=10)
        
        # QR 코드 이미지
        img = img.resize((300, 300))
        tk_img = ImageTk.PhotoImage(img)
        
        qr_label = tk.Label(window, image=tk_img, bg='#f0f0f0')
        qr_label.pack(pady=20)
        
        # 기기 정보
        info_text = f"기기 ID: {data.get('m_uid', 'N/A')}\n생성 시간: {data.get('createdAt', 'N/A')}"
        info_label = tk.Label(
            window,
            text=info_text,
            font=("Arial", 10),
            bg='#f0f0f0',
            fg='#95a5a6'
        )
        info_label.pack(pady=10)
        
        # 대기 메시지
        wait_label = tk.Label(
            window,
            text="⏳ 등록 완료를 기다리는 중...",
            font=("Arial", 12, "italic"),
            bg='#f0f0f0',
            fg='#e74c3c'
        )
        wait_label.pack(pady=20)
        
        # 점멸 효과
        def blink_wait_label():
            current_color = wait_label.cget("fg")
            new_color = "#e74c3c" if current_color == "#c0392b" else "#c0392b"
            wait_label.config(fg=new_color)
            window.after(1000, blink_wait_label)
        
        blink_wait_label()
        
        # 창이 닫힐 때까지 유지
        window.mainloop()
        
    except Exception as e:
        print(f"[ERROR] QR 코드 표시 실패: {e}")
