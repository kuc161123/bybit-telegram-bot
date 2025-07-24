#!/usr/bin/env python3
"""
Patch for enhanced_tp_sl_manager.py to ensure all monitors have account suffix
Apply this patch to ensure future monitors are created with proper keys
"""

# Patch for create_position_monitor method
def patched_create_position_monitor(self, symbol: str, side: str, position_size: str,
                                   entry_price: str, tp_prices: list, sl_price: str,
                                   tp_percentages: list = None, position_idx: int = 0,
                                   chat_id: int = None, approach: str = "CONSERVATIVE",
                                   account_type: str = "main", **kwargs):
    """
    Create monitoring entry for a position with TP/SL orders
    PATCHED: Ensures monitor key includes account suffix
    """
    try:
        # Ensure account_type is valid
        if account_type not in ['main', 'mirror']:
            account_type = 'main'
        
        # Create monitor key with account suffix
        monitor_key = f"{symbol}_{side}_{account_type}"
        
        # ... rest of the original method ...
        # The key change is using monitor_key with suffix throughout
        
        logger.info(f"Creating monitor with key: {monitor_key}")
        
        # Continue with original implementation but use monitor_key
        
    except Exception as e:
        logger.error(f"Error creating position monitor: {e}")
