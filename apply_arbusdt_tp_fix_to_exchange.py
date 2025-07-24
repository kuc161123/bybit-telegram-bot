#!/usr/bin/env python3
"""
Manually apply ARBUSDT TP adjustments to Bybit exchange.
This script cancels existing TP orders and places new ones with correct quantities.
"""

import asyncio
import logging
from decimal import Decimal
from datetime import datetime
import time

from clients.bybit_client import bybit_client
from clients.bybit_helpers import (
    cancel_order_with_retry, place_order_with_retry, 
    get_open_orders, get_instrument_info
)
from utils.helpers import value_adjusted_to_step
from config.settings import BYBIT_API_KEY_2, BYBIT_API_SECRET_2

# Import mirror client if available
try:
    from pybit.unified_trading import HTTP
    bybit_client_2 = HTTP(
        testnet=False,
        api_key=BYBIT_API_KEY_2,
        api_secret=BYBIT_API_SECRET_2
    )
except:
    bybit_client_2 = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SYMBOL = "ARBUSDT"

async def fix_arbusdt_tps():
    """Fix ARBUSDT TP orders for both accounts."""
    
    logger.info("Starting ARBUSDT TP fix on exchange...")
    
    # Define correct TP quantities
    main_tps = {
        'TP1': {'qty': Decimal('1799.96'), 'price': Decimal('0.4404')},
        'TP2': {'qty': Decimal('105.88'), 'price': Decimal('0.4609')},
        'TP3': {'qty': Decimal('105.88'), 'price': Decimal('0.4815')},
        'TP4': {'qty': Decimal('105.88'), 'price': Decimal('0.5432')}
    }
    
    mirror_tps = {
        'TP1': {'qty': Decimal('594.49'), 'price': Decimal('0.4404')},
        'TP2': {'qty': Decimal('34.97'), 'price': Decimal('0.4609')},
        'TP3': {'qty': Decimal('34.97'), 'price': Decimal('0.4815')},
        'TP4': {'qty': Decimal('34.97'), 'price': Decimal('0.5432')}
    }
    
    # Get instrument info
    instrument = await get_instrument_info(SYMBOL)
    if not instrument:
        logger.error("Failed to get instrument info")
        return
    
    qty_step = Decimal(instrument['lotSizeFilter']['qtyStep'])
    
    # Process main account
    logger.info("\n=== Processing Main Account ===")
    await process_account(bybit_client, main_tps, qty_step, "main")
    
    # Process mirror account
    if bybit_client_2:
        logger.info("\n=== Processing Mirror Account ===")
        await process_account(bybit_client_2, mirror_tps, qty_step, "mirror")
    
    logger.info("\n✅ TP fix complete!")

async def process_account(client, tp_config, qty_step, account_name):
    """Process TP orders for one account."""
    
    # Get current open orders
    try:
        orders_response = client.get_open_orders(
            category="linear",
            symbol=SYMBOL,
            orderFilter="Order"
        )
        
        if orders_response['retCode'] != 0:
            logger.error(f"Failed to get orders: {orders_response['retMsg']}")
            return
            
        orders = orders_response['result']['list']
        logger.info(f"Found {len(orders)} open orders")
        
    except Exception as e:
        logger.error(f"Error getting orders: {e}")
        return
    
    # Find and cancel existing TP orders
    tp_orders_to_cancel = []
    for order in orders:
        order_link_id = order.get('orderLinkId', '')
        if any(tp in order_link_id for tp in ['_TP1_', '_TP2_', '_TP3_', '_TP4_']):
            tp_orders_to_cancel.append(order)
    
    logger.info(f"Found {len(tp_orders_to_cancel)} TP orders to cancel")
    
    # Cancel existing TP orders
    for order in tp_orders_to_cancel:
        try:
            logger.info(f"Cancelling order {order['orderId']} ({order['orderLinkId']})")
            response = client.cancel_order(
                category="linear",
                symbol=SYMBOL,
                orderId=order['orderId']
            )
            if response['retCode'] == 0:
                logger.info(f"✅ Cancelled {order['orderLinkId']}")
            else:
                logger.error(f"Failed to cancel: {response['retMsg']}")
            
            # Small delay between cancellations
            await asyncio.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
    
    # Wait a bit for cancellations to process
    await asyncio.sleep(2)
    
    # Place new TP orders
    logger.info("\nPlacing new TP orders...")
    
    for tp_name, tp_data in tp_config.items():
        try:
            # Adjust quantity to step size
            qty = value_adjusted_to_step(tp_data['qty'], qty_step)
            
            # Generate order link ID
            tp_num = tp_name[-1]  # Get TP number
            timestamp = int(time.time() * 1000)
            order_link_id = f"BOT_ARBUSDT_TP{tp_num}_FIX_{timestamp}"
            
            logger.info(f"Placing {tp_name}: {qty} @ {tp_data['price']}")
            
            response = client.place_order(
                category="linear",
                symbol=SYMBOL,
                side="Sell",  # TP for long position
                orderType="Limit",
                qty=str(qty),
                price=str(tp_data['price']),
                orderLinkId=order_link_id,
                reduceOnly=True,
                positionIdx=0  # One-way mode
            )
            
            if response['retCode'] == 0:
                logger.info(f"✅ Placed {tp_name}: {qty} @ {tp_data['price']}")
            else:
                logger.error(f"Failed to place {tp_name}: {response['retMsg']}")
            
            # Delay between orders
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Error placing {tp_name}: {e}")
    
    logger.info(f"\n✅ Completed {account_name} account")

async def main():
    """Main function."""
    await fix_arbusdt_tps()

if __name__ == "__main__":
    asyncio.run(main())