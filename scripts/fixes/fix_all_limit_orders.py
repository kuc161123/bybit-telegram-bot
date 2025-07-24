#!/usr/bin/env python3
"""
Fix ALL Limit Order Tracking Across Both Accounts
=================================================

This script finds and registers all untracked limit orders.
"""

import asyncio
import logging
import time
from pybit.unified_trading import HTTP
from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET,
    ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
)
from utils.pickle_lock import main_pickle_lock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_all_limit_orders():
    """Fix limit order tracking for ALL positions"""
    try:
        # Load current data
        data = main_pickle_lock.safe_load()
        if not data or 'bot_data' not in data:
            logger.error("No data loaded")
            return False
        
        monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
        updates_made = False
        
        # Check MAIN account
        logger.info("=== Checking MAIN Account ===")
        main_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY,
            api_secret=BYBIT_API_SECRET
        )
        
        response = main_client.get_open_orders(category="linear", settleCoin="USDT")
        if response['retCode'] == 0:
            orders = response['result']['list']
            logger.info(f"Total open orders on main account: {len(orders)}")
            
            # Group by symbol
            main_limit_orders = {}
            for order in orders:
                if (order['orderType'] == 'Limit' and 
                    not order.get('reduceOnly', False)):  # Entry orders only
                    symbol = order['symbol']
                    side = order['side']
                    key = f"{symbol}_{side}"
                    
                    if key not in main_limit_orders:
                        main_limit_orders[key] = []
                    
                    main_limit_orders[key].append(order['orderId'])
                    logger.info(f"Found limit order: {symbol} {side} - {order['orderId'][:8]}...")
            
            # Update monitors for main account
            for position_key, order_ids in main_limit_orders.items():
                monitor_key = f"{position_key}_main"
                
                # Also check without _main suffix for backward compatibility
                if monitor_key not in monitors and position_key in monitors:
                    monitor_key = position_key
                
                if monitor_key in monitors:
                    monitor = monitors[monitor_key]
                    if monitor.get('approach') == 'conservative':
                        current_orders = monitor.get('limit_orders', [])
                        
                        # Get existing order IDs
                        existing_ids = []
                        for o in current_orders:
                            if isinstance(o, dict):
                                existing_ids.append(o.get('order_id'))
                            else:
                                existing_ids.append(o)
                        
                        # Add new orders
                        for order_id in order_ids:
                            if order_id not in existing_ids:
                                if 'limit_orders' not in monitor:
                                    monitor['limit_orders'] = []
                                
                                monitor['limit_orders'].append({
                                    'order_id': order_id,
                                    'status': 'ACTIVE',
                                    'registered_at': time.time()
                                })
                                updates_made = True
                                logger.info(f"✅ Added {order_id[:8]}... to {monitor_key}")
        
        # Check MIRROR account
        if ENABLE_MIRROR_TRADING:
            logger.info("\n=== Checking MIRROR Account ===")
            mirror_client = HTTP(
                testnet=USE_TESTNET,
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2
            )
            
            response = mirror_client.get_open_orders(category="linear", settleCoin="USDT")
            if response['retCode'] == 0:
                orders = response['result']['list']
                logger.info(f"Total open orders on mirror account: {len(orders)}")
                
                # Group by symbol
                mirror_limit_orders = {}
                for order in orders:
                    if (order['orderType'] == 'Limit' and 
                        not order.get('reduceOnly', False)):  # Entry orders only
                        symbol = order['symbol']
                        side = order['side']
                        key = f"{symbol}_{side}"
                        
                        if key not in mirror_limit_orders:
                            mirror_limit_orders[key] = []
                        
                        mirror_limit_orders[key].append(order['orderId'])
                        logger.info(f"Found limit order: {symbol} {side} - {order['orderId'][:8]}...")
                
                # Update monitors for mirror account
                for position_key, order_ids in mirror_limit_orders.items():
                    # Check multiple possible monitor keys
                    possible_keys = [
                        f"{position_key}_mirror",
                        position_key,
                        f"{position_key.split('_')[0]}_{position_key.split('_')[1]}"  # Clean format
                    ]
                    
                    monitor_key = None
                    for key in possible_keys:
                        if key in monitors:
                            monitor_key = key
                            break
                    
                    if monitor_key:
                        monitor = monitors[monitor_key]
                        if monitor.get('approach') == 'conservative':
                            current_orders = monitor.get('limit_orders', [])
                            
                            # Get existing order IDs
                            existing_ids = []
                            for o in current_orders:
                                if isinstance(o, dict):
                                    existing_ids.append(o.get('order_id'))
                                else:
                                    existing_ids.append(o)
                            
                            # Add new orders
                            for order_id in order_ids:
                                if order_id not in existing_ids:
                                    if 'limit_orders' not in monitor:
                                        monitor['limit_orders'] = []
                                    
                                    monitor['limit_orders'].append({
                                        'order_id': order_id,
                                        'status': 'ACTIVE',
                                        'registered_at': time.time()
                                    })
                                    updates_made = True
                                    logger.info(f"✅ Added {order_id[:8]}... to {monitor_key}")
        
        # Save if updates were made
        if updates_made:
            success = main_pickle_lock.safe_save(data)
            if success:
                logger.info("\n✅ Successfully updated all monitors with limit orders")
            else:
                logger.error("\n❌ Failed to save updates")
                return False
        else:
            logger.info("\n✅ All limit orders were already tracked")
        
        # Show final summary
        logger.info("\n=== FINAL SUMMARY ===")
        total_monitors = 0
        total_limit_orders = 0
        
        for monitor_key, monitor in monitors.items():
            if monitor.get('approach') == 'conservative':
                limit_orders = monitor.get('limit_orders', [])
                if limit_orders:
                    total_monitors += 1
                    total_limit_orders += len(limit_orders)
                    logger.info(f"{monitor.get('symbol')} {monitor.get('side')} ({monitor.get('account_type', 'main')}): {len(limit_orders)} limit orders")
        
        logger.info(f"\nTotal: {total_monitors} positions tracking {total_limit_orders} limit orders")
        
        return True
        
    except Exception as e:
        logger.error(f"Error fixing limit orders: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    await fix_all_limit_orders()

if __name__ == "__main__":
    asyncio.run(main())