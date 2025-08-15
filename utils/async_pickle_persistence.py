#!/usr/bin/env python3
"""
Async Pickle Persistence System
Non-blocking pickle operations with dirty flag optimization for high-performance trading
"""
import asyncio
import pickle
import gzip
import os
import time
import logging
from typing import Any, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class AsyncPicklePersistence:
    """High-performance async pickle persistence with dirty flag optimization"""
    
    def __init__(self, file_path: str, enable_compression: bool = False, backup_interval: int = 900):
        self.file_path = file_path
        self.backup_file_path = f"{file_path}.backup"
        self.enable_compression = enable_compression
        self.backup_interval = backup_interval  # 15 minutes default
        
        # Performance tracking
        self.last_save_time = 0
        self.last_backup_time = 0
        self.dirty_flag = False
        self.save_count = 0
        self.skip_count = 0
        
        # Thread pool for CPU-intensive operations
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pickle_async")
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
        
    async def cleanup(self):
        """Cleanup resources"""
        self.executor.shutdown(wait=True)
        
    def _save_pickle_sync(self, data: Any, file_path: str) -> Dict[str, Any]:
        """Synchronous pickle save operation (runs in thread pool)"""
        start_time = time.time()
        
        try:
            # Create directory if needed
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            if self.enable_compression:
                # Use gzip compression for large data
                with gzip.open(file_path, 'wb', compresslevel=6) as f:
                    pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            else:
                # Standard pickle for speed
                with open(file_path, 'wb') as f:
                    pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            save_time = time.time() - start_time
            file_size = os.path.getsize(file_path)
            
            return {
                'success': True,
                'save_time': save_time,
                'file_size': file_size,
                'compressed': self.enable_compression
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'save_time': time.time() - start_time
            }
    
    def _load_pickle_sync(self, file_path: str) -> Dict[str, Any]:
        """Synchronous pickle load operation (runs in thread pool)"""
        start_time = time.time()
        
        try:
            if not os.path.exists(file_path):
                return {'success': False, 'error': 'File not found'}
            
            if self.enable_compression:
                with gzip.open(file_path, 'rb') as f:
                    data = pickle.load(f)
            else:
                with open(file_path, 'rb') as f:
                    data = pickle.load(f)
            
            load_time = time.time() - start_time
            
            return {
                'success': True,
                'data': data,
                'load_time': load_time,
                'compressed': self.enable_compression
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'load_time': time.time() - start_time
            }
    
    async def save_async(self, data: Any, force: bool = False, reason: str = "periodic") -> bool:
        """
        Async save with dirty flag optimization
        
        Args:
            data: Data to save
            force: Force save even if not dirty
            reason: Reason for save (for logging)
            
        Returns:
            bool: True if saved, False if skipped
        """
        async with self._lock:
            current_time = time.time()
            
            # Check if we should skip this save
            if not force and not self.dirty_flag:
                self.skip_count += 1
                logger.debug(f"⏭️ Skipped save #{self.skip_count} - no changes detected")
                return False
            
            # Throttle saves to prevent excessive I/O (max once per 5 seconds unless forced)
            min_save_interval = 5 if not force else 0
            if current_time - self.last_save_time < min_save_interval and not force:
                logger.debug(f"⏭️ Save throttled - {current_time - self.last_save_time:.1f}s since last save")
                return False
            
            try:
                # Run save operation in thread pool to prevent blocking
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    self.executor, 
                    self._save_pickle_sync, 
                    data, 
                    self.file_path
                )
                
                if result['success']:
                    self.last_save_time = current_time
                    self.dirty_flag = False
                    self.save_count += 1
                    
                    # Log performance metrics
                    save_time = result['save_time']
                    file_size_mb = result['file_size'] / (1024 * 1024)
                    
                    if save_time > 1.0 or force:  # Only log slow saves or forced saves
                        logger.info(f"💾 Saved pickle ({reason}) in {save_time:.2f}s - {file_size_mb:.1f}MB")
                    else:
                        logger.debug(f"💾 Quick save ({reason}) in {save_time:.3f}s")
                    
                    # Create backup if needed
                    await self._create_backup_if_needed(data, current_time)
                    
                    return True
                else:
                    logger.error(f"❌ Failed to save pickle: {result['error']}")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Error in async save: {e}")
                return False
    
    async def load_async(self) -> Optional[Any]:
        """Async load operation"""
        try:
            # Try main file first
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._load_pickle_sync,
                self.file_path
            )
            
            if result['success']:
                load_time = result['load_time']
                if load_time > 0.5:  # Only log slow loads
                    logger.info(f"📂 Loaded pickle in {load_time:.2f}s")
                else:
                    logger.debug(f"📂 Quick load in {load_time:.3f}s")
                
                return result['data']
            else:
                # Try backup file
                logger.warning(f"Main file failed ({result['error']}), trying backup...")
                
                backup_result = await loop.run_in_executor(
                    self.executor,
                    self._load_pickle_sync,
                    self.backup_file_path
                )
                
                if backup_result['success']:
                    logger.info(f"✅ Loaded from backup in {backup_result['load_time']:.2f}s")
                    return backup_result['data']
                else:
                    logger.error(f"❌ Both main and backup files failed to load")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Error in async load: {e}")
            return None
    
    async def _create_backup_if_needed(self, data: Any, current_time: float):
        """Create backup if interval has passed"""
        if current_time - self.last_backup_time > self.backup_interval:
            try:
                # Create backup in thread pool (non-blocking)
                loop = asyncio.get_running_loop()
                backup_result = await loop.run_in_executor(
                    self.executor,
                    self._save_pickle_sync,
                    data,
                    self.backup_file_path
                )
                
                if backup_result['success']:
                    self.last_backup_time = current_time
                    logger.debug(f"💾 Backup created in {backup_result['save_time']:.2f}s")
                else:
                    logger.warning(f"⚠️ Backup creation failed: {backup_result['error']}")
                    
            except Exception as e:
                logger.error(f"❌ Error creating backup: {e}")
    
    def mark_dirty(self, reason: str = "data_changed"):
        """Mark data as dirty (needing save)"""
        if not self.dirty_flag:
            logger.debug(f"🔄 Data marked dirty: {reason}")
        self.dirty_flag = True
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return {
            'save_count': self.save_count,
            'skip_count': self.skip_count,
            'last_save_time': self.last_save_time,
            'last_backup_time': self.last_backup_time,
            'dirty_flag': self.dirty_flag,
            'compression_enabled': self.enable_compression,
            'save_efficiency': self.save_count / (self.save_count + self.skip_count) if (self.save_count + self.skip_count) > 0 else 0
        }

# Global instance for the bot
_global_persistence = None

def get_async_persistence(file_path: str = None) -> AsyncPicklePersistence:
    """Get or create global async persistence instance"""
    global _global_persistence
    
    if _global_persistence is None or file_path:
        file_path = file_path or 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        enable_compression = os.getenv('ENABLE_PICKLE_COMPRESSION', 'false').lower() == 'true'
        backup_interval = int(os.getenv('PICKLE_BACKUP_INTERVAL', 900))  # 15 minutes
        
        _global_persistence = AsyncPicklePersistence(
            file_path=file_path,
            enable_compression=enable_compression,
            backup_interval=backup_interval
        )
    
    return _global_persistence

@asynccontextmanager
async def async_pickle_context(file_path: str = None):
    """Context manager for async pickle operations"""
    persistence = get_async_persistence(file_path)
    try:
        yield persistence
    finally:
        # Cleanup handled by context manager
        pass