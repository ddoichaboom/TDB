# utils/voice_feedback.py (라즈베리파이 음성 피드백 시스템)
import threading
import queue
import time
import subprocess
import os
from pathlib import Path
from config import VOICE_CONFIG, RASPBERRY_PI_CONFIG

class VoiceFeedbackManager:
    """라즈베리파이용 음성 피드백 관리자"""
    
    def __init__(self):
        self.enabled = VOICE_CONFIG['enabled'] and RASPBERRY_PI_CONFIG['audio_enabled']
        self.voice_queue = queue.Queue()
        self.current_language = VOICE_CONFIG['language']
        self.volume = VOICE_CONFIG['volume']
        self.speech_rate = VOICE_CONFIG['speech_rate']
        
        # 라즈베리파이용 TTS 설정
        self.tts_engine = 'espeak'  # espeak이 라즈베리파이에서 가장 안정적
        self.audio_device = RASPBERRY_PI_CONFIG['audio_device']
        
        # 음성 메시지 템플릿
        self.voice_templates = {
            'ko': {
                'smart_dispenser_ready': "스마트 약 디스펜서가 준비되었습니다.",
                'welcome': "환영합니다. RFID 카드를 대주세요.",
                'rfid_detected': "카드가 감지되었습니다.",
                'user_authenticated': "인증되었습니다.",
                'dispensing_start': "약을 배출하고 있습니다.",
                'dispense_complete': "약 배출이 완료되었습니다.",
                'dispense_failed': "약 배출에 실패했습니다. 관리자에게 문의하세요.",
                'no_medicine_scheduled': "현재 복용할 약이 없습니다.",
                'low_medicine_warning': "약품이 부족합니다. 보충이 필요합니다.",
                'system_error': "시스템 오류가 발생했습니다.",
                'connection_error': "서버 연결에 문제가 있습니다.",
                'connection_restored': "서버 연결이 복구되었습니다.",
                'maintenance_mode': "현재 유지보수 모드입니다.",
                'user_not_registered': "등록되지 않은 사용자입니다. 앱에서 등록해주세요.",
                'access_denied': "접근이 거부되었습니다.",
                'system_shutdown': "시스템을 종료합니다."
            },
            'en': {
                'smart_dispenser_ready': "Smart medicine dispenser is ready.",
                'welcome': "Welcome. Please present your RFID card.",
                'rfid_detected': "Card detected.",
                'user_authenticated': "User authenticated.",
                'dispensing_start': "Dispensing medicine.",
                'dispense_complete': "Medicine dispensing completed.",
                'dispense_failed': "Medicine dispensing failed. Please contact administrator.",
                'no_medicine_scheduled': "No medicine scheduled at this time.",
                'low_medicine_warning': "Medicine running low. Refill needed.",
                'system_error': "System error occurred.",
                'connection_error': "Server connection problem.",
                'connection_restored': "Server connection restored.",
                'maintenance_mode': "Currently in maintenance mode.",
                'user_not_registered': "User not registered. Please register in the app.",
                'access_denied': "Access denied.",
                'system_shutdown': "System shutting down."
            }
        }
        
        # 사운드 효과 파일 매핑 (라즈베리파이 경로)
        self.sound_effects = {
            'beep': '/usr/share/sounds/alsa/Front_Left.wav',
            'success': '/usr/share/sounds/alsa/Front_Right.wav',
            'error': '/usr/share/sounds/alsa/Rear_Left.wav',
            'notification': '/usr/share/sounds/alsa/Rear_Right.wav'
        }
        
        self.init_audio_system()
        self.start_voice_worker()
    
    def init_audio_system(self):
        """오디오 시스템 초기화"""
        if not self.enabled:
            print("[INFO] 음성 피드백이 비활성화되어 있습니다.")
            return
        
        try:
            # HDMI 오디오 출력 설정
            if self.audio_device == 'HDMI':
                subprocess.run(['amixer', 'cset', 'numid=3', '2'], check=False)
            
            # 볼륨 설정
            volume_percent = int(self.volume * 100)
            subprocess.run(['amixer', 'set', 'Master', f'{volume_percent}%'], check=False)
            
            # espeak 설정 확인
            result = subprocess.run(['which', 'espeak'], capture_output=True)
            if result.returncode != 0:
                print("[WARNING] espeak이 설치되지 않음. 음성 기능이 제한됩니다.")
                subprocess.run(['sudo', 'apt-get', 'install', '-y', 'espeak'], check=False)
            
            # 한국어 음성 확인 (espeak-data-ko)
            if self.current_language == 'ko':
                result = subprocess.run(['espeak', '--voices=ko'], capture_output=True, text=True)
                if 'korean' not in result.stdout.lower():
                    print("[WARNING] 한국어 음성 팩이 없습니다. 영어로 대체합니다.")
                    self.current_language = 'en'
            
            print("[INFO] 오디오 시스템 초기화 완료")
            
        except Exception as e:
            print(f"[ERROR] 오디오 시스템 초기화 실패: {e}")
            self.enabled = False
    
    def start_voice_worker(self):
        """음성 작업자 스레드 시작"""
        def voice_worker():
            while True:
                try:
                    # 큐에서 음성 작업 가져오기
                    voice_task = self.voice_queue.get(timeout=1)
                    
                    if voice_task is None:  # 종료 신호
                        break
                    
                    task_type = voice_task.get('type')
                    
                    if task_type == 'speak':
                        self._execute_speak(voice_task)
                    elif task_type == 'sound':
                        self._execute_sound(voice_task)
                    
                    self.voice_queue.task_done()
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"[ERROR] 음성 작업자 오류: {e}")
        
        thread = threading.Thread(target=voice_worker, daemon=True)
        thread.start()
        print("[INFO] 음성 작업자 스레드 시작됨")
    
    def speak_async(self, message_key, **kwargs):
        """비동기 음성 출력"""
        if not self.enabled:
            return
        
        try:
            # 메시지 템플릿에서 텍스트 가져오기
            template = self.voice_templates.get(self.current_language, {}).get(message_key)
            
            if not template:
                print(f"[WARNING] 음성 템플릿 없음: {message_key}")
                return
            
            # 변수 치환
            message_text = template.format(**kwargs)
            
            voice_task = {
                'type': 'speak',
                'text': message_text,
                'language': self.current_language,
                'rate': self.speech_rate,
                'volume': self.volume
            }
            
            self.voice_queue.put(voice_task)
            
        except Exception as e:
            print(f"[ERROR] 비동기 음성 출력 오류: {e}")
    
    def speak_text(self, text, language=None):
        """직접 텍스트 음성 출력"""
        if not self.enabled:
            return
        
        try:
            voice_task = {
                'type': 'speak',
                'text': text,
                'language': language or self.current_language,
                'rate': self.speech_rate,
                'volume': self.volume
            }
            
            self.voice_queue.put(voice_task)
            
        except Exception as e:
            print(f"[ERROR] 텍스트 음성 출력 오류: {e}")
    
    def play_sound_async(self, sound_name):
        """비동기 사운드 효과 재생"""
        if not self.enabled or not VOICE_CONFIG['sound_effects'].get(sound_name, True):
            return
        
        try:
            sound_task = {
                'type': 'sound',
                'sound_name': sound_name
            }
            
            self.voice_queue.put(sound_task)
            
        except Exception as e:
            print(f"[ERROR] 비동기 사운드 재생 오류: {e}")
    
    def _execute_speak(self, task):
        """음성 출력 실행"""
        try:
            text = task['text']
            language = task.get('language', 'en')
            rate = task.get('rate', self.speech_rate)
            volume = task.get('volume', self.volume)
            
            # espeak 명령어 구성
            cmd = ['espeak']
            
            # 언어 설정
            if language == 'ko':
                cmd.extend(['-v', 'ko'])  # 한국어 음성
            else:
                cmd.extend(['-v', 'en'])  # 영어 음성
            
            # 속도 설정 (단어/분)
            cmd.extend(['-s', str(rate)])
            
            # 볼륨 설정 (0-200)
            volume_val = int(volume * 200)
            cmd.extend(['-a', str(volume_val)])
            
            # 출력 장치 설정
            if self.audio_device == 'HDMI':
                # ALSA 디바이스로 출력
                cmd.extend(['-d', '/dev/stdout'])
                cmd.append(text)
                
                # aplay로 HDMI 출력
                espeak_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                aplay_process = subprocess.Popen(['aplay', '-D', 'plughw:1,0'], stdin=espeak_process.stdout, stderr=subprocess.PIPE)
                
                espeak_process.stdout.close()
                aplay_process.communicate()
            else:
                # 직접 스피커 출력
                cmd.append(text)
                subprocess.run(cmd, check=False, capture_output=True)
            
            print(f"[INFO] 음성 출력 완료: {text[:30]}...")
            
        except Exception as e:
            print(f"[ERROR] 음성 출력 실행 오류: {e}")
    
    def _execute_sound(self, task):
        """사운드 효과 실행"""
        try:
            sound_name = task['sound_name']
            sound_file = self.sound_effects.get(sound_name)
            
            if sound_file and Path(sound_file).exists():
                # aplay로 사운드 파일 재생
                if self.audio_device == 'HDMI':
                    subprocess.run(['aplay', '-D', 'plughw:1,0', sound_file], check=False, capture_output=True)
                else:
                    subprocess.run(['aplay', sound_file], check=False, capture_output=True)
                
                print(f"[INFO] 사운드 재생 완료: {sound_name}")
            else:
                # 기본 비프음 생성 (sox 사용)
                self._generate_beep(sound_name)
                
        except Exception as e:
            print(f"[ERROR] 사운드 효과 실행 오류: {e}")
    
    def _generate_beep(self, sound_type):
        """기본 비프음 생성"""
        try:
            # 사운드 타입별 주파수 설정
            frequencies = {
                'beep': 800,
                'success': 1000,
                'error': 400,
                'notification': 600
            }
            
            freq = frequencies.get(sound_type, 800)
            duration = 0.3
            
            # sox를 사용해서 비프음 생성 및 재생
            cmd = [
                'play', '-n', 'synth', str(duration), 'sin', str(freq),
                'vol', str(self.volume)
            ]
            
            if self.audio_device == 'HDMI':
                cmd.extend(['-t', 'alsa', '-d', 'plughw:1,0'])
            
            subprocess.run(cmd, check=False, capture_output=True)
            
        except Exception as e:
            print(f"[ERROR] 비프음 생성 오류: {e}")
    
    def set_volume(self, volume):
        """볼륨 설정 (0.0 - 1.0)"""
        try:
            self.volume = max(0.0, min(1.0, volume))
            
            # 시스템 볼륨도 함께 조정
            volume_percent = int(self.volume * 100)
            subprocess.run(['amixer', 'set', 'Master', f'{volume_percent}%'], check=False)
            
            print(f"[INFO] 볼륨 설정: {volume_percent}%")
            
        except Exception as e:
            print(f"[ERROR] 볼륨 설정 오류: {e}")
    
    def set_speech_rate(self, rate):
        """음성 속도 설정 (단어/분)"""
        self.speech_rate = max(80, min(300, rate))
        print(f"[INFO] 음성 속도 설정: {self.speech_rate} wpm")
    
    def set_language(self, language):
        """언어 설정"""
        if language in self.voice_templates:
            self.current_language = language
            print(f"[INFO] 언어 설정: {language}")
        else:
            print(f"[WARNING] 지원하지 않는 언어: {language}")
    
    def test_audio(self):
        """오디오 테스트"""
        try:
            print("[INFO] 오디오 테스트 시작...")
            
            # 사운드 효과 테스트
            self.play_sound_async('beep')
            time.sleep(1)
            
            # 음성 테스트
            self.speak_async('smart_dispenser_ready')
            
            print("[INFO] 오디오 테스트 완료")
            
        except Exception as e:
            print(f"[ERROR] 오디오 테스트 실패: {e}")
    
    def cleanup(self):
        """정리 작업"""
        try:
            print("[INFO] 음성 시스템 정리 중...")
            
            # 종료 신호 전송
            self.voice_queue.put(None)
            
            # 큐 정리
            while not self.voice_queue.empty():
                try:
                    self.voice_queue.get_nowait()
                    self.voice_queue.task_done()
                except queue.Empty:
                    break
            
            print("[INFO] 음성 시스템 정리 완료")
            
        except Exception as e:
            print(f"[ERROR] 음성 시스템 정리 오류: {e}")

# 편의 함수들
def create_voice_manager():
    """음성 관리자 생성"""
    return VoiceFeedbackManager()

def speak_message(message_key, **kwargs):
    """빠른 음성 메시지 (전역 인스턴스 사용)"""
    global _global_voice_manager
    
    if '_global_voice_manager' not in globals():
        _global_voice_manager = VoiceFeedbackManager()
    
    _global_voice_manager.speak_async(message_key, **kwargs)

def play_sound(sound_name):
    """빠른 사운드 재생 (전역 인스턴스 사용)"""
    global _global_voice_manager
    
    if '_global_voice_manager' not in globals():
        _global_voice_manager = VoiceFeedbackManager()
    
    _global_voice_manager.play_sound_async(sound_name)

# 자주 사용되는 음성 메시지 단축 함수들
def announce_rfid_detected():
    speak_message('rfid_detected')

def announce_dispense_complete():
    speak_message('dispense_complete')
    play_sound('success')

def announce_error(error_type='system_error'):
    speak_message(error_type)
    play_sound('error')

def announce_welcome():
    speak_message('welcome')

def announce_low_medicine(medicine_name):
    speak_message('low_medicine_warning', medicine_name=medicine_name)
    play_sound('notification')