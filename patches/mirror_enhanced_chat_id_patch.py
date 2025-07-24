#!/usr/bin/env python3
"""
Patch for mirror_enhanced_tp_sl.py to ensure chat_id is always set
"""

from config.settings import DEFAULT_ALERT_CHAT_ID

def ensure_mirror_chat_id(monitor_data):
    """Ensure monitor data has valid chat_id"""
    if 'chat_id' not in monitor_data or not monitor_data['chat_id']:
        monitor_data['chat_id'] = DEFAULT_ALERT_CHAT_ID or 5634913742
    return monitor_data
