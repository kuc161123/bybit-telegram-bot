#!/usr/bin/env python3
"""
Check open orders for positions with missing limit order tracking
"""

import asyncio
import logging
from pybit.unified_trading import HTTP
from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET,
    ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_open_orders():
    """Check open orders for both accounts"""
    try:
        # Check mirror account since we have CAKEUSDT positions there
        if ENABLE_MIRROR_TRADING:
            mirror_client = HTTP(
                testnet=USE_TESTNET,
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2
            )
            
            logger.info("Checking mirror account orders...")
            
            # Get all open orders
            response = mirror_client.get_open_orders(category="linear", settleCoin="USDT")
            
            if response['retCode'] == 0:
                orders = response['result']['list']
                logger.info(f"Total open orders on mirror account: {len(orders)}")
                
                # Filter for CAKEUSDT
                cake_orders = [o for o in orders if o['symbol'] == 'CAKEUSDT']
                logger.info(f"CAKEUSDT open orders: {len(cake_orders)}")
                
                # Show details of CAKEUSDT orders
                for order in cake_orders:
                    logger.info(f"\nOrder Details:")
                    logger.info(f"  - Order ID: {order['orderId']}")
                    logger.info(f"  - Type: {order['orderType']}")
                    logger.info(f"  - Side: {order['side']}")
                    logger.info(f"  - Price: {order['price']}")
                    logger.info(f"  - Qty: {order['qty']}")
                    logger.info(f"  - Reduce Only: {order.get('reduceOnly', False)}")
                    logger.info(f"  - Status: {order['orderStatus']}")
                    logger.info(f"  - Order Link ID: {order.get('orderLinkId', 'N/A')}")
                    
                    # Check if it's an entry limit order
                    if (order['orderType'] == 'Limit' and 
                        order['side'] == 'Buy' and 
                        not order.get('reduceOnly', False)):
                        logger.info("  ✅ This is an ENTRY LIMIT ORDER that should be tracked!")
            else:
                logger.error(f"Failed to get orders: {response}")
                
        # Also check main account
        main_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY,
            api_secret=BYBIT_API_SECRET
        )
        
        logger.info("\nChecking main account orders...")
        response = main_client.get_open_orders(category="linear", settleCoin="USDT")
        
        if response['retCode'] == 0:
            orders = response['result']['list']
            logger.info(f"Total open orders on main account: {len(orders)}")
            
            # Show limit entry orders
            limit_entries = [o for o in orders if o['orderType'] == 'Limit' and not o.get('reduceOnly', False)]
            logger.info(f"Limit entry orders: {len(limit_entries)}")
            
            for order in limit_entries:
                logger.info(f"  - {order['symbol']} {order['side']}: {order['orderId'][:8]}...")
                
    except Exception as e:
        logger.error(f"Error checking orders: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_open_orders())