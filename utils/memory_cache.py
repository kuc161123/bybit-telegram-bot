#!/usr/bin/env python3
"""
In-memory cache layer for pickle data to reduce file I/O
Significantly improves performance by keeping frequently accessed data in memory
"""
import time
import asyncio
import logging
from typing import Dict, Any, Optional, Tuple
from copy import deepcopy
import pickle

logger = logging.getLogger(__name__)


class MemoryCache:
    """In-memory cache for pickle data with write-through capability"""
    
    def __init__(self, pickle_file: str):
        self.pickle_file = pickle_file
        self._cache: Optional[Dict] = None
        self._cache_time: float = 0
        self._cache_ttl: float = 60  # 1 minute TTL for full cache
        self._dirty: bool = False
        self._last_write: float = 0
        self._write_interval: float = 5  # Write dirty data every 5 seconds
        self._lock = asyncio.Lock()
        
        # Partial cache for frequently accessed paths
        self._partial_cache: Dict[str, Tuple[Any, float]] = {}
        self._partial_ttl: float = 30  # 30 seconds for partial cache
        
    async def get(self, path: Optional[str] = None) -> Any:
        """Get data from cache or load from file"""
        async with self._lock:
            # Check partial cache first
            if path and path in self._partial_cache:
                value, timestamp = self._partial_cache[path]
                if time.time() - timestamp < self._partial_ttl:
                    logger.debug(f"Partial cache hit for {path}")
                    return deepcopy(value)
            
            # Check if we need to reload full cache
            if self._cache is None or time.time() - self._cache_time > self._cache_ttl:
                await self._load_from_file()
            
            if path:
                # Navigate to requested path
                result = self._navigate_path(self._cache, path)
                # Cache the result
                self._partial_cache[path] = (result, time.time())
                return deepcopy(result)
            else:
                return deepcopy(self._cache)
    
    async def set(self, data: Dict, path: Optional[str] = None) -> None:
        """Set data in cache and mark as dirty"""
        async with self._lock:
            if path:
                # Update specific path
                if self._cache is None:
                    await self._load_from_file()
                self._set_path(self._cache, path, data)
                # Invalidate partial cache for this path
                self._partial_cache.pop(path, None)
            else:
                # Replace entire cache
                self._cache = deepcopy(data)
                self._cache_time = time.time()
                # Clear partial cache
                self._partial_cache.clear()
            
            self._dirty = True
            
            # Write if enough time has passed
            if time.time() - self._last_write > self._write_interval:
                await self._write_to_file()
    
    async def flush(self) -> None:
        """Force write dirty data to file"""
        async with self._lock:
            if self._dirty:
                await self._write_to_file()
    
    async def invalidate(self, path: Optional[str] = None) -> None:
        """Invalidate cache entries"""
        async with self._lock:
            if path:
                self._partial_cache.pop(path, None)
            else:
                self._cache = None
                self._partial_cache.clear()
    
    async def _load_from_file(self) -> None:
        """Load data from pickle file"""
        try:
            with open(self.pickle_file, 'rb') as f:
                self._cache = pickle.load(f)
                self._cache_time = time.time()
                logger.debug("Loaded pickle data into memory cache")
        except Exception as e:
            logger.error(f"Error loading pickle file: {e}")
            self._cache = {}
    
    async def _write_to_file(self) -> None:
        """Write cache to pickle file"""
        if not self._dirty or self._cache is None:
            return
            
        try:
            # Write to temporary file first
            temp_file = f"{self.pickle_file}.tmp"
            with open(temp_file, 'wb') as f:
                pickle.dump(self._cache, f)
            
            # Atomic rename
            import os
            os.replace(temp_file, self.pickle_file)
            
            self._dirty = False
            self._last_write = time.time()
            logger.debug("Wrote memory cache to pickle file")
            
        except Exception as e:
            logger.error(f"Error writing to pickle file: {e}")
    
    def _navigate_path(self, data: Dict, path: str) -> Any:
        """Navigate to a specific path in the data structure"""
        parts = path.split('.')
        current = data
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
                
        return current
    
    def _set_path(self, data: Dict, path: str, value: Any) -> None:
        """Set value at a specific path in the data structure"""
        parts = path.split('.')
        current = data
        
        # Navigate to parent
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Set the value
        if parts:
            current[parts[-1]] = value


class PickleMemoryCache:
    """Enhanced pickle operations with memory caching"""
    
    def __init__(self, filepath: str):
        self.cache = MemoryCache(filepath)
        self._background_task = None
        
    async def start(self):
        """Start background writer task"""
        self._background_task = asyncio.create_task(self._background_writer())
        
    async def stop(self):
        """Stop background writer and flush"""
        if self._background_task:
            self._background_task.cancel()
        await self.cache.flush()
        
    async def _background_writer(self):
        """Periodically write dirty data"""
        while True:
            try:
                await asyncio.sleep(5)
                await self.cache.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in background writer: {e}")
    
    async def read_data(self, path: Optional[str] = None) -> Any:
        """Read data with memory cache"""
        return await self.cache.get(path)
    
    async def write_data(self, data: Any, path: Optional[str] = None) -> None:
        """Write data with memory cache"""
        await self.cache.set(data, path)
    
    async def get_monitors(self) -> Dict:
        """Get monitors from cache"""
        bot_data = await self.cache.get('bot_data')
        if bot_data and isinstance(bot_data, dict):
            return bot_data.get('enhanced_tp_sl_monitors', {})
        return {}
    
    async def get_user_positions(self, chat_id: int) -> List[Dict]:
        """Get user positions from cache"""
        user_data = await self.cache.get(f'user_data.{chat_id}')
        if user_data and isinstance(user_data, dict):
            return user_data.get('positions', [])
        return []
    
    async def update_monitor(self, monitor_key: str, updates: Dict) -> None:
        """Update specific monitor efficiently"""
        monitors = await self.get_monitors()
        if monitor_key in monitors:
            monitors[monitor_key].update(updates)
            await self.cache.set(monitors, 'bot_data.enhanced_tp_sl_monitors')


# Global instance
pickle_memory_cache: Optional[PickleMemoryCache] = None


def get_pickle_cache() -> PickleMemoryCache:
    """Get or create global pickle cache instance"""
    global pickle_memory_cache
    if pickle_memory_cache is None:
        from utils.robust_persistence import PERSISTENCE_FILE
        pickle_memory_cache = PickleMemoryCache(PERSISTENCE_FILE)
    return pickle_memory_cache