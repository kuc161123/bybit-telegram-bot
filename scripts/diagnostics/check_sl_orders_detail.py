#!/usr/bin/env python3
"""
Check SL order details for all positions
"""

import asyncio
import logging
from decimal import Decimal
from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2 as mirror_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def check_position_sl_orders(client, symbol, side, account_name):
    """Check SL orders for a position"""
    try:
        # Get position
        pos_response = await asyncio.to_thread(
            client.get_positions,
            category="linear",
            symbol=symbol
        )
        
        position = None
        if pos_response['retCode'] == 0:
            for pos in pos_response['result']['list']:
                if pos['symbol'] == symbol and pos['side'] == side and float(pos['size']) > 0:
                    position = pos
                    break
        
        if not position:
            return
            
        avg_price = float(position['avgPrice'])
        size = float(position['size'])
        
        # Get orders
        response = await asyncio.to_thread(
            client.get_open_orders,
            category="linear",
            symbol=symbol
        )
        
        if response['retCode'] != 0:
            return
        
        sl_orders = []
        tp_orders = []
        
        for order in response['result']['list']:
            if order.get('reduceOnly'):
                order_price = float(order.get('price', 0))
                
                # Check if it's SL based on price relative to position
                if side == 'Buy':
                    # For long position, SL is below entry
                    if order['side'] == 'Sell' and (order_price < avg_price or order.get('orderType') in ['StopLimit', 'StopMarket']):
                        sl_orders.append(order)
                    elif order['side'] == 'Sell' and order_price > avg_price:
                        tp_orders.append(order)
                else:  # Sell/Short
                    # For short position, SL is above entry
                    if order['side'] == 'Buy' and (order_price > avg_price or order.get('orderType') in ['StopLimit', 'StopMarket']):
                        sl_orders.append(order)
                    elif order['side'] == 'Buy' and order_price < avg_price:
                        tp_orders.append(order)
        
        # Display results
        logger.info(f"\n{'='*50}")
        logger.info(f"📊 {symbol} {side} ({account_name})")
        logger.info(f"   Position: {size} @ ${avg_price}")
        logger.info(f"   TP Orders: {len(tp_orders)}")
        logger.info(f"   SL Orders: {len(sl_orders)}")
        
        if sl_orders:
            logger.info(f"\n   🛡️ Stop Loss Orders:")
            for sl in sl_orders:
                logger.info(f"      Type: {sl.get('orderType')}")
                logger.info(f"      Qty: {sl.get('qty')}")
                logger.info(f"      Price: {sl.get('price', 'N/A')}")
                logger.info(f"      Trigger: {sl.get('triggerPrice', 'N/A')}")
                logger.info(f"      OrderId: {sl.get('orderId')}")
        else:
            logger.warning(f"   ⚠️ NO STOP LOSS ORDERS FOUND!")
            
    except Exception as e:
        logger.error(f"Error checking {symbol}: {e}")

async def main():
    """Check all positions"""
    logger.info("🔍 CHECKING STOP LOSS ORDERS FOR ALL POSITIONS")
    
    # Check main account
    positions_main = [
        ('IDUSDT', 'Sell'),
        ('LDOUSDT', 'Sell'),
        ('ICPUSDT', 'Sell'),
        ('LINKUSDT', 'Buy'),
        ('XRPUSDT', 'Buy'),
        ('JUPUSDT', 'Sell'),
        ('DOGEUSDT', 'Buy'),
        ('TIAUSDT', 'Buy')
    ]
    
    logger.info("\n🏦 MAIN ACCOUNT:")
    for symbol, side in positions_main:
        await check_position_sl_orders(bybit_client, symbol, side, "Main")
    
    # Check mirror account
    positions_mirror = [
        ('IDUSDT', 'Sell'),
        ('LDOUSDT', 'Sell'),
        ('ICPUSDT', 'Sell'),
        ('LINKUSDT', 'Buy'),
        ('XRPUSDT', 'Buy'),
        ('JUPUSDT', 'Sell'),
        ('TIAUSDT', 'Buy')
    ]
    
    logger.info("\n\n🏦 MIRROR ACCOUNT:")
    for symbol, side in positions_mirror:
        await check_position_sl_orders(mirror_client, symbol, side, "Mirror")

if __name__ == "__main__":
    asyncio.run(main())