#!/usr/bin/env python3
# check_x11.py - X11 서버 상태 확인 및 자동 수정

import os
import subprocess
import time

def check_x11_server():
    """X11 서버 상태 확인"""
    print("🔍 X11 서버 상태 확인")
    print("="*30)
    
    # 1. DISPLAY 환경변수 확인
    display = os.environ.get('DISPLAY')
    print(f"DISPLAY 환경변수: {display or '❌ 설정되지 않음'}")
    
    # 2. X11 프로세스 확인
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if 'Xorg' in result.stdout or '/usr/bin/X' in result.stdout:
            print("X11 서버: ✅ 실행 중")
            x11_running = True
        else:
            print("X11 서버: ❌ 실행되지 않음")
            x11_running = False
    except:
        print("X11 서버: ❓ 확인 불가")
        x11_running = False
    
    # 3. xrandr로 디스플레이 확인
    try:
        if display:
            result = subprocess.run(['xrandr'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print("디스플레이 연결: ✅ 정상")
                for line in result.stdout.split('\n'):
                    if ' connected' in line:
                        print(f"  모니터: {line.strip()}")
            else:
                print("디스플레이 연결: ❌ 오류")
        else:
            print("디스플레이 연결: ❌ DISPLAY 환경변수 없음")
    except subprocess.TimeoutExpired:
        print("디스플레이 연결: ⏱️ 타임아웃")
    except:
        print("디스플레이 연결: ❓ 확인 불가")
    
    return x11_running and display

def fix_display_environment():
    """디스플레이 환경 수정"""
    print("\n🔧 디스플레이 환경 수정")
    print("="*30)
    
    fixes_applied = []
    
    # 1. DISPLAY 환경변수 설정
    if not os.environ.get('DISPLAY'):
        os.environ['DISPLAY'] = ':0'
        print("✅ DISPLAY 환경변수를 :0으로 설정")
        fixes_applied.append("DISPLAY 설정")
    
    # 2. X11 권한 설정
    try:
        subprocess.run(['xhost', '+local:'], 
                      check=False, capture_output=True, timeout=5)
        print("✅ X11 접근 권한 설정")
        fixes_applied.append("X11 권한")
    except:
        print("⚠️ X11 권한 설정 실패")
    
    # 3. 화면 보호기 비활성화
    try:
        subprocess.run(['xset', 's', 'off'], 
                      check=False, capture_output=True, timeout=5)
        subprocess.run(['xset', '-dpms'], 
                      check=False, capture_output=True, timeout=5)
        subprocess.run(['xset', 's', 'noblank'], 
                      check=False, capture_output=True, timeout=5)
        print("✅ 화면 보호기 비활성화")
        fixes_applied.append("화면 보호기 설정")
    except:
        print("⚠️ 화면 보호기 설정 실패")
    
    return fixes_applied

def test_gui_simple():
    """간단한 GUI 테스트"""
    print("\n🧪 GUI 테스트")
    print("="*30)
    
    try:
        import tkinter as tk
        
        root = tk.Tk()
        root.title("X11 테스트")
        root.geometry("200x100+100+100")
        
        label = tk.Label(root, text="GUI 테스트 성공!", font=("Arial", 12))
        label.pack(expand=True)
        
        print("✅ GUI 윈도우 생성 성공")
        print("   3초 후 자동으로 닫힙니다")
        
        root.after(3000, root.destroy)
        root.mainloop()
        
        return True
        
    except Exception as e:
        print(f"❌ GUI 테스트 실패: {e}")
        return False

def restart_x11_if_needed():
    """필요시 X11 서버 재시작"""
    print("\n🔄 X11 서버 재시작 시도")
    print("="*30)
    
    try:
        # lightdm 재시작 (라즈베리파이 기본 디스플레이 매니저)
        print("lightdm 서비스 재시작 시도...")
        result = subprocess.run(['sudo', 'systemctl', 'restart', 'lightdm'], 
                               capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✅ lightdm 재시작 성공")
            print("⏳ 5초 대기 중...")
            time.sleep(5)
            return True
        else:
            print(f"❌ lightdm 재시작 실패: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏱️ lightdm 재시작 타임아웃")
        return False
    except Exception as e:
        print(f"❌ lightdm 재시작 오류: {e}")
        return False

def show_manual_solutions():
    """수동 해결 방법 안내"""
    print("\n📋 수동 해결 방법")
    print("="*50)
    
    print("1. 🔄 라즈베리파이 재부팅:")
    print("   sudo reboot")
    
    print("\n2. 🖥️ X11 서버 수동 시작:")
    print("   sudo systemctl start lightdm")
    
    print("\n3. 📺 모니터 연결 확인:")
    print("   - HDMI 케이블이 제대로 연결되었는지 확인")
    print("   - 모니터 전원이 켜져 있는지 확인")
    
    print("\n4. 🔧 설정 확인:")
    print("   sudo raspi-config")
    print("   → Advanced Options → GL Driver → Legacy")
    
    print("\n5. 🌐 SSH에서 GUI 실행:")
    print("   export DISPLAY=:0")
    print("   python3 main.py --gui")

def main():
    """메인 함수"""
    print("🔍 X11 서버 진단 및 수정 도구")
    print("="*50)
    
    # 1. 현재 상태 확인
    x11_ok = check_x11_server()
    
    if x11_ok:
        print("\n✅ X11 환경이 정상입니다!")
        
        # GUI 테스트
        if test_gui_simple():
            print("\n🎉 GUI 테스트 성공!")
            print("이제 main.py --gui를 실행할 수 있습니다.")
            return True
        else:
            print("\n⚠️ GUI 테스트 실패. 추가 수정이 필요합니다.")
    
    # 2. 환경 수정 시도
    fixes = fix_display_environment()
    
    if fixes:
        print(f"\n✅ {len(fixes)}개 항목 수정 완료")
        
        # 수정 후 다시 테스트
        if test_gui_simple():
            print("\n🎉 수정 후 GUI 테스트 성공!")
            print("이제 main.py --gui를 실행할 수 있습니다.")
            return True
    
    # 3. X11 재시작 시도
    print("\n⚠️ 일반적인 수정으로 해결되지 않았습니다.")
    user_input = input("X11 서버를 재시작하시겠습니까? (y/N): ")
    
    if user_input.lower() in ['y', 'yes']:
        if restart_x11_if_needed():
            print("X11 재시작 후 다시 테스트하세요:")
            print("python3 check_x11.py")
        else:
            show_manual_solutions()
    else:
        show_manual_solutions()
    
    return False

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n🚀 준비 완료! 다음 명령으로 GUI 실행:")
            print("python3 main.py --gui")
    except KeyboardInterrupt:
        print("\n⚠️ 사용자가 중단했습니다")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()