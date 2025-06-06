#!/usr/bin/env python3
# test_server.py - 독립적인 서버 연결 테스트
import requests
import json
import time

# 서버 설정
SERVER_URL = "http://192.168.59.208:3000/dispenser"
TIMEOUT = 10

def test_connection():
    """기본 연결 테스트"""
    print(f"=== 서버 연결 테스트 ===")
    print(f"서버 주소: {SERVER_URL}")
    
    try:
        # 기본 GET 요청으로 서버 응답 확인
        response = requests.get(SERVER_URL, timeout=TIMEOUT)
        print(f"✅ 서버 응답: {response.status_code}")
        
        if response.status_code == 200:
            print("서버가 정상적으로 응답합니다.")
            return True
        else:
            print(f"서버 응답 코드: {response.status_code}")
            print(f"응답 내용: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ 연결 타임아웃 - 서버가 응답하지 않습니다.")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ 연결 오류 - 서버에 접근할 수 없습니다.")
        print("네트워크 연결과 서버 주소를 확인해주세요.")
        return False
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        return False

def test_verify_uid(test_uid):
    """사용자 인증 테스트"""
    print(f"\n=== 사용자 인증 테스트 ===")
    print(f"테스트 UID: {test_uid}")
    
    try:
        url = f"{SERVER_URL}/verify-uid"
        data = {"uid": test_uid}
        
        print(f"요청 URL: {url}")
        print(f"요청 데이터: {json.dumps(data)}")
        
        response = requests.post(url, json=data, timeout=TIMEOUT)
        print(f"응답 코드: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 인증 성공!")
            print(f"응답 데이터: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return result
        else:
            print(f"❌ 인증 실패 - 응답 코드: {response.status_code}")
            print(f"응답 내용: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 인증 요청 오류: {e}")
        return None

def test_dispense_list(test_uid):
    """배출 목록 조회 테스트"""
    print(f"\n=== 배출 목록 조회 테스트 ===")
    print(f"테스트 UID: {test_uid}")
    
    try:
        url = f"{SERVER_URL}/dispense-list"
        data = {"k_uid": test_uid}  # 서버가 기대하는 k_uid 사용
        
        print(f"요청 URL: {url}")
        print(f"요청 데이터: {json.dumps(data)}")
        
        response = requests.post(url, json=data, timeout=TIMEOUT)
        print(f"응답 코드: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 배출 목록 조회 성공!")
            print(f"응답 데이터: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return result
        else:
            print(f"❌ 배출 목록 조회 실패 - 응답 코드: {response.status_code}")
            print(f"응답 내용: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 배출 목록 요청 오류: {e}")
        return None

def test_dispense_result(test_uid):
    """배출 결과 전송 테스트"""
    print(f"\n=== 배출 결과 전송 테스트 ===")
    print(f"테스트 UID: {test_uid}")
    
    try:
        url = f"{SERVER_URL}/dispense-result"
        data = {
            "k_uid": test_uid,  # 서버가 기대하는 k_uid 사용
            "dispenseList": [   # 서버가 기대하는 dispenseList 사용
                {"medi_id": "M001", "dose": 1},
                {"medi_id": "M002", "dose": 2}
            ]
        }
        
        print(f"요청 URL: {url}")
        print(f"요청 데이터: {json.dumps(data, indent=2)}")
        
        response = requests.post(url, json=data, timeout=TIMEOUT)
        print(f"응답 코드: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 배출 결과 전송 성공!")
            print(f"응답 데이터: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return result
        else:
            print(f"❌ 배출 결과 전송 실패 - 응답 코드: {response.status_code}")
            print(f"응답 내용: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 배출 결과 전송 오류: {e}")
        return None

def main():
    """메인 테스트 실행"""
    print("🏥 Smart Medicine Dispenser - 서버 연결 테스트")
    print("=" * 60)
    
    # 1. 기본 연결 테스트
    if not test_connection():
        print("\n❌ 서버 연결 실패 - 테스트를 중단합니다.")
        print("\n해결 방법:")
        print("1. 서버가 실행 중인지 확인하세요")
        print("2. 네트워크 연결을 확인하세요")
        print("3. 서버 주소가 올바른지 확인하세요")
        return False
    
    # 2. 테스트할 UID 목록
    test_uids = ["K001", "K002", "K003", "INVALID_UID"]
    
    for test_uid in test_uids:
        print(f"\n{'='*60}")
        print(f"🧪 UID 테스트: {test_uid}")
        print(f"{'='*60}")
        
        # 인증 테스트
        auth_result = test_verify_uid(test_uid)
        
        if auth_result and auth_result.get('status') == 'ok':
            print(f"✅ {test_uid} 인증 성공 - 추가 테스트 진행")
            
            # 배출 목록 테스트
            dispense_result = test_dispense_list(test_uid)
            
            # 배출 결과 테스트 (시뮬레이션)
            result_response = test_dispense_result(test_uid)
            
            # 성공한 UID 하나에 대해서만 전체 테스트 완료
            print(f"\n✅ {test_uid}로 모든 API 테스트 완료!")
            break
            
        elif auth_result and auth_result.get('status') == 'unregistered':
            print(f"⚠️ {test_uid}는 미등록 사용자입니다.")
            
        else:
            print(f"❌ {test_uid} 인증 실패")
    
    print(f"\n{'='*60}")
    print("🎉 서버 연결 테스트 완료!")
    print("모든 API가 정상적으로 작동하면 main.py를 실행하세요.")
    print(f"{'='*60}")
    
    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자에 의해 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류 발생: {e}")
        import traceback
        traceback.print_exc()
