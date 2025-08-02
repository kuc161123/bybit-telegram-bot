#!/usr/bin/env python3
"""
Automatic Performance Management System
Monitors performance and applies optimizations without requiring restarts
"""
import asyncio
import gc
import logging
import os
import pickle
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Try to import psutil, fallback to basic monitoring if not available
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not available - using basic performance monitoring")

logger = logging.getLogger(__name__)

class AutoPerformanceManager:
    """Automatically manages bot performance without restarts"""
    
    def __init__(self):
        self.last_optimization = 0
        self.last_memory_cleanup = 0
        self.last_monitor_cleanup = 0
        self.performance_metrics = {}
        self.optimization_history = []
        self.is_optimizing = False
        
        # Performance thresholds
        self.max_monitor_processing_time = 30.0  # seconds
        self.max_memory_usage_mb = 500  # MB
        self.max_monitor_count = 25
        self.cleanup_interval = 1800  # 30 minutes
        self.optimization_cooldown = 600  # 10 minutes
        
    async def monitor_performance_loop(self):
        """Main performance monitoring loop"""
        logger.info("🎯 Auto Performance Manager started")
        
        while True:
            try:
                await self._check_and_optimize_performance()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Performance monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def _check_and_optimize_performance(self):
        """Check performance metrics and apply optimizations if needed"""
        if self.is_optimizing:
            return
            
        current_time = time.time()
        
        # Skip if recently optimized
        if current_time - self.last_optimization < self.optimization_cooldown:
            return
            
        try:
            # Collect performance metrics
            metrics = await self._collect_performance_metrics()
            
            # Check if optimization is needed
            needs_optimization = self._analyze_performance_needs(metrics)
            
            if needs_optimization:
                logger.warning("🚨 Performance degradation detected - applying automatic optimizations")
                await self._apply_automatic_optimizations(metrics)
                
            # Periodic cleanups
            if current_time - self.last_memory_cleanup > 900:  # 15 minutes
                await self._automatic_memory_cleanup()
                
            if current_time - self.last_monitor_cleanup > self.cleanup_interval:
                await self._automatic_monitor_cleanup()
                
        except Exception as e:
            logger.error(f"Performance check failed: {e}")
    
    async def _collect_performance_metrics(self) -> Dict:
        """Collect current performance metrics"""
        try:
            # System metrics
            if PSUTIL_AVAILABLE:
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                cpu_percent = process.cpu_percent()
                runtime_hours = (time.time() - process.create_time()) / 3600
            else:
                # Fallback metrics without psutil
                memory_mb = 0  # Cannot get memory without psutil
                cpu_percent = 0  # Cannot get CPU without psutil
                runtime_hours = 1  # Assume 1 hour for basic monitoring
            
            # Monitor metrics
            monitor_count, processing_time = await self._get_monitor_metrics()
            
            metrics = {
                'memory_mb': memory_mb,
                'cpu_percent': cpu_percent,
                'monitor_count': monitor_count,
                'processing_time': processing_time,
                'runtime_hours': runtime_hours,
                'timestamp': time.time()
            }
            
            self.performance_metrics = metrics
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")
            return {}
    
    async def _get_monitor_metrics(self) -> Tuple[int, float]:
        """Get monitor count and processing time"""
        try:
            # Read pickle file to get monitor data
            pickle_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
            if not os.path.exists(pickle_path):
                return 0, 0.0
                
            with open(pickle_path, 'rb') as f:
                data = pickle.load(f)
            
            # Count active monitors
            monitors = data.get('enhanced_tp_sl_monitors', {})
            active_monitors = sum(1 for m in monitors.values() if m.get('active', False))
            
            # Estimate processing time (rough calculation)
            # Each monitor takes ~0.5-2 seconds depending on API calls
            estimated_time = active_monitors * 1.5
            
            return active_monitors, estimated_time
            
        except Exception as e:
            logger.error(f"Failed to get monitor metrics: {e}")
            return 0, 0.0
    
    def _analyze_performance_needs(self, metrics: Dict) -> bool:
        """Analyze if performance optimization is needed"""
        if not metrics:
            return False
            
        needs_optimization = False
        reasons = []
        
        # Check memory usage
        if metrics.get('memory_mb', 0) > self.max_memory_usage_mb:
            needs_optimization = True
            reasons.append(f"High memory: {metrics['memory_mb']:.1f}MB")
        
        # Check monitor count
        if metrics.get('monitor_count', 0) > self.max_monitor_count:
            needs_optimization = True
            reasons.append(f"Too many monitors: {metrics['monitor_count']}")
        
        # Check processing time
        if metrics.get('processing_time', 0) > self.max_monitor_processing_time:
            needs_optimization = True
            reasons.append(f"Slow processing: {metrics['processing_time']:.1f}s")
        
        # Check runtime (restart needed after 24 hours)
        if metrics.get('runtime_hours', 0) > 24:
            needs_optimization = True
            reasons.append(f"Long runtime: {metrics['runtime_hours']:.1f}h")
        
        if needs_optimization:
            logger.warning(f"Performance issues detected: {', '.join(reasons)}")
            
        return needs_optimization
    
    async def _apply_automatic_optimizations(self, metrics: Dict):
        """Apply automatic performance optimizations"""
        self.is_optimizing = True
        optimizations_applied = []
        
        try:
            # 1. Adjust monitor intervals dynamically
            if metrics.get('monitor_count', 0) > 15:
                await self._optimize_monitor_intervals()
                optimizations_applied.append("Monitor intervals optimized")
            
            # 2. Memory cleanup
            if metrics.get('memory_mb', 0) > 300:
                await self._automatic_memory_cleanup()
                optimizations_applied.append("Memory cleanup performed")
            
            # 3. Clean obsolete monitors
            cleaned_count = await self._automatic_monitor_cleanup()
            if cleaned_count > 0:
                optimizations_applied.append(f"Removed {cleaned_count} obsolete monitors")
            
            # 4. Optimize cache settings
            await self._optimize_cache_settings()
            optimizations_applied.append("Cache settings optimized")
            
            # 5. Adjust API rate limits
            await self._optimize_api_settings()
            optimizations_applied.append("API settings optimized")
            
            self.last_optimization = time.time()
            
            # Log successful optimization
            logger.info(f"✅ Auto-optimization complete: {', '.join(optimizations_applied)}")
            
            # Record optimization history
            self.optimization_history.append({
                'timestamp': time.time(),
                'metrics_before': metrics.copy(),
                'optimizations': optimizations_applied
            })
            
            # Keep only last 10 optimizations
            if len(self.optimization_history) > 10:
                self.optimization_history = self.optimization_history[-10:]
                
        except Exception as e:
            logger.error(f"Auto-optimization failed: {e}")
        finally:
            self.is_optimizing = False
    
    async def _optimize_monitor_intervals(self):
        """Dynamically adjust monitor intervals based on load"""
        try:
            # Get current monitor count
            monitor_count, _ = await self._get_monitor_metrics()
            
            # Calculate optimal interval
            if monitor_count > 20:
                optimal_interval = 12  # Slow down significantly
            elif monitor_count > 15:
                optimal_interval = 8   # Moderate slowdown
            elif monitor_count > 10:
                optimal_interval = 6   # Slight slowdown
            else:
                optimal_interval = 5   # Normal speed
            
            # Update environment variable
            os.environ['POSITION_MONITOR_INTERVAL'] = str(optimal_interval)
            
            logger.info(f"🎛️ Monitor interval adjusted to {optimal_interval}s for {monitor_count} monitors")
            
        except Exception as e:
            logger.error(f"Failed to optimize monitor intervals: {e}")
    
    async def _automatic_memory_cleanup(self):
        """Perform automatic memory cleanup"""
        try:
            # Force garbage collection
            collected = gc.collect()
            
            # Clear any temporary variables from modules
            import sys
            for module_name in list(sys.modules.keys()):
                if 'temp' in module_name.lower() or 'cache' in module_name.lower():
                    try:
                        module = sys.modules[module_name]
                        if hasattr(module, '__dict__'):
                            # Clear module-level temporary variables
                            temp_vars = [k for k in module.__dict__.keys() 
                                       if k.startswith('_temp') or k.startswith('_cache')]
                            for var in temp_vars:
                                delattr(module, var)
                    except:
                        pass
            
            self.last_memory_cleanup = time.time()
            logger.info(f"🧹 Memory cleanup complete - collected {collected} objects")
            
        except Exception as e:
            logger.error(f"Memory cleanup failed: {e}")
    
    async def _automatic_monitor_cleanup(self) -> int:
        """Clean up obsolete monitors automatically"""
        cleaned_count = 0
        
        try:
            pickle_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
            if not os.path.exists(pickle_path):
                return 0
            
            # Load current data
            with open(pickle_path, 'rb') as f:
                data = pickle.load(f)
            
            monitors = data.get('enhanced_tp_sl_monitors', {})
            positions = data.get('positions', {})
            
            # Find monitors without corresponding positions
            monitors_to_remove = []
            
            for monitor_key, monitor in monitors.items():
                symbol = monitor.get('symbol', '')
                account = monitor.get('account_type', 'main')
                
                # Check if position exists
                position_exists = False
                for pos_key, position in positions.items():
                    if (position.get('symbol') == symbol and 
                        position.get('account_type', 'main') == account and
                        float(position.get('size', 0)) > 0):
                        position_exists = True
                        break
                
                if not position_exists:
                    monitors_to_remove.append(monitor_key)
            
            # Remove obsolete monitors
            for monitor_key in monitors_to_remove:
                monitors.pop(monitor_key, None)
                cleaned_count += 1
            
            # Save if we removed any
            if cleaned_count > 0:
                data['enhanced_tp_sl_monitors'] = monitors
                
                # Create backup before saving
                backup_path = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_auto_cleanup_{int(time.time())}'
                with open(backup_path, 'wb') as f:
                    pickle.dump(data, f)
                
                # Save updated data
                with open(pickle_path, 'wb') as f:
                    pickle.dump(data, f)
                
                logger.info(f"🧹 Removed {cleaned_count} obsolete monitors")
            
            self.last_monitor_cleanup = time.time()
            
        except Exception as e:
            logger.error(f"Monitor cleanup failed: {e}")
        
        return cleaned_count
    
    async def _optimize_cache_settings(self):
        """Optimize cache settings for current load"""
        try:
            # Adjust cache TTL based on monitor count
            monitor_count, _ = await self._get_monitor_metrics()
            
            # Optimize for 60s monitoring intervals - ensure minimum 75s cache TTL
            if monitor_count > 15:
                cache_ttl = 600  # 10 minutes for high load
                cache_size = 500  # Smaller cache
            elif monitor_count > 10:
                cache_ttl = 300  # 5 minutes for medium load
                cache_size = 750
            else:
                cache_ttl = max(180, 75)  # Minimum 75s for 60s monitoring alignment
                cache_size = 1000
            
            os.environ['CACHE_DEFAULT_TTL'] = str(cache_ttl)
            os.environ['CACHE_MAX_SIZE'] = str(cache_size)
            
        except Exception as e:
            logger.error(f"Cache optimization failed: {e}")
    
    async def _optimize_api_settings(self):
        """Optimize API settings for current load"""
        try:
            # Adjust API rate limits based on monitor count
            monitor_count, _ = await self._get_monitor_metrics()
            
            if monitor_count > 20:
                api_rate = 3  # Very conservative
                concurrent = 15
            elif monitor_count > 15:
                api_rate = 4  # Conservative
                concurrent = 20
            else:
                api_rate = 5  # Normal
                concurrent = 25
            
            os.environ['API_RATE_LIMIT_CALLS_PER_SECOND'] = str(api_rate)
            os.environ['MAX_CONCURRENT_MONITORS'] = str(concurrent)
            
        except Exception as e:
            logger.error(f"API optimization failed: {e}")
    
    def get_performance_status(self) -> Dict:
        """Get current performance status"""
        return {
            'metrics': self.performance_metrics,
            'last_optimization': datetime.fromtimestamp(self.last_optimization) if self.last_optimization else None,
            'optimization_history': self.optimization_history[-5:],  # Last 5
            'is_optimizing': self.is_optimizing
        }

# Global instance
auto_performance_manager = AutoPerformanceManager()