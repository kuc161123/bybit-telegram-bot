#!/usr/bin/env python3
"""
Patch to ensure mirror monitors are loaded in enhanced TP/SL manager
"""
import logging

logger = logging.getLogger(__name__)

def should_include_mirror_monitors():
    """Check if mirror monitors should be included"""
    # Always include mirror monitors if they exist in pickle
    return True

def get_all_monitor_keys(monitors_dict):
    """Get all monitor keys including mirror"""
    all_keys = []
    for key, monitor in monitors_dict.items():
        all_keys.append(key)
        logger.debug(f"Found monitor: {key} (account: {monitor.get('account_type', 'unknown')})")
    return all_keys

# Export functions
__all__ = ['should_include_mirror_monitors', 'get_all_monitor_keys']
