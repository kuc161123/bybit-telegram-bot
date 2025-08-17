#!/usr/bin/env python3
"""
Memory Management System
Prevents memory leaks by managing collection sizes and cleaning up stale data
"""
import gc
import logging
import time
from typing import Dict, List, Any, Set
from collections import deque
from weakref import WeakValueDictionary
import asyncio

logger = logging.getLogger(__name__)

class MemoryManager:
    """Manages memory usage and prevents leaks in collections"""
    
    def __init__(self, max_collection_size: int = 1000, cleanup_interval: int = 300):
        """
        Initialize memory manager
        
        Args:
            max_collection_size: Maximum size for managed collections
            cleanup_interval: Interval in seconds for automatic cleanup
        """
        self.max_collection_size = max_collection_size
        self.cleanup_interval = cleanup_interval
        self.last_cleanup = time.time()
        
        # Track managed collections
        self.managed_collections: Dict[str, Any] = {}
        
        # Memory usage tracking
        self.cleanup_count = 0
        self.items_removed = 0
        
    def manage_collection(self, name: str, collection: Any) -> None:
        """
        Register a collection for memory management
        
        Args:
            name: Name identifier for the collection
            collection: The collection to manage (list, dict, set, etc.)
        """
        self.managed_collections[name] = collection
        logger.debug(f"Registered collection '{name}' for memory management")
    
    def cleanup_collection(self, collection: Any, max_size: Optional[int] = None) -> int:
        """
        Clean up a collection to prevent unbounded growth
        
        Args:
            collection: Collection to clean up
            max_size: Maximum size to maintain (uses default if None)
            
        Returns:
            Number of items removed
        """
        if max_size is None:
            max_size = self.max_collection_size
        
        removed = 0
        
        try:
            if isinstance(collection, list):
                # Keep only the most recent items
                if len(collection) > max_size:
                    removed = len(collection) - max_size
                    del collection[:-max_size]
                    
            elif isinstance(collection, dict):
                # Remove oldest items (assumes insertion order is maintained)
                if len(collection) > max_size:
                    removed = len(collection) - max_size
                    keys_to_remove = list(collection.keys())[:-max_size]
                    for key in keys_to_remove:
                        del collection[key]
                        
            elif isinstance(collection, set):
                # Convert to list, keep recent, convert back
                if len(collection) > max_size:
                    removed = len(collection) - max_size
                    items = list(collection)
                    collection.clear()
                    collection.update(items[-max_size:])
                    
            elif isinstance(collection, deque):
                # Deque has maxlen, but we can still trim if needed
                while len(collection) > max_size:
                    collection.popleft()
                    removed += 1
                    
        except Exception as e:
            logger.error(f"Error cleaning up collection: {e}")
        
        if removed > 0:
            self.items_removed += removed
            logger.debug(f"Removed {removed} items from collection")
        
        return removed
    
    def cleanup_alert_history(self, alert_history: List[Dict], max_size: int = 500) -> None:
        """
        Clean up alert history to prevent unbounded growth
        
        Args:
            alert_history: Alert history list
            max_size: Maximum alerts to keep
        """
        if len(alert_history) > max_size:
            # Keep only the most recent alerts
            removed = len(alert_history) - max_size
            del alert_history[:-max_size]
            self.items_removed += removed
            logger.info(f"Cleaned up alert history: removed {removed} old alerts")
    
    def cleanup_monitor_collection(self, monitors: Dict[str, Any], active_positions: Set[str]) -> None:
        """
        Clean up stale monitors that don't have active positions
        
        Args:
            monitors: Monitor dictionary
            active_positions: Set of active position keys
        """
        stale_monitors = []
        
        for key in monitors.keys():
            # Extract symbol from monitor key (format: "SYMBOL_Side_account")
            parts = key.split('_')
            if len(parts) >= 2:
                symbol = parts[0]
                if symbol not in active_positions:
                    # Check if monitor is old (no updates for 10 minutes)
                    monitor = monitors[key]
                    last_update = monitor.get('last_update', 0)
                    if time.time() - last_update > 600:  # 10 minutes
                        stale_monitors.append(key)
        
        for key in stale_monitors:
            del monitors[key]
            self.items_removed += 1
        
        if stale_monitors:
            logger.info(f"Removed {len(stale_monitors)} stale monitors")
    
    def cleanup_cache_entries(self, cache: Dict[str, Any], ttl: int = 300) -> None:
        """
        Clean up expired cache entries
        
        Args:
            cache: Cache dictionary with timestamp entries
            ttl: Time to live in seconds
        """
        current_time = time.time()
        expired_keys = []
        
        for key, entry in cache.items():
            if isinstance(entry, dict):
                timestamp = entry.get('timestamp', entry.get('created', 0))
                if current_time - timestamp > ttl:
                    expired_keys.append(key)
        
        for key in expired_keys:
            del cache[key]
            self.items_removed += 1
        
        if expired_keys:
            logger.debug(f"Removed {len(expired_keys)} expired cache entries")
    
    def force_garbage_collection(self) -> Dict[str, Any]:
        """
        Force garbage collection and return stats
        
        Returns:
            Dict with garbage collection statistics
        """
        import gc
        
        # Get stats before collection
        before = gc.get_count()
        
        # Force collection
        collected = gc.collect()
        
        # Get stats after collection
        after = gc.get_count()
        
        stats = {
            'collected_objects': collected,
            'before_count': before,
            'after_count': after,
            'cleanup_count': self.cleanup_count,
            'total_items_removed': self.items_removed
        }
        
        logger.info(f"Garbage collection completed: {collected} objects collected")
        
        return stats
    
    def check_memory_usage(self) -> Dict[str, Any]:
        """
        Check current memory usage
        
        Returns:
            Dict with memory usage information
        """
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,
            'vms_mb': memory_info.vms / 1024 / 1024,
            'percent': process.memory_percent(),
            'available_mb': psutil.virtual_memory().available / 1024 / 1024
        }
    
    async def periodic_cleanup(self) -> None:
        """
        Perform periodic cleanup of all managed collections
        """
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                current_time = time.time()
                self.cleanup_count += 1
                
                # Cleanup each managed collection
                for name, collection in self.managed_collections.items():
                    try:
                        removed = self.cleanup_collection(collection)
                        if removed > 0:
                            logger.debug(f"Cleaned up {removed} items from {name}")
                    except Exception as e:
                        logger.error(f"Error cleaning up {name}: {e}")
                
                # Force garbage collection periodically
                if self.cleanup_count % 10 == 0:  # Every 10 cleanups
                    self.force_garbage_collection()
                
                # Log memory usage
                if self.cleanup_count % 5 == 0:  # Every 5 cleanups
                    memory_stats = self.check_memory_usage()
                    logger.info(f"Memory usage: {memory_stats['rss_mb']:.1f}MB RSS, "
                              f"{memory_stats['percent']:.1f}% of system memory")
                
                self.last_cleanup = current_time
                
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    def cleanup_now(self) -> Dict[str, Any]:
        """
        Perform immediate cleanup of all collections
        
        Returns:
            Cleanup statistics
        """
        stats = {
            'collections_cleaned': 0,
            'items_removed': 0,
            'memory_before': self.check_memory_usage(),
        }
        
        for name, collection in self.managed_collections.items():
            try:
                removed = self.cleanup_collection(collection)
                if removed > 0:
                    stats['collections_cleaned'] += 1
                    stats['items_removed'] += removed
            except Exception as e:
                logger.error(f"Error cleaning up {name}: {e}")
        
        # Force garbage collection
        gc_stats = self.force_garbage_collection()
        stats['gc_stats'] = gc_stats
        stats['memory_after'] = self.check_memory_usage()
        
        return stats


# Global memory manager instance
memory_manager = MemoryManager(max_collection_size=1000, cleanup_interval=300)


def setup_memory_management(collections: Dict[str, Any]) -> None:
    """
    Setup memory management for collections
    
    Args:
        collections: Dict of name -> collection to manage
    """
    for name, collection in collections.items():
        memory_manager.manage_collection(name, collection)
    
    logger.info(f"Memory management setup for {len(collections)} collections")


async def start_memory_cleanup_task() -> None:
    """Start the periodic memory cleanup task"""
    asyncio.create_task(memory_manager.periodic_cleanup())
    logger.info("Memory cleanup task started")


def get_memory_stats() -> Dict[str, Any]:
    """Get current memory statistics"""
    return {
        'memory_usage': memory_manager.check_memory_usage(),
        'cleanup_stats': {
            'cleanup_count': memory_manager.cleanup_count,
            'items_removed': memory_manager.items_removed,
            'last_cleanup': time.time() - memory_manager.last_cleanup
        }
    }