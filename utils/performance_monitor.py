#!/usr/bin/env python3
"""
Performance monitoring utilities for the trading bot
Tracks API calls, execution times, and resource usage
"""
import time
import asyncio
import psutil
import logging
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Optional, Any
from functools import wraps
import statistics

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Monitors and tracks performance metrics"""

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.api_calls = defaultdict(lambda: deque(maxlen=max_history))
        self.execution_times = defaultdict(lambda: deque(maxlen=max_history))
        self.error_counts = defaultdict(int)
        self.start_time = datetime.now()

        # Resource monitoring
        self.memory_usage = deque(maxlen=100)
        self.cpu_usage = deque(maxlen=100)

    def track_api_call(self, endpoint: str, duration: float, status: str = "success"):
        """Track API call performance"""
        self.api_calls[endpoint].append({
            'timestamp': datetime.now(),
            'duration': duration,
            'status': status
        })

        if status != "success":
            self.error_counts[endpoint] += 1

    def track_execution(self, operation: str, duration: float):
        """Track operation execution time"""
        self.execution_times[operation].append({
            'timestamp': datetime.now(),
            'duration': duration
        })

    def track_resources(self):
        """Track system resource usage"""
        try:
            process = psutil.Process()
            self.memory_usage.append({
                'timestamp': datetime.now(),
                'rss': process.memory_info().rss / 1024 / 1024,  # MB
                'percent': process.memory_percent()
            })
            self.cpu_usage.append({
                'timestamp': datetime.now(),
                'percent': process.cpu_percent(interval=0.1)
            })
        except Exception as e:
            logger.debug(f"Error tracking resources: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get performance statistics"""
        stats = {
            'uptime': str(datetime.now() - self.start_time),
            'api_stats': {},
            'execution_stats': {},
            'error_rates': {},
            'resource_usage': {}
        }

        # API call statistics
        for endpoint, calls in self.api_calls.items():
            if calls:
                durations = [c['duration'] for c in calls]
                stats['api_stats'][endpoint] = {
                    'count': len(calls),
                    'avg_duration': statistics.mean(durations),
                    'min_duration': min(durations),
                    'max_duration': max(durations),
                    'p95_duration': statistics.quantiles(durations, n=20)[18] if len(durations) > 20 else max(durations)
                }

        # Execution time statistics
        for operation, times in self.execution_times.items():
            if times:
                durations = [t['duration'] for t in times]
                stats['execution_stats'][operation] = {
                    'count': len(times),
                    'avg_duration': statistics.mean(durations),
                    'total_time': sum(durations)
                }

        # Error rates
        total_calls = sum(len(calls) for calls in self.api_calls.values())
        total_errors = sum(self.error_counts.values())
        stats['error_rates'] = {
            'total_errors': total_errors,
            'error_rate': (total_errors / total_calls * 100) if total_calls > 0 else 0,
            'by_endpoint': dict(self.error_counts)
        }

        # Resource usage
        if self.memory_usage:
            memory_values = [m['rss'] for m in self.memory_usage]
            stats['resource_usage']['memory'] = {
                'current_mb': memory_values[-1],
                'avg_mb': statistics.mean(memory_values),
                'max_mb': max(memory_values)
            }

        if self.cpu_usage:
            cpu_values = [c['percent'] for c in self.cpu_usage]
            stats['resource_usage']['cpu'] = {
                'current_percent': cpu_values[-1],
                'avg_percent': statistics.mean(cpu_values),
                'max_percent': max(cpu_values)
            }

        return stats

    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status"""
        stats = self.get_statistics()

        health = {
            'status': 'healthy',
            'checks': [],
            'timestamp': datetime.now().isoformat()
        }

        # Check error rate
        error_rate = stats['error_rates']['error_rate']
        if error_rate > 10:
            health['status'] = 'unhealthy'
            health['checks'].append(f"High error rate: {error_rate:.1f}%")
        elif error_rate > 5:
            health['status'] = 'degraded'
            health['checks'].append(f"Elevated error rate: {error_rate:.1f}%")

        # Check memory usage
        if 'memory' in stats['resource_usage']:
            current_memory = stats['resource_usage']['memory']['current_mb']
            if current_memory > 1000:  # 1GB
                health['status'] = 'degraded'
                health['checks'].append(f"High memory usage: {current_memory:.0f}MB")

        # Check API latency
        for endpoint, api_stats in stats['api_stats'].items():
            if api_stats['avg_duration'] > 5:  # 5 seconds
                health['status'] = 'degraded'
                health['checks'].append(f"Slow API response for {endpoint}: {api_stats['avg_duration']:.1f}s")

        if not health['checks']:
            health['checks'].append("All systems operational")

        return health

# Global instance
performance_monitor = PerformanceMonitor()

def track_performance(operation: str):
    """Decorator to track function performance"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                performance_monitor.track_execution(operation, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                performance_monitor.track_execution(f"{operation}_error", duration)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                performance_monitor.track_execution(operation, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                performance_monitor.track_execution(f"{operation}_error", duration)
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

async def monitor_resources_task():
    """Background task to monitor resources"""
    while True:
        try:
            performance_monitor.track_resources()
            await asyncio.sleep(60)  # Check every minute
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in resource monitoring: {e}")
            await asyncio.sleep(60)