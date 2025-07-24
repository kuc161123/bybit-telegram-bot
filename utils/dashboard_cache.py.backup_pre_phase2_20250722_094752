#!/usr/bin/env python3
"""
Intelligent caching system for dashboard components
"""
import time
import hashlib
import json
from typing import Any, Dict, Optional, Callable, Tuple
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class DashboardCache:
    """Component-level caching for dashboard elements"""

    def __init__(self):
        self._cache: Dict[str, Tuple[Any, float, str]] = {}
        self._ttls = {
            'account_data': 60,      # 60 seconds for account balance (optimized for performance)
            'positions': 15,         # 15 seconds for positions (balanced performance vs accuracy)
            'orders': 15,           # 15 seconds for orders (balanced performance vs accuracy)
            'stats': 300,           # 5 minutes for statistics (longer cache for performance)
            'market_data': 180,     # 3 minutes for market data (faster updates)
            'ai_insights': 1800,    # 30 minutes for AI insights (expensive operations)
            'full_dashboard': 30,   # 30 seconds for complete dashboard (optimized UX)
        }
        self._last_refresh = {}  # Track last refresh times for debouncing
        self._min_refresh_interval = 2  # Minimum 2 seconds between refreshes
        
        # Performance monitoring
        self._cache_hits = 0
        self._cache_misses = 0
        self._last_performance_log = time.time()

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired"""
        if key in self._cache:
            value, timestamp, _ = self._cache[key]
            ttl = self._ttls.get(key.split('_')[0], 60)

            if time.time() - timestamp < ttl:
                self._cache_hits += 1
                self._log_performance_if_needed()
                return value
            else:
                # Expired, remove from cache
                del self._cache[key]
        
        self._cache_misses += 1
        self._log_performance_if_needed()
        return None
    
    def should_refresh(self, key: str) -> bool:
        """Check if enough time has passed for a refresh (debouncing)"""
        current_time = time.time()
        last_refresh = self._last_refresh.get(key, 0)
        
        if current_time - last_refresh < self._min_refresh_interval:
            logger.debug(f"Debouncing {key}: only {current_time - last_refresh:.1f}s since last refresh")
            return False
        
        self._last_refresh[key] = current_time
        return True
    
    def _log_performance_if_needed(self) -> None:
        """Log cache performance metrics periodically"""
        current_time = time.time()
        if current_time - self._last_performance_log > 300:  # Log every 5 minutes
            total_requests = self._cache_hits + self._cache_misses
            if total_requests > 0:
                hit_rate = (self._cache_hits / total_requests) * 100
                logger.info(f"📊 Dashboard Cache Performance: {hit_rate:.1f}% hit rate ({self._cache_hits} hits, {self._cache_misses} misses)")
            self._last_performance_log = current_time

    def set(self, key: str, value: Any, content_hash: Optional[str] = None) -> None:
        """Set cache value with timestamp and optional content hash"""
        if content_hash is None:
            # Generate content hash if not provided
            content_hash = self._generate_hash(value)
        self._cache[key] = (value, time.time(), content_hash)

    def has_changed(self, key: str, new_value: Any) -> bool:
        """Check if value has changed based on content hash"""
        if key not in self._cache:
            return True

        _, _, old_hash = self._cache[key]
        new_hash = self._generate_hash(new_value)
        return old_hash != new_hash

    def invalidate(self, pattern: Optional[str] = None) -> None:
        """Invalidate cache entries matching pattern or all if no pattern"""
        if pattern:
            keys_to_remove = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self._cache[key]
        else:
            self._cache.clear()

    def _generate_hash(self, value: Any) -> str:
        """Generate hash of value for change detection"""
        try:
            # Convert to JSON for consistent hashing
            content = json.dumps(value, sort_keys=True, default=str)
            return hashlib.md5(content.encode()).hexdigest()
        except:
            # Fallback to string representation
            return hashlib.md5(str(value).encode()).hexdigest()

    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        total_entries = len(self._cache)
        expired_entries = 0

        current_time = time.time()
        for key, (_, timestamp, _) in self._cache.items():
            ttl = self._ttls.get(key.split('_')[0], 60)
            if current_time - timestamp >= ttl:
                expired_entries += 1

        return {
            'total_entries': total_entries,
            'active_entries': total_entries - expired_entries,
            'expired_entries': expired_entries,
        }

    def invalidate_trading_data(self, chat_id: Optional[int] = None) -> None:
        """Invalidate all trading-related cache entries for immediate refresh"""
        patterns_to_clear = ['positions', 'orders', 'account_data', 'full_dashboard']
        keys_to_remove = []

        for key in self._cache.keys():
            key_type = key.split('_')[0]
            if key_type in patterns_to_clear:
                # If chat_id specified, only clear for that chat
                if chat_id is None or str(chat_id) in key:
                    keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._cache[key]

        logger.debug(f"Invalidated {len(keys_to_remove)} trading cache entries")


# Global cache instance
dashboard_cache = DashboardCache()


def cached_component(cache_key: str, ttl: Optional[int] = None):
    """Decorator for caching dashboard components"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate unique cache key based on function name and args
            full_key = f"{cache_key}_{func.__name__}"

            # Check cache first
            cached_value = dashboard_cache.get(full_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {full_key}")
                return cached_value

            # Cache miss, generate new value
            logger.debug(f"Cache miss for {full_key}")
            result = await func(*args, **kwargs)

            # Store in cache with custom TTL if provided
            if ttl:
                old_ttl = dashboard_cache._ttls.get(cache_key.split('_')[0], 60)
                dashboard_cache._ttls[cache_key.split('_')[0]] = ttl
                dashboard_cache.set(full_key, result)
                dashboard_cache._ttls[cache_key.split('_')[0]] = old_ttl
            else:
                dashboard_cache.set(full_key, result)

            return result
        return wrapper
    return decorator


def invalidate_dashboard_cache(pattern: Optional[str] = None):
    """Invalidate dashboard cache entries"""
    dashboard_cache.invalidate(pattern)
    logger.info(f"Dashboard cache invalidated: {pattern or 'all entries'}")