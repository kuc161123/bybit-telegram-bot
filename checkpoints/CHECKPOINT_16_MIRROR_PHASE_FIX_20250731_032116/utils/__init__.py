"""Utilities package for the trading bot."""

from .formatters import *
from .cache import *
from .helpers import *

# Global backup frequency limiter
import time
import os

_BACKUP_TIMES = {}
_BACKUP_INTERVAL = 300  # 5 minutes

def should_create_backup(filepath: str) -> bool:
    """Check if enough time has passed to create a backup"""
    global _BACKUP_TIMES, _BACKUP_INTERVAL
    current_time = time.time()
    
    if filepath in _BACKUP_TIMES:
        if current_time - _BACKUP_TIMES[filepath] < _BACKUP_INTERVAL:
            return False
    
    _BACKUP_TIMES[filepath] = current_time
    return True

def create_backup_if_needed(filepath: str) -> str:
    """Create backup only if enough time has passed"""
    if should_create_backup(filepath):
        import shutil
        backup_path = f"{filepath}.backup_{int(time.time())}"
        shutil.copy(filepath, backup_path)
        return backup_path
    return None
