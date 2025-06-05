# dispenser_gui.py (라즈베리파이 환경 최적화 - 키보드/마우스 없는 환경)
import tkinter as tk
from tkinter import ttk, Canvas
import datetime
import threading
import time
import queue
import platform
import subprocess
import os
from concurrent.futures import ThreadPoolExecutor
from utils.server_request import get_machine_status, get_connected_users, get_today_schedules
from utils.voice_feedback import VoiceFeedbackManager
from utils.system_monitor import SystemMonitor
from config import GUI_CONFIG, RASPBERRY_PI_CONFIG, VOICE_CONFIG, MONITORING_CONFIG

class RaspberryPiDispenserGUI:
    """라즈베리파이 환경에 최적화된 스마트 약 디스펜서 GUI"""
    
    def __init__(self, muid: str):
        self.muid = muid
        self.window = None
        self.tile_frames = {}
        self.update_running = False
        self.data_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=GUI_CONFIG['max_workers'])
        
        # 라즈베리파이 특화 컴포넌트들
        self.voice_manager = VoiceFeedbackManager() if VOICE_CONFIG['enabled'] else None
        self.system_monitor = SystemMonitor()
        self.auto_transition_timer = None
        
        # 데이터 캐시 및 상태 관리
        self.cached_data = {
            'users': None,
            'machine_status': None,
            'schedules': None,
            'last_update': None,
            'update_count': 0
        }
        
        self.connection_state = {
            'status': 'connecting',
            'last_success': None,
            'retry_count': 0,
            'error_message': None,
            'network_available': True
        }
        
        self.system_stats = {
            'total_dispenses_today': 0,
            'last_dispense_time': None,
            'system_uptime': datetime.datetime.now(),
            'alerts_count': 0,
            'network_latency': 0,
            'cpu_temp': 0,
            'memory_usage': 0,
            'last_rfid_scan': None
        }
        
        # UI 요소 참조
        self.ui_elements = {}
        self.current_screen = "main"  # main, status, maintenance
        self.screen_transition_lock = threading.Lock()
        
        # 자동 화면 관리
        self.last_user_activity = time.time()
        self.screen_timeout = GUI_CONFIG.get('auto_transition_time', 10000) // 1000
        
    def create_main_window(self):
        """메인 윈도우 생성 (라즈베리파이 최적화)"""
        self.window = tk.Tk()
        self.window.title("Smart Tablet Dispenser")
        
        # 라즈베리파이 디스플레이 설정
        self.setup_raspberry_pi_display()
        
        # 윈도우 이벤트 바인딩
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.window.bind('<Configure>', self.on_window_configure)
        
        # 메인 컨테이너 설정
        self.setup_main_layout()
        
        # 시스템 초기화
        self.initialize_system()
        
        # 환영 메시지
        if self.voice_manager:
            self.voice_manager.speak_async("smart_dispenser_ready")

    def setup_raspberry_pi_display(self):
        """라즈베리파이 디스플레이 설정"""
        try:
            # 전체화면 설정
            if RASPBERRY_PI_CONFIG['fullscreen']:
                self.window.attributes('-fullscreen', True)
            
            # 커서 숨김
            if RASPBERRY_PI_CONFIG['hide_cursor']:
                self.window.config(cursor="none")
            
            # 항상 최상위
            self.window.attributes('-topmost', True)
            
            # 배경색 설정
            self.window.configure(bg=GUI_CONFIG['colors']['background'])
            
            # 화면 크기 설정
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()
            
            if not RASPBERRY_PI_CONFIG['fullscreen']:
                self.window.geometry(f"{screen_width}x{screen_height}+0+0")
            
            print(f"[INFO] 디스플레이 설정 완료: {screen_width}x{screen_height}")
            
        except Exception as e:
            print(f"[ERROR] 디스플레이 설정 실패: {e}")
            # 기본 설정으로 폴백
            self.window.geometry("1024x768+0+0")

    def setup_main_layout(self):
        """메인 레이아웃 설정"""
        # 메인 컨테이너
        self.main_container = tk.Frame(
            self.window, 
            bg=GUI_CONFIG['colors']['background']
        )
        self.main_container.pack(fill="both", expand=True)
        
        # 상단 상태바
        self.create_status_bar()
        
        # 메인 콘텐츠 영역
        self.content_frame = tk.Frame(
            self.main_container,
            bg=GUI_CONFIG['colors']['background']
        )
        self.content_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # 하단 정보바
        self.create_info_bar()
        
        # 초기 메인 화면 생성
        self.create_main_screen()

    def create_status_bar(self):
        """상단 상태바 생성"""
        status_bar = tk.Frame(
            self.main_container,
            bg=GUI_CONFIG['colors']['primary'],
            height=60
        )
        status_bar.pack(fill="x")
        status_bar.pack_propagate(False)
        
        # 좌측: 시스템 상태
        left_frame = tk.Frame(status_bar, bg=GUI_CONFIG['colors']['primary'])
        left_frame.pack(side="left", fill="y", padx=20)
        
        self.ui_elements['connection_indicator'] = tk.Label(
            left_frame,
            text="●",
            font=("DejaVu Sans", 20),
            bg=GUI_CONFIG['colors']['primary'],
            fg=GUI_CONFIG['colors']['warning']
        )
        self.ui_elements['connection_indicator'].pack(side="top", pady=5)
        
        self.ui_elements['connection_text'] = tk.Label(
            left_frame,
            text="연결 확인 중...",
            font=("DejaVu Sans", 10),
            bg=GUI_CONFIG['colors']['primary'],
            fg="white"
        )
        self.ui_elements['connection_text'].pack(side="top")
        
        # 중앙: 제목 및 시간
        center_frame = tk.Frame(status_bar, bg=GUI_CONFIG['colors']['primary'])
        center_frame.pack(expand=True, fill="both")
        
        title_label = tk.Label(
            center_frame,
            text="🏥 Smart Tablet Dispenser",
            font=("DejaVu Sans", 18, "bold"),
            bg=GUI_CONFIG['colors']['primary'],
            fg="white"
        )
        title_label.pack(expand=True)
        
        # 우측: 시간 및 기기 정보
        right_frame = tk.Frame(status_bar, bg=GUI_CONFIG['colors']['primary'])
        right_frame.pack(side="right", fill="y", padx=20)
        
        self.ui_elements['current_time'] = tk.Label(
            right_frame,
            text="",
            font=("DejaVu Sans", 14, "bold"),
            bg=GUI_CONFIG['colors']['primary'],
            fg="white"
        )
        self.ui_elements['current_time'].pack(side="top", pady=2)
        
        device_label = tk.Label(
            right_frame,
            text=f"Device: {self.muid}",
            font=("DejaVu Sans", 9),
            bg=GUI_CONFIG['colors']['primary'],
            fg="white"
        )
        device_label.pack(side="top")

    def create_info_bar(self):
        """하단 정보바 생성"""
        info_bar = tk.Frame(
            self.main_container,
            bg=GUI_CONFIG['colors']['text_primary'],
            height=40
        )
        info_bar.pack(fill="x", side="bottom")
        info_bar.pack_propagate(False)
        
        # 좌측: 마지막 업데이트
        self.ui_elements['last_update'] = tk.Label(
            info_bar,
            text="시스템 시작 중...",
            font=("DejaVu Sans", 10),
            bg=GUI_CONFIG['colors']['text_primary'],
            fg=GUI_CONFIG['colors']['text_muted']
        )
        self.ui_elements['last_update'].pack(side="left", padx=15, pady=8)
        
        # 우측: 시스템 정보
        system_info_frame = tk.Frame(info_bar, bg=GUI_CONFIG['colors']['text_primary'])
        system_info_frame.pack(side="right", padx=15, pady=8)
        
        self.ui_elements['cpu_temp'] = tk.Label(
            system_info_frame,
            text="CPU: --°C",
            font=("DejaVu Sans", 9),
            bg=GUI_CONFIG['colors']['text_primary'],
            fg=GUI_CONFIG['colors']['text_muted']
        )
        self.ui_elements['cpu_temp'].pack(side="right", padx=5)
        
        self.ui_elements['memory_usage'] = tk.Label(
            system_info_frame,
            text="RAM: --%",
            font=("DejaVu Sans", 9),
            bg=GUI_CONFIG['colors']['text_primary'],
            fg=GUI_CONFIG['colors']['text_muted']
        )
        self.ui_elements['memory_usage'].pack(side="right", padx=5)

    def create_main_screen(self):
        """메인 화면 생성"""
        # 기존 콘텐츠 지우기
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        self.current_screen = "main"
        
        # 메인 화면 컨테이너
        main_screen = tk.Frame(
            self.content_frame,
            bg=GUI_CONFIG['colors']['background']
        )
        main_screen.pack(fill="both", expand=True)
        
        # 2x2 그리드 레이아웃
        for i in range(2):
            main_screen.rowconfigure(i, weight=1)
            main_screen.columnconfigure(i, weight=1)
        
        # 타일 생성
        self.create_dashboard_tiles(main_screen)

    def create_dashboard_tiles(self, parent):
        """대시보드 타일들 생성"""
        tile_configs = [
            {
                "key": "users",
                "title": "👥 등록된 사용자",
                "color": GUI_CONFIG['colors']['primary'],
                "row": 0, "col": 0
            },
            {
                "key": "medicine", 
                "title": "💊 약품 현황",
                "color": GUI_CONFIG['colors']['success'],
                "row": 0, "col": 1
            },
            {
                "key": "schedule",
                "title": "📅 오늘의 스케줄", 
                "color": GUI_CONFIG['colors']['warning'],
                "row": 1, "col": 0
            },
            {
                "key": "system",
                "title": "⚙️ 시스템 상태",
                "color": GUI_CONFIG['colors']['danger'],
                "row": 1, "col": 1
            }
        ]
        
        self.tile_frames = {}
        
        for config in tile_configs:
            self.tile_frames[config["key"]] = self.create_enhanced_tile(
                parent,
                config["title"],
                config["color"], 
                config["row"],
                config["col"]
            )
        
        # 타일 내용 초기화
        self.initialize_tiles()

    def create_enhanced_tile(self, parent, title, color, row, col):
        """향상된 타일 생성"""
        # 외부 컨테이너
        container = tk.Frame(parent, bg=GUI_CONFIG['colors']['background'])
        container.grid(row=row, column=col, sticky="nsew", padx=15, pady=15)
        
        # 메인 카드
        card = tk.Frame(
            container,
            bg=GUI_CONFIG['colors']['card_bg'],
            relief="raised",
            bd=2
        )
        card.pack(fill="both", expand=True)
        
        # 헤더
        header = tk.Frame(card, bg=color, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        title_label = tk.Label(
            header,
            text=title,
            font=("DejaVu Sans", GUI_CONFIG['fonts']['sizes']['header'], "bold"),
            bg=color,
            fg="white"
        )
        title_label.pack(expand=True)
        
        # 콘텐츠 영역
        content = tk.Frame(card, bg=GUI_CONFIG['colors']['card_bg'])
        content.pack(fill="both", expand=True, padx=15, pady=15)
        
        return content

    def initialize_tiles(self):
        """타일 초기화"""
        for key in self.tile_frames:
            self.show_loading_state(self.tile_frames[key])

    def show_loading_state(self, parent, message="데이터 로딩 중..."):
        """로딩 상태 표시"""
        for widget in parent.winfo_children():
            widget.destroy()
        
        loading_frame = tk.Frame(parent, bg=GUI_CONFIG['colors']['card_bg'])
        loading_frame.pack(expand=True, fill="both")
        
        # 로딩 스피너
        spinner_label = tk.Label(
            loading_frame,
            text="⟳",
            font=("DejaVu Sans", 48),
            bg=GUI_CONFIG['colors']['card_bg'],
            fg=GUI_CONFIG['colors']['primary']
        )
        spinner_label.pack(pady=(30, 15))
        
        message_label = tk.Label(
            loading_frame,
            text=message,
            font=("DejaVu Sans", GUI_CONFIG['fonts']['sizes']['body']),
            bg=GUI_CONFIG['colors']['card_bg'],
            fg=GUI_CONFIG['colors']['text_secondary']
        )
        message_label.pack()
        
        # 스피너 애니메이션
        self.animate_spinner(spinner_label)

    def animate_spinner(self, label):
        """스피너 애니메이션"""
        def rotate():
            try:
                if label.winfo_exists():
                    current = label.cget("text")
                    next_char = "⟲" if current == "⟳" else "⟳"
                    label.config(text=next_char)
                    self.window.after(500, rotate)
            except:
                pass
        rotate()

    def initialize_system(self):
        """시스템 초기화"""
        # 시스템 모니터링 시작
        if MONITORING_CONFIG['enabled']:
            self.system_monitor.start_monitoring()
        
        # 화면 세이버 비활성화
        if RASPBERRY_PI_CONFIG['disable_screensaver']:
            self.disable_screensaver()
        
        # 초기 데이터 로드
        self.start_initial_load()
        
        # 업데이트 시스템 시작
        self.start_updates()
        
        # 자동 화면 관리 시작
        self.start_screen_management()

    def disable_screensaver(self):
        """화면 보호기 비활성화"""
        try:
            subprocess.run(['xset', 's', 'off'], check=False)
            subprocess.run(['xset', '-dpms'], check=False)
            subprocess.run(['xset', 's', 'noblank'], check=False)
            print("[INFO] 화면 보호기 비활성화 완료")
        except Exception as e:
            print(f"[WARNING] 화면 보호기 설정 실패: {e}")

    def start_initial_load(self):
        """초기 데이터 로드"""
        self.executor.submit(self.load_all_data_async)

    def load_all_data_async(self):
        """모든 데이터 비동기 로드"""
        try:
            start_time = time.time()
            
            # 데이터 로드
            users_data = get_connected_users(self.muid)
            machine_data = get_machine_status(self.muid)
            schedule_data = get_today_schedules(self.muid)
            
            # 네트워크 지연 시간 계산
            self.system_stats['network_latency'] = int((time.time() - start_time) * 1000)
            
            # 캐시 업데이트
            self.cached_data.update({
                'users': users_data,
                'machine_status': machine_data,
                'schedules': schedule_data,
                'last_update': datetime.datetime.now(),
                'update_count': self.cached_data['update_count'] + 1
            })
            
            # 연결 상태 업데이트
            self.connection_state.update({
                'status': 'connected',
                'last_success': datetime.datetime.now(),
                'retry_count': 0,
                'error_message': None
            })
            
            # UI 업데이트 요청
            self.data_queue.put(('update_all', None))
            
        except Exception as e:
            print(f"[ERROR] 데이터 로드 실패: {e}")
            self.connection_state.update({
                'status': 'error',
                'retry_count': self.connection_state['retry_count'] + 1,
                'error_message': str(e)
            })
            self.data_queue.put(('update_error', str(e)))

    def start_updates(self):
        """업데이트 시스템 시작"""
        self.update_running = True
        
        def update_loop():
            while self.update_running:
                try:
                    # 큐 처리
                    try:
                        message, data = self.data_queue.get_nowait()
                        if self.window:
                            self.window.after(0, self.process_update_message, message, data)
                    except queue.Empty:
                        pass
                    
                    # 주기적 데이터 업데이트
                    if int(time.time()) % GUI_CONFIG['update_interval'] == 0:
                        self.executor.submit(self.load_all_data_async)
                    
                    # 시간 업데이트
                    if int(time.time()) % GUI_CONFIG['time_update_interval'] == 0:
                        if self.window:
                            self.window.after(0, self.update_time_display)
                    
                    # 시스템 상태 업데이트
                    if int(time.time()) % 30 == 0:  # 30초마다
                        self.update_system_status()
                        
                except Exception as e:
                    print(f"[ERROR] 업데이트 루프 오류: {e}")
                
                time.sleep(1)
        
        thread = threading.Thread(target=update_loop, daemon=True)
        thread.start()

    def start_screen_management(self):
        """자동 화면 관리 시작"""
        def screen_manager():
            while self.update_running:
                try:
                    current_time = time.time()
                    
                    # 비활성 시간 확인
                    inactive_time = current_time - self.last_user_activity
                    
                    # 10분 이상 비활성 시 절전 화면으로 전환
                    if inactive_time > 600 and self.current_screen != "screensaver":
                        self.window.after(0, self.show_screensaver)
                    
                    # 화면 전환 체크
                    self.check_auto_screen_transition()
                    
                except Exception as e:
                    print(f"[ERROR] 화면 관리 오류: {e}")
                
                time.sleep(10)  # 10초마다 체크
        
        thread = threading.Thread(target=screen_manager, daemon=True)
        thread.start()

    def process_update_message(self, message, data):
        """업데이트 메시지 처리"""
        try:
            if message == 'update_all':
                self.update_all_tiles()
                self.update_connection_status()
            elif message == 'update_error':
                self.handle_connection_error(data)
            elif message == 'rfid_detected':
                self.handle_rfid_activity(data)
            elif message == 'dispense_complete':
                self.handle_dispense_complete(data)
        except Exception as e:
            print(f"[ERROR] 메시지 처리 오류: {e}")

    def update_all_tiles(self):
        """모든 타일 업데이트"""
        try:
            if self.current_screen != "main":
                return
            
            # 사용자 타일
            users_data = self.cached_data.get('users')
            if users_data:
                self.update_users_tile(users_data)
            
            # 약품 타일
            machine_data = self.cached_data.get('machine_status')
            if machine_data:
                self.update_medicine_tile(machine_data)
            
            # 스케줄 타일
            schedule_data = self.cached_data.get('schedules')
            if schedule_data:
                self.update_schedule_tile(schedule_data)
            
            # 시스템 타일
            self.update_system_tile()
            
        except Exception as e:
            print(f"[ERROR] 타일 업데이트 오류: {e}")

    def update_users_tile(self, users_data):
        """사용자 타일 업데이트"""
        content = self.tile_frames["users"]
        
        # 기존 내용 지우기
        for widget in content.winfo_children():
            widget.destroy()
        
        if users_data and 'users' in users_data:
            users = users_data['users']
            
            if users:
                # 사용자 수 큰 글씨로 표시
                count_label = tk.Label(
                    content,
                    text=str(len(users)),
                    font=("DejaVu Sans", 72, "bold"),
                    bg=GUI_CONFIG['colors']['card_bg'],
                    fg=GUI_CONFIG['colors']['primary']
                )
                count_label.pack(pady=(20, 5))
                
                subtitle = tk.Label(
                    content,
                    text="명 등록됨",
                    font=("DejaVu Sans", GUI_CONFIG['fonts']['sizes']['body']),
                    bg=GUI_CONFIG['colors']['card_bg'],
                    fg=GUI_CONFIG['colors']['text_secondary']
                )
                subtitle.pack()
                
                # 최근 복용자 표시
                recent_users = [u for u in users if u.get('took_today')]
                if recent_users:
                    recent_label = tk.Label(
                        content,
                        text=f"오늘 {len(recent_users)}명 복용",
                        font=("DejaVu Sans", GUI_CONFIG['fonts']['sizes']['small']),
                        bg=GUI_CONFIG['colors']['card_bg'],
                        fg=GUI_CONFIG['colors']['success']
                    )
                    recent_label.pack(pady=(10, 0))
            else:
                self.show_empty_tile(content, "등록된 사용자 없음")

    def update_medicine_tile(self, machine_data):
        """약품 타일 업데이트"""
        content = self.tile_frames["medicine"]
        
        # 기존 내용 지우기
        for widget in content.winfo_children():
            widget.destroy()
        
        if machine_data and 'slots' in machine_data:
            slots = machine_data['slots']
            active_slots = [s for s in slots if s.get('name')]
            
            if active_slots:
                # 활성 슬롯 수
                count_label = tk.Label(
                    content,
                    text=str(len(active_slots)),
                    font=("DejaVu Sans", 72, "bold"),
                    bg=GUI_CONFIG['colors']['card_bg'],
                    fg=GUI_CONFIG['colors']['success']
                )
                count_label.pack(pady=(20, 5))
                
                subtitle = tk.Label(
                    content,
                    text="개 슬롯 활성",
                    font=("DejaVu Sans", GUI_CONFIG['fonts']['sizes']['body']),
                    bg=GUI_CONFIG['colors']['card_bg'],
                    fg=GUI_CONFIG['colors']['text_secondary']
                )
                subtitle.pack()
                
                # 부족한 약품 경고
                low_medicines = [s for s in active_slots if s.get('remain', 0) < 10]
                if low_medicines:
                    warning_label = tk.Label(
                        content,
                        text=f"⚠️ {len(low_medicines)}개 약품 부족",
                        font=("DejaVu Sans", GUI_CONFIG['fonts']['sizes']['small']),
                        bg=GUI_CONFIG['colors']['card_bg'],
                        fg=GUI_CONFIG['colors']['danger']
                    )
                    warning_label.pack(pady=(10, 0))
            else:
                self.show_empty_tile(content, "등록된 약품 없음")

    def update_schedule_tile(self, schedule_data):
        """스케줄 타일 업데이트"""
        content = self.tile_frames["schedule"]
        
        # 기존 내용 지우기
        for widget in content.winfo_children():
            widget.destroy()
        
        if schedule_data and 'schedules' in schedule_data:
            schedules = schedule_data['schedules']
            
            # 총 스케줄 수 계산
            total_schedules = sum(len(schedules.get(time_slot, [])) 
                                for time_slot in ['morning', 'afternoon', 'evening'])
            
            if total_schedules > 0:
                count_label = tk.Label(
                    content,
                    text=str(total_schedules),
                    font=("DejaVu Sans", 72, "bold"),
                    bg=GUI_CONFIG['colors']['card_bg'],
                    fg=GUI_CONFIG['colors']['warning']
                )
                count_label.pack(pady=(20, 5))
                
                subtitle = tk.Label(
                    content,
                    text="개 일정",
                    font=("DejaVu Sans", GUI_CONFIG['fonts']['sizes']['body']),
                    bg=GUI_CONFIG['colors']['card_bg'],
                    fg=GUI_CONFIG['colors']['text_secondary']
                )
                subtitle.pack()
                
                # 다음 스케줄 시간 표시
                next_schedule = self.get_next_schedule_time(schedules)
                if next_schedule:
                    next_label = tk.Label(
                        content,
                        text=f"다음: {next_schedule}",
                        font=("DejaVu Sans", GUI_CONFIG['fonts']['sizes']['small']),
                        bg=GUI_CONFIG['colors']['card_bg'],
                        fg=GUI_CONFIG['colors']['primary']
                    )
                    next_label.pack(pady=(10, 0))
            else:
                self.show_empty_tile(content, "오늘 일정 없음")

    def update_system_tile(self):
        """시스템 타일 업데이트"""
        content = self.tile_frames["system"]
        
        # 기존 내용 지우기
        for widget in content.winfo_children():
            widget.destroy()
        
        # 시스템 상태 아이콘
        status_icon = "🟢" if self.connection_state['status'] == 'connected' else "🔴"
        
        icon_label = tk.Label(
            content,
            text=status_icon,
            font=("DejaVu Sans", 48),
            bg=GUI_CONFIG['colors']['card_bg']
        )
        icon_label.pack(pady=(20, 10))
        
        # 상태 텍스트
        status_text = "시스템 정상" if self.connection_state['status'] == 'connected' else "연결 오류"
        status_label = tk.Label(
            content,
            text=status_text,
            font=("DejaVu Sans", GUI_CONFIG['fonts']['sizes']['body'], "bold"),
            bg=GUI_CONFIG['colors']['card_bg'],
            fg=GUI_CONFIG['colors']['success'] if self.connection_state['status'] == 'connected' else GUI_CONFIG['colors']['danger']
        )
        status_label.pack()
        
        # 가동 시간
        uptime = datetime.datetime.now() - self.system_stats['system_uptime']
        uptime_hours = int(uptime.total_seconds() // 3600)
        
        uptime_label = tk.Label(
            content,
            text=f"가동: {uptime_hours}시간",
            font=("DejaVu Sans", GUI_CONFIG['fonts']['sizes']['small']),
            bg=GUI_CONFIG['colors']['card_bg'],
            fg=GUI_CONFIG['colors']['text_secondary']
        )
        uptime_label.pack(pady=(10, 0))

    def show_empty_tile(self, parent, message):
        """빈 타일 표시"""
        empty_label = tk.Label(
            parent,
            text="—",
            font=("DejaVu Sans", 72),
            bg=GUI_CONFIG['colors']['card_bg'],
            fg=GUI_CONFIG['colors']['text_muted']
        )
        empty_label.pack(pady=(30, 10))
        
        message_label = tk.Label(
            parent,
            text=message,
            font=("DejaVu Sans", GUI_CONFIG['fonts']['sizes']['body']),
            bg=GUI_CONFIG['colors']['card_bg'],
            fg=GUI_CONFIG['colors']['text_muted']
        )
        message_label.pack()

    def update_time_display(self):
        """시간 표시 업데이트"""
        try:
            now = datetime.datetime.now()
            time_str = now.strftime("%H:%M:%S")
            
            if 'current_time' in self.ui_elements:
                self.ui_elements['current_time'].config(text=time_str)
                
        except Exception as e:
            print(f"[ERROR] 시간 업데이트 오류: {e}")

    def update_connection_status(self):
        """연결 상태 업데이트"""
        try:
            status = self.connection_state['status']
            
            # 상태 표시기 업데이트
            if status == 'connected':
                color = GUI_CONFIG['colors']['success']
                text = "온라인"
            elif status == 'connecting':
                color = GUI_CONFIG['colors']['warning']
                text = "연결 중"
            else:
                color = GUI_CONFIG['colors']['danger']
                text = "오프라인"
            
            if 'connection_indicator' in self.ui_elements:
                self.ui_elements['connection_indicator'].config(fg=color)
            
            if 'connection_text' in self.ui_elements:
                self.ui_elements['connection_text'].config(text=text)
            
            # 마지막 업데이트 시간
            if self.cached_data['last_update']:
                update_text = f"업데이트: {self.cached_data['last_update'].strftime('%H:%M:%S')}"
                if 'last_update' in self.ui_elements:
                    self.ui_elements['last_update'].config(text=update_text)
                    
        except Exception as e:
            print(f"[ERROR] 연결 상태 업데이트 오류: {e}")

    def update_system_status(self):
        """시스템 상태 업데이트"""
        try:
            # CPU 온도 (라즈베리파이)
            cpu_temp = self.system_monitor.get_cpu_temperature()
            if cpu_temp and 'cpu_temp' in self.ui_elements:
                temp_color = GUI_CONFIG['colors']['danger'] if cpu_temp > 70 else GUI_CONFIG['colors']['text_muted']
                self.ui_elements['cpu_temp'].config(
                    text=f"CPU: {cpu_temp:.1f}°C",
                    fg=temp_color
                )
            
            # 메모리 사용량
            memory_usage = self.system_monitor.get_memory_usage()
            if memory_usage and 'memory_usage' in self.ui_elements:
                mem_color = GUI_CONFIG['colors']['danger'] if memory_usage > 85 else GUI_CONFIG['colors']['text_muted']
                self.ui_elements['memory_usage'].config(
                    text=f"RAM: {memory_usage:.1f}%",
                    fg=mem_color
                )
                
        except Exception as e:
            print(f"[ERROR] 시스템 상태 업데이트 오류: {e}")

    def get_next_schedule_time(self, schedules):
        """다음 스케줄 시간 계산"""
        try:
            now = datetime.datetime.now()
            current_hour = now.hour
            
            time_slots = {
                'morning': (8, '오전'),
                'afternoon': (14, '오후'), 
                'evening': (19, '저녁')
            }
            
            for time_key, (hour, name) in time_slots.items():
                if current_hour < hour and schedules.get(time_key):
                    return f"{name} {hour:02d}:00"
            
            # 내일 오전
            if schedules.get('morning'):
                return "내일 오전 08:00"
                
            return None
            
        except Exception as e:
            print(f"[ERROR] 다음 스케줄 계산 오류: {e}")
            return None

    def handle_rfid_activity(self, data):
        """RFID 활동 처리"""
        try:
            self.last_user_activity = time.time()
            
            # 절전 화면에서 복귀
            if self.current_screen == "screensaver":
                self.show_main_screen()
            
            # 음성 피드백
            if self.voice_manager:
                self.voice_manager.speak_async("rfid_detected")
                
        except Exception as e:
            print(f"[ERROR] RFID 활동 처리 오류: {e}")

    def handle_dispense_complete(self, data):
        """약 배출 완료 처리"""
        try:
            self.system_stats['total_dispenses_today'] += 1
            self.system_stats['last_dispense_time'] = datetime.datetime.now()
            
            # 음성 피드백
            if self.voice_manager:
                self.voice_manager.speak_async("dispense_complete")
            
            # 성공 표시 (간단한 오버레이)
            self.show_success_overlay("약 배출이 완료되었습니다")
            
        except Exception as e:
            print(f"[ERROR] 배출 완료 처리 오류: {e}")

    def show_success_overlay(self, message, duration=3000):
        """성공 오버레이 표시"""
        try:
            overlay = tk.Toplevel(self.window)
            overlay.overrideredirect(True)
            overlay.attributes('-topmost', True)
            
            # 화면 중앙에 위치
            overlay.geometry("400x150+{}+{}".format(
                (self.window.winfo_width() - 400) // 2,
                (self.window.winfo_height() - 150) // 2
            ))
            
            # 배경
            frame = tk.Frame(
                overlay,
                bg=GUI_CONFIG['colors']['success'],
                relief="raised",
                bd=3
            )
            frame.pack(fill="both", expand=True)
            
            # 아이콘
            icon_label = tk.Label(
                frame,
                text="✅",
                font=("DejaVu Sans", 48),
                bg=GUI_CONFIG['colors']['success'],
                fg="white"
            )
            icon_label.pack(pady=(20, 10))
            
            # 메시지
            message_label = tk.Label(
                frame,
                text=message,
                font=("DejaVu Sans", GUI_CONFIG['fonts']['sizes']['body'], "bold"),
                bg=GUI_CONFIG['colors']['success'],
                fg="white"
            )
            message_label.pack()
            
            # 자동 닫기
            self.window.after(duration, overlay.destroy)
            
        except Exception as e:
            print(f"[ERROR] 성공 오버레이 표시 오류: {e}")

    def show_screensaver(self):
        """절전 화면 표시"""
        try:
            with self.screen_transition_lock:
                if self.current_screen == "screensaver":
                    return
                
                # 기존 콘텐츠 지우기
                for widget in self.content_frame.winfo_children():
                    widget.destroy()
                
                self.current_screen = "screensaver"
                
                # 절전 화면
                screensaver_frame = tk.Frame(
                    self.content_frame,
                    bg="black"
                )
                screensaver_frame.pack(fill="both", expand=True)
                
                # 시계 표시
                self.ui_elements['screensaver_clock'] = tk.Label(
                    screensaver_frame,
                    text="",
                    font=("DejaVu Sans", 72, "bold"),
                    bg="black",
                    fg="white"
                )
                self.ui_elements['screensaver_clock'].pack(expand=True)
                
                # 절전 모드 메시지
                screensaver_message = tk.Label(
                    screensaver_frame,
                    text="RFID 카드를 대주세요",
                    font=("DejaVu Sans", 24),
                    bg="black",
                    fg="gray"
                )
                screensaver_message.pack(pady=(0, 50))
                
                # 시계 업데이트 시작
                self.update_screensaver_clock()
                
        except Exception as e:
            print(f"[ERROR] 절전 화면 표시 오류: {e}")

    def update_screensaver_clock(self):
        """절전 화면 시계 업데이트"""
        try:
            if (self.current_screen == "screensaver" and 
                'screensaver_clock' in self.ui_elements and
                self.ui_elements['screensaver_clock'].winfo_exists()):
                
                now = datetime.datetime.now()
                time_str = now.strftime("%H:%M")
                self.ui_elements['screensaver_clock'].config(text=time_str)
                
                # 1분마다 업데이트
                self.window.after(60000, self.update_screensaver_clock)
                
        except Exception as e:
            print(f"[ERROR] 절전 화면 시계 오류: {e}")

    def show_main_screen(self):
        """메인 화면으로 복귀"""
        try:
            with self.screen_transition_lock:
                if self.current_screen == "main":
                    return
                
                self.create_main_screen()
                self.last_user_activity = time.time()
                
        except Exception as e:
            print(f"[ERROR] 메인 화면 복귀 오류: {e}")

    def check_auto_screen_transition(self):
        """자동 화면 전환 체크"""
        # 현재는 기본 구현만, 필요시 확장 가능
        pass

    def handle_connection_error(self, error_message):
        """연결 오류 처리"""
        try:
            print(f"[ERROR] 연결 오류: {error_message}")
            
            # 음성 피드백
            if self.voice_manager:
                self.voice_manager.speak_async("connection_error")
            
            # 재연결 시도
            retry_count = self.connection_state['retry_count']
            if retry_count < 5:  # 최대 5회 재시도
                self.window.after(5000, lambda: self.executor.submit(self.load_all_data_async))
                
        except Exception as e:
            print(f"[ERROR] 연결 오류 처리 실패: {e}")

    def on_window_configure(self, event):
        """윈도우 설정 변경 이벤트"""
        # 필요시 구현
        pass

    def on_closing(self):
        """창 닫기 처리"""
        try:
            print("[INFO] 시스템 종료 중...")
            
            self.update_running = False
            
            # 컴포넌트 정리
            if self.voice_manager:
                self.voice_manager.cleanup()
            
            if self.system_monitor:
                self.system_monitor.stop_monitoring()
            
            # 스레드 풀 종료
            self.executor.shutdown(wait=False)
            
            # 윈도우 파괴
            if self.window:
                self.window.destroy()
                
        except Exception as e:
            print(f"[ERROR] 종료 처리 오류: {e}")

    def show(self):
        """GUI 표시"""
        try:
            self.create_main_window()
            self.window.mainloop()
        except KeyboardInterrupt:
            print("[INFO] 키보드 인터럽트로 종료")
        except Exception as e:
            print(f"[ERROR] GUI 실행 오류: {e}")
        finally:
            self.update_running = False
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=False)


def show_main_screen(muid: str):
    """메인 화면 표시 함수"""
    gui = RaspberryPiDispenserGUI(muid)
    gui.show()