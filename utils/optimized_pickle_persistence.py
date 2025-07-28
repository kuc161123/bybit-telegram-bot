#!/usr/bin/env python3
"""
Optimized Pickle Persistence System with Dirty Flags and Batch Writes
Implements 2025 best practices for high-performance pickle operations
"""
import pickle
import pickletools
import asyncio
import time
import logging
import os
import threading
import gzip
from typing import Dict, Any, Optional, Set, List
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class PickleStats:
    """Statistics for pickle operations"""
    total_saves: int = 0
    total_loads: int = 0
    batch_saves: int = 0
    individual_saves: int = 0
    compression_ratio: float = 0.0
    average_save_time: float = 0.0
    average_load_time: float = 0.0
    file_size_mb: float = 0.0
    last_optimization_time: Optional[datetime] = None

class OptimizedPicklePersistence:
    """
    High-performance pickle persistence with batch writes and dirty flags
    Based on 2025 best practices for pickle optimization
    """
    
    def __init__(self, file_path: str, enable_compression: bool = True, 
                 enable_optimization: bool = True, batch_interval: float = 15.0):
        self.file_path = Path(file_path)
        self.enable_compression = enable_compression
        self.enable_optimization = enable_optimization
        self.batch_interval = batch_interval
        
        # Dirty flags system
        self._dirty_keys: Set[str] = set()
        self._dirty_lock = threading.Lock()
        
        # In-memory cache with write-through
        self._data_cache: Dict[str, Any] = {}
        self._cache_lock = threading.Lock()
        
        # Batch writing system
        self._batch_pending = False
        self._last_batch_time = 0
        self._batch_task: Optional[asyncio.Task] = None
        
        # Performance statistics
        self.stats = PickleStats()
        
        # Background task control
        self._stop_event = asyncio.Event()
        self._batch_writer_task: Optional[asyncio.Task] = None
        
        # Backup management
        self.max_backups = 5
        self.backup_on_save = True
        
        logger.info(f"🚀 Optimized pickle persistence initialized")
        logger.info(f"   File: {self.file_path}")
        logger.info(f"   Compression: {enable_compression}")
        logger.info(f"   Optimization: {enable_optimization}")
        logger.info(f"   Batch interval: {batch_interval}s")
    
    async def load_data(self) -> Dict[str, Any]:
        """
        Load data from pickle file with optimization
        Uses protocol 5 and optimized loading for better performance
        """
        start_time = time.time()
        
        try:
            if not self.file_path.exists():
                logger.info(f"📄 Pickle file not found, starting fresh: {self.file_path}")
                self._data_cache = {}
                return {}
            
            # Load with appropriate method based on compression
            if self.enable_compression and self.file_path.suffix == '.gz':
                with gzip.open(self.file_path, 'rb') as f:
                    data = pickle.load(f)
            else:
                with open(self.file_path, 'rb') as f:
                    data = pickle.load(f)
            
            # Update cache
            with self._cache_lock:
                self._data_cache = data.copy()
            
            # Update statistics
            load_time = time.time() - start_time
            self.stats.total_loads += 1
            self.stats.average_load_time = (
                (self.stats.average_load_time * (self.stats.total_loads - 1) + load_time) / 
                self.stats.total_loads
            )
            
            file_size = self.file_path.stat().st_size
            self.stats.file_size_mb = file_size / (1024 * 1024)
            
            logger.info(f"✅ Loaded pickle data in {load_time:.3f}s ({self.stats.file_size_mb:.2f}MB)")
            
            return data
            
        except Exception as e:
            logger.error(f"❌ Failed to load pickle file {self.file_path}: {e}")
            return {}
    
    async def save_data(self, data: Dict[str, Any], force: bool = False) -> bool:
        """
        Save data with dirty flag optimization and batching
        
        Args:
            data: Data to save
            force: Force immediate save (bypass batching)
            
        Returns:
            bool: Success status
        """
        # Update cache first
        with self._cache_lock:
            self._data_cache.update(data)
        
        if force:
            return await self._immediate_save(data)
        else:
            return await self._batch_save(data)
    
    async def _immediate_save(self, data: Dict[str, Any]) -> bool:
        """Perform immediate save operation"""
        start_time = time.time()
        
        try:
            # Create backup if enabled
            if self.backup_on_save and self.file_path.exists():
                await self._create_backup()
            
            # Prepare data for saving
            save_data = data.copy()
            
            # Use temporary file for atomic write
            temp_file = self.file_path.with_suffix('.tmp')
            
            if self.enable_compression:
                # Save with compression
                with gzip.open(temp_file, 'wb', compresslevel=6) as f:
                    if self.enable_optimization:
                        # Use optimized pickle with protocol 5
                        pickled_data = pickle.dumps(save_data, protocol=pickle.HIGHEST_PROTOCOL)
                        optimized_data = pickletools.optimize(pickled_data)
                        f.write(optimized_data)
                    else:
                        pickle.dump(save_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            else:
                # Save without compression
                with open(temp_file, 'wb') as f:
                    if self.enable_optimization:
                        pickled_data = pickle.dumps(save_data, protocol=pickle.HIGHEST_PROTOCOL)
                        optimized_data = pickletools.optimize(pickled_data)
                        f.write(optimized_data)
                    else:
                        pickle.dump(save_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            # Atomic move
            temp_file.replace(self.file_path)
            
            # Update statistics
            save_time = time.time() - start_time
            self.stats.total_saves += 1
            self.stats.individual_saves += 1
            self.stats.average_save_time = (
                (self.stats.average_save_time * (self.stats.total_saves - 1) + save_time) / 
                self.stats.total_saves
            )
            
            # Calculate compression ratio if compression is enabled
            if self.enable_compression:
                uncompressed_size = len(pickle.dumps(save_data, protocol=pickle.HIGHEST_PROTOCOL))
                compressed_size = self.file_path.stat().st_size
                self.stats.compression_ratio = compressed_size / uncompressed_size
            
            file_size = self.file_path.stat().st_size
            self.stats.file_size_mb = file_size / (1024 * 1024)
            
            logger.debug(f"💾 Immediate save completed in {save_time:.3f}s ({self.stats.file_size_mb:.2f}MB)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save pickle file {self.file_path}: {e}")
            
            # Clean up temp file if it exists
            temp_file = self.file_path.with_suffix('.tmp')
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
            
            return False
    
    async def _batch_save(self, data: Dict[str, Any]) -> bool:
        """Add data to batch queue for later saving"""
        current_time = time.time()
        
        # Mark data as dirty
        with self._dirty_lock:
            for key in data.keys():
                self._dirty_keys.add(key)
        
        self._batch_pending = True
        
        # Start batch writer if not running
        if self._batch_writer_task is None or self._batch_writer_task.done():
            self._batch_writer_task = asyncio.create_task(self._batch_writer_loop())
        
        # If enough time has passed or we have critical data, trigger immediate batch
        if (current_time - self._last_batch_time > self.batch_interval or 
            self._should_force_batch(data)):
            asyncio.create_task(self._execute_batch())
        
        return True
    
    def _should_force_batch(self, data: Dict[str, Any]) -> bool:
        """Determine if we should force immediate batching"""
        # Force batch for critical data like monitor state changes
        critical_keys = ['enhanced_tp_sl_monitors', 'position_monitors', 'monitor_tasks']
        return any(key in data for key in critical_keys)
    
    async def _batch_writer_loop(self):
        """Background loop for batch writing"""
        logger.debug("📝 Batch writer loop started")
        
        while not self._stop_event.is_set():
            try:
                # Wait for batch interval or stop signal
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.batch_interval)
                    break  # Stop signal received
                except asyncio.TimeoutError:
                    pass  # Timeout is expected, continue with batch check
                
                # Execute batch if pending
                if self._batch_pending:
                    await self._execute_batch()
                
            except Exception as e:
                logger.error(f"❌ Batch writer loop error: {e}")
                await asyncio.sleep(1)
        
        logger.debug("📝 Batch writer loop stopped")
    
    async def _execute_batch(self):
        """Execute pending batch write"""
        if not self._batch_pending:
            return
        
        try:
            current_time = time.time()
            
            # Get current cache data
            with self._cache_lock:
                batch_data = self._data_cache.copy()
            
            # Clear dirty flags
            with self._dirty_lock:
                dirty_count = len(self._dirty_keys)
                self._dirty_keys.clear()
            
            # Perform the save
            success = await self._immediate_save(batch_data)
            
            if success:
                self._batch_pending = False
                self._last_batch_time = current_time
                self.stats.batch_saves += 1
                
                logger.debug(f"📦 Batch save completed ({dirty_count} dirty keys)")
            else:
                logger.error("❌ Batch save failed")
                
        except Exception as e:
            logger.error(f"❌ Batch execution error: {e}")
    
    async def _create_backup(self):
        """Create timestamped backup of current file"""
        try:
            if not self.file_path.exists():
                return
            
            timestamp = int(time.time())
            backup_path = self.file_path.with_suffix(f'.backup_{timestamp}')
            
            # Copy file to backup
            import shutil
            shutil.copy2(self.file_path, backup_path)
            
            # Clean up old backups
            await self._cleanup_old_backups()
            
            logger.debug(f"📂 Created backup: {backup_path.name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to create backup: {e}")
    
    async def _cleanup_old_backups(self):
        """Remove old backup files beyond max_backups limit"""
        try:
            backup_pattern = f"{self.file_path.stem}.backup_*"
            backup_files = list(self.file_path.parent.glob(backup_pattern))
            
            if len(backup_files) > self.max_backups:
                # Sort by timestamp (newest first)
                backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                
                # Remove oldest files
                for old_backup in backup_files[self.max_backups:]:
                    try:
                        old_backup.unlink()
                        logger.debug(f"🗑️ Removed old backup: {old_backup.name}")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not remove backup {old_backup}: {e}")
                        
        except Exception as e:
            logger.error(f"❌ Backup cleanup error: {e}")
    
    def mark_dirty(self, *keys: str):
        """Mark specific keys as dirty for next batch save"""
        with self._dirty_lock:
            for key in keys:
                self._dirty_keys.add(key)
        
        self._batch_pending = True
    
    def get_dirty_keys(self) -> Set[str]:
        """Get current dirty keys"""
        with self._dirty_lock:
            return self._dirty_keys.copy()
    
    async def force_save(self) -> bool:
        """Force immediate save of all cached data"""
        with self._cache_lock:
            data = self._data_cache.copy()
        
        return await self._immediate_save(data)
    
    async def optimize_file(self) -> bool:
        """
        Optimize existing pickle file using pickletools.optimize()
        This can reduce file size by removing redundant data
        """
        try:
            if not self.file_path.exists():
                logger.warning("⚠️ Cannot optimize: file does not exist")
                return False
            
            logger.info("🔧 Starting pickle file optimization...")
            start_time = time.time()
            
            # Load current data
            with open(self.file_path, 'rb') as f:
                original_data = f.read()
            
            # Optimize the pickle data
            optimized_data = pickletools.optimize(original_data)
            
            # Calculate size reduction
            original_size = len(original_data)
            optimized_size = len(optimized_data)
            reduction_percent = ((original_size - optimized_size) / original_size) * 100
            
            # Save optimized version
            temp_file = self.file_path.with_suffix('.opt_tmp')
            with open(temp_file, 'wb') as f:
                f.write(optimized_data)
            
            # Atomic replace
            temp_file.replace(self.file_path)
            
            optimization_time = time.time() - start_time
            self.stats.last_optimization_time = datetime.now()
            
            logger.info(f"✅ Optimization completed in {optimization_time:.3f}s")
            logger.info(f"   Size reduction: {reduction_percent:.1f}% ({original_size} → {optimized_size} bytes)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Pickle optimization failed: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        with self._dirty_lock:
            dirty_count = len(self._dirty_keys)
        
        with self._cache_lock:
            cache_size = len(self._data_cache)
        
        return {
            "total_saves": self.stats.total_saves,
            "total_loads": self.stats.total_loads,
            "batch_saves": self.stats.batch_saves,
            "individual_saves": self.stats.individual_saves,
            "compression_ratio": self.stats.compression_ratio,
            "average_save_time": self.stats.average_save_time,
            "average_load_time": self.stats.average_load_time,
            "file_size_mb": self.stats.file_size_mb,
            "dirty_keys_count": dirty_count,
            "cache_size": cache_size,
            "batch_pending": self._batch_pending,
            "last_optimization": self.stats.last_optimization_time,
            "enable_compression": self.enable_compression,
            "enable_optimization": self.enable_optimization,
            "batch_interval": self.batch_interval
        }
    
    async def start(self):
        """Start the optimized persistence system"""
        logger.info("🚀 Starting optimized pickle persistence system")
        
        # Load initial data
        await self.load_data()
        
        # Start batch writer
        if self._batch_writer_task is None:
            self._batch_writer_task = asyncio.create_task(self._batch_writer_loop())
    
    async def stop(self):
        """Stop the persistence system gracefully"""
        logger.info("⏹️ Stopping optimized pickle persistence system")
        
        # Signal stop
        self._stop_event.set()
        
        # Execute final batch if pending
        if self._batch_pending:
            await self._execute_batch()
        
        # Wait for batch writer to complete
        if self._batch_writer_task and not self._batch_writer_task.done():
            try:
                await asyncio.wait_for(self._batch_writer_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("⚠️ Batch writer task did not complete in time")
                self._batch_writer_task.cancel()
        
        logger.info("✅ Optimized pickle persistence stopped")

# Global instance
optimized_persistence: Optional[OptimizedPicklePersistence] = None

def get_optimized_persistence(file_path: str = "bybit_bot_dashboard_v4.1_enhanced.pkl") -> OptimizedPicklePersistence:
    """Get or create the global optimized persistence instance"""
    global optimized_persistence
    
    if optimized_persistence is None:
        optimized_persistence = OptimizedPicklePersistence(file_path)
    
    return optimized_persistence

async def save_with_optimization(data: Dict[str, Any], force: bool = False) -> bool:
    """Convenience function for optimized saving"""
    persistence = get_optimized_persistence()
    return await persistence.save_data(data, force=force)

async def load_with_optimization() -> Dict[str, Any]:
    """Convenience function for optimized loading"""
    persistence = get_optimized_persistence()
    return await persistence.load_data()

def mark_data_dirty(*keys: str):
    """Mark data keys as dirty for batch saving"""
    persistence = get_optimized_persistence()
    persistence.mark_dirty(*keys)