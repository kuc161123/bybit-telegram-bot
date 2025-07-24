#!/usr/bin/env python3
"""
Request batching and deduplication for API calls
Improves performance by reducing duplicate API requests
"""
import asyncio
import time
import logging
from typing import Dict, List, Any, Optional, Callable, Set
from functools import wraps
import hashlib

logger = logging.getLogger(__name__)


class RequestBatcher:
    """Batch and deduplicate API requests for better performance"""
    
    def __init__(self):
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._request_window = 0.1  # 100ms window to batch requests
        self._last_batch_time = 0
        self._request_cache: Dict[str, Any] = {}
        self._cache_ttl = 5  # 5 seconds cache for identical requests
        
    def _get_request_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate unique key for request deduplication"""
        # Create a hashable representation of the request
        key_parts = [func_name]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_str = "|".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    async def batch_request(self, func: Callable, *args, **kwargs) -> Any:
        """Batch and deduplicate requests"""
        request_key = self._get_request_key(func.__name__, args, kwargs)
        
        # Check cache first
        if request_key in self._request_cache:
            cached_result, timestamp = self._request_cache[request_key]
            if time.time() - timestamp < self._cache_ttl:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
        
        # Check if identical request is already pending
        if request_key in self._pending_requests:
            logger.debug(f"Deduplicating request for {func.__name__}")
            return await self._pending_requests[request_key]
        
        # Create future for this request
        future = asyncio.create_future()
        self._pending_requests[request_key] = future
        
        try:
            # Execute the request
            result = await func(*args, **kwargs)
            
            # Cache the result
            self._request_cache[request_key] = (result, time.time())
            
            # Clean old cache entries
            self._clean_cache()
            
            future.set_result(result)
            return result
            
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            # Remove from pending
            self._pending_requests.pop(request_key, None)
    
    def _clean_cache(self):
        """Remove expired cache entries"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self._request_cache.items()
            if current_time - timestamp >= self._cache_ttl
        ]
        for key in expired_keys:
            del self._request_cache[key]


# Global batcher instance
request_batcher = RequestBatcher()


class BatchedAPIClient:
    """Enhanced API client with request batching"""
    
    def __init__(self, client):
        self.client = client
        self._position_requests: Set[str] = set()
        self._order_requests: Set[str] = set()
        self._batch_lock = asyncio.Lock()
        
    async def get_positions_batch(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get multiple positions in a single optimized call"""
        async with self._batch_lock:
            # If we're already fetching all positions, just filter the results
            all_positions = await request_batcher.batch_request(
                self._get_all_positions
            )
            
            # Filter to requested symbols
            result = {}
            for pos in all_positions:
                symbol = pos.get('symbol')
                if symbol in symbols:
                    result[symbol] = pos
                    
            return result
    
    async def get_orders_batch(self, symbols: List[str]) -> Dict[str, List[Dict]]:
        """Get multiple orders in a single optimized call"""
        async with self._batch_lock:
            # Fetch all orders once
            all_orders = await request_batcher.batch_request(
                self._get_all_orders
            )
            
            # Group by symbol
            result = {symbol: [] for symbol in symbols}
            for order in all_orders:
                symbol = order.get('symbol')
                if symbol in symbols:
                    result[symbol].append(order)
                    
            return result
    
    async def _get_all_positions(self) -> List[Dict]:
        """Internal method to get all positions"""
        from clients.bybit_helpers import get_all_positions
        return await get_all_positions(self.client)
    
    async def _get_all_orders(self) -> List[Dict]:
        """Internal method to get all orders"""
        from clients.bybit_helpers import get_all_open_orders
        return await get_all_open_orders(self.client)


def batch_api_calls(func: Callable) -> Callable:
    """Decorator to automatically batch API calls"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await request_batcher.batch_request(func, *args, **kwargs)
    return wrapper


# Enhanced batch functions for common operations
async def get_dashboard_data_optimized(chat_id: int) -> Dict[str, Any]:
    """Get all dashboard data in optimized parallel calls with deduplication"""
    from clients.bybit_helpers import get_positions_and_orders_batch
    from utils.cache import get_usdt_wallet_balance_cached, get_mirror_wallet_balance_cached
    
    # Use request batcher for deduplication
    tasks = [
        request_batcher.batch_request(get_positions_and_orders_batch),
        request_batcher.batch_request(get_usdt_wallet_balance_cached),
        request_batcher.batch_request(get_mirror_wallet_balance_cached),
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    positions_orders = results[0] if not isinstance(results[0], Exception) else ([], [], [], [])
    main_balance = results[1] if not isinstance(results[1], Exception) else 0
    mirror_balance = results[2] if not isinstance(results[2], Exception) else 0
    
    main_positions, main_orders, mirror_positions, mirror_orders = positions_orders
    
    return {
        'main_positions': main_positions,
        'main_orders': main_orders,
        'mirror_positions': mirror_positions,
        'mirror_orders': mirror_orders,
        'main_balance': main_balance,
        'mirror_balance': mirror_balance,
    }