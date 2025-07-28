#!/usr/bin/env python3
"""
Enhanced Performance Monitoring Module for Long-Running Trading Bot
Provides comprehensive performance tracking, memory monitoring, and automated cleanup
Based on 2025 best practices for Python long-running applications

Features:
- Advanced memory leak detection
- Strategic garbage collection management
- Connection pool optimization
- Cache performance monitoring
- Automated performance optimization
"""
import gc
import os
import time
import asyncio
import psutil
import logging
import weakref
import tracemalloc
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Optional, Any, Tuple
from functools import wraps
from dataclasses import dataclass, asdict
from decimal import Decimal
import statistics

logger = logging.getLogger(__name__)

@dataclass
class MemoryMetrics:
    """Memory usage metrics snapshot"""
    timestamp: float
    rss_mb: float  # Resident Set Size in MB
    vms_mb: float  # Virtual Memory Size in MB
    percent: float  # Memory percentage of system
    available_mb: float  # Available system memory
    gc_objects: int  # Number of objects tracked by GC
    gc_gen0: int  # Generation 0 objects
    gc_gen1: int  # Generation 1 objects
    gc_gen2: int  # Generation 2 objects

@dataclass
class PerformanceMetrics:
    """Performance metrics snapshot"""
    timestamp: float
    cpu_percent: float
    memory_metrics: MemoryMetrics
    active_threads: int
    active_tasks: int
    cache_hit_rate: float
    connection_pool_usage: int
    gc_collections: Tuple[int, int, int]  # Collections per generation

