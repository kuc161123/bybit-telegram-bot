#!/usr/bin/env python3
"""Check JTOUSDT position and orders to diagnose the issue"""
import asyncio
import logging
from clients.bybit_helpers import get_all_positions, get_all_open_orders
from utils.order_identifier import group_orders_by_type

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_jtousdt():
    """Check JTOUSDT position and orders"""
    try:
        # Get all positions and orders
        positions = await get_all_positions()
        orders = await get_all_open_orders()
        
        # Find JTOUSDT position
        jto_position = None
        for pos in positions:
            if pos['symbol'] == 'JTOUSDT' and float(pos.get('size', 0)) > 0:
                jto_position = pos
                logger.info("=== JTOUSDT Position ===")
                logger.info(f"Side: {pos['side']}")
                logger.info(f"Size: {pos['size']}")
                logger.info(f"Entry Price: {pos.get('avgPrice')}")
                logger.info(f"Mark Price: {pos.get('markPrice')}")
                logger.info("")
                break
        
        if not jto_position:
            logger.warning("No active JTOUSDT position found")
            return
        
        # Find JTOUSDT orders
        jto_orders = [o for o in orders if o['symbol'] == 'JTOUSDT']
        
        logger.info(f"=== JTOUSDT Orders ({len(jto_orders)} total) ===")
        
        # Group orders using order identifier
        grouped = group_orders_by_type(jto_orders, jto_position)
        
        logger.info(f"\nTP Orders: {len(grouped['tp_orders'])}")
        for i, order in enumerate(grouped['tp_orders']):
            logger.info(f"  TP{i+1}: qty={order['qty']}, price={order['price']}, linkId={order.get('orderLinkId', '')}")
        
        logger.info(f"\nSL Orders: {len(grouped['sl_orders'])}")
        for order in grouped['sl_orders']:
            logger.info(f"  SL: qty={order['qty']}, trigger={order['triggerPrice']}, linkId={order.get('orderLinkId', '')}")
        
        logger.info(f"\nLimit Orders: {len(grouped['limit_orders'])}")
        for order in grouped['limit_orders']:
            logger.info(f"  Limit: qty={order['qty']}, price={order['price']}, linkId={order.get('orderLinkId', '')}")
        
        logger.info(f"\nUnknown Orders: {len(grouped['unknown_orders'])}")
        for order in grouped['unknown_orders']:
            logger.info(f"  Unknown: qty={order['qty']}, type={order.get('orderType')}, linkId={order.get('orderLinkId', '')}")
        
        # Check for multiple approaches
        tp_count = len(grouped['tp_orders'])
        if tp_count == 1:
            logger.info("\n✅ Appears to be Fast approach (1 TP)")
        elif tp_count == 4:
            logger.info("\n✅ Appears to be Conservative approach (4 TPs)")
        elif tp_count == 5:
            logger.warning("\n⚠️  ISSUE: Found 5 TP orders - likely mixed approaches!")
            logger.info("This could happen if both Fast and Conservative trades were created")
        else:
            logger.warning(f"\n⚠️  Unexpected TP count: {tp_count}")
            
    except Exception as e:
        logger.error(f"Error checking JTOUSDT: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(check_jtousdt())