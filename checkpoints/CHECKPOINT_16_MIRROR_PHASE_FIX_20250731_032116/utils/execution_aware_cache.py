#!/usr/bin/env python3
"""
Execution-Aware Cache System for Trading Bot
Implements 2025 best practices for cache-on-demand with execution mode awareness
"""
import asyncio
import time
import logging
from typing import Dict, Any, Optional, Union, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

class CacheMode(Enum):
    """Cache operation modes"""
    MONITORING = "monitoring"    # Normal monitoring operations (15s TTL)
    EXECUTION = "execution"      # Active trade execution (5s TTL)
    MAINTENANCE = "maintenance"  # Cleanup and maintenance (30s TTL)

class ExecutionAwareCache:
    """
    Dynamic cache management system that adapts TTL based on operation mode
    Based on 2025 best practices for high-performance async caching
    """
    
    def __init__(self):
        # Cache storage by mode
        self._caches = {
            CacheMode.MONITORING: {},
            CacheMode.EXECUTION: {},
            CacheMode.MAINTENANCE: {}
        }
        
        # TTL settings by mode
        self._ttls = {
            CacheMode.MONITORING: 15,    # 15 seconds for monitoring
            CacheMode.EXECUTION: 5,      # 5 seconds for execution
            CacheMode.MAINTENANCE: 30    # 30 seconds for maintenance
        }
        
        # Current operation mode
        self._current_mode = CacheMode.MONITORING
        
        # Performance metrics
        self._stats = {
            "requests": {mode: 0 for mode in CacheMode},
            "hits": {mode: 0 for mode in CacheMode},
            "hit_rates": {mode: 0.0 for mode in CacheMode},
            "cache_sizes": {mode: 0 for mode in CacheMode}
        }
        
        # Last cleanup times
        self._last_cleanup = {mode: 0 for mode in CacheMode}
        self._cleanup_intervals = {
            CacheMode.MONITORING: 60,     # Clean every minute
            CacheMode.EXECUTION: 30,      # Clean every 30 seconds
            CacheMode.MAINTENANCE: 120    # Clean every 2 minutes
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    async def set_mode(self, mode: CacheMode):
        """Set the current cache operation mode"""
        async with self._lock:
            old_mode = self._current_mode
            self._current_mode = mode
            
            if old_mode != mode:
                logger.debug(f"🔄 Cache mode changed: {old_mode.value} → {mode.value}")
                # Optionally clear execution cache when switching out of execution mode
                if old_mode == CacheMode.EXECUTION and mode != CacheMode.EXECUTION:
                    await self._clear_mode_cache(CacheMode.EXECUTION)
                    logger.debug("🧹 Cleared execution cache on mode switch")
    
    def get_mode(self) -> CacheMode:
        """Get the current cache operation mode"""
        return self._current_mode
    
    async def get(self, key: str, mode: Optional[CacheMode] = None) -> Optional[Any]:
        """
        Get value from cache with mode-aware TTL
        
        Args:
            key: Cache key
            mode: Optional specific mode to check (defaults to current mode)
        
        Returns:
            Cached value or None if expired/not found
        """
        if mode is None:
            mode = self._current_mode
        
        async with self._lock:
            self._stats["requests"][mode] += 1
            
            cache = self._caches[mode]
            if key not in cache:
                return None
            
            entry = cache[key]
            current_time = time.time()
            ttl = self._ttls[mode]
            
            # Check if expired
            if current_time - entry["timestamp"] > ttl:
                # Remove expired entry
                del cache[key]
                return None
            
            # Update stats and return value
            self._stats["hits"][mode] += 1
            self._update_hit_rate(mode)
            return entry["value"]
    
    async def set(self, key: str, value: Any, mode: Optional[CacheMode] = None):
        """
        Set value in cache with mode-aware TTL
        
        Args:
            key: Cache key
            value: Value to cache
            mode: Optional specific mode to use (defaults to current mode)
        """
        if mode is None:
            mode = self._current_mode
        
        async with self._lock:
            cache = self._caches[mode]
            cache[key] = {
                "value": value,
                "timestamp": time.time()
            }
            
            self._stats["cache_sizes"][mode] = len(cache)
            
            # Periodic cleanup check
            await self._cleanup_if_needed(mode)
    
    async def invalidate(self, key: str, mode: Optional[CacheMode] = None):
        """Invalidate specific cache entry"""
        if mode is None:
            mode = self._current_mode
        
        async with self._lock:
            cache = self._caches[mode]
            if key in cache:
                del cache[key]
                self._stats["cache_sizes"][mode] = len(cache)
                logger.debug(f"🗑️ Invalidated cache key: {key} (mode: {mode.value})")
    
    async def invalidate_pattern(self, pattern: str, mode: Optional[CacheMode] = None):
        """Invalidate all cache entries matching pattern"""
        if mode is None:
            mode = self._current_mode
        
        async with self._lock:
            cache = self._caches[mode]
            keys_to_remove = [k for k in cache.keys() if pattern in k]
            
            for key in keys_to_remove:
                del cache[key]
            
            self._stats["cache_sizes"][mode] = len(cache)
            
            if keys_to_remove:
                logger.debug(f"🗑️ Invalidated {len(keys_to_remove)} cache entries matching '{pattern}' (mode: {mode.value})")
    
    async def clear_all(self):
        """Clear all caches"""
        async with self._lock:
            for mode in CacheMode:
                self._caches[mode].clear()
                self._stats["cache_sizes"][mode] = 0
            logger.info("🧹 All caches cleared")
    
    async def _clear_mode_cache(self, mode: CacheMode):
        """Clear cache for specific mode"""
        self._caches[mode].clear()
        self._stats["cache_sizes"][mode] = 0
        logger.debug(f"🧹 {mode.value} cache cleared")
    
    async def _cleanup_if_needed(self, mode: CacheMode):
        """Cleanup expired entries if interval has passed"""
        current_time = time.time()
        cleanup_interval = self._cleanup_intervals[mode]
        
        if current_time - self._last_cleanup[mode] > cleanup_interval:
            await self._cleanup_expired_entries(mode)
            self._last_cleanup[mode] = current_time
    
    async def _cleanup_expired_entries(self, mode: CacheMode):
        """Remove expired entries from cache"""
        cache = self._caches[mode]
        current_time = time.time()
        ttl = self._ttls[mode]
        
        expired_keys = [
            key for key, entry in cache.items()
            if current_time - entry["timestamp"] > ttl
        ]
        
        for key in expired_keys:
            del cache[key]
        
        self._stats["cache_sizes"][mode] = len(cache)
        
        if expired_keys:
            logger.debug(f"🧹 Cleaned up {len(expired_keys)} expired entries from {mode.value} cache")
    
    def _update_hit_rate(self, mode: CacheMode):
        """Update hit rate statistics"""
        requests = self._stats["requests"][mode]
        hits = self._stats["hits"][mode]
        
        if requests > 0:
            self._stats["hit_rates"][mode] = (hits / requests) * 100
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        async with self._lock:
            # Update all hit rates
            for mode in CacheMode:
                self._update_hit_rate(mode)
            
            return {
                "current_mode": self._current_mode.value,
                "stats": dict(self._stats),
                "ttls": {mode.value: ttl for mode, ttl in self._ttls.items()},
                "total_entries": sum(self._stats["cache_sizes"].values()),
                "memory_estimate_kb": self._estimate_memory_usage()
            }
    
    def _estimate_memory_usage(self) -> float:
        """Rough estimate of cache memory usage in KB"""
        total_entries = sum(self._stats["cache_sizes"].values())
        # Rough estimate: 1KB per cache entry (key + value + metadata)
        return total_entries * 1.0
    
    async def get_cached_api_call(self, operation_type: str, params: Dict[str, Any], 
                                api_call_func, *args, **kwargs) -> Any:
        """
        Wrapper for API calls with intelligent caching
        
        Args:
            operation_type: Type of operation (e.g., 'position_info', 'order_info')
            params: Parameters for the API call (used for cache key)
            api_call_func: The actual API function to call
            *args, **kwargs: Arguments for the API function
        
        Returns:
            API call result (cached or fresh)
        """
        # Generate cache key
        param_str = "_".join(f"{k}:{v}" for k, v in sorted(params.items()))
        cache_key = f"{operation_type}_{param_str}"
        
        # Try to get from cache first
        cached_result = await self.get(cache_key)
        if cached_result is not None:
            logger.debug(f"💨 Cache hit for {operation_type}: {cache_key[:50]}...")
            return cached_result
        
        # Cache miss - make API call
        try:
            logger.debug(f"🌐 Cache miss, making API call for {operation_type}: {cache_key[:50]}...")
            result = await api_call_func(*args, **kwargs)
            
            # Cache the result
            await self.set(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ API call failed for {operation_type}: {e}")
            raise
    
    async def start_maintenance_task(self):
        """Start background maintenance task"""
        asyncio.create_task(self._maintenance_loop())
        logger.info("🔧 Cache maintenance task started")
    
    async def _maintenance_loop(self):
        """Background maintenance loop"""
        while True:
            try:
                # Clean up all caches
                for mode in CacheMode:
                    await self._cleanup_expired_entries(mode)
                
                # Log statistics every 5 minutes
                stats = await self.get_stats()
                if int(time.time()) % 300 == 0:  # Every 5 minutes
                    logger.info(f"📊 Cache stats: {stats}")
                
                # Sleep for 30 seconds
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"❌ Cache maintenance error: {e}")
                await asyncio.sleep(30)

# Global cache instance
execution_aware_cache = ExecutionAwareCache()

# Convenience functions for backward compatibility
async def get_cached(key: str, mode: Optional[CacheMode] = None) -> Optional[Any]:
    """Get value from execution-aware cache"""
    return await execution_aware_cache.get(key, mode)

async def set_cached(key: str, value: Any, mode: Optional[CacheMode] = None):
    """Set value in execution-aware cache"""
    await execution_aware_cache.set(key, value, mode)

async def invalidate_cached(key: str, mode: Optional[CacheMode] = None):
    """Invalidate cached value"""
    await execution_aware_cache.invalidate(key, mode)

async def set_cache_mode(mode: CacheMode):
    """Set global cache mode"""
    await execution_aware_cache.set_mode(mode)

async def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    return await execution_aware_cache.get_stats()

async def start_cache_maintenance():
    """Start cache maintenance task"""
    await execution_aware_cache.start_maintenance_task()