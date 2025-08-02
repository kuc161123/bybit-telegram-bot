#!/usr/bin/env python3
"""
Performance utilities for dashboard operations
"""

import time
import asyncio
from functools import wraps, lru_cache
from typing import Dict, Any, Optional, Callable
import hashlib
import json

# NO CACHE SYSTEM - Direct API calls only for reliable TP detection
# Cache system completely removed to ensure real-time position monitoring

# Debouncing storage
_debounce_timers: Dict[str, asyncio.Task] = {}
_last_call_time: Dict[str, float] = {}

def no_cache_direct_api():
    """Decorator for direct API calls - NO CACHING for reliable TP detection"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # DIRECT API CALL - No caching for real-time data
            result = await func(*args, **kwargs)
            return result
        return wrapper
    return decorator

def debounce(wait: float):
    """Decorator to debounce function calls"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = f"{func.__name__}_{id(args[0]) if args else 'global'}"
            
            # Cancel previous timer if exists
            if key in _debounce_timers:
                _debounce_timers[key].cancel()
            
            # Create new timer
            async def delayed_call():
                await asyncio.sleep(wait)
                await func(*args, **kwargs)
                if key in _debounce_timers:
                    del _debounce_timers[key]
            
            _debounce_timers[key] = asyncio.create_task(delayed_call())
        return wrapper
    return decorator

def rate_limit(calls: int, period: float):
    """Decorator to rate limit function calls"""
    call_times: list = []
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_time = time.time()
            
            # Remove old calls
            nonlocal call_times
            call_times = [t for t in call_times if current_time - t < period]
            
            # Check rate limit
            if len(call_times) >= calls:
                raise Exception(f"Rate limit exceeded: {calls} calls per {period} seconds")
            
            # Record call and execute
            call_times.append(current_time)
            return await func(*args, **kwargs)
        return wrapper
    return decorator

@lru_cache(maxsize=256)
def generate_button_data(symbol: str, side: str, approach: str, index: int) -> str:
    """Cache button callback data generation"""
    return f"pos_{index}_{symbol}_{side}_{approach}"

def get_dashboard_stats() -> Dict[str, Any]:
    """Get dashboard statistics (NO CACHE SYSTEM)"""
    return {
        "cache_system": "DISABLED - Direct API calls only",
        "active_debounce_timers": len(_debounce_timers),
        "direct_api_mode": True,
        "tp_detection": "Real-time via direct API calls"
    }

# Batch operations helper
class BatchProcessor:
    """Process operations in batches for better performance"""
    
    def __init__(self, batch_size: int = 10, delay: float = 0.1):
        self.batch_size = batch_size
        self.delay = delay
        self.queue = []
        self.processing = False
        
    async def add(self, operation: Callable, *args, **kwargs):
        """Add operation to batch queue"""
        self.queue.append((operation, args, kwargs))
        
        if not self.processing:
            asyncio.create_task(self._process_queue())
    
    async def _process_queue(self):
        """Process queued operations in batches"""
        self.processing = True
        
        while self.queue:
            # Get batch
            batch = self.queue[:self.batch_size]
            self.queue = self.queue[self.batch_size:]
            
            # Process batch concurrently
            tasks = []
            for operation, args, kwargs in batch:
                tasks.append(asyncio.create_task(operation(*args, **kwargs)))
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Small delay between batches
            if self.queue:
                await asyncio.sleep(self.delay)
        
        self.processing = False

# Global batch processor instance
dashboard_batch_processor = BatchProcessor(batch_size=5, delay=0.05)
