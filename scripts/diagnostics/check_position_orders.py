#!/usr/bin/env python3
"""
Check what orders exist for current positions
"""
import asyncio
import logging
from decimal import Decimal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_position_orders():
    """Check orders for each position"""
    try:
        from clients.bybit_helpers import get_all_positions, get_open_orders
        
        logger.info("🔍 Checking orders for all positions...")
        
        # Get positions
        positions = await get_all_positions()
        logger.info(f"\n📊 Found {len(positions)} positions:")
        
        for position in positions:
            symbol = position.get('symbol', '')
            side = position.get('side', '')
            size = Decimal(str(position.get('size', '0')))
            avg_price = Decimal(str(position.get('avgPrice', '0')))
            
            logger.info(f"\n{'='*50}")
            logger.info(f"📊 {symbol} {side}")
            logger.info(f"   Size: {size}")
            logger.info(f"   Entry: ${avg_price}")
        
        # Get all orders
        all_orders = await get_open_orders()
        logger.info(f"\n📋 Total open orders: {len(all_orders)}")
        
        # Group orders by symbol
        orders_by_symbol = {}
        for order in all_orders:
            symbol = order.get('symbol', '')
            if symbol not in orders_by_symbol:
                orders_by_symbol[symbol] = []
            orders_by_symbol[symbol].append(order)
        
        # Show orders for each position symbol
        position_symbols = {p.get('symbol') for p in positions}
        
        for symbol in position_symbols:
            orders = orders_by_symbol.get(symbol, [])
            logger.info(f"\n📋 Orders for {symbol}: {len(orders)}")
            
            for order in orders:
                order_type = order.get('orderType', '')
                side = order.get('side', '')
                qty = order.get('qty', '')
                price = order.get('price', '')
                trigger_price = order.get('triggerPrice', '')
                reduce_only = order.get('reduceOnly', False)
                order_status = order.get('orderStatus', '')
                order_link_id = order.get('orderLinkId', '')
                order_id = order.get('orderId', '')
                
                logger.info(f"\n   Order: {order_id[:8]}...")
                logger.info(f"   Type: {order_type}")
                logger.info(f"   Side: {side}")
                logger.info(f"   Qty: {qty}")
                logger.info(f"   Price: {price}")
                logger.info(f"   Trigger: {trigger_price}")
                logger.info(f"   Reduce Only: {reduce_only}")
                logger.info(f"   Status: {order_status}")
                logger.info(f"   Link ID: {order_link_id}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_position_orders())