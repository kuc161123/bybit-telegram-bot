#!/usr/bin/env python3
"""
Clean up duplicate orders for JUPUSDT
"""

import asyncio
from clients.bybit_helpers import get_all_open_orders, cancel_order_with_retry
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    logger.info("🧹 Cleaning up JUPUSDT duplicate orders...")
    
    # Get all orders
    orders = await get_all_open_orders()
    
    # Find JUPUSDT orders
    jup_orders = [o for o in orders if o.get('symbol') == 'JUPUSDT']
    
    # Separate by type
    tp_orders = []
    sl_orders = []
    
    for order in jup_orders:
        link_id = order.get('orderLinkId', '')
        if 'TP' in link_id and order.get('reduceOnly'):
            tp_orders.append(order)
        elif 'SL' in link_id and order.get('reduceOnly'):
            sl_orders.append(order)
    
    logger.info(f"Found {len(tp_orders)} TP orders and {len(sl_orders)} SL orders")
    
    # Sort orders by creation time (keep newest)
    tp_orders.sort(key=lambda x: x.get('createdTime', 0), reverse=True)
    sl_orders.sort(key=lambda x: x.get('createdTime', 0), reverse=True)
    
    # Keep only 4 newest TPs
    if len(tp_orders) > 4:
        logger.info(f"⚠️ Cancelling {len(tp_orders) - 4} duplicate TP orders...")
        for order in tp_orders[4:]:
            order_id = order.get('orderId')
            result = await cancel_order_with_retry('JUPUSDT', order_id)
            if result:
                logger.info(f"✅ Cancelled duplicate TP: {order_id[:8]}...")
    
    # Keep only 1 newest SL
    if len(sl_orders) > 1:
        logger.info(f"⚠️ Cancelling {len(sl_orders) - 1} duplicate SL orders...")
        for order in sl_orders[1:]:
            order_id = order.get('orderId')
            result = await cancel_order_with_retry('JUPUSDT', order_id)
            if result:
                logger.info(f"✅ Cancelled duplicate SL: {order_id[:8]}...")
    
    logger.info("✅ JUPUSDT cleanup complete!")

if __name__ == "__main__":
    asyncio.run(main())