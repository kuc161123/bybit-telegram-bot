#!/usr/bin/env python3
"""
Enhanced API Cache System
High-performance caching with intelligent TTL management and request deduplication
"""
import asyncio
import time
import hashlib
import json
import logging
from typing import Any, Dict, Optional, List, Set, Callable
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class CacheMode(Enum):
    """Cache operation modes for different system states"""
    EXECUTION = "execution"      # 5s TTL - during active trading
    MONITORING = "monitoring"    # 15s TTL - position monitoring
    MAINTENANCE = "maintenance"  # 30s TTL - background tasks
    IDLE = "idle"               # 60s TTL - low activity

@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    data: Any
    timestamp: float
    access_count: int
    last_access: float
    ttl: float
    mode: CacheMode

class EnhancedAPICache:
    """High-performance API cache with intelligent TTL and deduplication"""
    
    def __init__(self):
        self.cache: Dict[str, CacheEntry] = {}
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.mode = CacheMode.MONITORING
        self.stats = {
            'hits': 0,
            'misses': 0,
            'pending_hits': 0,
            'expired': 0,
            'evicted': 0
        }
        
        # Mode-specific TTLs (configurable via environment)
        self.mode_ttls = {
            CacheMode.EXECUTION: 5,
            CacheMode.MONITORING: 15,
            CacheMode.MAINTENANCE: 30,
            CacheMode.IDLE: 60
        }
        
        # Cleanup task
        self._cleanup_task = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Start background cleanup task"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """Background cleanup of expired entries"""
        while True:
            try:
                await asyncio.sleep(30)  # Clean every 30 seconds
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Cache cleanup error: {e}")
    
    async def _cleanup_expired(self):
        """Remove expired cache entries"""
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self.cache.items():
            if current_time - entry.timestamp > entry.ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
            self.stats['expired'] += 1
        
        if expired_keys:
            logger.debug(f"🧹 Cleaned {len(expired_keys)} expired cache entries")
    
    def _generate_cache_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate cache key from function call"""
        # Create deterministic key from function name and arguments
        key_data = {
            'func': func_name,
            'args': args,
            'kwargs': sorted(kwargs.items()) if kwargs else {}
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def set_mode(self, mode: CacheMode):
        """Set cache operation mode"""
        if mode != self.mode:
            logger.debug(f"🎯 Cache mode: {self.mode.value} → {mode.value}")
            self.mode = mode
    
    async def get_or_execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Get from cache or execute function with request deduplication
        
        Args:
            func: Async function to execute
            *args, **kwargs: Function arguments
            
        Returns:
            Function result (from cache or fresh execution)
        """
        # Generate cache key
        func_name = getattr(func, '__name__', str(func))
        cache_key = self._generate_cache_key(func_name, args, kwargs)
        current_time = time.time()
        
        # Check cache first
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            
            # Update access stats
            entry.access_count += 1
            entry.last_access = current_time
            
            # Check if still valid
            if current_time - entry.timestamp <= entry.ttl:
                self.stats['hits'] += 1
                logger.debug(f"🎯 Cache hit: {func_name} ({current_time - entry.timestamp:.1f}s old)")
                return entry.data
            else:
                # Expired - remove it
                del self.cache[cache_key]
                self.stats['expired'] += 1
        
        # Check if there's a pending request for the same operation
        if cache_key in self.pending_requests:
            self.stats['pending_hits'] += 1
            logger.debug(f"⏳ Waiting for pending request: {func_name}")
            try:
                result = await self.pending_requests[cache_key]
                return result
            except Exception as e:
                logger.error(f"❌ Pending request failed: {e}")
                # Remove failed request from pending
                if cache_key in self.pending_requests:
                    del self.pending_requests[cache_key]
                raise
        
        # Miss - execute function
        self.stats['misses'] += 1
        
        # Create future for request deduplication
        future = asyncio.Future()
        self.pending_requests[cache_key] = future
        
        try:
            logger.debug(f"🔄 Cache miss: executing {func_name}")
            result = await func(*args, **kwargs)
            
            # Cache the result
            ttl = self.mode_ttls[self.mode]
            entry = CacheEntry(
                data=result,
                timestamp=current_time,
                access_count=1,
                last_access=current_time,
                ttl=ttl,
                mode=self.mode
            )
            
            self.cache[cache_key] = entry
            
            # Resolve pending requests
            future.set_result(result)
            
            logger.debug(f"💾 Cached result: {func_name} (TTL: {ttl}s)")
            return result
            
        except Exception as e:
            # Propagate exception to pending requests
            future.set_exception(e)
            raise
        finally:
            # Remove from pending requests
            if cache_key in self.pending_requests:
                del self.pending_requests[cache_key]
    
    async def batch_execute(self, requests: List[Dict[str, Any]]) -> List[Any]:
        """
        Execute multiple requests concurrently with caching
        
        Args:
            requests: List of {'func': callable, 'args': tuple, 'kwargs': dict}
            
        Returns:
            List of results in same order as requests
        """
        logger.debug(f"📦 Batch executing {len(requests)} requests")
        
        # Create tasks for all requests
        tasks = []
        for req in requests:
            func = req['func']
            args = req.get('args', ())
            kwargs = req.get('kwargs', {})
            
            task = self.get_or_execute(func, *args, **kwargs)
            tasks.append(task)
        
        # Execute all concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log any exceptions
        error_count = sum(1 for r in results if isinstance(r, Exception))
        if error_count > 0:
            logger.warning(f"⚠️ Batch execution: {error_count}/{len(requests)} requests failed")
        
        return results
    
    def invalidate(self, func_name: str = None, pattern: str = None):
        """
        Invalidate cache entries
        
        Args:
            func_name: Specific function name to invalidate
            pattern: String pattern to match in cache keys
        """
        if func_name is None and pattern is None:
            # Clear all
            cleared = len(self.cache)
            self.cache.clear()
            logger.info(f"🧹 Cleared all cache entries: {cleared}")
            return
        
        keys_to_remove = []
        
        for key in self.cache.keys():
            # Check if we should remove this key
            if func_name and func_name in key:
                keys_to_remove.append(key)
            elif pattern and pattern in key:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.cache[key]
        
        if keys_to_remove:
            logger.debug(f"🧹 Invalidated {len(keys_to_remove)} cache entries")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'total_entries': len(self.cache),
            'pending_requests': len(self.pending_requests),
            'mode': self.mode.value,
            'hit_rate_percent': round(hit_rate, 1),
            'stats': self.stats.copy(),
            'mode_ttls': {mode.value: ttl for mode, ttl in self.mode_ttls.items()}
        }
    
    def optimize_for_load(self, high_load: bool = False):
        """Optimize cache settings based on system load"""
        if high_load:
            # Increase TTLs during high load to reduce API calls
            self.mode_ttls[CacheMode.EXECUTION] = 8
            self.mode_ttls[CacheMode.MONITORING] = 25
            self.mode_ttls[CacheMode.MAINTENANCE] = 45
            self.mode_ttls[CacheMode.IDLE] = 90
            logger.info("🚀 Cache optimized for HIGH LOAD (extended TTLs)")
        else:
            # Standard TTLs for normal operation
            self.mode_ttls[CacheMode.EXECUTION] = 5
            self.mode_ttls[CacheMode.MONITORING] = 15
            self.mode_ttls[CacheMode.MAINTENANCE] = 30
            self.mode_ttls[CacheMode.IDLE] = 60
            logger.info("🎯 Cache optimized for NORMAL LOAD (standard TTLs)")
    
    async def shutdown(self):
        """Shutdown cache and cleanup resources"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self.cache.clear()
        self.pending_requests.clear()
        logger.info("🛑 Enhanced API cache shutdown complete")

# Global cache instance
_global_cache = None

def get_api_cache() -> EnhancedAPICache:
    """Get or create global API cache instance"""
    global _global_cache
    if _global_cache is None:
        _global_cache = EnhancedAPICache()
    return _global_cache

def cache_api_call(func: Callable):
    """Decorator for caching API calls"""
    async def wrapper(*args, **kwargs):
        cache = get_api_cache()
        return await cache.get_or_execute(func, *args, **kwargs)
    return wrapper

# Convenience functions for specific operations
async def cached_position_check(symbol: str, account_type: str, position_func: Callable) -> Any:
    """Cache position data with smart TTL"""
    cache = get_api_cache()
    cache.set_mode(CacheMode.MONITORING)  # 15s TTL for position data
    return await cache.get_or_execute(position_func, symbol, account_type)

async def cached_order_check(symbol: str, account_type: str, order_func: Callable) -> Any:
    """Cache order data with execution-aware TTL"""
    cache = get_api_cache()
    cache.set_mode(CacheMode.EXECUTION)  # 5s TTL for order data
    return await cache.get_or_execute(order_func, symbol, account_type)