# utils/system_monitor.py (라즈베리파이 시스템 모니터링)
import threading
import time
import subprocess
import psutil
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from config import MONITORING_CONFIG, RASPBERRY_PI_CONFIG, SYSTEM_PATHS

class SystemMonitor:
    """라즈베리파이 시스템 모니터링 클래스"""
    
    def __init__(self):
        self.monitoring_enabled = MONITORING_CONFIG['enabled']
        self.monitoring_interval = MONITORING_CONFIG['metrics_interval']
        self.monitoring_thread = None
        self.running = False
        
        # 시스템 메트릭 저장
        self.metrics = {
            'cpu_temperature': 0.0,
            'cpu_usage': 0.0,
            'memory_usage': 0.0,
            'disk_usage': 0.0,
            'network_rx': 0,
            'network_tx': 0,
            'uptime': 0,
            'load_average': [0.0, 0.0, 0.0],
            'gpu_temperature': 0.0,
            'throttling_state': False,
            'voltage': {
                'core': 0.0,
                'sdram_c': 0.0,
                'sdram_i': 0.0,
                'sdram_p': 0.0
            }
        }
        
        # 알람 임계값
        self.thresholds = {
            'cpu_temp_warning': MONITORING_CONFIG.get('temperature_threshold', 70),
            'cpu_temp_critical': 80,
            'memory_warning': MONITORING_CONFIG.get('memory_threshold', 85),
            'memory_critical': 95,
            'cpu_usage_warning': MONITORING_CONFIG.get('cpu_threshold', 90),
            'cpu_usage_critical': 98,
            'disk_warning': MONITORING_CONFIG.get('disk_threshold', 90),
            'disk_critical': 95,
            'voltage_low': 4.8  # 5V 기준 4.8V 이하시 경고
        }
        
        # 알람 상태 관리
        self.alerts = {
            'active_alerts': set(),
            'alert_history': [],
            'last_alert_time': {}
        }
       
        
        # ✅ 동적 로그 파일 경로 설정
        self.log_file = self.get_log_file_path()

        print("[INFO] 시스템 모니터 초기화 완료")

    def get_log_file_path(self):
        """로그 파일 경로 동적 결정"""
        try:
            # 1순위: config.py의 SYSTEM_PATHS 사용
            if 'logs_dir' in SYSTEM_PATHS:
                logs_dir = Path(SYSTEM_PATHS['logs_dir'])
                logs_dir.mkdir(parents=True, exist_ok=True)
                return logs_dir / 'system_metrics.log'
            
            # 2순위: 현재 프로젝트 디렉토리
            project_logs = Path.cwd() / 'logs'
            if os.access(Path.cwd(), os.W_OK):
                project_logs.mkdir(exist_ok=True)
                return project_logs / 'system_metrics.log'
            
            # 3순위: 사용자 홈 디렉토리
            user_logs = Path.home() / '.dispenser' / 'logs'
            user_logs.mkdir(parents=True, exist_ok=True)
            return user_logs / 'system_metrics.log'
            
        except Exception as e:
            print(f"[ERROR] 로그 파일 경로 설정 오류: {e}")
            # 최후 수단: 임시 디렉토리
            import tempfile
            temp_dir = Path(tempfile.gettempdir()) / 'dispenser_logs'
            temp_dir.mkdir(exist_ok=True)
            return temp_dir / 'system_metrics.log'
    
    def start_monitoring(self):
        """모니터링 시작"""
        if not self.monitoring_enabled:
            print("[INFO] 시스템 모니터링이 비활성화되어 있습니다.")
            return
        
        if self.running:
            print("[WARNING] 시스템 모니터링이 이미 실행 중입니다.")
            return
        
        self.running = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        print("[INFO] 시스템 모니터링 시작됨")
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self.running = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)
        
        print("[INFO] 시스템 모니터링 중지됨")
    
    def _monitoring_loop(self):
        """모니터링 메인 루프"""
        while self.running:
            try:
                start_time = time.time()
                
                # 모든 메트릭 수집
                self._collect_cpu_metrics()
                self._collect_memory_metrics()
                self._collect_disk_metrics()
                self._collect_network_metrics()
                self._collect_raspberry_pi_metrics()
                self._collect_system_metrics()
                
                # 알람 체크
                self._check_alerts()
                
                # 로그 기록
                self._log_metrics()
                
                # 자동 복구 체크
                if MONITORING_CONFIG.get('auto_recovery', False):
                    self._check_auto_recovery()
                
                # 수집 시간 계산 및 대기
                collection_time = time.time() - start_time
                sleep_time = max(0, self.monitoring_interval - collection_time)
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    print(f"[WARNING] 메트릭 수집 시간이 간격을 초과: {collection_time:.2f}초")
                
            except Exception as e:
                print(f"[ERROR] 모니터링 루프 오류: {e}")
                time.sleep(10)  # 오류 발생 시 10초 대기
    
    def _collect_cpu_metrics(self):
        """CPU 메트릭 수집"""
        try:
            # CPU 사용률
            self.metrics['cpu_usage'] = psutil.cpu_percent(interval=1)
            
            # 로드 평균
            load_avg = os.getloadavg()
            self.metrics['load_average'] = list(load_avg)
            
        except Exception as e:
            print(f"[ERROR] CPU 메트릭 수집 오류: {e}")
    
    def _collect_memory_metrics(self):
        """메모리 메트릭 수집"""
        try:
            memory = psutil.virtual_memory()
            self.metrics['memory_usage'] = memory.percent
            
        except Exception as e:
            print(f"[ERROR] 메모리 메트릭 수집 오류: {e}")
    
    def _collect_disk_metrics(self):
        """디스크 메트릭 수집"""
        try:
            disk = psutil.disk_usage('/')
            self.metrics['disk_usage'] = (disk.used / disk.total) * 100
            
        except Exception as e:
            print(f"[ERROR] 디스크 메트릭 수집 오류: {e}")
    
    def _collect_network_metrics(self):
        """네트워크 메트릭 수집"""
        try:
            network = psutil.net_io_counters()
            self.metrics['network_rx'] = network.bytes_recv
            self.metrics['network_tx'] = network.bytes_sent
            
        except Exception as e:
            print(f"[ERROR] 네트워크 메트릭 수집 오류: {e}")
    
    def _collect_raspberry_pi_metrics(self):
        """라즈베리파이 특화 메트릭 수집"""
        try:
            # CPU 온도
            self.metrics['cpu_temperature'] = self._get_cpu_temperature()
            
            # GPU 온도
            self.metrics['gpu_temperature'] = self._get_gpu_temperature()
            
            # 스로틀링 상태
            self.metrics['throttling_state'] = self._get_throttling_state()
            
            # 전압 모니터링
            self.metrics['voltage'] = self._get_voltage_info()
            
        except Exception as e:
            print(f"[ERROR] 라즈베리파이 메트릭 수집 오류: {e}")
    
    def _collect_system_metrics(self):
        """시스템 메트릭 수집"""
        try:
            # 시스템 가동 시간
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                self.metrics['uptime'] = uptime_seconds
            
        except Exception as e:
            print(f"[ERROR] 시스템 메트릭 수집 오류: {e}")
    
    def _get_cpu_temperature(self):
        """CPU 온도 가져오기"""
        try:
            # 라즈베리파이 CPU 온도 파일 읽기
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp_millidegree = int(f.read().strip())
                return temp_millidegree / 1000.0
        except:
            try:
                # vcgencmd 사용 (백업 방법)
                result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                      capture_output=True, text=True, check=True)
                temp_str = result.stdout.strip()
                # temp=42.8'C 형식에서 숫자 추출
                temp = float(temp_str.split('=')[1].split("'")[0])
                return temp
            except:
                return 0.0
    
    def _get_gpu_temperature(self):
        """GPU 온도 가져오기"""
        try:
            result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                  capture_output=True, text=True, check=True)
            # GPU와 CPU가 같은 칩이므로 동일한 온도
            temp_str = result.stdout.strip()
            temp = float(temp_str.split('=')[1].split("'")[0])
            return temp
        except:
            return 0.0
    
    def _get_throttling_state(self):
        """스로틀링 상태 확인"""
        try:
            result = subprocess.run(['vcgencmd', 'get_throttled'], 
                                  capture_output=True, text=True, check=True)
            throttled_hex = result.stdout.strip().split('=')[1]
            throttled_int = int(throttled_hex, 16)
            
            # 스로틀링 비트 체크 (비트 0-3: 현재 상태, 비트 16-19: 이력)
            return throttled_int != 0
        except:
            return False
    
    def _get_voltage_info(self):
        """전압 정보 가져오기"""
        voltage_info = {
            'core': 0.0,
            'sdram_c': 0.0,
            'sdram_i': 0.0,
            'sdram_p': 0.0
        }
        
        voltage_commands = {
            'core': 'core',
            'sdram_c': 'sdram_c',
            'sdram_i': 'sdram_i', 
            'sdram_p': 'sdram_p'
        }
        
        for key, cmd in voltage_commands.items():
            try:
                result = subprocess.run(['vcgencmd', 'measure_volts', cmd], 
                                      capture_output=True, text=True, check=True)
                volt_str = result.stdout.strip()
                # volt=1.2000V 형식에서 숫자 추출
                voltage = float(volt_str.split('=')[1].rstrip('V'))
                voltage_info[key] = voltage
            except:
                voltage_info[key] = 0.0
        
        return voltage_info
    
    def _check_alerts(self):
        """알람 조건 체크"""
        try:
            current_time = datetime.now()
            new_alerts = set()
            
            # CPU 온도 체크
            cpu_temp = self.metrics['cpu_temperature']
            if cpu_temp >= self.thresholds['cpu_temp_critical']:
                new_alerts.add('cpu_temp_critical')
            elif cpu_temp >= self.thresholds['cpu_temp_warning']:
                new_alerts.add('cpu_temp_warning')
            
            # 메모리 사용량 체크
            memory_usage = self.metrics['memory_usage']
            if memory_usage >= self.thresholds['memory_critical']:
                new_alerts.add('memory_critical')
            elif memory_usage >= self.thresholds['memory_warning']:
                new_alerts.add('memory_warning')
            
            # CPU 사용량 체크
            cpu_usage = self.metrics['cpu_usage']
            if cpu_usage >= self.thresholds['cpu_usage_critical']:
                new_alerts.add('cpu_usage_critical')
            elif cpu_usage >= self.thresholds['cpu_usage_warning']:
                new_alerts.add('cpu_usage_warning')
            
            # 디스크 사용량 체크
            disk_usage = self.metrics['disk_usage']
            if disk_usage >= self.thresholds['disk_critical']:
                new_alerts.add('disk_critical')
            elif disk_usage >= self.thresholds['disk_warning']:
                new_alerts.add('disk_warning')
            
            # 스로틀링 체크
            if self.metrics['throttling_state']:
                new_alerts.add('throttling_detected')
            
            # 전압 체크
            core_voltage = self.metrics['voltage']['core']
            if core_voltage > 0 and core_voltage < self.thresholds['voltage_low']:
                new_alerts.add('voltage_low')
            
            # 새로운 알람 처리
            for alert in new_alerts - self.alerts['active_alerts']:
                self._trigger_alert(alert, current_time)
            
            # 해결된 알람 처리
            for alert in self.alerts['active_alerts'] - new_alerts:
                self._resolve_alert(alert, current_time)
            
            self.alerts['active_alerts'] = new_alerts
            
        except Exception as e:
            print(f"[ERROR] 알람 체크 오류: {e}")
    
    def _trigger_alert(self, alert_type, timestamp):
        """알람 발생 처리"""
        try:
            alert_info = {
                'type': alert_type,
                'timestamp': timestamp,
                'status': 'triggered',
                'metrics': self.metrics.copy()
            }
            
            self.alerts['alert_history'].append(alert_info)
            self.alerts['last_alert_time'][alert_type] = timestamp
            
            # 알람 메시지 생성
            message = self._get_alert_message(alert_type)
            print(f"[ALERT] {message}")
            
            # 알람 로그 기록
            self._log_alert(alert_info)
            
            # 음성 알림 (중요한 알람만)
            if alert_type.endswith('_critical'):
                try:
                    from utils.voice_feedback import announce_error
                    announce_error('system_error')
                except:
                    pass
            
        except Exception as e:
            print(f"[ERROR] 알람 발생 처리 오류: {e}")
    
    def _resolve_alert(self, alert_type, timestamp):
        """알람 해결 처리"""
        try:
            alert_info = {
                'type': alert_type,
                'timestamp': timestamp,
                'status': 'resolved',
                'metrics': self.metrics.copy()
            }
            
            self.alerts['alert_history'].append(alert_info)
            
            message = f"{alert_type} 알람이 해결되었습니다"
            print(f"[INFO] {message}")
            
            # 해결 로그 기록
            self._log_alert(alert_info)
            
        except Exception as e:
            print(f"[ERROR] 알람 해결 처리 오류: {e}")
    
    def _get_alert_message(self, alert_type):
        """알람 메시지 생성"""
        messages = {
            'cpu_temp_warning': f"CPU 온도 경고: {self.metrics['cpu_temperature']:.1f}°C",
            'cpu_temp_critical': f"CPU 온도 위험: {self.metrics['cpu_temperature']:.1f}°C",
            'memory_warning': f"메모리 사용량 경고: {self.metrics['memory_usage']:.1f}%",
            'memory_critical': f"메모리 사용량 위험: {self.metrics['memory_usage']:.1f}%",
            'cpu_usage_warning': f"CPU 사용량 경고: {self.metrics['cpu_usage']:.1f}%",
            'cpu_usage_critical': f"CPU 사용량 위험: {self.metrics['cpu_usage']:.1f}%",
            'disk_warning': f"디스크 사용량 경고: {self.metrics['disk_usage']:.1f}%",
            'disk_critical': f"디스크 사용량 위험: {self.metrics['disk_usage']:.1f}%",
            'throttling_detected': "CPU 스로틀링 감지됨",
            'voltage_low': f"전압 부족: {self.metrics['voltage']['core']:.2f}V"
        }
        
        return messages.get(alert_type, f"알 수 없는 알람: {alert_type}")
    
    def _check_auto_recovery(self):
        """자동 복구 체크"""
        try:
            # 메모리 사용량이 임계치를 넘으면 재시작 고려
            if (MONITORING_CONFIG.get('restart_on_memory_limit', False) and
                self.metrics['memory_usage'] > 95):
                
                print("[WARNING] 메모리 사용량이 95%를 초과했습니다. 자동 복구를 고려합니다.")
                self._trigger_memory_cleanup()
            
            # 온도가 임계치를 넘으면 쿨다운
            if (MONITORING_CONFIG.get('restart_on_temperature_limit', False) and
                self.metrics['cpu_temperature'] > 80):
                
                print("[WARNING] CPU 온도가 80°C를 초과했습니다. 시스템 부하를 줄입니다.")
                self._trigger_thermal_protection()
            
        except Exception as e:
            print(f"[ERROR] 자동 복구 체크 오류: {e}")
    
    def _trigger_memory_cleanup(self):
        """메모리 정리 실행"""
        try:
            # 캐시 정리
            subprocess.run(['sync'], check=False)
            subprocess.run(['echo', '3', '>', '/proc/sys/vm/drop_caches'], 
                          shell=True, check=False)
            
            print("[INFO] 메모리 캐시 정리 완료")
            
        except Exception as e:
            print(f"[ERROR] 메모리 정리 오류: {e}")
    
    def _trigger_thermal_protection(self):
        """열 보호 실행"""
        try:
            # CPU 주파수 제한 (일시적)
            subprocess.run(['echo', 'powersave', '>', '/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'], 
                          shell=True, check=False)
            
            print("[INFO] 열 보호 모드 활성화")
            
            # 30초 후 정상 모드로 복귀
            def restore_performance():
                time.sleep(30)
                subprocess.run(['echo', 'ondemand', '>', '/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'], 
                              shell=True, check=False)
                print("[INFO] 열 보호 모드 해제")
            
            threading.Thread(target=restore_performance, daemon=True).start()
            
        except Exception as e:
            print(f"[ERROR] 열 보호 실행 오류: {e}")
    
    def _log_metrics(self):
        """메트릭 로그 기록"""
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'metrics': self.metrics.copy(),
                'active_alerts': list(self.alerts['active_alerts'])
            }
            
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            
            # 로그 파일 크기 제한 (10MB)
            if self.log_file.stat().st_size > 10 * 1024 * 1024:
                self._rotate_log_file()
                
        except Exception as e:
            print(f"[ERROR] 메트릭 로그 기록 오류: {e}")
    
    def _log_alert(self, alert_info):
        """알람 로그 기록"""
        try:
            alert_log_file = self.log_file.parent / 'alerts.log'
            
            with open(alert_log_file, 'a') as f:
                log_entry = {
                    'timestamp': alert_info['timestamp'].isoformat(),
                    'type': alert_info['type'],
                    'status': alert_info['status'],
                    'cpu_temp': alert_info['metrics']['cpu_temperature'],
                    'memory_usage': alert_info['metrics']['memory_usage'],
                    'cpu_usage': alert_info['metrics']['cpu_usage']
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                
        except Exception as e:
            print(f"[ERROR] 알람 로그 기록 오류: {e}")
    
    def _rotate_log_file(self):
        """로그 파일 로테이션"""
        try:
            backup_file = self.log_file.parent / f"{self.log_file.stem}_backup.log"
            
            if backup_file.exists():
                backup_file.unlink()
            
            self.log_file.rename(backup_file)
            print("[INFO] 로그 파일 로테이션 완료")
            
        except Exception as e:
            print(f"[ERROR] 로그 파일 로테이션 오류: {e}")
    
    # 외부 인터페이스 메서드들
    def get_cpu_temperature(self):
        """CPU 온도 반환"""
        return self.metrics.get('cpu_temperature', 0.0)
    
    def get_memory_usage(self):
        """메모리 사용량 반환"""
        return self.metrics.get('memory_usage', 0.0)
    
    def get_cpu_usage(self):
        """CPU 사용량 반환"""
        return self.metrics.get('cpu_usage', 0.0)
    
    def get_disk_usage(self):
        """디스크 사용량 반환"""
        return self.metrics.get('disk_usage', 0.0)
    
    def get_system_uptime(self):
        """시스템 가동 시간 반환 (초)"""
        return self.metrics.get('uptime', 0)
    
    def get_all_metrics(self):
        """모든 메트릭 반환"""
        return self.metrics.copy()
    
    def get_active_alerts(self):
        """활성 알람 반환"""
        return list(self.alerts['active_alerts'])
    
    def get_alert_history(self, hours=24):
        """알람 히스토리 반환"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_alerts = [
            alert for alert in self.alerts['alert_history']
            if alert['timestamp'] > cutoff_time
        ]
        
        return recent_alerts
    
    def is_system_healthy(self):
        """시스템 건강 상태 확인"""
        critical_alerts = [alert for alert in self.alerts['active_alerts'] 
                          if 'critical' in alert]
        
        return len(critical_alerts) == 0
    
    def get_system_summary(self):
        """시스템 요약 정보 반환"""
        return {
            'cpu_temp': self.metrics['cpu_temperature'],
            'memory_usage': self.metrics['memory_usage'],
            'cpu_usage': self.metrics['cpu_usage'],
            'disk_usage': self.metrics['disk_usage'],
            'uptime_hours': self.metrics['uptime'] / 3600,
            'active_alerts': len(self.alerts['active_alerts']),
            'is_healthy': self.is_system_healthy(),
            'throttling': self.metrics['throttling_state']
        }