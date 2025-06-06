#!/usr/bin/env python3
# simple_test_gui.py - 간단한 GUI 테스트

import tkinter as tk
from tkinter import ttk
import datetime
import threading
import time

class SimpleDispenserGUI:
    """간단한 디스펜서 GUI 테스트"""
    
    def __init__(self, device_id="17FD8197"):
        self.device_id = device_id
        self.window = None
        self.running = True
        
    def create_window(self):
        """윈도우 생성"""
        self.window = tk.Tk()
        self.window.title("Smart Medicine Dispenser - 테스트")
        self.window.geometry("800x600+100+100")
        self.window.configure(bg='#f0f0f0')
        
        # 메인 프레임
        main_frame = tk.Frame(self.window, bg='#f0f0f0')
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 제목
        title_label = tk.Label(
            main_frame,
            text="🏥 Smart Medicine Dispenser",
            font=("Arial", 24, "bold"),
            bg='#f0f0f0',
            fg='#2563eb'
        )
        title_label.pack(pady=(0, 20))
        
        # 디바이스 ID
        device_label = tk.Label(
            main_frame,
            text=f"Device ID: {self.device_id}",
            font=("Arial", 14),
            bg='#f0f0f0',
            fg='#64748b'
        )
        device_label.pack(pady=(0, 10))
        
        # 시간 표시
        self.time_label = tk.Label(
            main_frame,
            text="",
            font=("Arial", 18),
            bg='#f0f0f0',
            fg='#1e293b'
        )
        self.time_label.pack(pady=(0, 20))
        
        # 상태 표시
        status_frame = tk.Frame(main_frame, bg='#ffffff', relief='raised', bd=2)
        status_frame.pack(fill="x", pady=(0, 20))
        
        status_title = tk.Label(
            status_frame,
            text="시스템 상태",
            font=("Arial", 16, "bold"),
            bg='#ffffff',
            fg='#1e293b'
        )
        status_title.pack(pady=10)
        
        # 상태 정보들
        self.status_labels = {}
        
        status_items = [
            ("시뮬레이션 모드", "✅ 활성화"),
            ("RFID 리더", "✅ 준비됨"),
            ("GUI 환경", "✅ 정상"),
            ("서버 연결", "🔄 확인 중..."),
        ]
        
        for item, status in status_items:
            item_frame = tk.Frame(status_frame, bg='#ffffff')
            item_frame.pack(fill="x", padx=20, pady=5)
            
            item_label = tk.Label(
                item_frame,
                text=item + ":",
                font=("Arial", 12),
                bg='#ffffff',
                fg='#64748b'
            )
            item_label.pack(side="left")
            
            status_label = tk.Label(
                item_frame,
                text=status,
                font=("Arial", 12, "bold"),
                bg='#ffffff',
                fg='#16a34a'
            )
            status_label.pack(side="right")
            
            self.status_labels[item] = status_label
        
        # 사용법 안내
        usage_frame = tk.Frame(main_frame, bg='#fef3c7', relief='raised', bd=2)
        usage_frame.pack(fill="x", pady=(0, 20))
        
        usage_title = tk.Label(
            usage_frame,
            text="📋 사용법",
            font=("Arial", 14, "bold"),
            bg='#fef3c7',
            fg='#92400e'
        )
        usage_title.pack(pady=(10, 5))
        
        usage_text = tk.Label(
            usage_frame,
            text="1. RFID 카드를 스캔하세요\n2. 콘솔에서 UID를 입력하세요 (시뮬레이션 모드)\n3. 약이 자동으로 배출됩니다",
            font=("Arial", 11),
            bg='#fef3c7',
            fg='#92400e',
            justify="left"
        )
        usage_text.pack(pady=(0, 10))
        
        # 로그 출력 영역
        log_frame = tk.Frame(main_frame, bg='#ffffff', relief='raised', bd=2)
        log_frame.pack(fill="both", expand=True)
        
        log_title = tk.Label(
            log_frame,
            text="📄 시스템 로그",
            font=("Arial", 14, "bold"),
            bg='#ffffff',
            fg='#1e293b'
        )
        log_title.pack(pady=(10, 5))
        
        # 스크롤 가능한 텍스트 영역
        log_scroll_frame = tk.Frame(log_frame, bg='#ffffff')
        log_scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.log_text = tk.Text(
            log_scroll_frame,
            height=8,
            font=("Courier", 10),
            bg='#1e293b',
            fg='#f8fafc',
            wrap=tk.WORD
        )
        
        scrollbar = tk.Scrollbar(log_scroll_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 하단 버튼들
        button_frame = tk.Frame(main_frame, bg='#f0f0f0')
        button_frame.pack(fill="x", pady=(20, 0))
        
        test_button = tk.Button(
            button_frame,
            text="🧪 GUI 테스트",
            font=("Arial", 12, "bold"),
            bg='#2563eb',
            fg='white',
            command=self.test_gui_functions,
            relief='raised',
            bd=2
        )
        test_button.pack(side="left", padx=(0, 10))
        
        close_button = tk.Button(
            button_frame,
            text="❌ 닫기",
            font=("Arial", 12, "bold"),
            bg='#dc2626',
            fg='white',
            command=self.close_window,
            relief='raised',
            bd=2
        )
        close_button.pack(side="right")
        
        # 윈도우 이벤트
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)
        
        # 주기적 업데이트 시작
        self.start_updates()
        
        # 초기 로그 메시지
        self.add_log("시스템 시작됨")
        self.add_log("GUI 초기화 완료")
        self.add_log("RFID 리더 대기 중...")
        
        print("✅ GUI 윈도우 생성 완료")
    
    def add_log(self, message):
        """로그 메시지 추가"""
        try:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}\n"
            
            self.log_text.insert(tk.END, log_entry)
            self.log_text.see(tk.END)  # 자동 스크롤
            
            # 로그가 너무 많으면 오래된 것 삭제
            lines = self.log_text.get(1.0, tk.END).split('\n')
            if len(lines) > 100:
                # 처음 20줄 삭제
                self.log_text.delete(1.0, f"{21}.0")
                
        except Exception as e:
            print(f"로그 추가 오류: {e}")
    
    def update_time(self):
        """시간 업데이트"""
        try:
            now = datetime.datetime.now()
            time_str = now.strftime("%Y년 %m월 %d일 %H:%M:%S")
            self.time_label.config(text=time_str)
        except Exception as e:
            print(f"시간 업데이트 오류: {e}")
    
    def start_updates(self):
        """주기적 업데이트 시작"""
        def update_loop():
            while self.running:
                try:
                    if self.window and self.window.winfo_exists():
                        self.window.after(0, self.update_time)
                    else:
                        break
                except:
                    break
                
                time.sleep(1)
        
        update_thread = threading.Thread(target=update_loop, daemon=True)
        update_thread.start()
    
    def test_gui_functions(self):
        """GUI 기능 테스트"""
        self.add_log("GUI 기능 테스트 시작")
        
        # 상태 업데이트 테스트
        self.status_labels["서버 연결"].config(text="✅ 연결됨", fg='#16a34a')
        self.add_log("서버 연결 상태 업데이트")
        
        # 시뮬레이션 RFID 스캔
        test_uid = "K005"
        self.add_log(f"RFID 스캔 시뮬레이션: {test_uid}")
        self.add_log("사용자 인증 중...")
        
        # 지연 후 결과 표시
        def delayed_result():
            time.sleep(2)
            self.window.after(0, lambda: self.add_log("✅ 인증 성공: 차호준"))
            self.window.after(0, lambda: self.add_log("약 배출 시뮬레이션 완료"))
            self.window.after(0, lambda: self.add_log("GUI 테스트 완료"))
        
        threading.Thread(target=delayed_result, daemon=True).start()
    
    def close_window(self):
        """윈도우 닫기"""
        try:
            self.running = False
            print("GUI 윈도우 닫는 중...")
            self.add_log("시스템 종료 중...")
            
            if self.window:
                self.window.after(1000, self.window.destroy)
        except Exception as e:
            print(f"윈도우 닫기 오류: {e}")
    
    def run(self):
        """GUI 실행"""
        try:
            self.create_window()
            print("GUI 윈도우가 표시되었습니다.")
            print("모니터를 확인하세요!")
            
            self.window.mainloop()
            
        except Exception as e:
            print(f"GUI 실행 오류: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return True

def main():
    """메인 함수"""
    print("🧪 간단한 GUI 테스트 시작")
    print("="*40)
    
    try:
        gui = SimpleDispenserGUI()
        success = gui.run()
        
        if success:
            print("✅ GUI 테스트 완료")
        else:
            print("❌ GUI 테스트 실패")
        
        return success
        
    except KeyboardInterrupt:
        print("\n⚠️ 사용자가 중단했습니다")
        return False
    except Exception as e:
        print(f"❌ 테스트 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)