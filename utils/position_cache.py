#!/usr/bin/env python3
"""
Position Cache System
Reduces API calls by caching position data with intelligent TTL management
"""
import time
import logging
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from decimal import Decimal
from threading import RLock
import asyncio

logger = logging.getLogger(__name__)

class PositionCache:
    """High-performance position caching with TTL and invalidation"""
    
    def __init__(self, default_ttl: int = 5, urgent_ttl: int = 2):
        """
        Initialize position cache
        
        Args:
            default_ttl: Default TTL in seconds for position data
            urgent_ttl: Reduced TTL for positions near TP/SL levels
        """
        self.default_ttl = default_ttl
        self.urgent_ttl = urgent_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = RLock()
        
        # Performance metrics
        self.hit_count = 0
        self.miss_count = 0
        self.api_calls_saved = 0
        self.last_cleanup = time.time()
        
    def _is_position_urgent(self, position: Dict) -> bool:
        """
        Check if position is near TP/SL and needs more frequent updates
        
        Args:
            position: Position data dict
            
        Returns:
            True if position needs urgent monitoring
        """
        try:
            if not position or float(position.get('size', 0)) == 0:
                return False
            
            mark_price = float(position.get('markPrice', 0))
            if mark_price == 0:
                return False
            
            # Check if position has TP/SL prices in data
            tp_price = float(position.get('takeProfit', 0))
            sl_price = float(position.get('stopLoss', 0))
            
            if tp_price > 0:
                # Within 2% of TP is urgent
                if abs(mark_price - tp_price) / tp_price < 0.02:
                    return True
            
            if sl_price > 0:
                # Within 2% of SL is urgent
                if abs(mark_price - sl_price) / sl_price < 0.02:
                    return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Error checking position urgency: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get position from cache if not expired
        
        Args:
            key: Cache key (usually symbol or position identifier)
            
        Returns:
            Cached position data or None if expired/not found
        """
        with self._lock:
            if key not in self._cache:
                self.miss_count += 1
                return None
            
            entry = self._cache[key]
            current_time = time.time()
            
            # Check expiration
            if current_time > entry['expires']:
                # Expired - remove and return None
                del self._cache[key]
                self.miss_count += 1
                return None
            
            # Valid cache hit
            self.hit_count += 1
            self.api_calls_saved += 1
            
            # Update access time for LRU
            entry['last_accessed'] = current_time
            
            return entry['data']
    
    def set(self, key: str, data: Any, custom_ttl: Optional[int] = None) -> None:
        """
        Set position in cache with TTL
        
        Args:
            key: Cache key
            data: Position data to cache
            custom_ttl: Optional custom TTL, otherwise uses default or urgent based on position
        """
        with self._lock:
            current_time = time.time()
            
            # Determine TTL
            if custom_ttl is not None:
                ttl = custom_ttl
            elif self._is_position_urgent(data):
                ttl = self.urgent_ttl
                logger.debug(f"Using urgent TTL ({self.urgent_ttl}s) for {key}")
            else:
                ttl = self.default_ttl
            
            self._cache[key] = {
                'data': data,
                'expires': current_time + ttl,
                'created': current_time,
                'last_accessed': current_time,
                'ttl': ttl
            }
            
            # Cleanup old entries periodically
            if current_time - self.last_cleanup > 60:  # Every minute
                self._cleanup_expired()
    
    def invalidate(self, key: str) -> None:
        """
        Invalidate specific cache entry
        
        Args:
            key: Cache key to invalidate
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Invalidated cache entry: {key}")
    
    def invalidate_all(self) -> None:
        """Clear all cache entries"""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Invalidated all {count} cache entries")
    
    def _cleanup_expired(self) -> None:
        """Remove expired entries from cache"""
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self._cache.items():
            if current_time > entry['expires']:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        self.last_cleanup = current_time
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache performance statistics
        
        Returns:
            Dict with cache statistics
        """
        with self._lock:
            total_requests = self.hit_count + self.miss_count
            hit_rate = (self.hit_count / total_requests * 100) if total_requests > 0 else 0
            
            # Count urgent vs normal cached positions
            urgent_count = 0
            for entry in self._cache.values():
                if entry['ttl'] == self.urgent_ttl:
                    urgent_count += 1
            
            return {
                'total_entries': len(self._cache),
                'hit_count': self.hit_count,
                'miss_count': self.miss_count,
                'hit_rate': hit_rate,
                'api_calls_saved': self.api_calls_saved,
                'urgent_positions': urgent_count,
                'normal_positions': len(self._cache) - urgent_count
            }
    
    def reset_stats(self) -> None:
        """Reset performance statistics"""
        with self._lock:
            self.hit_count = 0
            self.miss_count = 0
            self.api_calls_saved = 0
            logger.debug("Position cache statistics reset")
    
    async def get_or_fetch(self, key: str, fetch_func: callable, 
                           custom_ttl: Optional[int] = None) -> Optional[Any]:
        """
        Get from cache or fetch if not present
        
        Args:
            key: Cache key
            fetch_func: Async function to fetch data if not cached
            custom_ttl: Optional custom TTL
            
        Returns:
            Cached or fetched data
        """
        # Try cache first
        data = self.get(key)
        if data is not None:
            return data
        
        # Fetch new data
        try:
            data = await fetch_func()
            if data is not None:
                self.set(key, data, custom_ttl)
            return data
        except Exception as e:
            logger.error(f"Error fetching data for key {key}: {e}")
            return None
    
    def batch_get(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple positions from cache in one operation
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dict of key -> data for found entries
        """
        result = {}
        with self._lock:
            for key in keys:
                data = self.get(key)
                if data is not None:
                    result[key] = data
        return result
    
    def batch_set(self, items: Dict[str, Any], custom_ttl: Optional[int] = None) -> None:
        """
        Set multiple positions in cache in one operation
        
        Args:
            items: Dict of key -> data to cache
            custom_ttl: Optional custom TTL for all items
        """
        for key, data in items.items():
            self.set(key, data, custom_ttl)


# Global position cache instance
position_cache = PositionCache(default_ttl=5, urgent_ttl=2)


async def get_position_cached(symbol: str, fetch_func: callable) -> Optional[Dict]:
    """
    Get position with caching
    
    Args:
        symbol: Trading symbol
        fetch_func: Function to fetch position if not cached
        
    Returns:
        Position data or None
    """
    return await position_cache.get_or_fetch(f"position_{symbol}", fetch_func)


def invalidate_position_cache(symbol: Optional[str] = None) -> None:
    """
    Invalidate position cache
    
    Args:
        symbol: Specific symbol to invalidate, or None for all
    """
    if symbol:
        position_cache.invalidate(f"position_{symbol}")
        logger.info(f"Invalidated position cache for {symbol}")
    else:
        position_cache.invalidate_all()
        logger.info("Invalidated all position caches")


def get_position_cache_stats() -> Dict[str, Any]:
    """Get position cache statistics"""
    return position_cache.get_stats()