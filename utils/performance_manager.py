#!/usr/bin/env python3
"""
Performance Manager
Comprehensive performance monitoring and optimization system
"""
import asyncio
import gc
import os
import psutil
import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from collections import deque, defaultdict

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance metrics snapshot"""
    timestamp: float
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    active_threads: int
    open_connections: int
    cache_hit_rate: float
    api_response_time_ms: float
    monitor_processing_time_ms: float

class PerformanceManager:
    """Comprehensive performance monitoring and optimization"""
    
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.metrics_history: deque = deque(maxlen=max_history)
        self.api_timings: deque = deque(maxlen=50)
        self.monitor_timings: deque = deque(maxlen=50)
        
        # Performance thresholds
        self.thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 85.0,
            'api_response_time_ms': 2000,
            'monitor_processing_time_ms': 5000,
            'cache_hit_rate': 70.0
        }
        
        # Circuit breaker states
        self.circuit_breakers = defaultdict(lambda: {
            'failures': 0,
            'last_failure': 0,
            'state': 'closed',  # closed, open, half-open
            'next_attempt': 0
        })
        
        # Performance optimization state
        self.optimization_active = False
        self.last_gc_time = 0
        self.last_optimization = 0
        
        # System process info
        self.process = psutil.Process()
        
    def record_api_timing(self, operation: str, duration_ms: float, success: bool = True):
        """Record API operation timing"""
        self.api_timings.append({
            'timestamp': time.time(),
            'operation': operation,
            'duration_ms': duration_ms,
            'success': success
        })
        
        # Update circuit breaker
        if not success:
            self._record_failure(f"api_{operation}")
        else:
            self._record_success(f"api_{operation}")
    
    def record_monitor_timing(self, monitor_count: int, duration_ms: float):
        """Record monitor processing timing"""
        self.monitor_timings.append({
            'timestamp': time.time(),
            'monitor_count': monitor_count,
            'duration_ms': duration_ms,
            'per_monitor_ms': duration_ms / monitor_count if monitor_count > 0 else 0
        })
    
    def _record_failure(self, operation: str):
        """Record operation failure for circuit breaker"""
        breaker = self.circuit_breakers[operation]
        breaker['failures'] += 1
        breaker['last_failure'] = time.time()
        
        # Check if we should open the circuit
        failure_threshold = int(os.getenv('CIRCUIT_BREAKER_FAILURE_THRESHOLD', 5))
        if breaker['failures'] >= failure_threshold:
            breaker['state'] = 'open'
            recovery_timeout = int(os.getenv('CIRCUIT_BREAKER_RECOVERY_TIMEOUT', 60))
            breaker['next_attempt'] = time.time() + recovery_timeout
            logger.warning(f"🚨 Circuit breaker OPENED for {operation} ({breaker['failures']} failures)")
    
    def _record_success(self, operation: str):
        """Record operation success for circuit breaker"""
        breaker = self.circuit_breakers[operation]
        if breaker['state'] == 'half-open':
            # Success in half-open state - close the circuit
            breaker['state'] = 'closed'
            breaker['failures'] = 0
            logger.info(f"✅ Circuit breaker CLOSED for {operation}")
        elif breaker['state'] == 'closed':
            # Reset failure count on success
            breaker['failures'] = max(0, breaker['failures'] - 1)
    
    def is_circuit_open(self, operation: str) -> bool:
        """Check if circuit breaker is open for operation"""
        breaker = self.circuit_breakers[operation]
        current_time = time.time()
        
        if breaker['state'] == 'open':
            if current_time >= breaker['next_attempt']:
                # Try half-open state
                breaker['state'] = 'half-open'
                logger.info(f"🔄 Circuit breaker HALF-OPEN for {operation}")
                return False
            return True
        
        return False
    
    async def collect_metrics(self) -> PerformanceMetrics:
        """Collect current performance metrics"""
        try:
            # System metrics
            cpu_percent = self.process.cpu_percent()
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            memory_percent = self.process.memory_percent()
            
            # Thread and connection info
            active_threads = self.process.num_threads()
            open_connections = len(self.process.connections())
            
            # Calculate cache hit rate
            cache_hit_rate = await self._calculate_cache_hit_rate()
            
            # Calculate average API response time
            api_response_time_ms = self._calculate_avg_api_time()
            
            # Calculate average monitor processing time
            monitor_processing_time_ms = self._calculate_avg_monitor_time()
            
            metrics = PerformanceMetrics(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                memory_percent=memory_percent,
                active_threads=active_threads,
                open_connections=open_connections,
                cache_hit_rate=cache_hit_rate,
                api_response_time_ms=api_response_time_ms,
                monitor_processing_time_ms=monitor_processing_time_ms
            )
            
            self.metrics_history.append(metrics)
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error collecting performance metrics: {e}")
            return None
    
    async def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate from API cache"""
        try:
            from utils.enhanced_api_cache import get_api_cache
            cache = get_api_cache()
            stats = cache.get_cache_stats()
            return stats.get('hit_rate_percent', 0.0)
        except Exception:
            return 0.0
    
    def _calculate_avg_api_time(self) -> float:
        """Calculate average API response time from recent calls"""
        if not self.api_timings:
            return 0.0
        
        recent_timings = [t['duration_ms'] for t in list(self.api_timings)[-10:]]
        return sum(recent_timings) / len(recent_timings)
    
    def _calculate_avg_monitor_time(self) -> float:
        """Calculate average monitor processing time"""
        if not self.monitor_timings:
            return 0.0
        
        recent_timings = [t['duration_ms'] for t in list(self.monitor_timings)[-5:]]
        return sum(recent_timings) / len(recent_timings)
    
    async def optimize_performance(self, force: bool = False) -> Dict[str, Any]:
        """Perform automatic performance optimizations"""
        current_time = time.time()
        
        # Don't optimize too frequently
        if not force and current_time - self.last_optimization < 300:  # 5 minutes
            return {'status': 'skipped', 'reason': 'too_frequent'}
        
        self.last_optimization = current_time
        optimizations = []
        
        try:
            # Collect current metrics
            metrics = await self.collect_metrics()
            if not metrics:
                return {'status': 'failed', 'reason': 'metrics_collection_failed'}
            
            # Memory optimization
            if metrics.memory_percent > self.thresholds['memory_percent'] or force:
                gc_collected = await self._optimize_memory()
                optimizations.append(f"garbage_collection: {gc_collected} objects")
            
            # Cache optimization
            if metrics.cache_hit_rate < self.thresholds['cache_hit_rate'] or force:
                cache_opts = await self._optimize_cache(metrics)
                optimizations.extend(cache_opts)
            
            # Connection optimization
            if metrics.open_connections > 100 or force:
                conn_opts = await self._optimize_connections()
                optimizations.extend(conn_opts)
            
            # API optimization
            if metrics.api_response_time_ms > self.thresholds['api_response_time_ms'] or force:
                api_opts = await self._optimize_api_performance()
                optimizations.extend(api_opts)
            
            logger.info(f"🚀 Performance optimization complete: {optimizations}")
            
            return {
                'status': 'completed',
                'optimizations': optimizations,
                'metrics_before': metrics,
                'timestamp': current_time
            }
            
        except Exception as e:
            logger.error(f"❌ Performance optimization failed: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    async def _optimize_memory(self) -> int:
        """Optimize memory usage"""
        # Force garbage collection
        collected = gc.collect()
        self.last_gc_time = time.time()
        
        # Clear any large data structures that can be recreated
        try:
            # Clear old metrics history if it's too large
            if len(self.metrics_history) > self.max_history * 0.8:
                excess = len(self.metrics_history) - int(self.max_history * 0.6)
                for _ in range(excess):
                    self.metrics_history.popleft()
                logger.debug(f"🧹 Trimmed {excess} old metrics")
        except Exception as e:
            logger.warning(f"⚠️ Memory optimization warning: {e}")
        
        return collected
    
    async def _optimize_cache(self, metrics: PerformanceMetrics) -> List[str]:
        """Optimize cache performance"""
        optimizations = []
        
        try:
            from utils.enhanced_api_cache import get_api_cache
            cache = get_api_cache()
            
            # Optimize for high load if performance is poor
            if metrics.api_response_time_ms > 1000 or metrics.cache_hit_rate < 50:
                cache.optimize_for_load(high_load=True)
                optimizations.append("cache_optimized_for_high_load")
            else:
                cache.optimize_for_load(high_load=False)
                optimizations.append("cache_optimized_for_normal_load")
                
        except Exception as e:
            logger.warning(f"⚠️ Cache optimization error: {e}")
        
        return optimizations
    
    async def _optimize_connections(self) -> List[str]:
        """Optimize connection usage"""
        optimizations = []
        
        try:
            # Force cleanup of HTTP sessions if they exist
            from clients.bybit_client import cleanup_http_session
            await cleanup_http_session()
            optimizations.append("http_session_recycled")
            
        except Exception as e:
            logger.warning(f"⚠️ Connection optimization error: {e}")
        
        return optimizations
    
    async def _optimize_api_performance(self) -> List[str]:
        """Optimize API performance"""
        optimizations = []
        
        try:
            # Enable high-load cache optimization
            from utils.enhanced_api_cache import get_api_cache
            cache = get_api_cache()
            cache.optimize_for_load(high_load=True)
            optimizations.append("api_cache_extended_ttl")
            
        except Exception as e:
            logger.warning(f"⚠️ API optimization error: {e}")
        
        return optimizations
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive system health report"""
        if not self.metrics_history:
            return {'status': 'no_data', 'metrics': None}
        
        latest = self.metrics_history[-1]
        
        # Determine health status
        health_issues = []
        
        if latest.cpu_percent > self.thresholds['cpu_percent']:
            health_issues.append(f"high_cpu: {latest.cpu_percent:.1f}%")
        
        if latest.memory_percent > self.thresholds['memory_percent']:
            health_issues.append(f"high_memory: {latest.memory_percent:.1f}%")
        
        if latest.api_response_time_ms > self.thresholds['api_response_time_ms']:
            health_issues.append(f"slow_api: {latest.api_response_time_ms:.0f}ms")
        
        if latest.cache_hit_rate < self.thresholds['cache_hit_rate']:
            health_issues.append(f"low_cache: {latest.cache_hit_rate:.1f}%")
        
        # Overall health status
        if not health_issues:
            status = 'healthy'
        elif len(health_issues) <= 2:
            status = 'warning'
        else:
            status = 'critical'
        
        return {
            'status': status,
            'issues': health_issues,
            'metrics': latest,
            'circuit_breakers': dict(self.circuit_breakers),
            'uptime_seconds': time.time() - (self.metrics_history[0].timestamp if self.metrics_history else time.time()),
            'recommendations': self._get_health_recommendations(health_issues)
        }
    
    def _get_health_recommendations(self, issues: List[str]) -> List[str]:
        """Get health improvement recommendations"""
        recommendations = []
        
        for issue in issues:
            if issue.startswith('high_cpu'):
                recommendations.append("Consider reducing monitoring frequency or enabling adaptive intervals")
            elif issue.startswith('high_memory'):
                recommendations.append("Run memory optimization or restart bot if persistent")
            elif issue.startswith('slow_api'):
                recommendations.append("Enable API batching or check network connectivity")
            elif issue.startswith('low_cache'):
                recommendations.append("Increase cache TTL or check for cache invalidation issues")
        
        return recommendations

# Global performance manager instance
_global_performance_manager = None

def get_performance_manager() -> PerformanceManager:
    """Get or create global performance manager"""
    global _global_performance_manager
    if _global_performance_manager is None:
        _global_performance_manager = PerformanceManager()
    return _global_performance_manager

# Convenience functions
async def record_operation_time(operation: str, start_time: float, success: bool = True):
    """Record operation timing"""
    duration_ms = (time.time() - start_time) * 1000
    manager = get_performance_manager()
    manager.record_api_timing(operation, duration_ms, success)

async def get_system_health() -> Dict[str, Any]:
    """Get current system health status"""
    manager = get_performance_manager()
    return manager.get_health_report()

async def optimize_system_performance(force: bool = False) -> Dict[str, Any]:
    """Run system performance optimization"""
    manager = get_performance_manager()
    return await manager.optimize_performance(force=force)