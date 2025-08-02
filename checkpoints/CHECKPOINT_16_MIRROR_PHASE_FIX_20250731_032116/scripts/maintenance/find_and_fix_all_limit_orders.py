#!/usr/bin/env python3
"""
Find and fix ALL limit orders
"""

import asyncio
import logging
import time
from decimal import Decimal
from pybit.unified_trading import HTTP
from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET,
    ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
)
from utils.pickle_lock import main_pickle_lock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_and_fix_all_limit_orders():
    """Find and register all limit orders"""
    try:
        # Load monitors
        data = main_pickle_lock.safe_load()
        if not data or 'bot_data' not in data:
            logger.error("No data found")
            return
        
        monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
        logger.info(f"Found {len(monitors)} monitors")
        
        # Show all monitors first
        logger.info("\n=== CURRENT MONITORS ===")
        for key, monitor in monitors.items():
            symbol = monitor.get('symbol')
            side = monitor.get('side')
            approach = monitor.get('approach')
            account = monitor.get('account_type', 'main')
            size = monitor.get('position_size', 0)
            logger.info(f"{symbol} {side} ({account}) - {approach} - Size: {size}")
        
        updates_made = False
        
        # Check MAIN account
        logger.info("\n=== CHECKING MAIN ACCOUNT ORDERS ===")
        main_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY,
            api_secret=BYBIT_API_SECRET
        )
        
        # Get open orders
        try:
            response = main_client.get_open_orders(category="linear", settleCoin="USDT")
            if response['retCode'] == 0:
                orders = response['result']['list']
                logger.info(f"Total orders on main: {len(orders)}")
                
                # Find limit entry orders
                for order in orders:
                    if order['orderType'] == 'Limit' and not order.get('reduceOnly', False):
                        symbol = order['symbol']
                        side = order['side']
                        order_id = order['orderId']
                        price = order['price']
                        qty = order['qty']
                        
                        logger.info(f"\nFound limit order: {symbol} {side} - {qty} @ {price}")
                        logger.info(f"  Order ID: {order_id}")
                        
                        # Find matching monitor
                        found_monitor = None
                        for monitor_key, monitor in monitors.items():
                            if (monitor.get('symbol') == symbol and 
                                monitor.get('side') == side and
                                monitor.get('account_type', 'main') == 'main'):
                                found_monitor = (monitor_key, monitor)
                                break
                        
                        if found_monitor:
                            monitor_key, monitor = found_monitor
                            logger.info(f"  Found monitor: {monitor_key}")
                            
                            # Check if already tracked
                            limit_orders = monitor.get('limit_orders', [])
                            tracked_ids = []
                            for lo in limit_orders:
                                if isinstance(lo, dict):
                                    tracked_ids.append(lo.get('order_id'))
                                else:
                                    tracked_ids.append(lo)
                            
                            if order_id not in tracked_ids:
                                # Add it
                                if 'limit_orders' not in monitor:
                                    monitor['limit_orders'] = []
                                
                                monitor['limit_orders'].append({
                                    'order_id': order_id,
                                    'status': 'ACTIVE',
                                    'registered_at': time.time()
                                })
                                updates_made = True
                                logger.info(f"  ✅ Added to tracking")
                            else:
                                logger.info(f"  Already tracked")
                        else:
                            logger.warning(f"  ⚠️ No monitor found for this position!")
        except Exception as e:
            logger.error(f"Error checking main orders: {e}")
        
        # Check MIRROR account
        if ENABLE_MIRROR_TRADING:
            logger.info("\n=== CHECKING MIRROR ACCOUNT ORDERS ===")
            mirror_client = HTTP(
                testnet=USE_TESTNET,
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2
            )
            
            try:
                response = mirror_client.get_open_orders(category="linear", settleCoin="USDT")
                if response['retCode'] == 0:
                    orders = response['result']['list']
                    logger.info(f"Total orders on mirror: {len(orders)}")
                    
                    # Find limit entry orders
                    for order in orders:
                        if order['orderType'] == 'Limit' and not order.get('reduceOnly', False):
                            symbol = order['symbol']
                            side = order['side']
                            order_id = order['orderId']
                            price = order['price']
                            qty = order['qty']
                            
                            logger.info(f"\nFound limit order: {symbol} {side} - {qty} @ {price}")
                            logger.info(f"  Order ID: {order_id}")
                            
                            # Find matching monitor
                            found_monitor = None
                            for monitor_key, monitor in monitors.items():
                                if (monitor.get('symbol') == symbol and 
                                    monitor.get('side') == side):
                                    # Check if it's a mirror monitor
                                    if (monitor.get('account_type') == 'mirror' or
                                        'mirror' in monitor_key.lower() or
                                        monitor_key == f"{symbol}_{side}"):  # Generic key might be mirror
                                        found_monitor = (monitor_key, monitor)
                                        break
                            
                            if found_monitor:
                                monitor_key, monitor = found_monitor
                                logger.info(f"  Found monitor: {monitor_key}")
                                
                                # Check if already tracked
                                limit_orders = monitor.get('limit_orders', [])
                                tracked_ids = []
                                for lo in limit_orders:
                                    if isinstance(lo, dict):
                                        tracked_ids.append(lo.get('order_id'))
                                    else:
                                        tracked_ids.append(lo)
                                
                                if order_id not in tracked_ids:
                                    # Add it
                                    if 'limit_orders' not in monitor:
                                        monitor['limit_orders'] = []
                                    
                                    monitor['limit_orders'].append({
                                        'order_id': order_id,
                                        'status': 'ACTIVE',
                                        'registered_at': time.time()
                                    })
                                    updates_made = True
                                    logger.info(f"  ✅ Added to tracking")
                                else:
                                    logger.info(f"  Already tracked")
                            else:
                                logger.warning(f"  ⚠️ No monitor found for this position!")
            except Exception as e:
                logger.error(f"Error checking mirror orders: {e}")
        
        # Save if updates made
        if updates_made:
            success = main_pickle_lock.safe_save(data)
            if success:
                logger.info("\n✅ Successfully saved all limit order updates")
            else:
                logger.error("\n❌ Failed to save updates")
        
        # Final summary
        logger.info("\n=== FINAL SUMMARY ===")
        conservative_count = 0
        total_limit_orders = 0
        
        for monitor_key, monitor in monitors.items():
            if monitor.get('approach') == 'conservative':
                conservative_count += 1
                limit_orders = monitor.get('limit_orders', [])
                if limit_orders:
                    total_limit_orders += len(limit_orders)
                    symbol = monitor.get('symbol')
                    side = monitor.get('side')
                    account = monitor.get('account_type', 'main')
                    logger.info(f"{symbol} {side} ({account}): {len(limit_orders)} limit orders")
        
        logger.info(f"\nTotal: {conservative_count} conservative positions, {total_limit_orders} limit orders tracked")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    find_and_fix_all_limit_orders()