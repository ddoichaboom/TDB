# utils/server_request.py (AWS EC2 연동 및 라즈베리파이 최적화)
import requests
import json
import time
import threading
import queue
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import ssl
import socket
from config import (
    BASE_API_URL, GUI_CONFIG, DEBUG_CONFIG, NETWORK_CONFIG, 
    SECURITY_CONFIG, SYSTEM_PATHS
)
from utils.logger import log_info, log_error, log_warning, log_api_call, performance_timer

class EnhancedServerRequestManager:
    """AWS EC2 연동 및 라즈베리파이 최적화된 서버 요청 관리자"""
    
    def __init__(self):
        self.primary_server = NETWORK_CONFIG['primary_server']
        self.backup_server = NETWORK_CONFIG['backup_server']
        self.current_server = self.primary_server
        self.fallback_mode = NETWORK_CONFIG['fallback_mode']
        
        # 세션 및 연결 관리
        self.session = self._create_enhanced_session()
        self.backup_session = self._create_enhanced_session()
        self.timeout = GUI_CONFIG['request_timeout']
        self.max_retries = GUI_CONFIG['max_retry_count']
        self.executor = ThreadPoolExecutor(max_workers=GUI_CONFIG['max_workers'])
        
        # 연결 상태 관리
        self.connection_status = {
            'primary_online': True,
            'backup_online': True,
            'last_primary_check': 0,
            'last_backup_check': 0,
            'current_server_type': 'primary',
            'failover_count': 0,
            'total_requests': 0,
            'failed_requests': 0
        }
        
        # 캐시 설정
        self._cache = {}
        self._cache_lock = threading.RLock()
        self.cache_duration = GUI_CONFIG['cache_duration']
        
        # 오프라인 데이터 저장
        self.offline_data_path = Path(SYSTEM_PATHS['base_dir']) / 'offline_data.json'
        self.offline_queue_path = Path(SYSTEM_PATHS['base_dir']) / 'offline_queue.json'
        self.offline_queue = []
        
        # SSL/TLS 설정
        self.ssl_context = self._create_ssl_context()
        
        # API 키 로드
        self.api_key = self._load_api_key()
        
        # 자동 재연결 설정
        self.auto_reconnect = NETWORK_CONFIG['auto_reconnect']
        self.reconnect_thread = None
        self.reconnect_running = False
        
        # 성능 모니터링
        self.performance_stats = {
            'request_times': [],
            'error_rates': {},
            'server_response_times': {'primary': [], 'backup': []},
            'cache_hit_rate': 0,
            'last_stats_reset': time.time()
        }
        
        self.start_background_tasks()
        log_info("Enhanced 서버 요청 매니저 초기화 완료", "SERVER")
    
    def _create_enhanced_session(self):
        """향상된 세션 생성 (AWS EC2 최적화)"""
        session = requests.Session()
        
        # AWS 최적화된 재시도 전략
        retry_strategy = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504, 520, 521, 522, 523, 524],
            method_whitelist=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"],
            raise_on_status=False
        )
        
        # 연결 풀 설정 (라즈베리파이 리소스 고려)
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=2,  # 라즈베리파이용 제한
            pool_maxsize=4,
            pool_block=True
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 기본 헤더 설정
        session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'RaspberryPi-Dispenser/2.0',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        
        # API 키 헤더 추가
        if self.api_key:
            session.headers.update({'Authorization': f'Bearer {self.api_key}'})
        
        return session
    
    def _create_ssl_context(self):
        """SSL 컨텍스트 생성"""
        try:
            context = ssl.create_default_context()
            
            # 인증서 파일이 있다면 로드
            cert_path = Path(SECURITY_CONFIG.get('ssl_cert_path', ''))
            if cert_path.exists():
                cert_file = cert_path / 'server.crt'
                if cert_file.exists():
                    context.load_verify_locations(str(cert_file))
                    log_info("SSL 인증서 로드 완료", "SSL")
            
            # SSL 검증 설정
            if not NETWORK_CONFIG.get('ssl_verify', True):
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                log_warning("SSL 검증이 비활성화되어 있습니다", "SSL")
            
            return context
            
        except Exception as e:
            log_error(f"SSL 컨텍스트 생성 실패: {e}", "SSL")
            return None
    
    def _load_api_key(self):
        """API 키 로드"""
        try:
            api_key_file = Path(SECURITY_CONFIG.get('api_key_file', ''))
            if api_key_file.exists():
                with open(api_key_file, 'r') as f:
                    api_key = f.read().strip()
                log_info("API 키 로드 완료", "AUTH")
                return api_key
            else:
                log_warning("API 키 파일이 없습니다", "AUTH")
                return None
        except Exception as e:
            log_error(f"API 키 로드 실패: {e}", "AUTH")
            return None
    
    def start_background_tasks(self):
        """백그라운드 작업 시작"""
        # 자동 재연결 시작
        if self.auto_reconnect:
            self.start_auto_reconnect()
        
        # 오프라인 큐 처리 시작
        self.start_offline_queue_processor()
        
        # 성능 모니터링 시작
        self.start_performance_monitoring()
    
    def start_auto_reconnect(self):
        """자동 재연결 스레드 시작"""
        def reconnect_loop():
            self.reconnect_running = True
            log_info("자동 재연결 스레드 시작", "RECONNECT")
            
            while self.reconnect_running:
                try:
                    # 서버 상태 확인
                    self.check_server_health()
                    
                    # 필요시 서버 전환
                    self.manage_server_failover()
                    
                    # 재연결 간격 대기
                    time.sleep(NETWORK_CONFIG['reconnect_interval'])
                    
                except Exception as e:
                    log_error(f"자동 재연결 오류: {e}", "RECONNECT")
                    time.sleep(60)
        
        self.reconnect_thread = threading.Thread(target=reconnect_loop, daemon=True)
        self.reconnect_thread.start()
    
    def start_offline_queue_processor(self):
        """오프라인 큐 처리기 시작"""
        def process_offline_queue():
            while True:
                try:
                    if self.offline_queue and self.is_online():
                        self.process_queued_requests()
                    time.sleep(30)  # 30초마다 체크
                except Exception as e:
                    log_error(f"오프라인 큐 처리 오류: {e}", "OFFLINE")
                    time.sleep(60)
        
        thread = threading.Thread(target=process_offline_queue, daemon=True)
        thread.start()
    
    def start_performance_monitoring(self):
        """성능 모니터링 시작"""
        def monitor_performance():
            while True:
                try:
                    # 성능 통계 업데이트
                    self.update_performance_stats()
                    
                    # 1시간마다 통계 로그
                    if int(time.time()) % 3600 == 0:
                        self.log_performance_stats()
                    
                    time.sleep(60)  # 1분마다 체크
                except Exception as e:
                    log_error(f"성능 모니터링 오류: {e}", "PERFORMANCE")
                    time.sleep(300)
        
        thread = threading.Thread(target=monitor_performance, daemon=True)
        thread.start()
    
    def check_server_health(self):
        """서버 건강 상태 확인"""
        current_time = time.time()
        
        # Primary 서버 체크
        if current_time - self.connection_status['last_primary_check'] > 60:
            self.connection_status['primary_online'] = self._ping_server(self.primary_server)
            self.connection_status['last_primary_check'] = current_time
        
        # Backup 서버 체크
        if current_time - self.connection_status['last_backup_check'] > 60:
            self.connection_status['backup_online'] = self._ping_server(self.backup_server)
            self.connection_status['last_backup_check'] = current_time
    
    def _ping_server(self, server_url):
        """서버 핑 테스트"""
        try:
            health_endpoint = f"{server_url}/health"
            response = requests.get(health_endpoint, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def manage_server_failover(self):
        """서버 장애조치 관리"""
        primary_online = self.connection_status['primary_online']
        backup_online = self.connection_status['backup_online']
        current_type = self.connection_status['current_server_type']
        
        # Primary 서버 복구 시 복귀
        if current_type == 'backup' and primary_online:
            log_info("Primary 서버 복구 - 복귀", "FAILOVER")
            self.current_server = self.primary_server
            self.connection_status['current_server_type'] = 'primary'
            return
        
        # Primary 서버 장애 시 Backup으로 전환
        if current_type == 'primary' and not primary_online and backup_online:
            log_warning("Primary 서버 장애 - Backup 서버로 전환", "FAILOVER")
            self.current_server = self.backup_server
            self.connection_status['current_server_type'] = 'backup'
            self.connection_status['failover_count'] += 1
            return
        
        # 모든 서버 장애 시 오프라인 모드
        if not primary_online and not backup_online:
            if self.fallback_mode:
                log_error("모든 서버 장애 - 오프라인 모드", "FAILOVER")
            else:
                log_error("모든 서버 장애 - 서비스 중단", "FAILOVER")
    
    def is_online(self):
        """온라인 상태 확인"""
        return (self.connection_status['primary_online'] or 
                self.connection_status['backup_online'])
    
    def _get_cache_key(self, endpoint, params=None, method='GET'):
        """캐시 키 생성"""
        key = f"{method}_{endpoint}"
        if params:
            key += "_" + str(hash(frozenset(params.items()) if isinstance(params, dict) else params))
        return key
    
    def _is_cache_valid(self, cache_entry):
        """캐시 유효성 검사"""
        if not cache_entry:
            return False
        return (time.time() - cache_entry['timestamp']) < self.cache_duration
    
    def _get_from_cache(self, cache_key):
        """캐시에서 데이터 조회"""
        with self._cache_lock:
            cache_entry = self._cache.get(cache_key)
            if self._is_cache_valid(cache_entry):
                log_info(f"캐시 히트: {cache_key}", "CACHE")
                self.performance_stats['cache_hit_rate'] += 1
                return cache_entry['data']
            return None
    
    def _set_cache(self, cache_key, data):
        """캐시에 데이터 저장"""
        with self._cache_lock:
            self._cache[cache_key] = {
                'data': data,
                'timestamp': time.time()
            }
            # 캐시 크기 제한 (라즈베리파이 메모리 고려)
            if len(self._cache) > 50:
                oldest_key = min(self._cache.keys(), 
                               key=lambda k: self._cache[k]['timestamp'])
                del self._cache[oldest_key]
    
    def _make_request(self, method, endpoint, use_backup=False, **kwargs):
        """실제 HTTP 요청 수행"""
        server_url = self.backup_server if use_backup else self.current_server
        url = f"{server_url}/{endpoint.lstrip('/')}"
        
        start_time = time.time()
        
        try:
            # 세션 선택
            session = self.backup_session if use_backup else self.session
            
            # SSL 컨텍스트 적용
            if self.ssl_context and url.startswith('https'):
                kwargs['verify'] = self.ssl_context
            
            with performance_timer(f"api_{method.lower()}_{endpoint}"):
                response = session.request(
                    method=method,
                    url=url,
                    timeout=self.timeout,
                    **kwargs
                )
            
            response_time = (time.time() - start_time) * 1000
            
            # 성능 통계 업데이트
            server_type = 'backup' if use_backup else 'primary'
            self.performance_stats['server_response_times'][server_type].append(response_time)
            
            # 응답 시간이 너무 길면 경고
            if response_time > 5000:  # 5초
                log_warning(f"느린 응답: {endpoint} ({response_time:.0f}ms)", "PERFORMANCE")
            
            log_api_call(endpoint, method, response.status_code, response_time)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if DEBUG_CONFIG['verbose_api_logs']:
                        log_info(f"API 응답: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}", "API")
                    return data
                except json.JSONDecodeError as e:
                    log_error(f"JSON 파싱 실패: {e}", "API")
                    return None
            elif response.status_code == 401:
                log_error("인증 실패 - API 키 확인 필요", "AUTH")
                return None
            elif response.status_code == 429:
                log_warning("Rate limit 도달 - 요청 제한", "API")
                time.sleep(2)  # 2초 대기 후 재시도
                return None
            else:
                log_warning(f"API 오류 응답: {response.status_code} - {response.text}", "API")
                return None
                
        except requests.exceptions.Timeout:
            log_error(f"API 타임아웃: {endpoint}", "API")
            self.performance_stats['error_rates']['timeout'] = self.performance_stats['error_rates'].get('timeout', 0) + 1
            return None
        except requests.exceptions.ConnectionError:
            log_error(f"연결 오류: {endpoint}", "API")
            self.performance_stats['error_rates']['connection'] = self.performance_stats['error_rates'].get('connection', 0) + 1
            return None
        except requests.exceptions.SSLError as e:
            log_error(f"SSL 오류: {endpoint} - {e}", "SSL")
            return None
        except Exception as e:
            log_error(f"API 요청 실패: {endpoint} - {e}", "API", exc_info=True)
            self.performance_stats['error_rates']['general'] = self.performance_stats['error_rates'].get('general', 0) + 1
            return None
    
    def get(self, endpoint, use_cache=True, **kwargs):
        """GET 요청"""
        self.connection_status['total_requests'] += 1
        
        cache_key = self._get_cache_key(endpoint, kwargs.get('params'), 'GET')
        
        # 캐시 확인
        if use_cache:
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                return cached_data
        
        # 온라인 상태가 아니면 오프라인 데이터 반환
        if not self.is_online():
            offline_data = self.get_offline_data(endpoint)
            if offline_data:
                log_info(f"오프라인 데이터 반환: {endpoint}", "OFFLINE")
                return offline_data
            return None
        
        # 새로운 요청
        data = self._make_request('GET', endpoint, **kwargs)
        
        # 실패 시 백업 서버 시도
        if data is None and self.connection_status['backup_online']:
            log_info(f"백업 서버로 재시도: {endpoint}", "BACKUP")
            data = self._make_request('GET', endpoint, use_backup=True, **kwargs)
        
        # 성공한 경우 캐시 및 오프라인 데이터에 저장
        if data:
            if use_cache:
                self._set_cache(cache_key, data)
            self.save_offline_data(endpoint, data)
        else:
            self.connection_status['failed_requests'] += 1
        
        return data
    
    def post(self, endpoint, **kwargs):
        """POST 요청"""
        self.connection_status['total_requests'] += 1
        
        # 온라인 상태가 아니면 큐에 저장
        if not self.is_online():
            if self.fallback_mode:
                self.queue_offline_request('POST', endpoint, kwargs)
                log_info(f"요청을 오프라인 큐에 저장: {endpoint}", "OFFLINE")
                return {'status': 'queued', 'message': '오프라인 모드 - 요청이 큐에 저장됨'}
            return None
        
        # 새로운 요청
        data = self._make_request('POST', endpoint, **kwargs)
        
        # 실패 시 백업 서버 시도
        if data is None and self.connection_status['backup_online']:
            log_info(f"백업 서버로 재시도: {endpoint}", "BACKUP")
            data = self._make_request('POST', endpoint, use_backup=True, **kwargs)
        
        # 실패한 경우 오프라인 큐에 저장
        if data is None and self.fallback_mode:
            self.queue_offline_request('POST', endpoint, kwargs)
            self.connection_status['failed_requests'] += 1
            return {'status': 'queued', 'message': '요청 실패 - 큐에 저장됨'}
        
        return data
    
    def queue_offline_request(self, method, endpoint, kwargs):
        """오프라인 요청 큐에 저장"""
        try:
            request_data = {
                'method': method,
                'endpoint': endpoint,
                'kwargs': kwargs,
                'timestamp': time.time(),
                'retry_count': 0
            }
            
            self.offline_queue.append(request_data)
            
            # 큐를 파일에 저장
            self.save_offline_queue()
            
        except Exception as e:
            log_error(f"오프라인 요청 큐 저장 실패: {e}", "OFFLINE")
    
    def process_queued_requests(self):
        """큐에 저장된 요청들 처리"""
        try:
            if not self.offline_queue:
                return
            
            log_info(f"오프라인 큐 처리 시작: {len(self.offline_queue)}개 요청", "OFFLINE")
            
            processed_requests = []
            
            for request_data in self.offline_queue[:]:
                try:
                    method = request_data['method']
                    endpoint = request_data['endpoint']
                    kwargs = request_data['kwargs']
                    
                    # 요청 실행
                    if method == 'POST':
                        result = self._make_request('POST', endpoint, **kwargs)
                    elif method == 'GET':
                        result = self._make_request('GET', endpoint, **kwargs)
                    else:
                        continue
                    
                    if result:
                        processed_requests.append(request_data)
                        log_info(f"큐 요청 처리 완료: {endpoint}", "OFFLINE")
                    else:
                        # 재시도 카운트 증가
                        request_data['retry_count'] += 1
                        if request_data['retry_count'] >= 3:
                            processed_requests.append(request_data)
                            log_warning(f"큐 요청 최대 재시도 초과: {endpoint}", "OFFLINE")
                
                except Exception as e:
                    log_error(f"큐 요청 처리 오류: {e}", "OFFLINE")
                    processed_requests.append(request_data)
            
            # 처리된 요청들 제거
            for request_data in processed_requests:
                if request_data in self.offline_queue:
                    self.offline_queue.remove(request_data)
            
            # 큐 파일 업데이트
            self.save_offline_queue()
            
            if processed_requests:
                log_info(f"오프라인 큐 처리 완료: {len(processed_requests)}개", "OFFLINE")
                
        except Exception as e:
            log_error(f"큐 처리 오류: {e}", "OFFLINE")
    
    def save_offline_data(self, endpoint, data):
        """오프라인 데이터 저장"""
        try:
            offline_data = {}
            
            # 기존 오프라인 데이터 로드
            if self.offline_data_path.exists():
                with open(self.offline_data_path, 'r') as f:
                    offline_data = json.load(f)
            
            # 새 데이터 추가
            offline_data[endpoint] = {
                'data': data,
                'timestamp': time.time()
            }
            
            # 파일에 저장
            with open(self.offline_data_path, 'w') as f:
                json.dump(offline_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            log_error(f"오프라인 데이터 저장 실패: {e}", "OFFLINE")
    
    def get_offline_data(self, endpoint):
        """오프라인 데이터 조회"""
        try:
            if not self.offline_data_path.exists():
                return None
            
            with open(self.offline_data_path, 'r') as f:
                offline_data = json.load(f)
            
            if endpoint in offline_data:
                entry = offline_data[endpoint]
                # 24시간 이내 데이터만 사용
                if time.time() - entry['timestamp'] < 86400:
                    return entry['data']
            
            return None
            
        except Exception as e:
            log_error(f"오프라인 데이터 조회 실패: {e}", "OFFLINE")
            return None
    
    def save_offline_queue(self):
        """오프라인 큐 파일에 저장"""
        try:
            with open(self.offline_queue_path, 'w') as f:
                json.dump(self.offline_queue, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log_error(f"오프라인 큐 저장 실패: {e}", "OFFLINE")
    
    def load_offline_queue(self):
        """오프라인 큐 파일에서 로드"""
        try:
            if self.offline_queue_path.exists():
                with open(self.offline_queue_path, 'r') as f:
                    self.offline_queue = json.load(f)
                log_info(f"오프라인 큐 로드: {len(self.offline_queue)}개", "OFFLINE")
        except Exception as e:
            log_error(f"오프라인 큐 로드 실패: {e}", "OFFLINE")
            self.offline_queue = []
    
    def update_performance_stats(self):
        """성능 통계 업데이트"""
        try:
            # 응답 시간 리스트 크기 제한
            for server_type in self.performance_stats['server_response_times']:
                times = self.performance_stats['server_response_times'][server_type]
                if len(times) > 100:
                    self.performance_stats['server_response_times'][server_type] = times[-50:]
            
            # 캐시 히트율 계산
            total_requests = self.connection_status['total_requests']
            if total_requests > 0:
                self.performance_stats['cache_hit_rate'] = (
                    self.performance_stats['cache_hit_rate'] / total_requests * 100
                )
            
        except Exception as e:
            log_error(f"성능 통계 업데이트 오류: {e}", "PERFORMANCE")
    
    def log_performance_stats(self):
        """성능 통계 로깅"""
        try:
            stats = self.get_performance_summary()
            log_info(f"성능 통계: {stats}", "PERFORMANCE")
        except Exception as e:
            log_error(f"성능 통계 로깅 오류: {e}", "PERFORMANCE")
    
    def get_performance_summary(self):
        """성능 요약 반환"""
        try:
            total_requests = self.connection_status['total_requests']
            failed_requests = self.connection_status['failed_requests']
            success_rate = ((total_requests - failed_requests) / max(total_requests, 1)) * 100
            
            # 평균 응답 시간 계산
            primary_times = self.performance_stats['server_response_times']['primary']
            backup_times = self.performance_stats['server_response_times']['backup']
            
            avg_primary = sum(primary_times) / len(primary_times) if primary_times else 0
            avg_backup = sum(backup_times) / len(backup_times) if backup_times else 0
            
            return {
                'total_requests': total_requests,
                'success_rate': f"{success_rate:.1f}%",
                'failover_count': self.connection_status['failover_count'],
                'current_server': self.connection_status['current_server_type'],
                'avg_response_time_primary': f"{avg_primary:.0f}ms",
                'avg_response_time_backup': f"{avg_backup:.0f}ms",
                'cache_hit_rate': f"{self.performance_stats['cache_hit_rate']:.1f}%",
                'offline_queue_size': len(self.offline_queue),
                'cache_size': len(self._cache)
            }
        except Exception as e:
            log_error(f"성능 요약 생성 오류: {e}", "PERFORMANCE")
            return {}
    
    def clear_cache(self):
        """캐시 초기화"""
        with self._cache_lock:
            self._cache.clear()
            log_info("캐시 초기화 완료", "CACHE")
    
    def cleanup(self):
        """정리 작업"""
        try:
            log_info("서버 요청 매니저 정리 시작", "SERVER")
            
            # 재연결 스레드 중지
            self.reconnect_running = False
            if self.reconnect_thread and self.reconnect_thread.is_alive():
                self.reconnect_thread.join(timeout=5)
            
            # 마지막 큐 처리 시도
            if self.offline_queue and self.is_online():
                self.process_queued_requests()
            
            # 세션 정리
            self.session.close()
            self.backup_session.close()
            
            # 스레드 풀 종료
            self.executor.shutdown(wait=False)
            
            # 최종 통계 로그
            self.log_performance_stats()
            
            log_info("서버 요청 매니저 정리 완료", "SERVER")
            
        except Exception as e:
            log_error(f"서버 요청 매니저 정리 오류: {e}", "SERVER")


# 전역 인스턴스
_request_manager = None

def get_request_manager():
    """전역 요청 매니저 반환"""
    global _request_manager
    if _request_manager is None:
        _request_manager = EnhancedServerRequestManager()
        # 시작 시 오프라인 큐 로드
        _request_manager.load_offline_queue()
    return _request_manager

# 기존 함수들 (호환성 유지)
def is_muid_registered(muid):
    """기기 UID가 등록되었는지 확인"""
    try:
        manager = get_request_manager()
        data = manager.get(f"users/by-muid/{muid}")
        if data and 'users' in data:
            return len(data['users']) > 0
        return False
    except Exception as e:
        log_error(f"is_muid_registered 오류: {e}", "API")
        return False

def get_machine_status(muid):
    """기기 상태 조회"""
    try:
        manager = get_request_manager()
        return manager.get(f"machine-status/{muid}")
    except Exception as e:
        log_error(f"machine-status 오류: {e}", "API")
        return None

def get_connected_users(muid):
    """연결된 사용자들 조회"""
    try:
        manager = get_request_manager()
        return manager.get(f"users/by-muid/{muid}")
    except Exception as e:
        log_error(f"users/by-muid 오류: {e}", "API")
        return None

def get_today_schedules(muid):
    """오늘의 스케줄 조회"""
    try:
        manager = get_request_manager()
        return manager.get(f"schedules/today/{muid}")
    except Exception as e:
        log_error(f"schedules/today 오류: {e}", "API")
        return None

def verify_rfid_uid(uid):
    """RFID UID 인증"""
    try:
        manager = get_request_manager()
        return manager.post("verify-uid", json={"uid": uid})
    except Exception as e:
        log_error(f"verify-uid 오류: {e}", "API")
        return None

def get_dispense_list(k_uid):
    """배출할 약 목록 조회"""
    try:
        manager = get_request_manager()
        data = manager.post("dispense-list", json={"k_uid": k_uid})
        return data if data else []
    except Exception as e:
        log_error(f"dispense-list 오류: {e}", "API")
        return []

def report_dispense_result(k_uid, dispense_list):
    """약 배출 결과 보고"""
    try:
        manager = get_request_manager()
        return manager.post("dispense-result", 
                          json={"k_uid": k_uid, "dispenseList": dispense_list})
    except Exception as e:
        log_error(f"dispense-result 오류: {e}", "API")
        return None

def confirm_intake(uid):
    """복용 확인 처리"""
    try:
        manager = get_request_manager()
        return manager.post("confirm", json={"uid": uid})
    except Exception as e:
        log_error(f"confirm 오류: {e}", "API")
        return None

def get_all_dashboard_data(muid):
    """대시보드용 모든 데이터를 병렬로 조회"""
    try:
        manager = get_request_manager()
        
        # 병렬 요청 실행
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                'users': executor.submit(get_connected_users, muid),
                'machine_status': executor.submit(get_machine_status, muid),
                'schedules': executor.submit(get_today_schedules, muid)
            }
            
            results = {}
            for key, future in futures.items():
                try:
                    results[key] = future.result(timeout=10)
                except Exception as e:
                    log_error(f"병렬 요청 실패 ({key}): {e}", "API")
                    results[key] = None
            
            return results
            
    except Exception as e:
        log_error(f"get_all_dashboard_data 오류: {e}", "API")
        return {}

def health_check():
    """서버 연결 상태 확인"""
    try:
        manager = get_request_manager()
        start_time = time.time()
        
        # 간단한 헬스체크 엔드포인트 호출
        result = manager.get("health", use_cache=False)
        
        latency = (time.time() - start_time) * 1000
        
        return {
            'status': 'ok' if result else 'error',
            'latency': latency,
            'timestamp': time.time(),
            'server': manager.connection_status['current_server_type']
        }
    except Exception as e:
        log_error(f"헬스체크 실패: {e}", "HEALTH")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': time.time()
        }

def clear_request_cache():
    """요청 캐시 초기화"""
    manager = get_request_manager()
    manager.clear_cache()

def get_network_stats():
    """네트워크 통계 반환"""
    manager = get_request_manager()
    return manager.get_performance_summary()

def cleanup_request_manager():
    """요청 매니저 정리"""
    global _request_manager
    if _request_manager:
        _request_manager.cleanup()
        _request_manager = None