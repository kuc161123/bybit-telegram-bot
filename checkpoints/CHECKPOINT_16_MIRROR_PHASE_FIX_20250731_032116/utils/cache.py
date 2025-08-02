#!/usr/bin/env python3
"""
Enhanced caching system with TTL support and fixed async/sync compatibility.
FIXED: Proper async/sync method handling
ENHANCED: Better error handling and memory management
FIXED: Added _periodic_cache_cleanup function for main.py import
"""
import time
import logging
import asyncio
import weakref
from typing import Any, Optional, Dict
from decimal import Decimal
from threading import Lock

logger = logging.getLogger(__name__)

class EnhancedCache:
    """Enhanced cache with TTL support and memory management"""

    def __init__(self, max_size: int = 1000):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_times: Dict[str, float] = {}
        self._lock = Lock()  # Use threading lock for sync operations
        self._async_lock = asyncio.Lock()  # Separate async lock
        self._max_size = max_size
        self._cleanup_threshold = int(max_size * 0.8)  # Cleanup when 80% full
        
        # Enhanced monitoring (2025 best practices)
        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0
        self._size_limit_exceeded_count = 0
        self._last_health_check = 0
        self._health_check_interval = 300  # 5 minutes

    def _cleanup_expired(self) -> None:
        """Clean up expired entries"""
        current_time = time.time()
        expired_keys = []

        for key, entry in self._cache.items():
            if entry.get('expires') and current_time > entry['expires']:
                expired_keys.append(key)

        for key in expired_keys:
            self._cache.pop(key, None)
            self._access_times.pop(key, None)

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    def _cleanup_lru(self) -> None:
        """Clean up least recently used entries if cache is full (Enhanced 2025)"""
        if len(self._cache) < self._cleanup_threshold:
            return

        # Enhanced LRU cleanup with better eviction strategy
        current_time = time.time()
        sorted_items = sorted(self._access_times.items(), key=lambda x: x[1])
        
        # Calculate how many entries to remove (adaptive based on cache pressure)
        cache_pressure = len(self._cache) / self._max_size
        if cache_pressure > 0.95:
            # High pressure - remove 40%
            removal_ratio = 0.4
        elif cache_pressure > 0.9:
            # Medium pressure - remove 30%
            removal_ratio = 0.3
        else:
            # Normal pressure - remove 25%
            removal_ratio = 0.25
        
        removal_count = max(1, int(len(sorted_items) * removal_ratio))
        keys_to_remove = [key for key, _ in sorted_items[:removal_count]]

        # Priority eviction: Remove expired entries first
        expired_keys = []
        for key in keys_to_remove:
            entry = self._cache.get(key)
            if entry and entry.get('expires') and current_time > entry['expires']:
                expired_keys.append(key)
        
        # Remove expired entries first
        for key in expired_keys:
            self._cache.pop(key, None)
            self._access_times.pop(key, None)
            self._eviction_count += 1
        
        # Remove remaining LRU entries if needed
        remaining_to_remove = removal_count - len(expired_keys)
        if remaining_to_remove > 0:
            non_expired_keys = [k for k in keys_to_remove if k not in expired_keys]
            for key in non_expired_keys[:remaining_to_remove]:
                self._cache.pop(key, None)
                self._access_times.pop(key, None)
                self._eviction_count += 1

        total_removed = len(expired_keys) + min(remaining_to_remove, len(non_expired_keys))
        if total_removed > 0:
            logger.debug(f"Enhanced LRU cleanup: {total_removed} entries removed ({len(expired_keys)} expired, {total_removed - len(expired_keys)} LRU)")
        
        # Track size limit exceeded incidents
        if len(self._cache) >= self._max_size:
            self._size_limit_exceeded_count += 1

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired (thread-safe, enhanced with metrics)"""
        with self._lock:
            if key not in self._cache:
                self._miss_count += 1
                self._perform_health_check_if_needed()
                return None

            entry = self._cache[key]
            current_time = time.time()

            # Check expiration
            if entry.get('expires') and current_time > entry['expires']:
                # Expired - remove and return None
                self._cache.pop(key, None)
                self._access_times.pop(key, None)
                self._miss_count += 1
                return None

            # Update access time
            self._access_times[key] = current_time
            self._hit_count += 1

            return entry['value']

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL in seconds (thread-safe)"""
        with self._lock:
            expires = None
            if ttl and ttl > 0:
                expires = time.time() + ttl

            self._cache[key] = {
                'value': value,
                'expires': expires,
                'created': time.time()
            }

            self._access_times[key] = time.time()

            # Cleanup if needed
            if len(self._cache) > self._max_size:
                self._cleanup_expired()
                self._cleanup_lru()

    def delete(self, key: str) -> None:
        """Delete key from cache (thread-safe)"""
        with self._lock:
            self._cache.pop(key, None)
            self._access_times.pop(key, None)

    def clear(self) -> None:
        """Clear all cache (thread-safe)"""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()

    async def get_or_fetch_async(self, key: str, fetch_func, ttl: Optional[int] = None) -> Optional[Any]:
        """Get from cache or fetch if not present (async version)"""
        # First try to get from cache (sync operation)
        value = self.get(key)
        if value is not None:
            return value

        # Use async lock for fetch operation
        async with self._async_lock:
            # Double-check after acquiring lock
            value = self.get(key)
            if value is not None:
                return value

            # Fetch new value
            try:
                value = await fetch_func()
                if value is not None:
                    self.set(key, value, ttl)
                return value
            except Exception as e:
                logger.error(f"Error fetching value for key {key}: {e}")
                return None

    def _perform_health_check_if_needed(self) -> None:
        """Perform periodic health check (called from within lock)"""
        current_time = time.time()
        if (current_time - self._last_health_check) > self._health_check_interval:
            self._last_health_check = current_time
            
            # Calculate hit rate
            total_requests = self._hit_count + self._miss_count
            hit_rate = (self._hit_count / total_requests * 100) if total_requests > 0 else 0
            
            # Log health status
            if hit_rate < 70 and total_requests > 100:
                logger.warning(f"💾 Cache performance degraded: {hit_rate:.1f}% hit rate ({total_requests} requests)")
            elif hit_rate > 90 and total_requests > 100:
                logger.debug(f"💾 Cache performing well: {hit_rate:.1f}% hit rate ({total_requests} requests)")
            
            # Check for excessive evictions
            if self._eviction_count > 100:
                logger.info(f"💾 Cache evictions: {self._eviction_count} total, consider increasing cache size")
            
            # Auto-cleanup if needed
            if len(self._cache) > (self._max_size * 0.95):
                logger.debug("💾 Performing automatic cache cleanup due to high usage")
                self._cleanup_expired()
                self._cleanup_lru()

    def get_stats(self) -> Dict[str, Any]:
        """Get enhanced cache statistics (2025 version)"""
        with self._lock:
            current_time = time.time()
            expired_count = 0
            
            # Count expired entries
            for entry in self._cache.values():
                if entry.get('expires') and current_time > entry['expires']:
                    expired_count += 1
            
            total_requests = self._hit_count + self._miss_count
            hit_rate = (self._hit_count / total_requests) if total_requests > 0 else 0
            
            return {
                "total_entries": len(self._cache),
                "expired_entries": expired_count,
                "max_size": self._max_size,
                "usage_percent": (len(self._cache) / self._max_size) * 100,
                "hit_rate": hit_rate,
                "hit_count": self._hit_count,
                "miss_count": self._miss_count,
                "eviction_count": self._eviction_count,
                "size_limit_exceeded_count": self._size_limit_exceeded_count,
                "health_status": "healthy" if hit_rate > 0.7 or total_requests < 10 else "degraded"
            }
    
    def reset_metrics(self) -> None:
        """Reset performance metrics"""
        with self._lock:
            self._hit_count = 0
            self._miss_count = 0
            self._eviction_count = 0
            self._size_limit_exceeded_count = 0
            logger.debug("💾 Cache metrics reset")
    
    def get_cache_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive cache health report"""
        stats = self.get_stats()
        
        # Calculate performance grade
        hit_rate = stats['hit_rate']
        usage_percent = stats['usage_percent']
        
        if hit_rate > 0.9:
            performance_grade = "A"
        elif hit_rate > 0.8:
            performance_grade = "B"
        elif hit_rate > 0.7:
            performance_grade = "C"
        elif hit_rate > 0.5:
            performance_grade = "D"
        else:
            performance_grade = "F"
        
        # Determine recommendations
        recommendations = []
        if hit_rate < 0.7:
            recommendations.append("Consider increasing cache TTL values")
        if usage_percent > 90:
            recommendations.append("Consider increasing cache size")
        if stats['eviction_count'] > stats['total_entries']:
            recommendations.append("High eviction rate - optimize cache usage patterns")
        if not recommendations:
            recommendations.append("Cache performance is optimal")
        
        return {
            "performance_grade": performance_grade,
            "hit_rate_percent": hit_rate * 100,
            "memory_efficiency": 100 - usage_percent,
            "recommendations": recommendations,
            "detailed_stats": stats,
            "health_status": stats['health_status']
        }

# Global cache instance with reasonable size
enhanced_cache = EnhancedCache(max_size=1000)

# FIXED: Proper async/sync compatibility for cached functions
async def get_instrument_info_cached(symbol: str) -> Optional[Dict]:
    """Get instrument info with caching - FIXED async compatibility"""

    async def fetch():
        try:
            # FIXED: Import here to avoid circular imports
            from clients.bybit_client import bybit_client

            # FIXED: Proper async wrapper for sync client
            loop = asyncio.get_event_loop()

            # Use run_in_executor for thread-safe sync call
            response = await loop.run_in_executor(
                None,
                lambda: bybit_client.get_instruments_info(
                    category="linear",
                    symbol=symbol
                )
            )

            if response and response.get("retCode") == 0:
                result = response.get("result", {})
                instruments = result.get("list", [])
                if instruments:
                    logger.debug(f"Fetched instrument info for {symbol}")
                    return instruments[0]

            return None

        except Exception as e:
            logger.error(f"Error fetching instrument info for {symbol}: {e}")
            return None

    return await enhanced_cache.get_or_fetch_async(f"instrument_{symbol}", fetch, ttl=3600)

async def get_usdt_wallet_balance_cached() -> tuple[Optional[Decimal], Optional[Decimal]]:
    """Get USDT wallet balance with caching - returns (total_balance, available_balance)"""

    async def fetch():
        try:
            # FIXED: Import here to avoid circular imports
            from clients.bybit_client import bybit_client

            # FIXED: Proper async wrapper for sync client
            loop = asyncio.get_event_loop()

            # Use run_in_executor for thread-safe sync call
            response = await loop.run_in_executor(
                None,
                lambda: bybit_client.get_wallet_balance(accountType="UNIFIED")
            )

            if response and response.get("retCode") == 0:
                result = response.get("result", {})
                accounts = result.get("list", [])

                if accounts:
                    account = accounts[0]
                    # Get balance from account level
                    total_balance = Decimal(account.get("totalWalletBalance", "0"))
                    available_balance = Decimal(account.get("totalAvailableBalance", "0"))

                    logger.info(f"Account Balance - Total: {total_balance}, Available: {available_balance}")

                    # Also check USDT coin details if needed
                    coins = account.get("coin", [])
                    for coin in coins:
                        if coin.get("coin") == "USDT":
                            # Use coin wallet balance if account level is zero
                            coin_balance = Decimal(coin.get("walletBalance", "0"))
                            if total_balance == 0 and coin_balance > 0:
                                total_balance = coin_balance
                            logger.debug(f"USDT coin details - walletBalance: {coin_balance}")
                            break

                    return (total_balance, available_balance)

            return (Decimal("0"), Decimal("0"))

        except Exception as e:
            logger.error(f"Error fetching wallet balance: {e}")
            return (Decimal("0"), Decimal("0"))

    result = await enhanced_cache.get_or_fetch_async("wallet_balance_usdt", fetch, ttl=60)
    # Ensure we always return a tuple
    if isinstance(result, tuple) and len(result) == 2:
        return result
    elif isinstance(result, (Decimal, float, int)):
        # Backward compatibility - if cached value is single number
        return (result, result)
    else:
        return (Decimal("0"), Decimal("0"))

async def get_ticker_price_cached(symbol: str) -> Optional[Decimal]:
    """Get ticker price with caching - FIXED async compatibility"""

    async def fetch():
        try:
            # FIXED: Import here to avoid circular imports
            from clients.bybit_client import bybit_client

            # FIXED: Proper async wrapper for sync client
            loop = asyncio.get_event_loop()

            # Use run_in_executor for thread-safe sync call
            response = await loop.run_in_executor(
                None,
                lambda: bybit_client.get_tickers(
                    category="linear",
                    symbol=symbol
                )
            )

            if response and response.get("retCode") == 0:
                result = response.get("result", {})
                ticker_list = result.get("list", [])

                if ticker_list:
                    ticker = ticker_list[0]
                    last_price = ticker.get("lastPrice")

                    if last_price:
                        price = Decimal(last_price)
                        logger.debug(f"Fetched ticker price for {symbol}: {price}")
                        return price

            return None

        except Exception as e:
            logger.error(f"Error fetching ticker price for {symbol}: {e}")
            return None

    return await enhanced_cache.get_or_fetch_async(f"ticker_{symbol}", fetch, ttl=15)

async def get_market_data_cached(symbol: str) -> Optional[Dict]:
    """Get comprehensive market data with caching"""

    async def fetch():
        try:
            # FIXED: Import here to avoid circular imports
            from clients.bybit_client import bybit_client

            # FIXED: Proper async wrapper for sync client
            loop = asyncio.get_event_loop()

            # Fetch both ticker and instrument info
            ticker_task = loop.run_in_executor(
                None,
                lambda: bybit_client.get_tickers(category="linear", symbol=symbol)
            )

            instrument_task = loop.run_in_executor(
                None,
                lambda: bybit_client.get_instruments_info(category="linear", symbol=symbol)
            )

            ticker_response, instrument_response = await asyncio.gather(
                ticker_task, instrument_task, return_exceptions=True
            )

            market_data = {"symbol": symbol}

            # Process ticker data
            if (not isinstance(ticker_response, Exception) and
                ticker_response and ticker_response.get("retCode") == 0):
                ticker_list = ticker_response.get("result", {}).get("list", [])
                if ticker_list:
                    ticker = ticker_list[0]
                    market_data.update({
                        "lastPrice": ticker.get("lastPrice"),
                        "volume24h": ticker.get("volume24h"),
                        "priceChange": ticker.get("price24hPcnt"),
                        "highPrice24h": ticker.get("highPrice24h"),
                        "lowPrice24h": ticker.get("lowPrice24h")
                    })

            # Process instrument data
            if (not isinstance(instrument_response, Exception) and
                instrument_response and instrument_response.get("retCode") == 0):
                instruments = instrument_response.get("result", {}).get("list", [])
                if instruments:
                    instrument = instruments[0]
                    market_data.update({
                        "tickSize": instrument.get("priceFilter", {}).get("tickSize"),
                        "qtyStep": instrument.get("lotSizeFilter", {}).get("qtyStep"),
                        "minOrderQty": instrument.get("lotSizeFilter", {}).get("minOrderQty"),
                        "maxLeverage": instrument.get("leverageFilter", {}).get("maxLeverage")
                    })

            return market_data if len(market_data) > 1 else None

        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return None

    return await enhanced_cache.get_or_fetch_async(f"market_data_{symbol}", fetch, ttl=120)

# FIXED: Thread-safe cache management functions
def invalidate_balance_cache():
    """Invalidate balance cache"""
    enhanced_cache.delete("wallet_balance_usdt")
    logger.debug("Balance cache invalidated")

def invalidate_mirror_balance_cache():
    """Invalidate mirror balance cache"""
    enhanced_cache.delete("mirror_wallet_balance_usdt")
    logger.debug("Mirror balance cache invalidated")

def invalidate_ticker_cache(symbol: str):
    """Invalidate ticker cache for specific symbol"""
    enhanced_cache.delete(f"ticker_{symbol}")
    logger.debug(f"Ticker cache invalidated for {symbol}")

def invalidate_instrument_cache(symbol: str):
    """Invalidate instrument cache for specific symbol"""
    enhanced_cache.delete(f"instrument_{symbol}")
    logger.debug(f"Instrument cache invalidated for {symbol}")

def invalidate_market_data_cache(symbol: str):
    """Invalidate market data cache for specific symbol"""
    enhanced_cache.delete(f"market_data_{symbol}")
    logger.debug(f"Market data cache invalidated for {symbol}")

def invalidate_all_caches():
    """Clear all caches"""
    enhanced_cache.clear()
    logger.info("All caches cleared")

async def invalidate_all_caches_async():
    """Async version of invalidate_all_caches for non-blocking operation"""
    await asyncio.to_thread(invalidate_all_caches)
    logger.info("All caches cleared (async)")

async def progressive_cache_invalidation(volatile_only: bool = True):
    """
    Progressive cache invalidation to prevent blocking operations
    Based on 2025 best practices for async cache management
    
    Args:
        volatile_only: If True, only clear volatile data (prices, balances, market data)
                      If False, clear all caches including expensive AI analysis
    """
    logger.info(f"🧹 Starting progressive cache invalidation (volatile_only={volatile_only})")
    
    # Use async context to prevent blocking the main thread
    if volatile_only:
        # Clear only frequently-changing data to preserve expensive AI analysis
        await asyncio.to_thread(invalidate_volatile_caches)
        logger.info("✅ Progressive cache invalidation completed (volatile data only)")
    else:
        # Clear all caches in background thread
        await asyncio.to_thread(invalidate_all_caches)
        logger.info("✅ Progressive cache invalidation completed (all caches)")

def invalidate_position_related_caches():
    """Invalidate only position-related caches (keep instrument info)"""
    # Get all cache keys
    keys_to_remove = []
    with enhanced_cache._lock:
        for key in list(enhanced_cache._cache.keys()):
            # Keep instrument info and other stable data
            if not key.startswith("instrument_"):
                keys_to_remove.append(key)

    # Remove selected keys
    for key in keys_to_remove:
        enhanced_cache.delete(key)

    logger.info(f"Invalidated {len(keys_to_remove)} position-related cache entries")

def invalidate_volatile_caches():
    """Invalidate only volatile caches (prices, balances, market data)"""
    # Get all cache keys
    keys_to_remove = []
    with enhanced_cache._lock:
        for key in list(enhanced_cache._cache.keys()):
            # Remove volatile data including market data for fresh refresh
            if key.startswith(("ticker_", "wallet_balance", "mirror_wallet_balance", "market_data_")):
                keys_to_remove.append(key)

    # Remove selected keys
    for key in keys_to_remove:
        enhanced_cache.delete(key)

    logger.info(f"Invalidated {len(keys_to_remove)} volatile cache entries")

def invalidate_market_analysis_cache(symbol: Optional[str] = None):
    """Invalidate market analysis cache for specific symbol or all symbols"""
    keys_to_remove = []
    with enhanced_cache._lock:
        for key in list(enhanced_cache._cache.keys()):
            # Remove market status caches
            if key.startswith("market_status_"):
                if symbol is None or key == f"market_status_{symbol}":
                    keys_to_remove.append(key)
                    
    # Remove selected keys
    for key in keys_to_remove:
        enhanced_cache.delete(key)
        
    symbol_msg = f" for {symbol}" if symbol else ""
    logger.info(f"Invalidated {len(keys_to_remove)} market analysis cache entries{symbol_msg}")

def invalidate_ai_insights_cache(symbol: Optional[str] = None):
    """Invalidate AI insights cache for specific symbol or all symbols"""
    keys_to_remove = []
    with enhanced_cache._lock:
        for key in list(enhanced_cache._cache.keys()):
            # Remove AI analysis caches (these use method signatures in the key)
            if "analyze_market" in key:
                if symbol is None or symbol in key:
                    keys_to_remove.append(key)
                    
    # Remove selected keys
    for key in keys_to_remove:
        enhanced_cache.delete(key)
        
    symbol_msg = f" for {symbol}" if symbol else ""
    logger.info(f"Invalidated {len(keys_to_remove)} AI insights cache entries{symbol_msg}")

def force_refresh_market_data(symbol: str):
    """Force refresh market data by clearing caches for specific symbol"""
    invalidate_market_analysis_cache(symbol)
    invalidate_ai_insights_cache(symbol)
    invalidate_market_data_cache(symbol)
    logger.info(f"Force refresh completed for {symbol} - all related caches cleared")

def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics for monitoring"""
    return enhanced_cache.get_stats()

