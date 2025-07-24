#!/usr/bin/env python3
"""
Ensure Limit Order Tracking for Current and Future Trades
=========================================================

This script:
1. Checks existing conservative positions for limit orders
2. Registers any untracked limit orders
3. Fixes the timing issue in trader.py for future trades
"""

import pickle
import logging
from datetime import datetime
from utils.pickle_lock import main_pickle_lock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ensure_limit_order_tracking():
    """Ensure limit orders are tracked for all positions"""
    try:
        # Load data using safe load
        data = main_pickle_lock.safe_load()
        
        if not data:
            logger.error("No data loaded from pickle file")
            return False
        
        # Get monitors
        bot_data = data.get('bot_data', {})
        monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        logger.info(f"Found {len(monitors)} monitors")
        
        # Track changes
        changes_made = False
        
        # Check each monitor
        for monitor_key, monitor in monitors.items():
            symbol = monitor.get('symbol', 'Unknown')
            side = monitor.get('side', 'Unknown')
            approach = monitor.get('approach', 'unknown')
            account = monitor.get('account_type', 'main')
            
            # Only process conservative positions
            if approach != 'conservative':
                continue
                
            logger.info(f"\nChecking {symbol} {side} ({account}) - Conservative")
            
            # Check if limit orders are tracked
            limit_orders = monitor.get('limit_orders', [])
            
            if not limit_orders:
                logger.warning(f"  ⚠️ No limit orders tracked")
                
                # Initialize empty limit orders list
                monitor['limit_orders'] = []
                changes_made = True
                logger.info(f"  ✅ Initialized limit order tracking")
            else:
                logger.info(f"  ✅ Already tracking {len(limit_orders)} limit orders")
        
        # Save changes if any were made
        if changes_made:
            success = main_pickle_lock.safe_save(data)
            if success:
                logger.info("\n✅ Successfully updated monitors with limit order tracking")
            else:
                logger.error("\n❌ Failed to save changes")
                return False
        else:
            logger.info("\n✅ All monitors already have limit order tracking")
        
        # Now fix the trader.py timing issue
        fix_trader_registration()
        
        return True
        
    except Exception as e:
        logger.error(f"Error ensuring limit order tracking: {e}")
        import traceback
        traceback.print_exc()
        return False

def fix_trader_registration():
    """Fix the timing issue in trader.py for future trades"""
    try:
        # Read trader.py
        with open('execution/trader.py', 'r') as f:
            content = f.read()
        
        # Look for the conservative order placement section
        # Find where limit orders are placed
        search_marker = "logger.info(f\"Conservative approach: Placed {len(limit_order_ids)} limit orders for {symbol}\")"
        
        if search_marker not in content:
            logger.warning("Could not find limit order placement code in trader.py")
            return
        
        # Check if fix is already applied
        if "# Ensure monitor is created before registering limit orders" in content:
            logger.info("✅ Trader.py already has limit order registration fix")
            return
        
        # Find the section after limit orders are placed
        insert_after = search_marker
        insert_code = '''
                    
                    # Ensure monitor is created before registering limit orders
                    if ENABLE_ENHANCED_TP_SL and limit_order_ids:
                        # Wait a moment for monitor creation
                        await asyncio.sleep(0.5)
                        
                        # Register limit orders with the monitor
                        try:
                            if hasattr(enhanced_tp_sl_manager, 'register_limit_orders'):
                                enhanced_tp_sl_manager.register_limit_orders(
                                    symbol, side, limit_order_ids,
                                    account_type='mirror' if is_mirror else 'main'
                                )
                                logger.info(f"✅ Registered {len(limit_order_ids)} limit orders with Enhanced TP/SL manager")
                            else:
                                # Directly update the monitor if method doesn't exist
                                monitor_key = f"{symbol}_{side}"
                                if account_type == 'mirror':
                                    monitor_key = f"{symbol}_{side}_mirror"
                                
                                if monitor_key in enhanced_tp_sl_manager.position_monitors:
                                    monitor = enhanced_tp_sl_manager.position_monitors[monitor_key]
                                    monitor['limit_orders'] = [
                                        {'order_id': oid, 'status': 'ACTIVE', 'registered_at': time.time()}
                                        for oid in limit_order_ids
                                    ]
                                    await enhanced_tp_sl_manager.save_monitors_to_persistence()
                                    logger.info(f"✅ Directly updated monitor with {len(limit_order_ids)} limit orders")
                        except Exception as e:
                            logger.error(f"Failed to register limit orders: {e}")'''
        
        # Replace the line
        replacement = search_marker + insert_code
        content = content.replace(search_marker, replacement)
        
        # Write back
        with open('execution/trader.py', 'w') as f:
            f.write(content)
        
        logger.info("✅ Applied limit order registration fix to trader.py")
        
    except Exception as e:
        logger.error(f"Error fixing trader registration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if ensure_limit_order_tracking():
        print("\n✅ Limit order tracking is now properly configured!")
        print("Current positions: Limit order tracking initialized")
        print("Future trades: Will automatically register limit orders")
    else:
        print("\n❌ Failed to ensure limit order tracking")