class EnhancedPerformanceMonitor:
    """
    Enhanced performance monitoring system for long-running applications
    Implements 2025 best practices for Python memory management and performance optimization
    """
    
    def __init__(self, history_size: int = 1000, alert_thresholds: Optional[Dict] = None):
        # Legacy compatibility
        self.max_history = history_size
        self.api_calls = defaultdict(lambda: deque(maxlen=history_size))
        self.execution_times = defaultdict(lambda: deque(maxlen=history_size))
        self.error_counts = defaultdict(int)
        self.start_time = datetime.now()
        self.memory_usage = deque(maxlen=100)
        self.cpu_usage = deque(maxlen=100)
        
        # Enhanced monitoring
        self.process = psutil.Process()
        self.history_size = history_size
        self.metrics_history: deque = deque(maxlen=history_size)
        
        # Alert thresholds (defaults based on trading bot requirements)
        self.alert_thresholds = alert_thresholds or {
            'memory_mb': 1000,  # Alert if using > 1GB
            'memory_percent': 80,  # Alert if using > 80% of system memory
            'cpu_percent': 90,  # Alert if CPU > 90%
            'gc_objects': 100000,  # Alert if > 100k objects in GC
            'cache_hit_rate': 0.7  # Alert if cache hit rate < 70%
        }
        
        # Performance tracking
        self._last_gc_stats = gc.get_stats()
        self._gc_collection_history = deque(maxlen=100)
        self._memory_leak_detector = MemoryLeakDetector()
        
        # Background monitoring task
        self._monitoring_task: Optional[asyncio.Task] = None
        self._monitoring_interval = 60  # Monitor every minute
        self._cleanup_interval = 300  # Cleanup every 5 minutes
        self._last_cleanup = 0
        
        # Performance optimization state
        self._optimization_mode = 'normal'  # normal, conservative, aggressive
        self._last_optimization_time = 0
        
        # API Performance tracking (new from 2025 optimization plan)
        self.api_metrics: deque = deque(maxlen=history_size)
        self.trade_metrics: deque = deque(maxlen=history_size)
        
        # Circuit breaker system
        self.circuit_breakers = {
            "api_calls": {"failures": 0, "threshold": 10, "open": False, "reset_time": 0},
            "trade_execution": {"failures": 0, "threshold": 5, "open": False, "reset_time": 0},
            "persistence": {"failures": 0, "threshold": 3, "open": False, "reset_time": 0}
        }
        
        # Error recovery tracking
        self.error_recovery_stats = {
            "api_errors": 0,
            "api_timeouts": 0,
            "trade_failures": 0,
            "system_alerts": 0,
            "recovery_attempts": 0,
            "successful_recoveries": 0
        }
        
        # Performance statistics
        self.performance_stats = {
            "total_alerts": 0,
            "api_calls_tracked": 0,
            "trades_tracked": 0,
            "average_cpu": 0.0,
            "average_memory": 0.0,
            "average_api_response": 0.0,
            "cache_efficiency": 0.0
        }
        
        logger.info("✅ Enhanced performance monitor initialized with 2025 best practices")
        logger.info(f"   History size: {history_size}")
        logger.info(f"   Monitoring interval: {self._monitoring_interval}s")
        logger.info(f"   Alert thresholds: Memory {self.alert_thresholds['memory_mb']}MB, CPU {self.alert_thresholds['cpu_percent']}%")

    def get_current_memory_metrics(self) -> MemoryMetrics:
        """Get current memory usage metrics"""
        try:
            memory_info = self.process.memory_info()
            system_memory = psutil.virtual_memory()
            gc_stats = gc.get_stats()
            
            return MemoryMetrics(
                timestamp=time.time(),
                rss_mb=memory_info.rss / 1024 / 1024,
                vms_mb=memory_info.vms / 1024 / 1024,
                percent=self.process.memory_percent(),
                available_mb=system_memory.available / 1024 / 1024,
                gc_objects=len(gc.get_objects()),
                gc_gen0=gc_stats[0]['count'] if gc_stats else 0,
                gc_gen1=gc_stats[1]['count'] if len(gc_stats) > 1 else 0,
                gc_gen2=gc_stats[2]['count'] if len(gc_stats) > 2 else 0
            )
        except Exception as e:
            logger.error(f"Error getting memory metrics: {e}")
            return MemoryMetrics(
                timestamp=time.time(),
                rss_mb=0, vms_mb=0, percent=0, available_mb=0,
                gc_objects=0, gc_gen0=0, gc_gen1=0, gc_gen2=0
            )
    
    def get_current_performance_metrics(self) -> PerformanceMetrics:
        """Get comprehensive performance metrics"""
        try:
            memory_metrics = self.get_current_memory_metrics()
            
            # Get cache hit rate (if available)
            cache_hit_rate = 0.0
            try:
                from utils.cache import enhanced_cache
                stats = enhanced_cache.get_stats()
                # Calculate hit rate based on cache usage
                cache_hit_rate = min(1.0, stats.get('usage_percent', 0) / 100)
            except Exception:
                pass
            
            # Get connection pool usage (if available)  
            connection_pool_usage = 0
            try:
                from utils.connection_pool import enhanced_pool
                if hasattr(enhanced_pool, '_connector') and enhanced_pool._connector:
                    if hasattr(enhanced_pool._connector, '_connections'):
                        connection_pool_usage = len(enhanced_pool._connector._connections)
            except Exception:
                pass
            
            # Get GC collection counts
            current_gc_stats = gc.get_stats()
            gc_collections = (
                current_gc_stats[0]['collections'] if current_gc_stats else 0,
                current_gc_stats[1]['collections'] if len(current_gc_stats) > 1 else 0,
                current_gc_stats[2]['collections'] if len(current_gc_stats) > 2 else 0
            )
            
            return PerformanceMetrics(
                timestamp=time.time(),
                cpu_percent=self.process.cpu_percent(),
                memory_metrics=memory_metrics,
                active_threads=self.process.num_threads(),
                active_tasks=len([t for t in asyncio.all_tasks() if not t.done()]),
                cache_hit_rate=cache_hit_rate,
                connection_pool_usage=connection_pool_usage,
                gc_collections=gc_collections
            )
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            # Return minimal metrics on error
            return PerformanceMetrics(
                timestamp=time.time(),
                cpu_percent=0,
                memory_metrics=self.get_current_memory_metrics(),
                active_threads=0,
                active_tasks=0,
                cache_hit_rate=0,
                connection_pool_usage=0,
                gc_collections=(0, 0, 0)
            )
    
    def record_metrics(self) -> PerformanceMetrics:
        """Record current performance metrics to history"""
        metrics = self.get_current_performance_metrics()
        self.metrics_history.append(metrics)
        
        # Legacy compatibility - also update old tracking
        self.track_resources()
        
        # Check for alerts
        self._check_performance_alerts(metrics)
        
        # Check for memory leaks
        self._memory_leak_detector.check_for_leaks(metrics.memory_metrics)
        
        # Update circuit breakers
        self._update_circuit_breakers()
        
        # Update performance statistics
        self._update_performance_statistics(metrics)
        
        return metrics
    
    def _check_performance_alerts(self, metrics: PerformanceMetrics) -> None:
        """Check metrics against alert thresholds"""
        alerts = []
        
        # Memory alerts
        if metrics.memory_metrics.rss_mb > self.alert_thresholds['memory_mb']:
            alerts.append(f"High memory usage: {metrics.memory_metrics.rss_mb:.1f}MB")
        
        if metrics.memory_metrics.percent > self.alert_thresholds['memory_percent']:
            alerts.append(f"High memory percentage: {metrics.memory_metrics.percent:.1f}%")
        
        # CPU alerts
        if metrics.cpu_percent > self.alert_thresholds['cpu_percent']:
            alerts.append(f"High CPU usage: {metrics.cpu_percent:.1f}%")
        
        # GC alerts
        if metrics.memory_metrics.gc_objects > self.alert_thresholds['gc_objects']:
            alerts.append(f"High GC object count: {metrics.memory_metrics.gc_objects}")
        
        # Cache performance alerts
        if metrics.cache_hit_rate < self.alert_thresholds['cache_hit_rate']:
            alerts.append(f"Low cache hit rate: {metrics.cache_hit_rate:.1%}")
        
        if alerts:
            self.performance_stats["total_alerts"] += len(alerts)
            logger.warning(f"🚨 Performance alerts: {'; '.join(alerts)}")
    
    def _update_performance_statistics(self, metrics: PerformanceMetrics) -> None:
        """Update running performance statistics"""
        # Update CPU and memory averages
        if self.metrics_history:
            recent_metrics = list(self.metrics_history)[-10:]  # Last 10 measurements
            
            self.performance_stats["average_cpu"] = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
            self.performance_stats["average_memory"] = sum(m.memory_metrics.rss_mb for m in recent_metrics) / len(recent_metrics)
            
            # Update cache efficiency
            cache_rates = [m.cache_hit_rate for m in recent_metrics if m.cache_hit_rate > 0]
            if cache_rates:
                self.performance_stats["cache_efficiency"] = sum(cache_rates) / len(cache_rates)
        
        # Update API response time average
        if self.api_metrics:
            recent_api = list(self.api_metrics)[-50:]  # Last 50 API calls
            self.performance_stats["average_api_response"] = sum(m.response_time for m in recent_api) / len(recent_api)
    
    async def optimize_performance(self, force: bool = False) -> bool:
        """
        Perform performance optimization based on current metrics
        Implements 2025 best practices for long-running Python applications
        """
        try:
            current_time = time.time()
            
            # Don't optimize too frequently unless forced
            if not force and (current_time - self._last_optimization_time) < 300:
                return False
            
            metrics = self.get_current_performance_metrics()
            optimizations_performed = []
            
            # 1. Strategic Garbage Collection
            if self._should_run_gc(metrics):
                await self._perform_strategic_gc()
                optimizations_performed.append("garbage_collection")
            
            # 2. Cache Optimization
            if metrics.cache_hit_rate < 0.8:
                await self._optimize_caches()
                optimizations_performed.append("cache_optimization")
            
            # 3. Connection Pool Optimization
            if metrics.connection_pool_usage > 80:
                await self._optimize_connection_pool()
                optimizations_performed.append("connection_pool")
            
            # 4. Memory Cleanup
            if metrics.memory_metrics.rss_mb > 500:  # If using > 500MB
                await self._perform_memory_cleanup()
                optimizations_performed.append("memory_cleanup")
            
            self._last_optimization_time = current_time
            
            if optimizations_performed:
                logger.info(f"🔧 Performance optimizations performed: {', '.join(optimizations_performed)}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error during performance optimization: {e}")
            return False
    
    def _should_run_gc(self, metrics: PerformanceMetrics) -> bool:
        """Determine if garbage collection should be run"""
        # Run GC if we have many objects or memory usage is high
        return (
            metrics.memory_metrics.gc_objects > 50000 or
            metrics.memory_metrics.rss_mb > 300 or
            metrics.memory_metrics.percent > 60
        )
    
    async def _perform_strategic_gc(self) -> None:
        """Perform strategic garbage collection based on 2025 best practices"""
        try:
            before_objects = len(gc.get_objects())
            before_memory = self.process.memory_info().rss / 1024 / 1024
            
            # Disable GC temporarily for critical operations
            gc.disable()
            
            try:
                # Force collection starting from generation 0
                collected = [gc.collect(i) for i in range(3)]
                
                # Re-enable GC
                gc.enable()
                
                after_objects = len(gc.get_objects())
                after_memory = self.process.memory_info().rss / 1024 / 1024
                
                objects_freed = before_objects - after_objects
                memory_freed = before_memory - after_memory
                
                logger.info(
                    f"🗑️ Strategic GC completed: "
                    f"{objects_freed} objects freed, "
                    f"{memory_freed:.1f}MB memory freed, "
                    f"collections: {collected}"
                )
                
            finally:
                # Ensure GC is always re-enabled
                if not gc.isenabled():
                    gc.enable()
                    
        except Exception as e:
            logger.error(f"Error during strategic GC: {e}")
            # Ensure GC is enabled even on error
            if not gc.isenabled():
                gc.enable()
    
    async def _optimize_caches(self) -> None:
        """Optimize application caches"""
        try:
            from utils.cache import enhanced_cache
            
            # Force cleanup of expired entries
            with enhanced_cache._lock:
                enhanced_cache._cleanup_expired()
                enhanced_cache._cleanup_lru()
            
            logger.debug("🗄️  Cache optimization completed")
            
        except Exception as e:
            logger.error(f"Error optimizing caches: {e}")
    
    async def _optimize_connection_pool(self) -> None:
        """Optimize connection pool performance"""
        try:
            from utils.connection_pool import enhanced_pool
            
            # Check pool health and recreate if needed
            is_healthy = await enhanced_pool.health_check()
            if not is_healthy:
                logger.info("🔄 Recreating unhealthy connection pool")
                await enhanced_pool._create_optimized_session()
            
            logger.debug("🔌 Connection pool optimization completed")
            
        except Exception as e:
            logger.error(f"Error optimizing connection pool: {e}")
    
    async def _perform_memory_cleanup(self) -> None:
        """Perform comprehensive memory cleanup"""
        try:
            # Clean up weak references
            weakref_count = len([ref for ref in gc.get_referrers() if isinstance(ref, weakref.ref)])
            
            # Force cleanup of circular references
            before_cycles = gc.collect()
            
            # Clean up tracemalloc if enabled
            if tracemalloc.is_tracing():
                tracemalloc.clear_traces()
            
            logger.info(f"🧹 Memory cleanup completed: {before_cycles} cycles collected, {weakref_count} weak refs")
            
        except Exception as e:
            logger.error(f"Error during memory cleanup: {e}")
    
    # New API and Trade Performance Tracking Methods (from 2025 optimization plan)
    
    def track_api_performance(self, endpoint: str, response_time: float, status: str, error_message: str = None):
        """Track API call performance with enhanced metrics"""
        from dataclasses import dataclass
        
        @dataclass
        class APIPerformanceMetric:
            endpoint: str
            response_time: float
            status: str
            timestamp: float
            error_message: Optional[str] = None
        
        metric = APIPerformanceMetric(
            endpoint=endpoint,
            response_time=response_time,
            status=status,
            timestamp=time.time(),
            error_message=error_message
        )
        
        self.api_metrics.append(metric)
        self.performance_stats["api_calls_tracked"] += 1
        
        # Update error recovery stats and circuit breakers
        if status == "error":
            self.error_recovery_stats["api_errors"] += 1
            self._trigger_circuit_breaker("api_calls")
        elif status == "timeout":
            self.error_recovery_stats["api_timeouts"] += 1
            self._trigger_circuit_breaker("api_calls")
        
        # Legacy compatibility
        self.track_api_call(endpoint, response_time, status)
    
    def track_trade_performance(self, trade_id: str, symbol: str, total_time: float,
                              phase_times: Dict[str, float], orders_placed: int, 
                              orders_failed: int, concurrent_efficiency: float):
        """Track trade execution performance with detailed metrics"""
        from dataclasses import dataclass
        
        @dataclass
        class TradeExecutionMetric:
            trade_id: str
            symbol: str
            total_time: float
            phase_times: Dict[str, float]
            orders_placed: int
            orders_failed: int
            concurrent_efficiency: float
            timestamp: float
        
        metric = TradeExecutionMetric(
            trade_id=trade_id,
            symbol=symbol,
            total_time=total_time,
            phase_times=phase_times,
            orders_placed=orders_placed,
            orders_failed=orders_failed,
            concurrent_efficiency=concurrent_efficiency,
            timestamp=time.time()
        )
        
        self.trade_metrics.append(metric)
        self.performance_stats["trades_tracked"] += 1
        
        # Handle trade failures
        if orders_failed > 0:
            self.error_recovery_stats["trade_failures"] += orders_failed
            if orders_failed >= orders_placed * 0.5:  # 50% failure rate
                self._trigger_circuit_breaker("trade_execution")
        
        # Legacy compatibility
        self.track_execution(f"trade_{symbol}", total_time)
    
    def _trigger_circuit_breaker(self, circuit_name: str):
        """Trigger circuit breaker for failed operations"""
        if circuit_name not in self.circuit_breakers:
            return
        
        breaker = self.circuit_breakers[circuit_name]
        breaker["failures"] += 1
        
        if breaker["failures"] >= breaker["threshold"] and not breaker["open"]:
            breaker["open"] = True
            breaker["reset_time"] = time.time() + 300  # 5 minute circuit breaker
            
            logger.warning(f"🚨 Circuit breaker OPEN for {circuit_name} ({breaker['failures']} failures)")
            self.error_recovery_stats["system_alerts"] += 1
            self.performance_stats["total_alerts"] += 1
    
    def _update_circuit_breakers(self):
        """Update circuit breaker states and reset if needed"""
        current_time = time.time()
        
        for name, breaker in self.circuit_breakers.items():
            if breaker["open"] and current_time > breaker["reset_time"]:
                breaker["open"] = False
                breaker["failures"] = 0
                self.error_recovery_stats["successful_recoveries"] += 1
                logger.info(f"✅ Circuit breaker CLOSED for {name}")
    
    def is_circuit_open(self, circuit_name: str) -> bool:
        """Check if a circuit breaker is open"""
        if circuit_name not in self.circuit_breakers:
            return False
        return self.circuit_breakers[circuit_name]["open"]
    
    def get_api_performance_report(self, minutes: int = 60) -> Dict[str, Any]:
        """Get detailed API performance report for the last N minutes"""
        cutoff_time = time.time() - (minutes * 60)
        recent_api = [m for m in self.api_metrics if m.timestamp > cutoff_time]
        
        if not recent_api:
            return {"status": "no_data", "period_minutes": minutes}
        
        # Group by endpoint
        by_endpoint = {}
        for metric in recent_api:
            if metric.endpoint not in by_endpoint:
                by_endpoint[metric.endpoint] = {
                    "calls": 0,
                    "total_time": 0,
                    "errors": 0,
                    "timeouts": 0
                }
            
            endpoint_stats = by_endpoint[metric.endpoint]
            endpoint_stats["calls"] += 1
            endpoint_stats["total_time"] += metric.response_time
            
            if metric.status == "error":
                endpoint_stats["errors"] += 1
            elif metric.status == "timeout":
                endpoint_stats["timeouts"] += 1
        
        # Calculate averages
        for endpoint, stats in by_endpoint.items():
            stats["average_response_time"] = stats["total_time"] / stats["calls"]
            stats["error_rate"] = (stats["errors"] + stats["timeouts"]) / stats["calls"] * 100
        
        return {
            "period_minutes": minutes,
            "total_calls": len(recent_api),
            "by_endpoint": by_endpoint,
            "overall": {
                "average_response_time": sum(m.response_time for m in recent_api) / len(recent_api),
                "error_rate": len([m for m in recent_api if m.status in ["error", "timeout"]]) / len(recent_api) * 100
            }
        }
    
    def get_system_health_check(self) -> Dict[str, Any]:
        """Comprehensive system health check based on current metrics"""
        current_metrics = self.get_current_performance_metrics()
        
        health_checks = {
            "overall_status": "healthy",
            "timestamp": time.time(),
            "checks": {},
            "circuit_breakers": {},
            "recommendations": []
        }
        
        # CPU health check
        if current_metrics.cpu_percent > self.alert_thresholds["cpu_percent"]:
            health_checks["overall_status"] = "unhealthy"
            health_checks["checks"]["cpu"] = {
                "status": "critical",
                "value": current_metrics.cpu_percent,
                "threshold": self.alert_thresholds["cpu_percent"]
            }
            health_checks["recommendations"].append("Consider reducing concurrent operations or optimizing CPU-intensive tasks")
        elif current_metrics.cpu_percent > self.alert_thresholds["cpu_percent"] * 0.8:
            health_checks["checks"]["cpu"] = {
                "status": "warning", 
                "value": current_metrics.cpu_percent,
                "threshold": self.alert_thresholds["cpu_percent"]
            }
        else:
            health_checks["checks"]["cpu"] = {"status": "healthy", "value": current_metrics.cpu_percent}
        
        # Memory health check
        if current_metrics.memory_metrics.rss_mb > self.alert_thresholds["memory_mb"]:
            health_checks["overall_status"] = "unhealthy"
            health_checks["checks"]["memory"] = {
                "status": "critical",
                "value_mb": current_metrics.memory_metrics.rss_mb,
                "threshold_mb": self.alert_thresholds["memory_mb"],
                "percent": current_metrics.memory_metrics.percent
            }
            health_checks["recommendations"].append("Consider running garbage collection or optimizing memory usage")
        elif current_metrics.memory_metrics.rss_mb > self.alert_thresholds["memory_mb"] * 0.8:
            health_checks["checks"]["memory"] = {
                "status": "warning",
                "value_mb": current_metrics.memory_metrics.rss_mb,
                "percent": current_metrics.memory_metrics.percent
            }
        else:
            health_checks["checks"]["memory"] = {
                "status": "healthy", 
                "value_mb": current_metrics.memory_metrics.rss_mb,
                "percent": current_metrics.memory_metrics.percent
            }
        
        # Cache performance check
        if current_metrics.cache_hit_rate < self.alert_thresholds["cache_hit_rate"]:
            if health_checks["overall_status"] == "healthy":
                health_checks["overall_status"] = "degraded"
            health_checks["checks"]["cache"] = {
                "status": "warning",
                "hit_rate": current_metrics.cache_hit_rate,
                "threshold": self.alert_thresholds["cache_hit_rate"]
            }
            health_checks["recommendations"].append("Consider cache optimization or tuning cache TTL values")
        else:
            health_checks["checks"]["cache"] = {"status": "healthy", "hit_rate": current_metrics.cache_hit_rate}
        
        # Circuit breaker status
        for name, breaker in self.circuit_breakers.items():
            health_checks["circuit_breakers"][name] = {
                "open": breaker["open"],
                "failures": breaker["failures"],
                "threshold": breaker["threshold"]
            }
            
            if breaker["open"]:
                health_checks["overall_status"] = "unhealthy"
                health_checks["recommendations"].append(f"Circuit breaker '{name}' is open - investigate underlying issues")
        
        # GC object count check
        if current_metrics.memory_metrics.gc_objects > self.alert_thresholds["gc_objects"]:
            health_checks["checks"]["gc_objects"] = {
                "status": "warning",
                "count": current_metrics.memory_metrics.gc_objects,
                "threshold": self.alert_thresholds["gc_objects"]
            }
            health_checks["recommendations"].append("Consider running strategic garbage collection")
        else:
            health_checks["checks"]["gc_objects"] = {
                "status": "healthy",
                "count": current_metrics.memory_metrics.gc_objects
            }
        
        return health_checks
            
    # Legacy compatibility methods
    def track_api_call(self, endpoint: str, duration: float, status: str = "success"):
        """Track API call performance (legacy compatibility)"""
        self.api_calls[endpoint].append({
            'timestamp': datetime.now(),
            'duration': duration,
            'status': status
        })

        if status != "success":
            self.error_counts[endpoint] += 1

    def track_execution(self, operation: str, duration: float):
        """Track operation execution time (legacy compatibility)"""
        self.execution_times[operation].append({
            'timestamp': datetime.now(),
            'duration': duration
        })

    def track_resources(self):
        """Track system resource usage (legacy compatibility)"""
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
        """Get performance statistics (legacy compatibility)"""
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
        """Get system health status (legacy compatibility)"""
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
        
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        if not self.metrics_history:
            return {"status": "No metrics available"}
        
        recent_metrics = list(self.metrics_history)[-10:]  # Last 10 entries
        current = recent_metrics[-1] if recent_metrics else None
        
        if not current:
            return {"status": "No current metrics"}
        
        # Calculate averages
        avg_memory = sum(m.memory_metrics.rss_mb for m in recent_metrics) / len(recent_metrics)
        avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
        avg_tasks = sum(m.active_tasks for m in recent_metrics) / len(recent_metrics)
        
        # Memory trend analysis
        memory_trend = "stable"
        if len(recent_metrics) >= 5:
            first_half = recent_metrics[:len(recent_metrics)//2]
            second_half = recent_metrics[len(recent_metrics)//2:]
            
            first_avg = sum(m.memory_metrics.rss_mb for m in first_half) / len(first_half)
            second_avg = sum(m.memory_metrics.rss_mb for m in second_half) / len(second_half)
            
            change_percent = ((second_avg - first_avg) / first_avg) * 100
            if change_percent > 10:
                memory_trend = "increasing"
            elif change_percent < -10:
                memory_trend = "decreasing"
        
        return {
            "timestamp": current.timestamp,
            "uptime_hours": (time.time() - time.mktime(self.start_time.timetuple())) / 3600,
            "current": {
                "memory_mb": current.memory_metrics.rss_mb,
                "memory_percent": current.memory_metrics.percent,
                "cpu_percent": current.cpu_percent,
                "active_tasks": current.active_tasks,
                "gc_objects": current.memory_metrics.gc_objects,
                "cache_hit_rate": current.cache_hit_rate
            },
            "averages": {
                "memory_mb": avg_memory,
                "cpu_percent": avg_cpu,
                "active_tasks": avg_tasks
            },
            "trends": {
                "memory_trend": memory_trend
            },
            "optimization_mode": self._optimization_mode,
            "metrics_collected": len(self.metrics_history)
        }

# Backward compatibility alias
PerformanceMonitor = EnhancedPerformanceMonitor

class MemoryLeakDetector:
    """Detect potential memory leaks in long-running applications"""
    
    def __init__(self, sample_size: int = 20):
        self.sample_size = sample_size
        self.memory_samples: deque = deque(maxlen=sample_size)
        self.leak_threshold = 1.5  # 50% increase considered potential leak
        
    def check_for_leaks(self, memory_metrics: MemoryMetrics) -> bool:
        """Check for potential memory leaks"""
        self.memory_samples.append(memory_metrics.rss_mb)
        
        if len(self.memory_samples) < self.sample_size:
            return False
        
        # Calculate trend
        samples = list(self.memory_samples)
        first_quarter = samples[:len(samples)//4]
        last_quarter = samples[-len(samples)//4:]
        
        if not first_quarter or not last_quarter:
            return False
        
        first_avg = sum(first_quarter) / len(first_quarter)
        last_avg = sum(last_quarter) / len(last_quarter)
        
        if first_avg > 0:
            growth_ratio = last_avg / first_avg
            
            if growth_ratio > self.leak_threshold:
                logger.warning(
                    f"🚨 Potential memory leak detected: "
                    f"{first_avg:.1f}MB → {last_avg:.1f}MB "
                    f"(growth: {(growth_ratio-1)*100:.1f}%)"
                )
                return True
        
        return False

# Global instance (enhanced version)
performance_monitor = PerformanceMonitor()

# Enhanced global functions
def get_enhanced_performance_monitor() -> EnhancedPerformanceMonitor:
    """Get or create global enhanced performance monitor instance"""
    global performance_monitor
    if not isinstance(performance_monitor, EnhancedPerformanceMonitor):
        performance_monitor = EnhancedPerformanceMonitor()
    return performance_monitor

async def start_performance_monitoring() -> None:
    """Start global performance monitoring"""
    monitor = get_enhanced_performance_monitor()
    
    # Start background monitoring loop
    async def _monitoring_loop():
        while True:
            try:
                # Record current metrics
                metrics = monitor.record_metrics()
                
                # Perform cleanup if needed
                current_time = time.time()
                if (current_time - monitor._last_cleanup) > monitor._cleanup_interval:
                    await monitor.optimize_performance()
                    monitor._last_cleanup = current_time
                
                # Log periodic status
                if len(monitor.metrics_history) % 10 == 0:  # Every 10 minutes
                    uptime_hours = (time.time() - time.mktime(monitor.start_time.timetuple())) / 3600
                    logger.info(
                        f"📊 Performance Status (uptime: {uptime_hours:.1f}h): "
                        f"Memory: {metrics.memory_metrics.rss_mb:.1f}MB ({metrics.memory_metrics.percent:.1f}%), "
                        f"CPU: {metrics.cpu_percent:.1f}%, "
                        f"Tasks: {metrics.active_tasks}, "
                        f"GC Objects: {metrics.memory_metrics.gc_objects}"
                    )
                
                await asyncio.sleep(monitor._monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in performance monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    if monitor._monitoring_task is None or monitor._monitoring_task.done():
        monitor._monitoring_task = asyncio.create_task(_monitoring_loop())
        logger.info("🎯 Enhanced performance monitoring started")

async def stop_performance_monitoring() -> None:
    """Stop global performance monitoring"""
    monitor = get_enhanced_performance_monitor()
    if monitor._monitoring_task:
        monitor._monitoring_task.cancel()
        try:
            await monitor._monitoring_task
        except asyncio.CancelledError:
            pass
    logger.info("🛑 Performance monitoring stopped")

async def optimize_bot_performance(force: bool = False) -> bool:
    """Optimize bot performance using global monitor"""
    monitor = get_enhanced_performance_monitor()
    return await monitor.optimize_performance(force=force)

def get_bot_performance_report() -> Dict[str, Any]:
    """Get comprehensive performance report"""
    monitor = get_enhanced_performance_monitor()
    return monitor.get_performance_report()

# New convenience functions for 2025 optimization features

def track_api_performance(endpoint: str, response_time: float, status: str, error_message: str = None):
    """Convenience function to track API performance"""
    monitor = get_enhanced_performance_monitor()
    monitor.track_api_performance(endpoint, response_time, status, error_message)

def track_trade_performance(trade_id: str, symbol: str, total_time: float,
                          phase_times: Dict[str, float], orders_placed: int, 
                          orders_failed: int, concurrent_efficiency: float):
    """Convenience function to track trade performance"""
    monitor = get_enhanced_performance_monitor()
    monitor.track_trade_performance(
        trade_id, symbol, total_time, phase_times, 
        orders_placed, orders_failed, concurrent_efficiency
    )

def is_system_healthy() -> bool:
    """Check if system is performing within acceptable parameters"""
    monitor = get_enhanced_performance_monitor()
    health_check = monitor.get_system_health_check()
    return health_check.get("overall_status", "unhealthy") in ["healthy", "degraded"]

def is_circuit_breaker_open(circuit_name: str) -> bool:
    """Check if a circuit breaker is currently open"""
    monitor = get_enhanced_performance_monitor()
    return monitor.is_circuit_open(circuit_name)

def get_api_performance_report(minutes: int = 60) -> Dict[str, Any]:
    """Get API performance report for the last N minutes"""
    monitor = get_enhanced_performance_monitor()
    return monitor.get_api_performance_report(minutes)

def get_system_health_report() -> Dict[str, Any]:
    """Get comprehensive system health report"""
    monitor = get_enhanced_performance_monitor()
    return monitor.get_system_health_check()

def get_performance_statistics() -> Dict[str, Any]:
    """Get current performance statistics"""
    monitor = get_enhanced_performance_monitor()
    return {
        **monitor.performance_stats,
        "error_recovery": monitor.error_recovery_stats,
        "circuit_breakers": {
            name: {"open": breaker["open"], "failures": breaker["failures"]}
            for name, breaker in monitor.circuit_breakers.items()
        },
        "uptime_hours": (time.time() - time.mktime(monitor.start_time.timetuple())) / 3600
    }

def track_performance(operation: str):
    """Decorator to track function performance (enhanced version)"""
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
    """Enhanced background task to monitor resources"""
    while True:
        try:
            performance_monitor.track_resources()
            
            # Also record enhanced metrics if using enhanced monitor
            if isinstance(performance_monitor, EnhancedPerformanceMonitor):
                performance_monitor.record_metrics()
            
            await asyncio.sleep(60)  # Check every minute
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in resource monitoring: {e}")
            await asyncio.sleep(60)