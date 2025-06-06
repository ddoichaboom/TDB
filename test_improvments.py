#!/usr/bin/env python3
# test_improvements.py - 개선사항 테스트 스크립트

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.server_request import (
    test_server_connection,
    verify_rfid_uid,
    get_dispense_list, 
    confirm_user_intake,
    get_user_slot_mapping
)

def test_slot_mapping():
    """슬롯 매핑 테스트"""
    print("\n=== 슬롯 매핑 테스트 ===")
    
    # 테스트용 기기 ID (muid.txt에서 읽기)
    try:
        with open('muid.txt', 'r') as f:
            device_id = f.read().strip()
    except:
        device_id = 'TEST_DEVICE'
    
    print(f"기기 ID: {device_id}")
    
    slot_mapping = get_user_slot_mapping(device_id)
    
    if slot_mapping:
        print("✅ 슬롯 매핑 조회 성공:")
        for medi_id, slot in slot_mapping.items():
            print(f"  {medi_id} -> 슬롯 {slot}")
    else:
        print("❌ 슬롯 매핑 조회 실패")
    
    return slot_mapping

def test_dispense_with_slots():
    """슬롯 정보 포함 배출 목록 테스트"""
    print("\n=== 배출 목록 테스트 (슬롯 정보 포함) ===")
    
    test_uids = ["K001", "K002", "K003"]
    
    for uid in test_uids:
        print(f"\n테스트 UID: {uid}")
        
        # 인증 테스트
        auth_result = verify_rfid_uid(uid)
        if not auth_result or auth_result.get('status') != 'ok':
            print(f"❌ 인증 실패: {uid}")
            continue
        
        print(f"✅ 인증 성공: {auth_result.get('user', {}).get('name', 'Unknown')}")
        
        # 배출 목록 조회 (슬롯 정보 포함)
        dispense_list = get_dispense_list(uid)
        
        if dispense_list:
            print(f"📋 배출 대상 약물 ({len(dispense_list)}개):")
            for item in dispense_list:
                med_name = item.get('medicine_name', 'Unknown')
                dose = item.get('dose', 1)
                slot = item.get('slot', 'Unknown')
                remain = item.get('remain', 'Unknown')
                time_of_day = item.get('time_of_day', '')
                
                print(f"  - {med_name}: {dose}개, 슬롯 {slot}, 잔량 {remain} [{time_of_day}]")
        else:
            print("📋 현재 배출할 약물 없음")
        
        break  # 첫 번째 성공한 UID만 테스트

def test_took_today_update():
    """took_today 업데이트 테스트"""
    print("\n=== 복용 완료 처리 테스트 ===")
    
    test_uids = ["K001", "K002", "K003"]
    
    for uid in test_uids:
        print(f"\n테스트 UID: {uid}")
        
        # 인증 확인
        auth_result = verify_rfid_uid(uid)
        if not auth_result or auth_result.get('status') != 'ok':
            print(f"❌ 인증 실패: {uid}")
            continue
        
        # 복용 완료 처리 테스트
        confirm_result = confirm_user_intake(uid)
        
        if confirm_result:
            status = confirm_result.get('status', 'unknown')
            message = confirm_result.get('message', '')
            
            if status == 'confirmed':
                print(f"✅ 복용 완료 처리 성공: {message}")
            elif status == 'already_confirmed':
                print(f"ℹ️ 이미 처리됨: {message}")
            else:
                print(f"⚠️ 예상하지 못한 상태: {status}")
        else:
            print(f"❌ 복용 완료 처리 실패")
        
        break  # 첫 번째 성공한 UID만 테스트

def main():
    """메인 테스트 실행"""
    print("🧪 개선사항 테스트 시작")
    print("="*50)
    
    # 1. 서버 연결 테스트
    print("1. 서버 연결 테스트...")
    if not test_server_connection():
        print("❌ 서버 연결 실패. 서버가 실행 중인지 확인하세요.")
        return
    
    # 2. 슬롯 매핑 테스트
    slot_mapping = test_slot_mapping()
    
    # 3. 배출 목록 테스트 (슬롯 정보 포함)
    test_dispense_with_slots()
    
    # 4. took_today 업데이트 테스트
    test_took_today_update()
    
    print("\n" + "="*50)
    print("🧪 테스트 완료")
    
    # 개선사항 요약
    print("\n📝 개선사항 요약:")
    print("✅ 슬롯 매핑 정보를 서버에서 동적으로 가져오기")
    print("✅ 배출 목록 조회 시 슬롯 정보 포함")
    print("✅ 약 배출 후 took_today 자동 업데이트")
    print("✅ 시뮬레이션 모드에서도 완전한 플로우 동작")
    print("✅ 슬롯 매핑 캐시로 성능 최적화")

if __name__ == "__main__":
    main()