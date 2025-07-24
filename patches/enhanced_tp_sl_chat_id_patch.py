#!/usr/bin/env python3
"""
Patch for enhanced_tp_sl_manager.py to ensure chat_id is always set
"""

from config.settings import DEFAULT_ALERT_CHAT_ID

def ensure_chat_id(chat_id):
    """Ensure chat_id is valid, use default if not"""
    if not chat_id or chat_id is None:
        return DEFAULT_ALERT_CHAT_ID or 5634913742
    return chat_id

# Monkey patch for setup_enhanced_tp_sl
original_setup = None

def patched_setup_enhanced_tp_sl(self, symbol, side, position_size, entry_price, 
                                  tp_prices, sl_price, tp_percentages=None, 
                                  position_idx=0, chat_id=None, **kwargs):
    # Ensure chat_id is valid
    chat_id = ensure_chat_id(chat_id)
    
    # Call original with fixed chat_id
    return original_setup(self, symbol, side, position_size, entry_price, 
                         tp_prices, sl_price, tp_percentages, position_idx, 
                         chat_id, **kwargs)
