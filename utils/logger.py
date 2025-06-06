# utils/logger.py (라즈베리파이 최적화 로깅 시스템)
import logging
import logging.handlers
import os
import sys
import time
import threading
import json
import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from queue import Queue, Empty
from config import LOGGING_CONFIG, DEBUG_CONFIG, SYSTEM_PATHS

class RaspberryPiLogger:
    """라즈베리파이 최적화 로거 클래스"""
    
    def __init__(self):
        self._initialized = False
        self.performance_metrics = {}
        self.log_queue = Queue()
        self.background_thread = None
        self.running = False
        
        # 로그 레벨 매핑
        self.level_mapping = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        
        # 카테고리별 통계
        self.category_stats = {
            'GENERAL': {'count': 0, 'last_logged': None},
            'SYSTEM': {'count': 0, 'last_logged': None},
            'HARDWARE': {'count': 0, 'last_logged': None},
            'NETWORK': {'count': 0, 'last_logged': None},
            'API': {'count': 0, 'last_logged': None},
            'GUI': {'count': 0, 'last_logged': None},
            'RFID': {'count': 0, 'last_logged': None},
            'AUDIO': {'count': 0, 'last_logged': None},
            'PERFORMANCE': {'count': 0, 'last_logged': None}
        }
        
        # 로그 파일 경로 설정
        self.setup_log_paths()
        self.setup_logger()
        self.start_background_logging()
        
        self._initialized = True
    
    def setup_log_paths(self):
        """로그 파일 경로 설정"""
        try:
            # ✅ config.py의 SYSTEM_PATHS 사용
            from config import SYSTEM_PATHS
            log_dir = Path(SYSTEM_PATHS['logs_dir'])
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # 로그 파일 경로들
            self.log_files = {
                'main': log_dir / 'dispenser.log',
                'error': log_dir / 'error.log',
                'performance': log_dir / 'performance.log',
                'hardware': log_dir / 'hardware.log',
                'network': log_dir / 'network.log',
                'audit': log_dir / 'audit.log'
            }
            
            # 권한 설정 (라즈베리파이용)
            try:
                os.chmod(log_dir, 0o755)
                for log_file in self.log_files.values():
                    if log_file.exists():
                        os.chmod(log_file, 0o644)
            except:
                pass  # 권한 설정 실패는 무시
                
        except Exception as e:
            print(f"로그 경로 설정 실패: {e}")
            # 폴백: 현재 디렉토리 사용
            log_dir = Path.cwd() / 'logs'
            log_dir.mkdir(exist_ok=True)
            self.log_files = {
                'main': log_dir / 'dispenser.log',
                'error': log_dir / 'error.log',
                'performance': log_dir / 'performance.log',
                'hardware': log_dir / 'hardware.log',
                'network': log_dir / 'network.log',
                'audit': log_dir / 'audit.log'
            }
    
    def setup_logger(self):
        """로거 설정"""
        try:
            # 메인 로거 설정
            self.logger = logging.getLogger('dispenser')
            self.logger.setLevel(self.level_mapping[LOGGING_CONFIG['level']])
            
            # 기존 핸들러 제거
            for handler in self.logger.handlers[:]:
                self.logger.removeHandler(handler)
            
            # 포매터 생성
            self.formatter = self.create_formatter()
            
            # 콘솔 핸들러 (라즈베리파이는 SSH 접속이므로 중요)
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.level_mapping[LOGGING_CONFIG['level']])
            console_handler.setFormatter(self.formatter)
            self.logger.addHandler(console_handler)
            
            # 파일 핸들러들 설정
            if LOGGING_CONFIG['file_enabled']:
                self.setup_file_handlers()
            
            # systemd journal 핸들러 (라즈베리파이 서비스용)
            try:
                from systemd import journal
                journal_handler = journal.JournalHandler(SYSLOG_IDENTIFIER='dispenser')
                journal_handler.setFormatter(self.formatter)
                self.logger.addHandler(journal_handler)
                print("systemd journal 핸들러 추가됨")
            except ImportError:
                print("systemd journal 사용 불가 - 건너뛰기")
            
            # 로그 레벨 정보 출력
            print(f"로그 시스템 초기화 완료 - 레벨: {LOGGING_CONFIG['level']}")
            
        except Exception as e:
            print(f"로거 설정 실패: {e}")
            # 기본 로거라도 생성
            self.logger = logging.getLogger('dispenser')
            self.logger.setLevel(logging.INFO)
    
    def create_formatter(self):
        """로그 포매터 생성"""
        # 라즈베리파이 특화 포매터
        format_string = '[%(levelname)s] %(asctime)s | %(category)s | %(message)s'
        
        class CategoryFormatter(logging.Formatter):
            def format(self, record):
                # 카테고리 정보가 없으면 기본값 설정
                if not hasattr(record, 'category'):
                    record.category = 'GENERAL'
                return super().format(record)
        
        return CategoryFormatter(
            format_string,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def setup_file_handlers(self):
        """파일 핸들러들 설정"""
        try:
            # 메인 로그 파일 (로테이팅)
            main_handler = logging.handlers.RotatingFileHandler(
                self.log_files['main'],
                maxBytes=LOGGING_CONFIG['max_file_size'],
                backupCount=LOGGING_CONFIG['backup_count'],
                encoding='utf-8'
            )
            main_handler.setFormatter(self.formatter)
            self.logger.addHandler(main_handler)
            
            # 에러 전용 로그 파일
            error_handler = logging.handlers.RotatingFileHandler(
                self.log_files['error'],
                maxBytes=2 * 1024 * 1024,  # 2MB
                backupCount=3,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(self.formatter)
            self.logger.addHandler(error_handler)
            
            # 성능 로그 파일 (별도)
            if DEBUG_CONFIG.get('show_performance_metrics', False):
                self.perf_logger = logging.getLogger('dispenser.performance')
                self.perf_logger.setLevel(logging.INFO)
                
                perf_handler = logging.handlers.RotatingFileHandler(
                    self.log_files['performance'],
                    maxBytes=5 * 1024 * 1024,  # 5MB
                    backupCount=2,
                    encoding='utf-8'
                )
                perf_handler.setFormatter(self.formatter)
                self.perf_logger.addHandler(perf_handler)
            
            # 하드웨어 로그 파일
            self.hw_logger = logging.getLogger('dispenser.hardware')
            self.hw_logger.setLevel(logging.INFO)
            
            hw_handler = logging.handlers.RotatingFileHandler(
                self.log_files['hardware'],
                maxBytes=3 * 1024 * 1024,  # 3MB
                backupCount=2,
                encoding='utf-8'
            )
            hw_handler.setFormatter(self.formatter)
            self.hw_logger.addHandler(hw_handler)
            
            print("파일 핸들러 설정 완료")
            
        except Exception as e:
            print(f"파일 핸들러 설정 실패: {e}")
    
    def start_background_logging(self):
        """백그라운드 로깅 스레드 시작"""
        try:
            self.running = True
            self.background_thread = threading.Thread(
                target=self._background_log_worker,
                daemon=True,
                name="LogWorker"
            )
            self.background_thread.start()
            print("백그라운드 로깅 스레드 시작됨")
        except Exception as e:
            print(f"백그라운드 로깅 시작 실패: {e}")
    
    def _background_log_worker(self):
        """백그라운드 로그 처리"""
        while self.running:
            try:
                # 큐에서 로그 메시지 처리
                try:
                    log_entry = self.log_queue.get(timeout=1)
                    self._process_log_entry(log_entry)
                    self.log_queue.task_done()
                except Empty:
                    continue
                
                # 주기적 유지보수 작업
                if int(time.time()) % 3600 == 0:  # 1시간마다
                    self._perform_maintenance()
                
            except Exception as e:
                print(f"백그라운드 로깅 오류: {e}")
                time.sleep(5)
    
    def _process_log_entry(self, log_entry):
        """로그 엔트리 처리"""
        try:
            level = log_entry['level']
            message = log_entry['message']
            category = log_entry['category']
            extra = log_entry.get('extra', {})
            
            # 카테고리 통계 업데이트
            if category in self.category_stats:
                self.category_stats[category]['count'] += 1
                self.category_stats[category]['last_logged'] = datetime.now()
            
            # 로그 레코드 생성
            record = logging.LogRecord(
                name='dispenser',
                level=level,
                pathname='',
                lineno=0,
                msg=message,
                args=(),
                exc_info=None
            )
            record.category = category
            
            # 로거에 전달
            self.logger.handle(record)
            
            # 특별한 카테고리 처리
            if category == 'HARDWARE' and hasattr(self, 'hw_logger'):
                self.hw_logger.handle(record)
            elif category == 'PERFORMANCE' and hasattr(self, 'perf_logger'):
                self.perf_logger.handle(record)
            
        except Exception as e:
            print(f"로그 엔트리 처리 오류: {e}")
    
    def _perform_maintenance(self):
        """로그 유지보수 작업"""
        try:
            # 오래된 로그 파일 압축
            self._compress_old_logs()
            
            # 디스크 공간 확인 및 정리
            self._check_disk_space()
            
            # 성능 메트릭 정리
            self._cleanup_performance_metrics()
            
        except Exception as e:
            print(f"로그 유지보수 오류: {e}")
    
    def _compress_old_logs(self):
        """오래된 로그 파일 압축"""
        try:
            log_dir = Path(SYSTEM_PATHS['logs_dir'])
            cutoff_date = datetime.now() - timedelta(days=1)
            
            for log_file in log_dir.glob('*.log.*'):
                if log_file.stat().st_mtime < cutoff_date.timestamp():
                    if not str(log_file).endswith('.gz'):
                        # gzip 압축
                        with open(log_file, 'rb') as f_in:
                            with gzip.open(f"{log_file}.gz", 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        
                        log_file.unlink()  # 원본 파일 삭제
                        print(f"로그 파일 압축: {log_file}")
        except Exception as e:
            print(f"로그 압축 오류: {e}")
    
    def _check_disk_space(self):
        """디스크 공간 확인"""
        try:
            log_dir = Path(SYSTEM_PATHS['logs_dir'])
            
            # 디스크 사용량 확인
            import shutil
            total, used, free = shutil.disk_usage(log_dir)
            
            # 90% 이상 사용 시 오래된 로그 삭제
            if (used / total) > 0.9:
                self._cleanup_old_logs()
                print("디스크 공간 부족으로 오래된 로그 삭제")
                
        except Exception as e:
            print(f"디스크 공간 확인 오류: {e}")
    
    def _cleanup_old_logs(self):
        """오래된 로그 파일 삭제"""
        try:
            log_dir = Path(SYSTEM_PATHS['logs_dir'])
            cutoff_date = datetime.now() - timedelta(days=7)
            
            for log_file in log_dir.glob('*.log.*'):
                if log_file.stat().st_mtime < cutoff_date.timestamp():
                    log_file.unlink()
                    print(f"오래된 로그 파일 삭제: {log_file}")
                    
        except Exception as e:
            print(f"오래된 로그 삭제 오류: {e}")
    
    def _cleanup_performance_metrics(self):
        """성능 메트릭 정리"""
        try:
            # 오래된 성능 데이터 삭제
            cutoff_time = time.time() - 86400  # 24시간
            
            for operation in list(self.performance_metrics.keys()):
                metrics = self.performance_metrics[operation]
                if metrics.get('last_updated', 0) < cutoff_time:
                    del self.performance_metrics[operation]
                    
        except Exception as e:
            print(f"성능 메트릭 정리 오류: {e}")
    
    def log(self, level, message, category="GENERAL", **kwargs):
        """로그 메시지 추가"""
        try:
            log_entry = {
                'level': self.level_mapping.get(level, logging.INFO),
                'message': message,
                'category': category,
                'timestamp': time.time(),
                'extra': kwargs
            }
            
            # 큐에 추가 (논블로킹)
            try:
                self.log_queue.put_nowait(log_entry)
            except:
                # 큐가 가득 찬 경우 직접 처리
                self._process_log_entry(log_entry)
                
        except Exception as e:
            print(f"로그 추가 오류: {e}")
    
    def info(self, message, category="GENERAL"):
        """정보 로그"""
        self.log('INFO', message, category)
    
    def warning(self, message, category="GENERAL"):
        """경고 로그"""
        self.log('WARNING', message, category)
    
    def error(self, message, category="GENERAL", exc_info=False):
        """에러 로그"""
        if exc_info:
            import traceback
            message += f"\n{traceback.format_exc()}"
        self.log('ERROR', message, category)
    
    def debug(self, message, category="GENERAL"):
        """디버그 로그"""
        if DEBUG_CONFIG.get('enabled', False):
            self.log('DEBUG', message, category)
    
    def critical(self, message, category="GENERAL"):
        """중요 로그"""
        self.log('CRITICAL', message, category)
    
    def log_api_call(self, endpoint, method="GET", status_code=None, response_time=None):
        """API 호출 로그"""
        message = f"API {method} {endpoint}"
        if status_code:
            message += f" - {status_code}"
        if response_time:
            message += f" ({response_time:.0f}ms)"
        
        # 상태 코드에 따른 레벨 결정
        if status_code and status_code >= 400:
            level = 'ERROR' if status_code >= 500 else 'WARNING'
        else:
            level = 'INFO'
        
        self.log(level, message, 'API')
    
    def log_hardware_event(self, event, slot=None, details=None):
        """하드웨어 이벤트 로그"""
        message = f"Hardware: {event}"
        if slot:
            message += f" (Slot {slot})"
        if details:
            message += f" - {details}"
        
        self.log('INFO', message, 'HARDWARE')
    
    def log_performance(self, operation, duration, metadata=None):
        """성능 메트릭 로그"""
        if not DEBUG_CONFIG.get('show_performance_metrics', False):
            return
        
        try:
            # 성능 통계 업데이트
            if operation not in self.performance_metrics:
                self.performance_metrics[operation] = {
                    'count': 0,
                    'total_time': 0,
                    'min_time': float('inf'),
                    'max_time': 0,
                    'last_time': 0,
                    'last_updated': time.time()
                }
            
            metrics = self.performance_metrics[operation]
            metrics['count'] += 1
            metrics['total_time'] += duration
            metrics['min_time'] = min(metrics['min_time'], duration)
            metrics['max_time'] = max(metrics['max_time'], duration)
            metrics['last_time'] = duration
            metrics['last_updated'] = time.time()
            
            avg_time = metrics['total_time'] / metrics['count']
            
            message = f"Performance: {operation} took {duration:.0f}ms (avg: {avg_time:.0f}ms)"
            if metadata:
                message += f" - {metadata}"
            
            # 느린 작업은 경고로 로그
            level = 'WARNING' if duration > 5000 else 'INFO'
            self.log(level, message, 'PERFORMANCE')
            
        except Exception as e:
            print(f"성능 로그 오류: {e}")
    
    def get_performance_summary(self):
        """성능 요약 반환"""
        if not self.performance_metrics:
            return "성능 메트릭 없음"
        
        summary = []
        for operation, metrics in self.performance_metrics.items():
            avg_time = metrics['total_time'] / metrics['count']
            summary.append(
                f"{operation}: {metrics['count']}회, "
                f"평균 {avg_time:.0f}ms, "
                f"최소 {metrics['min_time']:.0f}ms, "
                f"최대 {metrics['max_time']:.0f}ms"
            )
        return "\n".join(summary)
    
    def get_category_stats(self):
        """카테고리별 통계 반환"""
        return self.category_stats.copy()
    
    def get_log_stats(self):
        """로그 통계 반환"""
        try:
            stats = {
                'queue_size': self.log_queue.qsize(),
                'performance_metrics_count': len(self.performance_metrics),
                'category_stats': self.get_category_stats(),
                'log_files': {}
            }
            
            # 로그 파일 크기 정보
            for name, path in self.log_files.items():
                if path.exists():
                    stats['log_files'][name] = {
                        'size': path.stat().st_size,
                        'modified': datetime.fromtimestamp(path.stat().st_mtime).isoformat()
                    }
            
            return stats
            
        except Exception as e:
            print(f"로그 통계 수집 오류: {e}")
            return {}
    
    def cleanup(self):
        """로거 정리"""
        try:
            print("로거 정리 시작...")
            
            self.running = False
            
            # 큐 비우기
            while not self.log_queue.empty():
                try:
                    log_entry = self.log_queue.get_nowait()
                    self._process_log_entry(log_entry)
                    self.log_queue.task_done()
                except Empty:
                    break
            
            # 백그라운드 스레드 종료 대기
            if self.background_thread and self.background_thread.is_alive():
                self.background_thread.join(timeout=3)
            
            # 핸들러 정리
            for handler in self.logger.handlers[:]:
                handler.close()
                self.logger.removeHandler(handler)
            
            print("로거 정리 완료")
            
        except Exception as e:
            print(f"로거 정리 오류: {e}")


class PerformanceTimer:
    """성능 측정용 컨텍스트 매니저"""
    
    def __init__(self, operation_name, logger=None, metadata=None):
        self.operation_name = operation_name
        self.logger = logger or get_logger()
        self.metadata = metadata
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time() * 1000  # 밀리초
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = (time.time() * 1000) - self.start_time
            self.logger.log_performance(self.operation_name, duration, self.metadata)


# 전역 로거 인스턴스
_logger = None

def get_logger():
    """전역 로거 인스턴스 반환"""
    global _logger
    if _logger is None:
        _logger = RaspberryPiLogger()
    return _logger

# 편의 함수들
def log_info(msg: str, category="GENERAL"):
    get_logger().info(msg, category)

def log_error(msg: str, category="GENERAL", exc_info=False):
    get_logger().error(msg, category, exc_info=exc_info)

def log_warning(msg: str, category="GENERAL"):
    get_logger().warning(msg, category)

def log_debug(msg: str, category="GENERAL"):
    get_logger().debug(msg, category)

def log_critical(msg: str, category="GENERAL"):
    get_logger().critical(msg, category)

def log_api_call(endpoint, method="GET", status_code=None, response_time=None):
    get_logger().log_api_call(endpoint, method, status_code, response_time)

def log_hardware_event(event, slot=None, details=None):
    get_logger().log_hardware_event(event, slot, details)

def performance_timer(operation_name, metadata=None):
    """성능 측정 데코레이터"""
    return PerformanceTimer(operation_name, get_logger(), metadata)

def get_performance_summary():
    """성능 요약 반환"""
    return get_logger().get_performance_summary()

def get_log_stats():
    """로그 통계 반환"""
    return get_logger().get_log_stats()

def cleanup_logger():
    """로거 정리"""
    global _logger
    if _logger:
        _logger.cleanup()
        _logger = None

# 시스템 종료 시 자동 정리
import atexit
atexit.register(cleanup_logger)