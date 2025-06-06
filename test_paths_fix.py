#!/usr/bin/env python3
# test_paths_fix.py - 경로 수정 확인 테스트

import os
import sys
from pathlib import Path

def test_config_paths():
    """config.py 경로 설정 테스트"""
    print("🔍 config.py 경로 설정 테스트")
    print("="*40)
    
    try:
        from config import SYSTEM_PATHS, BASE_DIR, DATA_DIR
        
        print(f"현재 사용자: {os.getenv('USER', 'unknown')}")
        print(f"현재 작업 디렉토리: {os.getcwd()}")
        print(f"사용자 홈 디렉토리: {os.path.expanduser('~')}")
        print()
        
        print("동적 경로 설정:")
        print(f"  BASE_DIR: {BASE_DIR}")
        print(f"  DATA_DIR: {DATA_DIR}")
        print()
        
        print("SYSTEM_PATHS:")
        for key, path in SYSTEM_PATHS.items():
            exists = "✅" if os.path.exists(path) else "❌"
            writable = "✅" if os.access(path, os.W_OK) else "❌" if os.path.exists(path) else "?"
            print(f"  {key}: {path}")
            print(f"    존재: {exists}, 쓰기가능: {writable}")
        
        return True
        
    except Exception as e:
        print(f"❌ config.py 테스트 실패: {e}")
        return False

def test_logger_paths():
    """logger.py 경로 설정 테스트"""
    print("\n🔍 logger.py 경로 설정 테스트")
    print("="*40)
    
    try:
        from utils.logger import get_logger
        
        logger = get_logger()
        
        print("로거 파일 경로:")
        for name, path in logger.log_files.items():
            exists = "✅" if path.exists() else "❌"
            print(f"  {name}: {path} {exists}")
        
        return True
        
    except Exception as e:
        print(f"❌ logger.py 테스트 실패: {e}")
        return False

def test_system_monitor_paths():
    """system_monitor.py 경로 설정 테스트"""
    print("\n🔍 system_monitor.py 경로 설정 테스트")
    print("="*40)
    
    try:
        from utils.system_monitor import SystemMonitor
        
        monitor = SystemMonitor()
        
        print(f"시스템 모니터 로그 파일: {monitor.log_file}")
        print(f"존재: {'✅' if monitor.log_file.exists() else '❌'}")
        print(f"디렉토리 쓰기 가능: {'✅' if os.access(monitor.log_file.parent, os.W_OK) else '❌'}")
        
        return True
        
    except Exception as e:
        print(f"❌ system_monitor.py 테스트 실패: {e}")
        return False

def test_gui_import():
    """GUI 모듈 import 테스트"""
    print("\n🔍 GUI 모듈 import 테스트")
    print("="*40)
    
    try:
        import dispenser_gui
        print("✅ dispenser_gui 모듈 import 성공")
        
        if hasattr(dispenser_gui, 'show_main_screen'):
            print("✅ show_main_screen 함수 존재")
        else:
            print("❌ show_main_screen 함수 없음")
        
        return True
        
    except Exception as e:
        print(f"❌ GUI 모듈 import 실패: {e}")
        return False

def test_main_import():
    """main.py import 테스트"""
    print("\n🔍 main.py import 테스트")
    print("="*40)
    
    try:
        # main.py에서 SimpleMedicineDispenser 클래스만 테스트
        sys.path.append('.')
        
        # main.py의 import들이 성공하는지 확인
        import main
        
        print("✅ main.py import 성공")
        
        if hasattr(main, 'SimpleMedicineDispenser'):
            print("✅ SimpleMedicineDispenser 클래스 존재")
        else:
            print("❌ SimpleMedicineDispenser 클래스 없음")
        
        return True
        
    except Exception as e:
        print(f"❌ main.py import 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_test_files():
    """테스트 파일 생성"""
    print("\n🔧 테스트 파일 생성")
    print("="*40)
    
    try:
        from config import SYSTEM_PATHS
        
        # 각 디렉토리에 테스트 파일 생성
        for dir_name, dir_path in SYSTEM_PATHS.items():
            if dir_name.endswith('_dir'):
                test_file = Path(dir_path) / 'test_write.txt'
                try:
                    test_file.write_text(f"테스트 파일 - {dir_name}")
                    print(f"✅ {dir_name} 쓰기 테스트 성공: {test_file}")
                    test_file.unlink()  # 테스트 파일 삭제
                except Exception as e:
                    print(f"❌ {dir_name} 쓰기 테스트 실패: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 테스트 파일 생성 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🧪 경로 수정 확인 테스트")
    print("="*50)
    
    tests = [
        ("config.py 경로 설정", test_config_paths),
        ("logger.py 경로 설정", test_logger_paths),
        ("system_monitor.py 경로 설정", test_system_monitor_paths),
        ("GUI 모듈 import", test_gui_import),
        ("main.py import", test_main_import),
        ("테스트 파일 생성", create_test_files),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 실행 오류: {e}")
            results.append((test_name, False))
    
    # 결과 요약
    print("\n" + "="*50)
    print("📊 테스트 결과 요약")
    print("="*50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print("-" * 50)
    print(f"성공: {passed}/{total}")
    print(f"성공률: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n🎉 모든 테스트 통과!")
        print("이제 GUI 모드로 실행할 수 있습니다:")
        print("python3 main.py --gui")
    else:
        print(f"\n⚠️ {total-passed}개 테스트 실패")
        print("문제를 해결한 후 다시 테스트하세요.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)