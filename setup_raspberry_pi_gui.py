#!/usr/bin/env python3
# setup_raspberry_pi_gui.py - 라즈베리파이 GUI 환경 설정 및 테스트

import os
import sys
import subprocess
import platform
import tkinter as tk
from pathlib import Path

class RaspberryPiGUISetup:
    """라즈베리파이 GUI 환경 설정 도구"""
    
    def __init__(self):
        self.is_raspberry_pi = self.check_raspberry_pi()
        self.display_available = self.check_display()
        self.issues = []
        self.solutions = []
        
    def check_raspberry_pi(self):
        """라즈베리파이 환경인지 확인"""
        try:
            # CPU 정보에서 라즈베리파이 확인
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
                if 'Raspberry Pi' in cpuinfo or 'BCM' in cpuinfo:
                    return True
            
            # 플랫폼 정보로 확인
            machine = platform.machine().lower()
            if 'arm' in machine:
                return True
                
            return False
        except:
            return False
    
    def check_display(self):
        """디스플레이 환경 확인"""
        display = os.environ.get('DISPLAY')
        if display:
            print(f"[INFO] DISPLAY 환경변수: {display}")
            return True
        else:
            print("[WARNING] DISPLAY 환경변수가 설정되지 않음")
            return False
    
    def diagnose_system(self):
        """시스템 진단"""
        print("🔍 라즈베리파이 GUI 환경 진단 시작...")
        print("="*50)
        
        # 1. 기본 환경 확인
        print("1. 기본 환경 확인")
        print(f"   - 라즈베리파이: {'✅ 예' if self.is_raspberry_pi else '❌ 아니오'}")
        print(f"   - DISPLAY 설정: {'✅ 설정됨' if self.display_available else '❌ 설정되지 않음'}")
        print(f"   - 파이썬 버전: {sys.version.split()[0]}")
        print(f"   - 플랫폼: {platform.platform()}")
        
        # 2. X11 서버 상태 확인
        print("\n2. X11 서버 상태 확인")
        try:
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            if 'Xorg' in result.stdout or 'X' in result.stdout:
                print("   - X11 서버: ✅ 실행 중")
            else:
                print("   - X11 서버: ❌ 실행되지 않음")
                self.issues.append("X11 서버가 실행되지 않음")
                self.solutions.append("sudo systemctl start lightdm 또는 재부팅")
        except:
            print("   - X11 서버: ❓ 확인 불가")
        
        # 3. tkinter 라이브러리 확인
        print("\n3. tkinter 라이브러리 확인")
        try:
            import tkinter
            print("   - tkinter 모듈: ✅ 사용 가능")
        except ImportError:
            print("   - tkinter 모듈: ❌ 설치되지 않음")
            self.issues.append("tkinter가 설치되지 않음")
            self.solutions.append("sudo apt-get install python3-tk")
        
        # 4. 필수 패키지 확인
        print("\n4. 필수 패키지 확인")
        required_packages = ['python3-tk', 'python3-pil', 'python3-pil.imagetk']
        
        for package in required_packages:
            try:
                result = subprocess.run(['dpkg', '-l', package], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"   - {package}: ✅ 설치됨")
                else:
                    print(f"   - {package}: ❌ 설치되지 않음")
                    self.issues.append(f"{package}가 설치되지 않음")
                    self.solutions.append(f"sudo apt-get install {package}")
            except:
                print(f"   - {package}: ❓ 확인 불가")
        
        # 5. 사용자 권한 확인
        print("\n5. 사용자 권한 확인")
        current_user = os.getenv('USER', 'unknown')
        print(f"   - 현재 사용자: {current_user}")
        
        # video 그룹 확인
        try:
            result = subprocess.run(['groups'], capture_output=True, text=True)
            if 'video' in result.stdout:
                print("   - video 그룹: ✅ 포함됨")
            else:
                print("   - video 그룹: ❌ 포함되지 않음")
                self.issues.append("사용자가 video 그룹에 속하지 않음")
                self.solutions.append(f"sudo usermod -a -G video {current_user}")
        except:
            print("   - video 그룹: ❓ 확인 불가")
        
        # 6. 해상도 및 모니터 확인
        print("\n6. 디스플레이 설정 확인")
        try:
            if self.display_available:
                result = subprocess.run(['xrandr'], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if ' connected' in line:
                            print(f"   - 모니터: ✅ {line.strip()}")
                else:
                    print("   - 모니터: ❓ xrandr 실행 실패")
            else:
                print("   - 모니터: ❌ DISPLAY 환경변수 없음")
        except:
            print("   - 모니터: ❓ 확인 불가")
        
    def show_issues_and_solutions(self):
        """발견된 문제와 해결책 표시"""
        if not self.issues:
            print("\n✅ 문제가 발견되지 않았습니다!")
            return
        
        print(f"\n⚠️ 발견된 문제: {len(self.issues)}개")
        print("="*50)
        
        for i, (issue, solution) in enumerate(zip(self.issues, self.solutions), 1):
            print(f"{i}. 문제: {issue}")
            print(f"   해결책: {solution}")
            print()
        
        print("🔧 모든 문제를 해결한 후 다시 테스트하세요.")
    
    def test_simple_gui(self):
        """간단한 GUI 테스트"""
        print("\n🧪 GUI 기능 테스트 중...")
        
        try:
            # 간단한 테스트 윈도우 생성
            test_window = tk.Tk()
            test_window.title("GUI 테스트")
            test_window.geometry("400x300+100+100")
            
            # 테스트 내용
            label = tk.Label(test_window, 
                           text="GUI 테스트 성공!\n이 창이 보이면 GUI가 정상 작동합니다.", 
                           font=("Arial", 14),
                           fg="green")
            label.pack(expand=True)
            
            # 닫기 버튼
            close_btn = tk.Button(test_window, 
                                text="닫기", 
                                command=test_window.destroy,
                                font=("Arial", 12))
            close_btn.pack(pady=20)
            
            print("✅ GUI 테스트 윈도우 생성 성공")
            print("   테스트 윈도우가 모니터에 표시되는지 확인하세요.")
            print("   5초 후 자동으로 닫힙니다.")
            
            # 5초 후 자동 종료
            test_window.after(5000, test_window.destroy)
            test_window.mainloop()
            
            return True
            
        except Exception as e:
            print(f"❌ GUI 테스트 실패: {e}")
            return False
    
    def apply_common_fixes(self):
        """일반적인 문제 자동 수정"""
        print("\n🔧 일반적인 GUI 문제 자동 수정 시도...")
        
        fixes_applied = []
        
        # 1. DISPLAY 환경변수 설정
        if not self.display_available:
            try:
                os.environ['DISPLAY'] = ':0'
                print("   - DISPLAY 환경변수를 :0으로 설정")
                fixes_applied.append("DISPLAY 환경변수 설정")
            except:
                pass
        
        # 2. 화면 보호기 비활성화
        try:
            subprocess.run(['xset', 's', 'off'], check=False, capture_output=True)
            subprocess.run(['xset', '-dpms'], check=False, capture_output=True)
            subprocess.run(['xset', 's', 'noblank'], check=False, capture_output=True)
            fixes_applied.append("화면 보호기 비활성화")
        except:
            pass
        
        # 3. 간단한 권한 수정
        try:
            subprocess.run(['xhost', '+local:'], check=False, capture_output=True)
            fixes_applied.append("X11 접근 권한 허용")
        except:
            pass
        
        if fixes_applied:
            print("   적용된 수정사항:")
            for fix in fixes_applied:
                print(f"     ✅ {fix}")
        else:
            print("   자동으로 적용할 수 있는 수정사항이 없습니다.")
    
    def run_full_test(self):
        """전체 테스트 실행"""
        print("🚀 라즈베리파이 GUI 환경 설정 도구")
        print("="*50)
        
        # 진단 실행
        self.diagnose_system()
        
        # 문제 및 해결책 표시
        self.show_issues_and_solutions()
        
        # 자동 수정 시도
        self.apply_common_fixes()
        
        # GUI 테스트
        print("\n" + "="*50)
        gui_success = self.test_simple_gui()
        
        # 최종 결과
        print("\n" + "="*50)
        if gui_success:
            print("🎉 GUI 테스트 성공!")
            print("   이제 main.py --gui로 디스펜서를 실행할 수 있습니다.")
        else:
            print("❌ GUI 테스트 실패")
            print("   위의 해결책을 적용한 후 다시 시도하세요.")
        
        return gui_success

def main():
    """메인 함수"""
    if len(sys.argv) > 1 and sys.argv[1] == '--quick-test':
        # 빠른 GUI 테스트만
        setup = RaspberryPiGUISetup()
        return setup.test_simple_gui()
    else:
        # 전체 진단 및 테스트
        setup = RaspberryPiGUISetup()
        return setup.run_full_test()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)