# FIXED: Renamed function to match import in main.py
async def _periodic_cache_cleanup():
    """Periodic cache cleanup task - matches import name in main.py"""
    while True:
        try:
            # Sleep for 5 minutes
            await asyncio.sleep(300)

            # Get stats before cleanup
            stats_before = enhanced_cache.get_stats()

            # Force cleanup of expired entries
            with enhanced_cache._lock:
                enhanced_cache._cleanup_expired()

            # Get stats after cleanup
            stats_after = enhanced_cache.get_stats()

            if stats_before["total_entries"] != stats_after["total_entries"]:
                logger.info(f"Cache cleanup: {stats_before['total_entries']} → {stats_after['total_entries']} entries")

        except Exception as e:
            logger.error(f"Error in periodic cache cleanup: {e}")
            await asyncio.sleep(60)  # Wait before retrying

# Backward compatibility - keep old function name too
periodic_cache_cleanup = _periodic_cache_cleanup

# Start periodic cleanup (call this from main application)
def start_cache_cleanup_task():
    """Start the periodic cache cleanup task"""
    try:
        asyncio.create_task(_periodic_cache_cleanup())
        logger.info("✅ Cache cleanup task started")
    except Exception as e:
        logger.error(f"Error starting cache cleanup task: {e}")

async def get_mirror_wallet_balance_cached() -> tuple[Optional[Decimal], Optional[Decimal]]:
    """Get USDT wallet balance from mirror account with caching - returns (total_balance, available_balance)"""

    async def fetch():
        try:
            # Import here to avoid circular imports
            from execution.mirror_trader import get_mirror_wallet_balance, is_mirror_trading_enabled

            if not is_mirror_trading_enabled():
                return (Decimal("0"), Decimal("0"))

            # Get mirror balance
            balance_tuple = await get_mirror_wallet_balance()
            return balance_tuple

        except Exception as e:
            logger.error(f"Error fetching mirror wallet balance: {e}")
            return (Decimal("0"), Decimal("0"))

    result = await enhanced_cache.get_or_fetch_async("mirror_wallet_balance_usdt", fetch, ttl=60)
    # Ensure we always return a tuple
    if isinstance(result, tuple) and len(result) == 2:
        return result
    else:
        return (Decimal("0"), Decimal("0"))

# Decorator for async caching
def async_cache(ttl_seconds: int = 300):
    """Decorator for caching async function results"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

            # Try to get from cache
            cached_result = enhanced_cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Call the actual function
            result = await func(*args, **kwargs)

            # Store in cache
            enhanced_cache.set(cache_key, result, ttl_seconds)

            return result

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator