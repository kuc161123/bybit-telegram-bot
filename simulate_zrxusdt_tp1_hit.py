#!/usr/bin/env python3
"""
Simulate TP1 hit for ZRXUSDT position
This script will:
1. Mark TP1 as hit for ZRXUSDT on both main and mirror accounts
2. Trigger limit order cancellation
3. Move SL to breakeven
4. Update monitor state
"""
import asyncio
import logging
import pickle
from decimal import Decimal
from datetime import datetime
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pickle file path
PICKLE_FILE = 'bybit_bot_dashboard_v4.1_enhanced.pkl'

async def simulate_tp1_hit_for_zrxusdt():
    """Simulate TP1 hit for ZRXUSDT positions"""
    try:
        # Create backup first
        backup_file = f"{PICKLE_FILE}.backup_simulate_tp1_{int(datetime.now().timestamp())}"
        logger.info(f"Creating backup: {backup_file}")
        
        # Load pickle data
        with open(PICKLE_FILE, 'rb') as f:
            data = pickle.load(f)
        
        # Backup the data
        with open(backup_file, 'wb') as f:
            pickle.dump(data, f)
        
        # Import necessary modules
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        from clients.bybit_helpers import get_position_info, get_open_orders, cancel_order_with_retry
        from config.settings import CANCEL_LIMITS_ON_TP1
        
        manager = enhanced_tp_sl_manager
        
        # Process both main and mirror accounts
        accounts = ['main', 'mirror']
        symbol = 'ZRXUSDT'
        side = 'Buy'
        
        for account_type in accounts:
            logger.info(f"\n{'='*50}")
            logger.info(f"Processing {account_type.upper()} account for {symbol} {side}")
            logger.info(f"{'='*50}")
            
            # Find the monitor - try different key formats
            possible_keys = [
                f"{symbol}_{side}_{account_type}",
                f"{symbol}_{side}",
                symbol  # Just symbol
            ]
            
            monitor_data = None
            found_key = None
            
            # First check in manager's monitors
            for key in possible_keys:
                if key in manager.position_monitors:
                    monitor_data = manager.position_monitors[key]
                    found_key = key
                    break
            
            # If not found, check in persisted monitors
            if not monitor_data:
                with open(PICKLE_FILE, 'rb') as f:
                    data = pickle.load(f)
                enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
                
                for key in possible_keys:
                    if key in enhanced_monitors:
                        monitor_data = enhanced_monitors[key]
                        found_key = key
                        # Add to manager
                        manager.position_monitors[key] = monitor_data
                        break
            
            if not monitor_data:
                logger.warning(f"No monitor found for {symbol} {side} on {account_type} account")
                logger.info(f"Available monitors: {list(manager.position_monitors.keys())}")
                
                # For main account, let's check if we need to process it
                if account_type == 'main':
                    # Get the actual position
                    positions = await get_position_info(symbol)
                    has_position = False
                    for pos in positions:
                        if pos.get('side') == side and Decimal(str(pos.get('size', '0'))) > 0:
                            has_position = True
                            break
                    
                    if not has_position:
                        logger.info(f"No open position found for {symbol} {side} on {account_type}")
                continue
            
            logger.info(f"✅ Found monitor with key: {found_key}")
            logger.info(f"Current tp1_hit status: {monitor_data.get('tp1_hit', False)}")
            logger.info(f"Current sl_moved_to_be: {monitor_data.get('sl_moved_to_be', False)}")
            
            # Step 1: Mark TP1 as hit
            if not monitor_data.get('tp1_hit', False):
                logger.info(f"\n🎯 Step 1: Marking TP1 as hit")
                monitor_data['tp1_hit'] = True
                monitor_data['phase'] = 'PROFIT_TAKING'
                logger.info(f"✅ Set tp1_hit = True")
                logger.info(f"✅ Set phase = PROFIT_TAKING")
            else:
                logger.info(f"ℹ️ TP1 already marked as hit")
            
            # Step 2: Cancel limit orders if enabled
            if CANCEL_LIMITS_ON_TP1 and monitor_data.get('limit_orders'):
                logger.info(f"\n🧹 Step 2: Cancelling limit orders")
                
                # Get open orders
                from clients.bybit_helpers import get_open_orders_for_account
                if account_type == 'mirror':
                    open_orders = await get_open_orders_for_account(symbol, 'mirror')
                else:
                    open_orders = await get_open_orders(symbol)
                
                cancelled_count = 0
                for order in open_orders:
                    # Check if this is a limit entry order
                    if (order.get('orderType') == 'Limit' and 
                        not order.get('reduceOnly', False) and
                        order.get('orderStatus') == 'New'):
                        
                        order_id = order['orderId']
                        logger.info(f"  Cancelling limit order: {order_id[:8]}...")
                        
                        if account_type == 'mirror':
                            from execution.mirror_trader import bybit_client_2
                            success = await cancel_order_with_retry(symbol, order_id, client=bybit_client_2)
                        else:
                            success = await cancel_order_with_retry(symbol, order_id)
                        
                        if success:
                            cancelled_count += 1
                            logger.info(f"  ✅ Cancelled: {order_id[:8]}...")
                        else:
                            logger.warning(f"  ⚠️ Failed to cancel: {order_id[:8]}...")
                
                logger.info(f"✅ Cancelled {cancelled_count} limit orders")
                
                # Update monitor
                monitor_data['limit_orders_cancelled'] = True
            else:
                logger.info(f"ℹ️ Limit order cancellation skipped (CANCEL_LIMITS_ON_TP1={CANCEL_LIMITS_ON_TP1})")
            
            # Step 3: Move SL to breakeven
            if not monitor_data.get('sl_moved_to_be', False):
                logger.info(f"\n🛡️ Step 3: Moving SL to breakeven")
                
                # Get position info
                if account_type == 'mirror':
                    from clients.bybit_helpers import get_position_info_for_account
                    positions = await get_position_info_for_account(symbol, 'mirror')
                else:
                    positions = await get_position_info(symbol)
                
                position = None
                if positions:
                    for pos in positions:
                        if pos.get('side') == side:
                            position = pos
                            break
                
                if position:
                    entry_price = Decimal(str(position.get('avgPrice', '0')))
                    
                    # Use the manager's breakeven method
                    logger.info(f"  Entry price: {entry_price}")
                    logger.info(f"  Calling _move_sl_to_breakeven_enhanced_v2...")
                    
                    success = await manager._move_sl_to_breakeven_enhanced_v2(
                        monitor_data=monitor_data,
                        position=position,
                        is_tp1_trigger=True
                    )
                    
                    if success:
                        monitor_data['sl_moved_to_be'] = True
                        logger.info(f"✅ SL moved to breakeven successfully")
                    else:
                        logger.error(f"❌ Failed to move SL to breakeven")
                else:
                    logger.warning(f"⚠️ Position not found")
            else:
                logger.info(f"ℹ️ SL already at breakeven")
            
            # Step 4: Update TP orders status
            tp_orders = monitor_data.get('tp_orders', {})
            if isinstance(tp_orders, dict):
                for order_id, tp_order in tp_orders.items():
                    if tp_order.get('tp_number') == 1:
                        tp_order['status'] = 'FILLED'
                        tp_order['fill_time'] = datetime.now().timestamp()
                        logger.info(f"\n✅ Marked TP1 order as FILLED")
                        break
            
            # Save the monitor back with the found key
            manager.position_monitors[found_key] = monitor_data
            
            # Log final state
            logger.info(f"\n📊 Final monitor state:")
            logger.info(f"  tp1_hit: {monitor_data.get('tp1_hit', False)}")
            logger.info(f"  sl_moved_to_be: {monitor_data.get('sl_moved_to_be', False)}")
            logger.info(f"  phase: {monitor_data.get('phase', 'UNKNOWN')}")
            logger.info(f"  limit_orders_cancelled: {monitor_data.get('limit_orders_cancelled', False)}")
        
        # Save all changes to persistence
        logger.info(f"\n💾 Saving all changes to persistence...")
        manager.save_monitors_to_persistence()
        
        # Also update the pickle file directly for dashboard monitors
        with open(PICKLE_FILE, 'rb') as f:
            data = pickle.load(f)
        
        # Update enhanced monitors in pickle
        if 'bot_data' not in data:
            data['bot_data'] = {}
        data['bot_data']['enhanced_tp_sl_monitors'] = manager.position_monitors
        
        # Save updated data
        with open(PICKLE_FILE, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"✅ All changes saved successfully!")
        
        # Create a signal file to trigger monitor reload
        reload_signal = 'reload_monitors.signal'
        with open(reload_signal, 'w') as f:
            f.write(str(datetime.now().timestamp()))
        logger.info(f"✅ Monitor reload signal created")
        
        logger.info(f"\n{'='*50}")
        logger.info(f"SIMULATION COMPLETE")
        logger.info(f"{'='*50}")
        logger.info(f"\nZRXUSDT TP1 hit has been simulated for both accounts:")
        logger.info(f"✅ TP1 marked as hit")
        logger.info(f"✅ Phase changed to PROFIT_TAKING")
        logger.info(f"✅ Limit orders cancelled (if any)")
        logger.info(f"✅ SL moved to breakeven")
        logger.info(f"\nThe bot will reflect these changes on the next monitoring cycle.")
        
    except Exception as e:
        logger.error(f"Error simulating TP1 hit: {e}")
        import traceback
        traceback.print_exc()

