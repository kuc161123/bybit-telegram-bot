#!/usr/bin/env python3
"""
Show all untracked limit orders
"""

import logging
from pybit.unified_trading import HTTP
from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET,
    ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
)
from utils.pickle_lock import main_pickle_lock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def show_all_untracked_orders():
    """Show all limit orders that aren't tracked"""
    try:
        # Load monitors
        data = main_pickle_lock.safe_load()
        monitors = {}
        if data and 'bot_data' in data:
            monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
        
        # Get all tracked order IDs
        tracked_order_ids = set()
        for monitor in monitors.values():
            for lo in monitor.get('limit_orders', []):
                if isinstance(lo, dict):
                    tracked_order_ids.add(lo.get('order_id'))
                else:
                    tracked_order_ids.add(lo)
        
        logger.info(f"Currently tracking {len(tracked_order_ids)} limit orders")
        
        untracked_orders = []
        
        # Check MAIN account
        logger.info("\n=== MAIN ACCOUNT ===")
        main_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY,
            api_secret=BYBIT_API_SECRET
        )
        
        response = main_client.get_open_orders(category="linear", settleCoin="USDT")
        if response['retCode'] == 0:
            orders = response['result']['list']
            
            for order in orders:
                if order['orderType'] == 'Limit' and not order.get('reduceOnly', False):
                    if order['orderId'] not in tracked_order_ids:
                        untracked_orders.append(('main', order))
                        logger.info(f"\n❌ UNTRACKED: {order['symbol']} {order['side']}")
                        logger.info(f"   Order ID: {order['orderId']}")
                        logger.info(f"   Price: {order['price']}, Qty: {order['qty']}")
        
        # Check MIRROR account
        if ENABLE_MIRROR_TRADING:
            logger.info("\n=== MIRROR ACCOUNT ===")
            mirror_client = HTTP(
                testnet=USE_TESTNET,
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2
            )
            
            response = mirror_client.get_open_orders(category="linear", settleCoin="USDT")
            if response['retCode'] == 0:
                orders = response['result']['list']
                
                for order in orders:
                    if order['orderType'] == 'Limit' and not order.get('reduceOnly', False):
                        if order['orderId'] not in tracked_order_ids:
                            untracked_orders.append(('mirror', order))
                            logger.info(f"\n❌ UNTRACKED: {order['symbol']} {order['side']}")
                            logger.info(f"   Order ID: {order['orderId']}")
                            logger.info(f"   Price: {order['price']}, Qty: {order['qty']}")
        
        logger.info(f"\n\nTotal untracked limit orders: {len(untracked_orders)}")
        
        if untracked_orders:
            logger.info("\nThese orders need monitors to be created for proper tracking.")
            logger.info("This typically happens when:")
            logger.info("1. Orders were placed manually on the exchange")
            logger.info("2. The bot crashed after placing orders but before creating monitors")
            logger.info("3. Monitors were deleted but orders remain open")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    show_all_untracked_orders()