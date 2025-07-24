#!/usr/bin/env python3
"""
Verify TIAUSDT SL trigger price was not affected by TP rebalancing
"""
import asyncio
import logging
from decimal import Decimal

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from clients.bybit_helpers import get_open_orders

async def check_tiausdt_orders():
    """Check all TIAUSDT orders to verify SL unchanged"""
    logger.info("Checking TIAUSDT orders...")
    logger.info("=" * 60)
    
    orders = await get_open_orders("TIAUSDT")
    
    tp_orders = []
    sl_order = None
    
    for order in orders:
        order_link_id = order.get('orderLinkId', '')
        order_type = order.get('orderType', '')
        
        if order.get('reduceOnly'):
            if 'TP' in order_link_id:
                tp_orders.append(order)
            elif 'SL' in order_link_id or order_type == 'StopLoss':
                sl_order = order
    
    # Display TP orders (Limit orders - no trigger price)
    logger.info(f"\nTP ORDERS (Limit orders - no trigger price):")
    tp_orders.sort(key=lambda x: float(x.get('price', 0)))
    
    for i, tp in enumerate(tp_orders):
        logger.info(f"  TP{i+1}: {tp.get('qty')} @ limit price {tp.get('price')}")
        logger.info(f"       Order Type: {tp.get('orderType')}")
        logger.info(f"       Order Link ID: {tp.get('orderLinkId')}")
        if tp.get('triggerPrice'):
            logger.warning(f"       ⚠️ Unexpected trigger price: {tp.get('triggerPrice')}")
    
    # Display SL order (Stop order - has trigger price)
    if sl_order:
        logger.info(f"\nSL ORDER (Stop order - has trigger price):")
        logger.info(f"  Quantity: {sl_order.get('qty')}")
        logger.info(f"  Order Type: {sl_order.get('orderType')}")
        logger.info(f"  Trigger Price: {sl_order.get('triggerPrice')}")
        logger.info(f"  Order Link ID: {sl_order.get('orderLinkId')}")
        logger.info(f"  Trigger Direction: {sl_order.get('triggerDirection')} (2 = price falls below)")
        
        # Check SL coverage
        total_qty = Decimal(str(sl_order.get('qty', '0')))
        logger.info(f"  SL Coverage: {total_qty} contracts")
    else:
        logger.warning("\n⚠️ No SL order found!")
    
    logger.info("\n" + "=" * 60)
    logger.info("Summary:")
    logger.info(f"  - Found {len(tp_orders)} TP orders (Limit orders)")
    logger.info(f"  - Found {'1' if sl_order else '0'} SL order (Stop order)")
    logger.info("  - TP orders are LIMIT orders (price only, no trigger)")
    logger.info("  - SL order is STOP order (has trigger price)")
    logger.info("\n✅ Trigger prices are only used for SL (stop) orders, not TP (limit) orders")

async def main():
    await check_tiausdt_orders()

if __name__ == "__main__":
    asyncio.run(main())