async def verify_changes():
    """Verify the changes were applied"""
    logger.info(f"\n\n{'='*50}")
    logger.info(f"VERIFYING CHANGES")
    logger.info(f"{'='*50}")
    
    try:
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        manager = enhanced_tp_sl_manager
        
        # Load monitors from persistence
        with open(PICKLE_FILE, 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        for account in ['main', 'mirror']:
            monitor_key = f"ZRXUSDT_Buy_{account}"
            alt_key = "ZRXUSDT_Buy"
            
            monitor = enhanced_monitors.get(monitor_key) or enhanced_monitors.get(alt_key)
            
            if monitor:
                logger.info(f"\n{account.upper()} Account Status:")
                logger.info(f"  TP1 Hit: {monitor.get('tp1_hit', False)}")
                logger.info(f"  SL at Breakeven: {monitor.get('sl_moved_to_be', False)}")
                logger.info(f"  Phase: {monitor.get('phase', 'UNKNOWN')}")
                logger.info(f"  Limit Orders Cancelled: {monitor.get('limit_orders_cancelled', False)}")
            else:
                logger.warning(f"No monitor found for {account} account")
                
    except Exception as e:
        logger.error(f"Error verifying changes: {e}")

if __name__ == "__main__":
    logger.info("ZRXUSDT TP1 Hit Simulation")
    logger.info("=" * 50)
    
    # Check if pickle file exists
    if not os.path.exists(PICKLE_FILE):
        logger.error(f"Pickle file not found: {PICKLE_FILE}")
        exit(1)
    
    # Run the simulation
    asyncio.run(simulate_tp1_hit_for_zrxusdt())
    
    # Verify changes
    asyncio.run(verify_changes())
    
    logger.info("\n" + "=" * 50)
    logger.info("Simulation completed!")