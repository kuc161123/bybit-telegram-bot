#!/usr/bin/env python3
"""
Check for conditional stop loss orders (StopLimit/StopMarket)
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

async def check_conditional_orders(client, symbol, side, account_name):
    """Check conditional orders for a position"""
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
            logger.warning(f"No position found for {symbol} {side}")
            return
            
        avg_price = float(position['avgPrice'])
        size = float(position['size'])
        
        # Get ALL orders including conditional
        response = await asyncio.to_thread(
            client.get_open_orders,
            category="linear",
            symbol=symbol,
            orderFilter="StopOrder"  # This gets conditional orders
        )
        
        if response['retCode'] != 0:
            logger.error(f"Failed to get orders: {response.get('retMsg', '')}")
            return
        
        conditional_orders = response['result']['list']
        
        # Also get regular orders
        regular_response = await asyncio.to_thread(
            client.get_open_orders,
            category="linear",
            symbol=symbol,
            orderFilter="Order"  # Regular orders
        )
        
        regular_orders = []
        if regular_response['retCode'] == 0:
            regular_orders = regular_response['result']['list']
        
        # Analyze orders
        sl_orders = []
        tp_orders = []
        
        # Check conditional orders
        for order in conditional_orders:
            if order.get('reduceOnly'):
                trigger_price = float(order.get('triggerPrice', 0))
                order_type = order.get('orderType', '')
                
                # Identify SL orders
                if 'Stop' in order_type:
                    if side == 'Buy' and order['side'] == 'Sell' and trigger_price < avg_price:
                        sl_orders.append(order)
                    elif side == 'Sell' and order['side'] == 'Buy' and trigger_price > avg_price:
                        sl_orders.append(order)
        
        # Count regular TP orders
        for order in regular_orders:
            if order.get('reduceOnly'):
                order_price = float(order.get('price', 0))
                if side == 'Buy' and order['side'] == 'Sell' and order_price > avg_price:
                    tp_orders.append(order)
                elif side == 'Sell' and order['side'] == 'Buy' and order_price < avg_price:
                    tp_orders.append(order)
        
        # Display results
        status = "✅" if sl_orders else "❌"
        logger.info(f"\n{status} {symbol} {side} ({account_name})")
        logger.info(f"   Position: {size} @ ${avg_price}")
        logger.info(f"   Regular TP Orders: {len(tp_orders)}")
        logger.info(f"   Conditional SL Orders: {len(sl_orders)}")
        
        if sl_orders:
            logger.info(f"\n   🛡️ Stop Loss Details:")
            for sl in sl_orders:
                logger.info(f"      Type: {sl.get('orderType')}")
                logger.info(f"      Qty: {sl.get('qty')}")
                logger.info(f"      Trigger: ${sl.get('triggerPrice')}")
                logger.info(f"      Order Price: ${sl.get('price', 'Market')}")
                logger.info(f"      Trigger Direction: {sl.get('triggerDirection')}")
                logger.info(f"      OrderId: {sl.get('orderId')[:8]}...")
        else:
            logger.warning(f"   ⚠️ NO STOP LOSS ORDERS FOUND!")
            
        # Check order totals
        logger.info(f"\n   📊 Order Summary:")
        logger.info(f"      Total Orders (All types): {len(conditional_orders) + len(regular_orders)}")
        logger.info(f"      Conditional Orders: {len(conditional_orders)}")
        logger.info(f"      Regular Orders: {len(regular_orders)}")
            
    except Exception as e:
        logger.error(f"Error checking {symbol}: {e}")

async def main():
    """Check all positions for conditional SL orders"""
    logger.info("🔍 CHECKING CONDITIONAL STOP LOSS ORDERS")
    logger.info("="*60)
    
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
    logger.info("="*60)
    sl_count = 0
    for symbol, side in positions_main:
        await check_conditional_orders(bybit_client, symbol, side, "Main")
        await asyncio.sleep(0.5)  # Rate limiting
    
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
    logger.info("="*60)
    for symbol, side in positions_mirror:
        await check_conditional_orders(mirror_client, symbol, side, "Mirror")
        await asyncio.sleep(0.5)  # Rate limiting

if __name__ == "__main__":
    asyncio.run(main())