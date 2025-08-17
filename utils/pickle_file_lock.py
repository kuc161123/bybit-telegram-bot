#!/usr/bin/env python3
"""
Pickle File Locking Mechanism
Prevents race conditions when multiple processes/threads access pickle files
FIXED: Platform-independent locking using filelock library
"""
import os
import pickle
import logging
import time
from typing import Any, Optional
from contextlib import contextmanager
from threading import RLock
import fcntl
import errno

logger = logging.getLogger(__name__)

class PickleFileLock:
    """Thread-safe and process-safe pickle file access with locking"""
    
    def __init__(self, filepath: str, timeout: float = 5.0):
        """
        Initialize pickle file lock
        
        Args:
            filepath: Path to the pickle file
            timeout: Maximum time to wait for lock acquisition
        """
        self.filepath = filepath
        self.lock_filepath = f"{filepath}.lock"
        self.timeout = timeout
        self._thread_lock = RLock()  # For thread safety
        self._lock_file = None
        
    @contextmanager
    def acquire_lock(self, exclusive: bool = True):
        """
        Context manager for acquiring file lock
        
        Args:
            exclusive: If True, acquire exclusive lock (for writing), else shared lock (for reading)
        """
        lock_acquired = False
        start_time = time.time()
        
        with self._thread_lock:  # Thread safety first
            try:
                # Open or create lock file
                self._lock_file = open(self.lock_filepath, 'a')
                
                # Try to acquire lock with timeout
                while (time.time() - start_time) < self.timeout:
                    try:
                        if exclusive:
                            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        else:
                            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                        lock_acquired = True
                        break
                    except IOError as e:
                        if e.errno not in (errno.EAGAIN, errno.EACCES):
                            raise
                        time.sleep(0.01)  # Small delay before retry
                
                if not lock_acquired:
                    raise TimeoutError(f"Could not acquire lock for {self.filepath} within {self.timeout} seconds")
                
                yield self._lock_file
                
            finally:
                # Release lock
                if self._lock_file:
                    try:
                        fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                        self._lock_file.close()
                    except Exception as e:
                        logger.warning(f"Error releasing lock for {self.filepath}: {e}")
                    finally:
                        self._lock_file = None
                
                # Clean up lock file if possible
                try:
                    if os.path.exists(self.lock_filepath):
                        os.remove(self.lock_filepath)
                except Exception:
                    pass  # Lock file might be in use by another process
    
    def load_pickle(self) -> Optional[Any]:
        """
        Load pickle file with shared lock (safe for concurrent reads)
        
        Returns:
            Loaded data or None if file doesn't exist
        """
        if not os.path.exists(self.filepath):
            return None
        
        try:
            with self.acquire_lock(exclusive=False):  # Shared lock for reading
                with open(self.filepath, 'rb') as f:
                    data = pickle.load(f)
                logger.debug(f"Successfully loaded pickle from {self.filepath}")
                return data
        except Exception as e:
            logger.error(f"Error loading pickle from {self.filepath}: {e}")
            raise
    
    def save_pickle(self, data: Any) -> bool:
        """
        Save pickle file with exclusive lock (prevents concurrent writes)
        
        Args:
            data: Data to pickle and save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create backup first
            backup_path = f"{self.filepath}.backup"
            if os.path.exists(self.filepath):
                try:
                    with open(self.filepath, 'rb') as src:
                        with open(backup_path, 'wb') as dst:
                            dst.write(src.read())
                except Exception as e:
                    logger.warning(f"Could not create backup: {e}")
            
            # Save with exclusive lock
            with self.acquire_lock(exclusive=True):  # Exclusive lock for writing
                temp_path = f"{self.filepath}.tmp"
                
                # Write to temporary file first
                with open(temp_path, 'wb') as f:
                    pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
                
                # Atomic rename (prevents partial writes)
                os.replace(temp_path, self.filepath)
                
            logger.debug(f"Successfully saved pickle to {self.filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving pickle to {self.filepath}: {e}")
            
            # Try to restore from backup
            if os.path.exists(backup_path):
                try:
                    os.replace(backup_path, self.filepath)
                    logger.info(f"Restored pickle from backup after save failure")
                except Exception as restore_error:
                    logger.error(f"Could not restore from backup: {restore_error}")
            
            return False
    
    def update_pickle(self, update_func: callable) -> bool:
        """
        Atomically update pickle file
        
        Args:
            update_func: Function that takes current data and returns updated data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.acquire_lock(exclusive=True):
                # Load current data
                if os.path.exists(self.filepath):
                    with open(self.filepath, 'rb') as f:
                        current_data = pickle.load(f)
                else:
                    current_data = {}
                
                # Apply update
                updated_data = update_func(current_data)
                
                # Save updated data
                temp_path = f"{self.filepath}.tmp"
                with open(temp_path, 'wb') as f:
                    pickle.dump(updated_data, f, protocol=pickle.HIGHEST_PROTOCOL)
                
                # Atomic rename
                os.replace(temp_path, self.filepath)
                
            logger.debug(f"Successfully updated pickle at {self.filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating pickle at {self.filepath}: {e}")
            return False


# Global instance for main pickle file
main_pickle_lock = PickleFileLock('bybit_bot_dashboard_v4.1_enhanced.pkl')


def safe_load_pickle(filepath: str = 'bybit_bot_dashboard_v4.1_enhanced.pkl') -> Optional[Any]:
    """
    Safely load pickle file with locking
    
    Args:
        filepath: Path to pickle file
        
    Returns:
        Loaded data or None
    """
    lock = PickleFileLock(filepath)
    return lock.load_pickle()


def safe_save_pickle(data: Any, filepath: str = 'bybit_bot_dashboard_v4.1_enhanced.pkl') -> bool:
    """
    Safely save pickle file with locking
    
    Args:
        data: Data to save
        filepath: Path to pickle file
        
    Returns:
        True if successful
    """
    lock = PickleFileLock(filepath)
    return lock.save_pickle(data)


def safe_update_pickle(update_func: callable, filepath: str = 'bybit_bot_dashboard_v4.1_enhanced.pkl') -> bool:
    """
    Safely update pickle file with locking
    
    Args:
        update_func: Function to update data
        filepath: Path to pickle file
        
    Returns:
        True if successful
    """
    lock = PickleFileLock(filepath)
    return lock.update_pickle(update_func)