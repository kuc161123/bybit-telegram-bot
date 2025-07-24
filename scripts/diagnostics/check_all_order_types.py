#!/usr/bin/env python3
"""
Check ALL order types for a sample position to debug
"""

import asyncio
import logging
from clients.bybit_client import bybit_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def check_all_orders_debug():
    """Debug check for all order types"""
    
    # Test with LDOUSDT Sell on main account
    symbol = 'LDOUSDT'
    
    logger.info(f"🔍 DEBUG: Checking ALL orders for {symbol}")
    logger.info("="*60)
    
    # Method 1: Get all open orders without filter
    try:
        logger.info("\n1️⃣ Method 1: All open orders (no filter)")
        response = await asyncio.to_thread(
            bybit_client.get_open_orders,
            category="linear",
            symbol=symbol
        )
        
        if response['retCode'] == 0:
            orders = response['result']['list']
            logger.info(f"   Found {len(orders)} orders")
            
            for i, order in enumerate(orders):
                logger.info(f"\n   Order {i+1}:")
                logger.info(f"      Type: {order.get('orderType')}")
                logger.info(f"      Side: {order.get('side')}")
                logger.info(f"      Qty: {order.get('qty')}")
                logger.info(f"      Price: {order.get('price', 'N/A')}")
                logger.info(f"      TriggerPrice: {order.get('triggerPrice', 'N/A')}")
                logger.info(f"      StopOrderType: {order.get('stopOrderType', 'N/A')}")
                logger.info(f"      ReduceOnly: {order.get('reduceOnly')}")
                logger.info(f"      OrderLinkId: {order.get('orderLinkId', 'N/A')}")
    except Exception as e:
        logger.error(f"Error in method 1: {e}")
    
    # Method 2: Get conditional orders specifically
    try:
        logger.info("\n2️⃣ Method 2: Conditional orders (StopOrder filter)")
        response = await asyncio.to_thread(
            bybit_client.get_open_orders,
            category="linear",
            symbol=symbol,
            orderFilter="StopOrder"
        )
        
        if response['retCode'] == 0:
            orders = response['result']['list']
            logger.info(f"   Found {len(orders)} conditional orders")
            
            for order in orders:
                if order.get('stopOrderType') or order.get('triggerPrice'):
                    logger.info(f"\n   Conditional Order:")
                    logger.info(f"      OrderId: {order.get('orderId')[:8]}...")
                    logger.info(f"      All fields: {list(order.keys())}")
    except Exception as e:
        logger.error(f"Error in method 2: {e}")
    
    # Method 3: Check position for stopLoss field
    try:
        logger.info("\n3️⃣ Method 3: Check position stopLoss field")
        response = await asyncio.to_thread(
            bybit_client.get_positions,
            category="linear",
            symbol=symbol
        )
        
        if response['retCode'] == 0:
            for pos in response['result']['list']:
                if pos['symbol'] == symbol and float(pos['size']) > 0:
                    logger.info(f"   Position found:")
                    logger.info(f"      StopLoss: {pos.get('stopLoss', 'N/A')}")
                    logger.info(f"      TakeProfit: {pos.get('takeProfit', 'N/A')}")
                    logger.info(f"      TpslMode: {pos.get('tpslMode', 'N/A')}")
    except Exception as e:
        logger.error(f"Error in method 3: {e}")

async def main():
    """Main execution"""
    await check_all_orders_debug()

if __name__ == "__main__":
    asyncio.run(main())