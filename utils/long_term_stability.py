#!/usr/bin/env python3
"""
Long-Term Stability System for Multi-Week Bot Operation
Enterprise-grade reliability features to prevent memory leaks, connection issues,
and data corruption during extended operation without restart.
"""
import asyncio
import gc
import logging
import os
import psutil
import time
import weakref
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

class LongTermStabilityManager:
    """
    Comprehensive stability management for weeks+ of continuous operation
    Handles memory management, connection health, data integrity, and system monitoring
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.last_memory_cleanup = 0
        self.last_connection_refresh = 0
        self.last_cache_cleanup = 0
        self.last_orphan_cleanup = 0
        self.last_health_check = 0
        self.last_log_cleanup = 0
        
        # System health tracking
        self.health_metrics = {
            "memory_usage_mb": 0,
            "memory_percent": 0,
            "cpu_percent": 0,
            "disk_usage_percent": 0,
            "active_connections": 0,
            "cache_size_mb": 0,
            "uptime_hours": 0,
            "last_gc_count": 0,
            "pickle_file_size_mb": 0
        }
        
        # Stability warnings and alerts
        self.stability_warnings = []
        self.last_alert_time = {}
        self.alert_cooldown = 3600  # 1 hour between same alerts
        
        # Memory leak detection
        self.memory_baseline = None
        self.memory_growth_tracking = []
        self.max_memory_growth_mb = 500  # Alert if memory grows >500MB
        
        logger.info("🏭 Long-Term Stability Manager initialized")
    
    async def start_stability_monitoring(self):
        """Start all long-term stability background tasks"""
        from config.settings import ENABLE_LONG_TERM_STABILITY
        
        if not ENABLE_LONG_TERM_STABILITY:
            logger.info("📊 Long-term stability monitoring disabled")
            return
        
        logger.info("🏭 Starting enterprise-grade stability monitoring")
        
        # Start all stability tasks concurrently
        tasks = [
            asyncio.create_task(self._memory_management_loop()),
            asyncio.create_task(self._connection_health_loop()),
            asyncio.create_task(self._cache_health_loop()),
            asyncio.create_task(self._data_integrity_loop()),
            asyncio.create_task(self._system_health_monitoring_loop()),
            asyncio.create_task(self._log_management_loop())
        ]
        
        logger.info("✅ All stability monitoring tasks started")
        
        # Don't wait for tasks to complete (they run indefinitely)
        return tasks
    
    async def _memory_management_loop(self):
        """Advanced memory management and leak prevention"""
        from config.settings import (
            MEMORY_CLEANUP_INTERVAL, AGGRESSIVE_MEMORY_CLEANUP,
            MEMORY_USAGE_THRESHOLD_MB, FORCE_GARBAGE_COLLECTION
        )
        
        logger.info(f"💾 Memory management started (interval: {MEMORY_CLEANUP_INTERVAL/60:.1f}min)")
        
        while True:
            try:
                await asyncio.sleep(MEMORY_CLEANUP_INTERVAL)
                
                # Get current memory usage
                process = psutil.Process()
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                
                # Set baseline on first run
                if self.memory_baseline is None:
                    self.memory_baseline = memory_mb
                    logger.info(f"💾 Memory baseline set: {memory_mb:.1f}MB")
                    continue
                
                # Track memory growth
                memory_growth = memory_mb - self.memory_baseline
                self.memory_growth_tracking.append({
                    'timestamp': time.time(),
                    'memory_mb': memory_mb,
                    'growth_mb': memory_growth
                })
                
                # Keep only last 24 hours of data
                cutoff_time = time.time() - 86400
                self.memory_growth_tracking = [
                    m for m in self.memory_growth_tracking 
                    if m['timestamp'] > cutoff_time
                ]
                
                # Log memory status
                logger.info(f"💾 Memory: {memory_mb:.1f}MB (growth: {memory_growth:+.1f}MB)")
                
                # Check for memory issues
                if memory_mb > MEMORY_USAGE_THRESHOLD_MB:
                    logger.warning(f"⚠️ High memory usage: {memory_mb:.1f}MB (threshold: {MEMORY_USAGE_THRESHOLD_MB}MB)")
                    await self._emergency_memory_cleanup()
                
                # Detect memory leaks
                if memory_growth > self.max_memory_growth_mb:
                    logger.error(f"🚨 Potential memory leak detected: {memory_growth:.1f}MB growth")
                    await self._memory_leak_mitigation()
                
                # Regular memory cleanup
                if AGGRESSIVE_MEMORY_CLEANUP:
                    await self._comprehensive_memory_cleanup()
                
                # Force garbage collection
                if FORCE_GARBAGE_COLLECTION:
                    collected = gc.collect()
                    if collected > 0:
                        logger.debug(f"🗑️ Garbage collection: {collected} objects collected")
                
                # Update health metrics
                self.health_metrics.update({
                    "memory_usage_mb": memory_mb,
                    "memory_percent": process.memory_percent(),
                    "last_gc_count": collected if FORCE_GARBAGE_COLLECTION else 0
                })
                
            except Exception as e:
                logger.error(f"❌ Error in memory management: {e}")
                await asyncio.sleep(60)  # Wait before retry
    
    async def _comprehensive_memory_cleanup(self):
        """Comprehensive memory cleanup without affecting functionality"""
        logger.info("🧹 Starting comprehensive memory cleanup")
        
        try:
            # Clean up Enhanced TP/SL Manager caches
            from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
            
            # Clean execution cache if not in execution mode
            if not enhanced_tp_sl_manager.is_execution_mode_active():
                cache_size = len(enhanced_tp_sl_manager._execution_cache)
                enhanced_tp_sl_manager._execution_cache.clear()
                if cache_size > 0:
                    logger.debug(f"🧹 Cleared execution cache: {cache_size} entries")
            
            # Clean old urgency cache entries
            current_time = time.time()
            old_urgency_keys = []
            for key, (urgency, cached_time) in enhanced_tp_sl_manager._position_urgency_cache.items():
                if current_time - cached_time > 1800:  # 30 minutes old
                    old_urgency_keys.append(key)
            
            for key in old_urgency_keys:
                del enhanced_tp_sl_manager._position_urgency_cache[key]
            
            if old_urgency_keys:
                logger.debug(f"🧹 Cleaned urgency cache: {len(old_urgency_keys)} old entries")
            
            # Clean up global cache
            from utils.cache import enhanced_cache
            stats_before = enhanced_cache.get_stats()
            
            # Force cleanup of expired entries
            with enhanced_cache._lock:
                enhanced_cache._cleanup_expired()
                enhanced_cache._cleanup_lru()
            
            stats_after = enhanced_cache.get_stats()
            if stats_before["total_entries"] != stats_after["total_entries"]:
                logger.info(f"🧹 Cache cleanup: {stats_before['total_entries']} → {stats_after['total_entries']} entries")
            
            # Clean up API batch processor
            try:
                from utils.api_batch_processor import get_batch_processor
                batch_processor = get_batch_processor()
                
                # Clean old request queues (if any)
                if hasattr(batch_processor, 'request_queue'):
                    queue_size = batch_processor.request_queue.qsize()
                    if queue_size > 1000:  # Large queue size
                        logger.warning(f"⚠️ Large API request queue: {queue_size} items")
            except Exception as e:
                logger.debug(f"API batch processor cleanup skipped: {e}")
            
            logger.info("✅ Comprehensive memory cleanup completed")
            
        except Exception as e:
            logger.error(f"❌ Error in comprehensive memory cleanup: {e}")
    
    async def _emergency_memory_cleanup(self):
        """Emergency memory cleanup when threshold is exceeded"""
        logger.warning("🚨 Emergency memory cleanup initiated")
        
        try:
            # Aggressive cache clearing
            from utils.cache import enhanced_cache
            enhanced_cache.clear()
            logger.warning("🚨 Emergency: All caches cleared")
            
            # Force multiple garbage collection cycles
            for i in range(3):
                collected = gc.collect()
                logger.warning(f"🚨 Emergency GC cycle {i+1}: {collected} objects")
                await asyncio.sleep(1)
            
            # Clear execution caches regardless of state
            from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
            enhanced_tp_sl_manager._execution_cache.clear()
            enhanced_tp_sl_manager._monitoring_cache.clear()
            enhanced_tp_sl_manager._position_urgency_cache.clear()
            
            logger.warning("🚨 Emergency memory cleanup completed")
            
        except Exception as e:
            logger.error(f"❌ Emergency memory cleanup failed: {e}")
    
    async def _memory_leak_mitigation(self):
        """Advanced memory leak detection and mitigation"""
        logger.error("🔍 Investigating potential memory leak")
        
        try:
            # Analyze memory growth pattern
            if len(self.memory_growth_tracking) >= 5:
                recent_growth = [m['growth_mb'] for m in self.memory_growth_tracking[-5:]]
                avg_growth = sum(recent_growth) / len(recent_growth)
                
                logger.error(f"🔍 Average memory growth (last 5 checks): {avg_growth:.1f}MB")
                
                if avg_growth > 100:  # Growing >100MB per check
                    logger.error("🚨 CRITICAL: Aggressive memory leak detected")
                    
                    # Emergency measures
                    await self._emergency_memory_cleanup()
                    
                    # Alert about potential need for restart
                    logger.error("🚨 Consider restarting bot if memory continues growing")
            
        except Exception as e:
            logger.error(f"❌ Memory leak investigation failed: {e}")
    
    async def _connection_health_loop(self):
        """Monitor and refresh connection pools for long-term stability"""
        from config.settings import (
            CONNECTION_POOL_REFRESH_INTERVAL, CONNECTION_HEALTH_CHECK_INTERVAL,
            STALE_CONNECTION_TIMEOUT
        )
        
        logger.info(f"🔗 Connection health monitoring started (refresh: {CONNECTION_POOL_REFRESH_INTERVAL/3600:.1f}h)")
        
        while True:
            try:
                await asyncio.sleep(CONNECTION_HEALTH_CHECK_INTERVAL)
                
                # Check connection pool health
                try:
                    from utils.connection_pool import enhanced_pool
                    if hasattr(enhanced_pool, 'get_stats'):
                        stats = enhanced_pool.get_stats()
                        active_connections = stats.get('active_connections', 0)
                        
                        logger.debug(f"🔗 Connection pool: {active_connections} active connections")
                        self.health_metrics["active_connections"] = active_connections
                        
                        # Check if pool refresh is needed
                        if time.time() - self.last_connection_refresh > CONNECTION_POOL_REFRESH_INTERVAL:
                            await self._refresh_connection_pools()
                            
                except Exception as e:
                    logger.debug(f"Connection pool health check skipped: {e}")
                
            except Exception as e:
                logger.error(f"❌ Error in connection health monitoring: {e}")
                await asyncio.sleep(60)
    
    async def _refresh_connection_pools(self):
        """Refresh connection pools to prevent stale connections"""
        logger.info("🔄 Refreshing connection pools")
        
        try:
            # Refresh HTTP connection pools
            from utils.connection_pool import enhanced_pool
            if hasattr(enhanced_pool, 'refresh_connections'):
                refreshed = await enhanced_pool.refresh_connections()
                logger.info(f"✅ Connection pool refreshed: {refreshed} connections")
            
            self.last_connection_refresh = time.time()
            
        except Exception as e:
            logger.error(f"❌ Connection pool refresh failed: {e}")
    
    async def _cache_health_loop(self):
        """Monitor cache health and prevent bloat"""
        from config.settings import (
            CACHE_HEALTH_CHECK_INTERVAL, CACHE_MAX_AGE_HOURS, CACHE_SIZE_LIMIT_MB
        )
        
        logger.info(f"💾 Cache health monitoring started (interval: {CACHE_HEALTH_CHECK_INTERVAL/60:.1f}min)")
        
        while True:
            try:
                await asyncio.sleep(CACHE_HEALTH_CHECK_INTERVAL)
                
                from utils.cache import enhanced_cache
                stats = enhanced_cache.get_stats()
                
                # Estimate cache size (rough calculation)
                cache_size_mb = stats.get("total_entries", 0) * 0.001  # Rough estimate
                self.health_metrics["cache_size_mb"] = cache_size_mb
                
                logger.debug(f"💾 Cache health: {stats['total_entries']} entries, ~{cache_size_mb:.1f}MB")
                
                # Check cache size limits
                if cache_size_mb > CACHE_SIZE_LIMIT_MB:
                    logger.warning(f"⚠️ Cache size limit exceeded: {cache_size_mb:.1f}MB > {CACHE_SIZE_LIMIT_MB}MB")
                    await self._aggressive_cache_cleanup()
                
                # Check cache hit rate
                hit_rate = stats.get("hit_rate", 0)
                if hit_rate < 0.3 and stats.get("hit_count", 0) > 100:
                    logger.warning(f"⚠️ Low cache hit rate: {hit_rate*100:.1f}%")
                
            except Exception as e:
                logger.error(f"❌ Error in cache health monitoring: {e}")
                await asyncio.sleep(60)
    
    async def _aggressive_cache_cleanup(self):
        """Aggressive cache cleanup when limits are exceeded"""
        logger.warning("🧹 Aggressive cache cleanup initiated")
        
        try:
            from utils.cache import enhanced_cache
            
            # Clear all volatile caches
            from utils.cache import invalidate_volatile_caches
            invalidate_volatile_caches()
            
            # Force LRU cleanup
            with enhanced_cache._lock:
                enhanced_cache._cleanup_lru()
            
            logger.warning("✅ Aggressive cache cleanup completed")
            
        except Exception as e:
            logger.error(f"❌ Aggressive cache cleanup failed: {e}")
    
    async def _data_integrity_loop(self):
        """Monitor data integrity and cleanup orphaned data"""
        from config.settings import (
            ORPHANED_DATA_CLEANUP_INTERVAL, PICKLE_INTEGRITY_CHECK_INTERVAL,
            BACKUP_RETENTION_DAYS
        )
        
        logger.info(f"🔍 Data integrity monitoring started (orphan cleanup: {ORPHANED_DATA_CLEANUP_INTERVAL/3600:.1f}h)")
        
        while True:
            try:
                await asyncio.sleep(min(ORPHANED_DATA_CLEANUP_INTERVAL, PICKLE_INTEGRITY_CHECK_INTERVAL))
                
                # Check pickle file integrity
                if time.time() - self.last_health_check > PICKLE_INTEGRITY_CHECK_INTERVAL:
                    await self._check_pickle_integrity()
                
                # Cleanup orphaned data
                if time.time() - self.last_orphan_cleanup > ORPHANED_DATA_CLEANUP_INTERVAL:
                    await self._cleanup_orphaned_data()
                
                # Cleanup old backups
                await self._cleanup_old_backups(BACKUP_RETENTION_DAYS)
                
            except Exception as e:
                logger.error(f"❌ Error in data integrity monitoring: {e}")
                await asyncio.sleep(300)
    
    async def _check_pickle_integrity(self):
        """Check pickle file integrity and size"""
        try:
            pickle_path = Path("bybit_bot_dashboard_v4.1_enhanced.pkl")
            
            if pickle_path.exists():
                size_mb = pickle_path.stat().st_size / 1024 / 1024
                self.health_metrics["pickle_file_size_mb"] = size_mb
                
                logger.debug(f"🔍 Pickle file size: {size_mb:.1f}MB")
                
                # Check if file is getting too large
                if size_mb > 100:  # 100MB threshold
                    logger.warning(f"⚠️ Large pickle file: {size_mb:.1f}MB")
                
                # Basic integrity check
                try:
                    import pickle
                    with open(pickle_path, 'rb') as f:
                        pickle.load(f)
                    logger.debug("✅ Pickle file integrity check passed")
                except Exception as e:
                    logger.error(f"🚨 Pickle file integrity check FAILED: {e}")
            
            self.last_health_check = time.time()
            
        except Exception as e:
            logger.error(f"❌ Pickle integrity check failed: {e}")
    
    async def _cleanup_orphaned_data(self):
        """Clean up orphaned monitors and data"""
        logger.info("🧹 Cleaning up orphaned data")
        
        try:
            # Use existing enhanced TP/SL manager cleanup
            from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
            await enhanced_tp_sl_manager._cleanup_orphaned_monitors()
            
            self.last_orphan_cleanup = time.time()
            logger.info("✅ Orphaned data cleanup completed")
            
        except Exception as e:
            logger.error(f"❌ Orphaned data cleanup failed: {e}")
    
    async def _cleanup_old_backups(self, retention_days: int):
        """Clean up old backup files"""
        try:
            current_time = time.time()
            retention_seconds = retention_days * 86400
            
            backup_pattern = "*.pkl.backup*"
            deleted_count = 0
            
            for backup_file in Path(".").glob(backup_pattern):
                if backup_file.is_file():
                    file_age = current_time - backup_file.stat().st_mtime
                    if file_age > retention_seconds:
                        backup_file.unlink()
                        deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"🧹 Cleaned up {deleted_count} old backup files (>{retention_days} days)")
            
        except Exception as e:
            logger.error(f"❌ Backup cleanup failed: {e}")
    
    async def _system_health_monitoring_loop(self):
        """Comprehensive system health monitoring"""
        from config.settings import SYSTEM_HEALTH_CHECK_INTERVAL, HEALTH_ALERT_THRESHOLD
        
        logger.info(f"📊 System health monitoring started (interval: {SYSTEM_HEALTH_CHECK_INTERVAL/60:.1f}min)")
        
        while True:
            try:
                await asyncio.sleep(SYSTEM_HEALTH_CHECK_INTERVAL)
                
                # Collect system metrics
                process = psutil.Process()
                
                self.health_metrics.update({
                    "cpu_percent": process.cpu_percent(),
                    "disk_usage_percent": psutil.disk_usage('.').percent,
                    "uptime_hours": (time.time() - self.start_time) / 3600
                })
                
                # Check for health issues
                alerts = []
                
                if self.health_metrics["memory_percent"] > HEALTH_ALERT_THRESHOLD * 100:
                    alerts.append(f"High memory usage: {self.health_metrics['memory_percent']:.1f}%")
                
                if self.health_metrics["cpu_percent"] > HEALTH_ALERT_THRESHOLD * 100:
                    alerts.append(f"High CPU usage: {self.health_metrics['cpu_percent']:.1f}%")
                
                if self.health_metrics["disk_usage_percent"] > HEALTH_ALERT_THRESHOLD * 100:
                    alerts.append(f"High disk usage: {self.health_metrics['disk_usage_percent']:.1f}%")
                
                # Log health status
                uptime_hours = self.health_metrics["uptime_hours"]
                if uptime_hours > 0 and int(uptime_hours) % 24 == 0 and int(uptime_hours) > 0:
                    # Log daily health summary
                    logger.info(f"📊 Daily Health Summary (Day {int(uptime_hours/24)}):")
                    logger.info(f"   Memory: {self.health_metrics['memory_usage_mb']:.1f}MB ({self.health_metrics['memory_percent']:.1f}%)")
                    logger.info(f"   CPU: {self.health_metrics['cpu_percent']:.1f}%")
                    logger.info(f"   Disk: {self.health_metrics['disk_usage_percent']:.1f}%")
                    logger.info(f"   Cache: {self.health_metrics['cache_size_mb']:.1f}MB")
                    logger.info(f"   Connections: {self.health_metrics['active_connections']}")
                
                # Handle alerts with cooldown
                for alert in alerts:
                    alert_key = alert.split(':')[0]  # Use first part as key
                    if self._should_send_alert(alert_key):
                        logger.warning(f"🚨 System Health Alert: {alert}")
                        self.last_alert_time[alert_key] = time.time()
                
            except Exception as e:
                logger.error(f"❌ Error in system health monitoring: {e}")
                await asyncio.sleep(60)
    
    def _should_send_alert(self, alert_key: str) -> bool:
        """Check if alert should be sent (respects cooldown)"""
        last_sent = self.last_alert_time.get(alert_key, 0)
        return time.time() - last_sent > self.alert_cooldown
    
    async def _log_management_loop(self):
        """Manage log files and prevent disk space issues"""
        from config.settings import LOG_CLEANUP_INTERVAL
        
        logger.info(f"📋 Log management started (cleanup: {LOG_CLEANUP_INTERVAL/3600:.1f}h)")
        
        while True:
            try:
                await asyncio.sleep(LOG_CLEANUP_INTERVAL)
                
                # Log rotation is handled by Python's RotatingFileHandler
                # This loop handles additional cleanup tasks
                
                # Check log directory size
                log_files = list(Path(".").glob("*.log*"))
                total_log_size = sum(f.stat().st_size for f in log_files if f.is_file()) / 1024 / 1024
                
                logger.debug(f"📋 Total log size: {total_log_size:.1f}MB ({len(log_files)} files)")
                
                if total_log_size > 1000:  # 1GB of logs
                    logger.warning(f"⚠️ Large log directory: {total_log_size:.1f}MB")
                
            except Exception as e:
                logger.error(f"❌ Error in log management: {e}")
                await asyncio.sleep(3600)  # Wait an hour on error
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report"""
        uptime_days = self.health_metrics["uptime_hours"] / 24
        
        return {
            "uptime": {
                "hours": self.health_metrics["uptime_hours"],
                "days": uptime_days,
                "status": "excellent" if uptime_days < 7 else "good" if uptime_days < 30 else "long_term"
            },
            "memory": {
                "usage_mb": self.health_metrics["memory_usage_mb"],
                "percent": self.health_metrics["memory_percent"],
                "status": "good" if self.health_metrics["memory_percent"] < 70 else "warning"
            },
            "performance": {
                "cpu_percent": self.health_metrics["cpu_percent"],
                "connections": self.health_metrics["active_connections"],
                "cache_size_mb": self.health_metrics["cache_size_mb"]
            },
            "data_integrity": {
                "pickle_size_mb": self.health_metrics["pickle_file_size_mb"],
                "last_cleanup": self.last_orphan_cleanup
            },
            "stability_score": self._calculate_stability_score()
        }
    
    def _calculate_stability_score(self) -> float:
        """Calculate overall stability score (0-100)"""
        score = 100.0
        
        # Deduct for high resource usage
        if self.health_metrics["memory_percent"] > 80:
            score -= 20
        elif self.health_metrics["memory_percent"] > 60:
            score -= 10
        
        if self.health_metrics["cpu_percent"] > 80:
            score -= 15
        elif self.health_metrics["cpu_percent"] > 60:
            score -= 5
        
        # Deduct for excessive cache size
        if self.health_metrics["cache_size_mb"] > 500:
            score -= 10
        
        # Deduct for very large pickle file
        if self.health_metrics["pickle_file_size_mb"] > 200:
            score -= 10
        
        return max(0, score)

# Global instance
stability_manager = LongTermStabilityManager()