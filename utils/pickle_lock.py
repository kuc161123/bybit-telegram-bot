#!/usr/bin/env python3
"""
Pickle File Locking Utility
==========================

This module provides thread-safe and process-safe pickle file operations
to prevent corruption during concurrent access.
"""

import pickle
import fcntl
import os
import time
import tempfile
import shutil
import logging
from typing import Any, Dict, Optional
from contextlib import contextmanager

# Backup frequency limiter
LAST_BACKUP_TIME = {}  # Track last backup per file
BACKUP_INTERVAL = 900  # Minimum seconds between backups (15 minutes)


logger = logging.getLogger(__name__)

class PickleFileLock:
    """Thread-safe and process-safe pickle file operations"""

    def __init__(self, filepath: str, timeout: float = 5.0):
        """
        Initialize pickle file lock

        Args:
            filepath: Path to the pickle file
            timeout: Maximum time to wait for lock acquisition
        """
        self.filepath = filepath
        self.timeout = timeout
        self.lock_filepath = f"{filepath}.lock"

    @contextmanager
    def acquire_lock(self):
        """Acquire exclusive lock on the pickle file"""
        lock_file = None
        start_time = time.time()

        try:
            # Try to acquire lock with timeout
            while True:
                try:
                    lock_file = open(self.lock_filepath, 'w')
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except IOError:
                    if time.time() - start_time > self.timeout:
                        raise TimeoutError(f"Failed to acquire lock on {self.filepath} after {self.timeout}s")
                    time.sleep(0.1)

            yield

        finally:
            if lock_file:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    lock_file.close()
                    os.remove(self.lock_filepath)
                except Exception as e:
                    logger.warning(f"Error releasing lock: {e}")

    def safe_load(self) -> Dict[str, Any]:
        """
        Safely load pickle file with lock and error recovery

        Returns:
            Loaded data or empty dict if file doesn't exist or is corrupted
        """
        with self.acquire_lock():
            try:
                if not os.path.exists(self.filepath):
                    logger.warning(f"Pickle file {self.filepath} not found, returning empty dict")
                    return {}

                with open(self.filepath, 'rb') as f:
                    data = pickle.load(f)
                return data

            except (EOFError, pickle.UnpicklingError) as e:
                logger.error(f"Corrupted pickle file {self.filepath}: {e}")

                # Try to recover from backup
                backup_path = f"{self.filepath}.backup"
                if os.path.exists(backup_path):
                    logger.info(f"Attempting recovery from backup {backup_path}")
                    try:
                        with open(backup_path, 'rb') as f:
                            data = pickle.load(f)

                        # Restore backup to main file
                        shutil.copy2(backup_path, self.filepath)
                        logger.info("Successfully recovered from backup")
                        return data

                    except Exception as backup_error:
                        logger.error(f"Backup recovery failed: {backup_error}")

                # Return empty dict if all recovery attempts fail
                return {}

            except Exception as e:
                logger.error(f"Error loading pickle file: {e}")
                return {}

    def safe_save(self, data: Dict[str, Any]) -> bool:
        """
        Safely save data to pickle file with atomic write

        Args:
            data: Data to save

        Returns:
            True if successful, False otherwise
        """
        with self.acquire_lock():
            try:
                # Create backup of existing file (respecting backup interval)
                if os.path.exists(self.filepath):
                    current_time = time.time()
                    
                    # Check if we should create a backup
                    if self.filepath not in LAST_BACKUP_TIME or \
                       current_time - LAST_BACKUP_TIME[self.filepath] >= BACKUP_INTERVAL:
                        backup_path = f"{self.filepath}.backup"
                        shutil.copy2(self.filepath, backup_path)
                        LAST_BACKUP_TIME[self.filepath] = current_time
                        logger.debug(f"Created backup: {backup_path}")

                # Write to temporary file first
                temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(self.filepath))
                try:
                    with os.fdopen(temp_fd, 'wb') as f:
                        pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

                    # Verify the temp file can be loaded
                    with open(temp_path, 'rb') as f:
                        pickle.load(f)

                    # Atomic rename
                    os.replace(temp_path, self.filepath)
                    return True

                except Exception as e:
                    logger.error(f"Error during safe save: {e}")
                    # Clean up temp file
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    return False

            except Exception as e:
                logger.error(f"Error saving pickle file: {e}")
                return False

    def update_data(self, update_func) -> bool:
        """
        Safely update pickle data with a function

        Args:
            update_func: Function that takes data dict and modifies it

        Returns:
            True if successful, False otherwise
        """
        try:
            # Load current data
            data = self.safe_load()

            # Apply updates
            update_func(data)

            # Save updated data
            return self.safe_save(data)

        except Exception as e:
            logger.error(f"Error updating pickle data: {e}")
            return False

# Global instance for the main pickle file
main_pickle_lock = PickleFileLock('bybit_bot_dashboard_v4.1_enhanced.pkl')