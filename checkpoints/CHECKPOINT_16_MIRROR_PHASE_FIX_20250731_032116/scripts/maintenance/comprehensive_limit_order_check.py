#!/usr/bin/env python3
"""
Comprehensive Limit Order Check
===============================

This script checks ALL orders on both accounts and identifies which ones should be tracked.
"""

import asyncio
import logging
from pybit.unified_trading import HTTP
from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET,
    ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
)
from utils.pickle_lock import main_pickle_lock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def comprehensive_limit_order_check():
    """Check all orders comprehensively"""
    try:
        # Load current monitors
        data = main_pickle_lock.safe_load()
        monitors = {}
        if data and 'bot_data' in data:
            monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
        
        logger.info("=" * 80)
        logger.info("COMPREHENSIVE LIMIT ORDER CHECK")
        logger.info("=" * 80)
        
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
            logger.info(f"Total open orders: {len(orders)}")
            
            # Categorize orders
            limit_entry_orders = []
            tp_orders = []
            sl_orders = []
            other_orders = []
            
            for order in orders:
                order_type = order['orderType']
                reduce_only = order.get('reduceOnly', False)
                side = order['side']
                symbol = order['symbol']
                
                if order_type == 'Limit' and not reduce_only:
                    limit_entry_orders.append(order)
                elif reduce_only and side != order.get('positionSide', side):  # TP order
                    tp_orders.append(order)
                elif reduce_only and side == order.get('positionSide', side):  # SL order
                    sl_orders.append(order)
                else:
                    other_orders.append(order)
            
            # Show limit entry orders
            if limit_entry_orders:
                logger.info(f"\n📥 LIMIT ENTRY ORDERS (should be tracked): {len(limit_entry_orders)}")
                for order in limit_entry_orders:
                    logger.info(f"  - {order['symbol']} {order['side']}")
                    logger.info(f"    Order ID: {order['orderId']}")
                    logger.info(f"    Price: {order['price']}, Qty: {order['qty']}")
                    logger.info(f"    Status: {order['orderStatus']}")
                    
                    # Check if it's tracked
                    position_key = f"{order['symbol']}_{order['side']}"
                    tracked = False
                    for monitor_key, monitor in monitors.items():
                        if (monitor.get('symbol') == order['symbol'] and 
                            monitor.get('side') == order['side'] and
                            monitor.get('account_type', 'main') == 'main'):
                            limit_orders = monitor.get('limit_orders', [])
                            order_ids = [o.get('order_id') if isinstance(o, dict) else o for o in limit_orders]
                            if order['orderId'] in order_ids:
                                tracked = True
                                break
                    
                    logger.info(f"    Tracked: {'✅ YES' if tracked else '❌ NO'}")
            
            # Show TP/SL orders
            logger.info(f"\n🎯 TP ORDERS: {len(tp_orders)}")
            logger.info(f"🛡️ SL ORDERS: {len(sl_orders)}")
            logger.info(f"❓ OTHER ORDERS: {len(other_orders)}")
        
        # Check MIRROR account
        if ENABLE_MIRROR_TRADING:
            logger.info("\n\n=== MIRROR ACCOUNT ===")
            mirror_client = HTTP(
                testnet=USE_TESTNET,
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2
            )
            
            response = mirror_client.get_open_orders(category="linear", settleCoin="USDT")
            if response['retCode'] == 0:
                orders = response['result']['list']
                logger.info(f"Total open orders: {len(orders)}")
                
                # Categorize orders
                limit_entry_orders = []
                tp_orders = []
                sl_orders = []
                other_orders = []
                
                for order in orders:
                    order_type = order['orderType']
                    reduce_only = order.get('reduceOnly', False)
                    side = order['side']
                    symbol = order['symbol']
                    
                    if order_type == 'Limit' and not reduce_only:
                        limit_entry_orders.append(order)
                    elif reduce_only and side != order.get('positionSide', side):  # TP order
                        tp_orders.append(order)
                    elif reduce_only and side == order.get('positionSide', side):  # SL order
                        sl_orders.append(order)
                    else:
                        other_orders.append(order)
                
                # Show limit entry orders
                if limit_entry_orders:
                    logger.info(f"\n📥 LIMIT ENTRY ORDERS (should be tracked): {len(limit_entry_orders)}")
                    for order in limit_entry_orders:
                        logger.info(f"  - {order['symbol']} {order['side']}")
                        logger.info(f"    Order ID: {order['orderId']}")
                        logger.info(f"    Price: {order['price']}, Qty: {order['qty']}")
                        logger.info(f"    Status: {order['orderStatus']}")
                        
                        # Check if it's tracked
                        position_key = f"{order['symbol']}_{order['side']}"
                        tracked = False
                        for monitor_key, monitor in monitors.items():
                            if (monitor.get('symbol') == order['symbol'] and 
                                monitor.get('side') == order['side'] and
                                monitor.get('account_type', 'main') == 'mirror'):
                                limit_orders = monitor.get('limit_orders', [])
                                order_ids = [o.get('order_id') if isinstance(o, dict) else o for o in limit_orders]
                                if order['orderId'] in order_ids:
                                    tracked = True
                                    break
                        
                        logger.info(f"    Tracked: {'✅ YES' if tracked else '❌ NO'}")
                
                # Show TP/SL orders
                logger.info(f"\n🎯 TP ORDERS: {len(tp_orders)}")
                logger.info(f"🛡️ SL ORDERS: {len(sl_orders)}")
                logger.info(f"❓ OTHER ORDERS: {len(other_orders)}")
        
        # Show current monitors
        logger.info("\n\n=== CURRENT MONITORS ===")
        for monitor_key, monitor in monitors.items():
            symbol = monitor.get('symbol')
            side = monitor.get('side')
            approach = monitor.get('approach')
            account = monitor.get('account_type', 'main')
            limit_orders = monitor.get('limit_orders', [])
            
            logger.info(f"\n{symbol} {side} ({account}) - {approach}")
            if limit_orders:
                logger.info(f"  Tracking {len(limit_orders)} limit orders")
            else:
                logger.info(f"  No limit orders tracked")
        
    except Exception as e:
        logger.error(f"Error in comprehensive check: {e}")
        import traceback
        traceback.print_exc()

async def main():
    await comprehensive_limit_order_check()

if __name__ == "__main__":
    asyncio.run(main())