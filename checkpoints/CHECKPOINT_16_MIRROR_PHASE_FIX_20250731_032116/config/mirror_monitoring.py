#!/usr/bin/env python3
"""
Mirror monitoring configuration
Ensures mirror monitors are loaded and monitored
"""

# Force enable mirror monitoring for enhanced TP/SL
ENABLE_MIRROR_MONITORING = True
MONITOR_BOTH_ACCOUNTS = True

# Export configuration
__all__ = ['ENABLE_MIRROR_MONITORING', 'MONITOR_BOTH_ACCOUNTS']
