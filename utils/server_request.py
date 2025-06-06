# utils/server_request.py (핵심 HTTP 통신에 집중)
import requests
import json
import time
import os
import sys

# 부모 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config import BASE_API_URL, GUI_CONFIG
except ImportError:
    # config 파일이 없는 경우 기본값 사용
    print("[WARNING] config.py를 찾을 수 없습니다. 기본 설정을 사용합니다.")
    BASE_API_URL = 'http://192.168.59.208:3000/dispenser'
    GUI_CONFIG = {
        'request_timeout': 10,
        'max_retry_count': 3,
        'retry_delay': 2
    }

class SimpleServerClient:
    """간소화된 서버 통신 클라이언트"""
    
    def __init__(self):
        self.base_url = BASE_API_URL
        self.timeout = GUI_CONFIG.get('request_timeout', 10)
        self.max_retries = GUI_CONFIG.get('max_retry_count', 3)
        self.retry_delay = GUI_CONFIG.get('retry_delay', 2)
        
        # 기본 헤더 설정
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        print(f"[SERVER] 클라이언트 초기화 - 서버: {self.base_url}")
    
    def _make_request(self, method, endpoint, data=None, params=None):
        """기본 HTTP 요청 수행"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        for attempt in range(self.max_retries):
            try:
                print(f"[SERVER] {method} {url} (시도 {attempt + 1}/{self.max_retries})")
                
                if data:
                    print(f"[SERVER] 요청 데이터: {json.dumps(data, ensure_ascii=False)}")
                
                start_time = time.time()
                
                if method.upper() == 'GET':
                    response = requests.get(
                        url, 
                        params=params, 
                        headers=self.headers,
                        timeout=self.timeout
                    )
                elif method.upper() == 'POST':
                    response = requests.post(
                        url, 
                        json=data, 
                        headers=self.headers,
                        timeout=self.timeout
                    )
                else:
                    raise ValueError(f"지원하지 않는 HTTP 메서드: {method}")
                
                response_time = (time.time() - start_time) * 1000
                print(f"[SERVER] 응답: {response.status_code} ({response_time:.0f}ms)")
                
                # 응답 처리 - 2xx 계열을 모두 성공으로 처리
                if 200 <= response.status_code < 300:
                    try:
                        result = response.json()
                        print(f"[SERVER] ✅ 성공 응답 데이터: {json.dumps(result, ensure_ascii=False)[:200]}...")
                        return result
                    except json.JSONDecodeError as e:
                        print(f"[ERROR] JSON 파싱 실패: {e}")
                        print(f"[ERROR] 응답 내용: {response.text[:200]}")
                        return None
                
                elif response.status_code == 404:
                    print(f"[ERROR] 엔드포인트를 찾을 수 없음: {url}")
                    return None
                    
                elif response.status_code == 500:
                    print(f"[ERROR] 서버 내부 오류: {response.text}")
                    
                else:
                    print(f"[ERROR] HTTP {response.status_code}: {response.text}")
                
                # 재시도 전 대기 (마지막 시도가 아닌 경우)
                if attempt < self.max_retries - 1:
                    print(f"[SERVER] {self.retry_delay}초 후 재시도...")
                    time.sleep(self.retry_delay)
                
            except requests.exceptions.Timeout:
                print(f"[ERROR] 요청 타임아웃 ({self.timeout}초)")
            except requests.exceptions.ConnectionError:
                print(f"[ERROR] 서버 연결 실패: {url}")
            except Exception as e:
                print(f"[ERROR] 요청 실패: {e}")
                
            # 재시도 전 대기 (마지막 시도가 아닌 경우)
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        print(f"[ERROR] 모든 재시도 실패: {endpoint}")
        return None
    
    def get(self, endpoint, params=None):
        """GET 요청"""
        return self._make_request('GET', endpoint, params=params)
    
    def post(self, endpoint, data=None):
        """POST 요청"""
        return self._make_request('POST', endpoint, data=data)

# 전역 클라이언트 인스턴스
_client = None

def get_client():
    """전역 서버 클라이언트 반환"""
    global _client
    if _client is None:
        _client = SimpleServerClient()
    return _client

# ============================================================================
# main.py에서 사용하는 핵심 API 함수들
# ============================================================================

def is_muid_registered(device_id):
    """기기 UID가 등록되었는지 확인
    
    Args:
        device_id (str): 기기 UID (m_uid)
        
    Returns:
        bool: 등록 여부
    """
    print(f"[API] 기기 등록 확인: {device_id}")
    
    # 기기별 사용자 조회로 등록 여부 확인
    result = get_connected_users(device_id)
    
    if result and 'users' in result:
        users = result['users']
        registered = len(users) > 0
        print(f"[API] 기기 등록 상태: {'등록됨' if registered else '미등록'} ({len(users)}명)")
        return registered
    
    print(f"[API] 기기 등록 확인 실패")
    return False

def verify_rfid_uid(uid):
    """RFID UID 인증
    
    Args:
        uid (str): RFID UID
        
    Returns:
        dict: 인증 결과 {'status': 'ok'/'error'/'unregistered', 'user': {...}}
    """
    print(f"[API] 사용자 인증 요청: {uid}")
    
    client = get_client()
    data = {"uid": uid}
    
    # 여러 가능한 엔드포인트 시도
    endpoints_to_try = [
        "verify-uid",       # 일반적인 형태
        "verify_uid",       # 언더스코어 형태
        "auth",             # 간단한 형태
        f"auth/{uid}",      # RESTful 형태
        "users/verify"      # 사용자 검증 형태
    ]
    
    for endpoint in endpoints_to_try:
        print(f"[API] 엔드포인트 시도: {endpoint}")
        result = client.post(endpoint, data)
        
        if result is not None:
            print(f"[API] ✅ 인증 요청 성공: {endpoint}")
            return result
    
    print(f"[API] ❌ 모든 인증 엔드포인트 실패")
    return None

def get_dispense_list(uid):
    """배출할 약 목록 조회
    
    Args:
        uid (str): 사용자 UID (k_uid)
        
    Returns:
        list: 배출할 약 목록 [{'medi_id': 'M001', 'dose': 2, 'medicine_name': '타이레놀'}, ...]
    """
    print(f"[API] 배출 목록 요청: {uid}")
    
    client = get_client()
    data = {"k_uid": uid}  # 서버가 기대하는 k_uid로 변경
    
    # 서버에 정의된 정확한 엔드포인트 먼저 시도
    endpoints_to_try = [
        "dispense-list",        # 서버에 정의된 정확한 엔드포인트
        "dispense_list",        # 백업 시도
        "medicines/dispense",   # 추가 시도
    ]
    
    for endpoint in endpoints_to_try:
        print(f"[API] 엔드포인트 시도: {endpoint}")
        result = client.post(endpoint, data)
        
        if result is not None:
            print(f"[API] ✅ 배출 목록 요청 성공: {endpoint}")
            
            # 응답 형태 정규화
            if isinstance(result, list):
                return result
            elif isinstance(result, dict):
                # 여러 가능한 키 확인
                for key in ['medicines', 'dispense_list', 'data', 'list']:
                    if key in result:
                        medicines = result[key]
                        if isinstance(medicines, list):
                            return medicines
                
                print(f"[API] ⚠️ 예상하지 못한 응답 형태: {result}")
                return []
    
    print(f"[API] ❌ 모든 배출 목록 엔드포인트 실패")
    return []

def report_dispense_result(uid, dispense_list):
    """배출 결과 서버에 전송
    
    Args:
        uid (str): 사용자 UID (k_uid)
        dispense_list (list): 성공한 배출 목록
        
    Returns:
        dict: 결과 응답
    """
    print(f"[API] 배출 결과 전송: {uid}, {len(dispense_list)}개")
    
    client = get_client()
    data = {
        "k_uid": uid,                    # 서버가 기대하는 k_uid로 변경
        "dispenseList": dispense_list,   # 서버가 기대하는 dispenseList로 변경
        "timestamp": time.time()
    }
    
    # 서버에 정의된 정확한 엔드포인트 먼저 시도
    endpoints_to_try = [
        "dispense-result",      # 서버에 정의된 정확한 엔드포인트
        "dispense_result",      # 백업 시도
        "result",               # 추가 시도
    ]
    
    for endpoint in endpoints_to_try:
        print(f"[API] 엔드포인트 시도: {endpoint}")
        result = client.post(endpoint, data)
        
        if result is not None:
            print(f"[API] ✅ 배출 결과 전송 성공: {endpoint}")
            return result
    
    print(f"[API] ❌ 모든 배출 결과 엔드포인트 실패")
    return None

# ============================================================================
# 추가 유틸리티 함수들
# ============================================================================

def test_server_connection():
    """서버 연결 테스트"""
    print(f"[TEST] 서버 연결 테스트: {BASE_API_URL}")
    
    client = get_client()
    
    # 기본 상태 확인 엔드포인트 시도
    test_endpoints = [
        "",           # 루트
        "health",     # 헬스체크
        "status",     # 상태
        "ping"        # 핑
    ]
    
    for endpoint in test_endpoints:
        result = client.get(endpoint)
        if result is not None:
            print(f"[TEST] ✅ 서버 연결 성공: {endpoint}")
            return True
    
    print(f"[TEST] ❌ 서버 연결 실패")
    return False

def get_machine_status(device_id):
    """기기 상태 조회 (GUI용)"""
    client = get_client()
    return client.get(f"machine-status/{device_id}")

def get_connected_users(device_id):
    """연결된 사용자 조회 (GUI용)"""
    client = get_client()
    return client.get(f"users/{device_id}")

def get_today_schedules(device_id):
    """오늘의 스케줄 조회 (GUI용)"""
    client = get_client()
    return client.get(f"schedules/{device_id}")

def confirm_user_intake(uid):
    """사용자 복용 완료 처리 (took_today = 1로 설정)
    
    Args:
        uid (str): 사용자 UID (k_uid)
        
    Returns:
        dict: 확인 결과 {'status': 'confirmed'/'already_confirmed', 'message': '...'}
    """
    print(f"[API] 복용 완료 처리: {uid}")
    
    client = get_client()
    data = {"uid": uid}
    
    # 서버에 정의된 정확한 엔드포인트
    endpoints_to_try = [
        "confirm",           # 서버에 정의된 엔드포인트
        "confirm-intake",    # 백업 시도
        "intake/confirm",    # 추가 시도
    ]
    
    for endpoint in endpoints_to_try:
        print(f"[API] 엔드포인트 시도: {endpoint}")
        result = client.post(endpoint, data)
        
        if result is not None:
            print(f"[API] ✅ 복용 완료 처리 성공: {endpoint}")
            return result
    
    print(f"[API] ❌ 모든 복용 완료 엔드포인트 실패")
    return None

def get_user_slot_mapping(device_id):
    """기기별 약물-슬롯 매핑 정보 조회
    
    Args:
        device_id (str): 기기 UID (m_uid)
        
    Returns:
        dict: 슬롯 매핑 정보 {medi_id: slot_number, ...}
    """
    print(f"[API] 슬롯 매핑 조회: {device_id}")
    
    client = get_client()
    
    # 기기 상태 조회로 슬롯 정보 가져오기
    machine_status = client.get(f"machine-status/{device_id}")
    
    if machine_status and 'slots' in machine_status:
        slot_mapping = {}
        for slot_info in machine_status['slots']:
            if slot_info.get('medi_id') and slot_info.get('slot'):
                slot_mapping[slot_info['medi_id']] = slot_info['slot']
        
        print(f"[API] ✅ 슬롯 매핑 조회 성공: {slot_mapping}")
        return slot_mapping
    else:
        print(f"[API] ❌ 슬롯 매핑 조회 실패")
        return {}

# ============================================================================
# 직접 실행시 테스트
# ============================================================================

if __name__ == "__main__":
    print("=== 서버 통신 테스트 ===")
    
    # 1. 서버 연결 테스트
    print("\n1. 서버 연결 테스트...")
    if test_server_connection():
        print("✅ 서버 연결 성공")
    else:
        print("❌ 서버 연결 실패")
        print("서버가 실행 중인지 확인하세요.")
        exit(1)
    
    # 2. 테스트 UID로 인증 테스트
    print("\n2. 인증 테스트...")
    test_uids = ["K001", "K002", "K003", "TEST001"]
    
    for uid in test_uids:
        print(f"\n테스트 UID: {uid}")
        auth_result = verify_rfid_uid(uid)
        
        if auth_result:
            print(f"✅ 인증 성공: {auth_result}")
            
            # 3. 배출 목록 테스트
            print(f"배출 목록 조회...")
            medicines = get_dispense_list(uid)
            print(f"배출 대상: {len(medicines)}개")
            
            if medicines:
                # 4. 결과 전송 테스트 (시뮬레이션)
                print(f"결과 전송 테스트...")
                fake_result = [{"medi_id": "M001", "dose": 1}]
                report_result = report_dispense_result(uid, fake_result)
                if report_result:
                    print(f"✅ 결과 전송 성공")
                else:
                    print(f"❌ 결과 전송 실패")
            
            break  # 성공한 UID 하나만 테스트
        else:
            print(f"❌ 인증 실패")
    
    print("\n=== 테스트 완료 ===")