#!/usr/bin/env python3
"""
Check LDOUSDT position and TP order status on main account
"""

import asyncio
import logging
from decimal import Decimal
from clients.bybit_client import bybit_client
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def check_ldousdt_status():
    """Check LDOUSDT position and orders on main account"""
    
    symbol = 'LDOUSDT'
    
    logger.info(f"\n{'='*60}")
    logger.info(f"🔍 Checking {symbol} Status on Main Account")
    logger.info(f"{'='*60}")
    
    # Get position
    try:
        response = await asyncio.to_thread(
            bybit_client.get_positions,
            category="linear",
            symbol=symbol
        )
        
        position = None
        if response['retCode'] == 0:
            for pos in response['result']['list']:
                if pos['symbol'] == symbol and float(pos['size']) > 0:
                    position = pos
                    break
        
        if not position:
            logger.info(f"❌ No active position found for {symbol}")
            return
            
        # Display position info
        size = float(position['size'])
        side = position['side']
        avg_price = float(position['avgPrice'])
        unrealized_pnl = float(position.get('unrealisedPnl', 0))
        
        logger.info(f"\n📊 POSITION DETAILS:")
        logger.info(f"   Symbol: {symbol}")
        logger.info(f"   Side: {side}")
        logger.info(f"   Size: {size}")
        logger.info(f"   Avg Price: ${avg_price}")
        logger.info(f"   Unrealized PnL: ${unrealized_pnl:.2f}")
        
    except Exception as e:
        logger.error(f"Error getting position: {e}")
        return
    
    # Get orders
    try:
        response = await asyncio.to_thread(
            bybit_client.get_open_orders,
            category="linear",
            symbol=symbol
        )
        
        if response['retCode'] != 0:
            logger.error(f"Failed to get orders: {response.get('retMsg', '')}")
            return
            
        orders = response['result']['list']
        
        # Separate TP and limit orders
        tp_orders = []
        limit_orders = []
        sl_orders = []
        
        for order in orders:
            if order.get('reduceOnly'):
                # It's a TP or SL order
                order_price = float(order['price'])
                if side == 'Sell' and order['side'] == 'Buy':
                    if order_price < avg_price:
                        tp_orders.append(order)
                    else:
                        sl_orders.append(order)
                elif side == 'Buy' and order['side'] == 'Sell':
                    if order_price > avg_price:
                        tp_orders.append(order)
                    else:
                        sl_orders.append(order)
            else:
                # Entry order
                limit_orders.append(order)
        
        # Sort TP orders by price
        tp_orders.sort(key=lambda x: float(x['price']), reverse=(side == 'Sell'))
        
        # Display TP orders
        logger.info(f"\n📈 TAKE PROFIT ORDERS ({len(tp_orders)} found):")
        total_tp_qty = 0
        for i, order in enumerate(tp_orders):
            qty = float(order['qty'])
            price = float(order['price'])
            total_tp_qty += qty
            pct_of_position = (qty / size * 100) if size > 0 else 0
            price_diff_pct = ((avg_price - price) / avg_price * 100) if side == 'Sell' else ((price - avg_price) / avg_price * 100)
            
            logger.info(f"   TP{i+1}: {qty} ({pct_of_position:.1f}%) @ ${price} [{price_diff_pct:.2f}% from entry]")
            logger.info(f"        Order ID: {order['orderId']}")
            logger.info(f"        Status: {order.get('orderStatus', 'Unknown')}")
        
        logger.info(f"   Total TP Coverage: {total_tp_qty} ({(total_tp_qty/size*100):.1f}%)")
        
        # Display limit orders
        if limit_orders:
            logger.info(f"\n📝 LIMIT ENTRY ORDERS ({len(limit_orders)} found):")
            for order in limit_orders:
                qty = float(order['qty'])
                price = float(order['price'])
                logger.info(f"   {order['side']}: {qty} @ ${price}")
                logger.info(f"   Order ID: {order['orderId']}")
                logger.info(f"   Order Link ID: {order.get('orderLinkId', 'None')}")
                logger.info(f"   Status: {order.get('orderStatus', 'Unknown')}")
                logger.info(f"   Created: {order.get('createdTime', 'Unknown')}")
        else:
            logger.info(f"\n📝 LIMIT ENTRY ORDERS: None")
            
        # Check for TP1 completion
        logger.info(f"\n🎯 TP1 STATUS CHECK:")
        if len(tp_orders) < 4:
            logger.info(f"   ⚠️ Less than 4 TP orders found (expected 4)")
            logger.info(f"   🤔 TP1 might have been filled already")
            
            # Check total coverage
            if total_tp_qty < size * 0.5:
                logger.info(f"   ✅ TP coverage is ~{(total_tp_qty/size*100):.1f}% - suggests TP1 (85%) was likely filled")
                logger.info(f"   📊 Original position was likely ~{size / 0.15:.0f} units")
            else:
                logger.info(f"   🔍 TP coverage is {(total_tp_qty/size*100):.1f}% - need more analysis")
        else:
            logger.info(f"   ✅ All 4 TP orders present - TP1 has NOT been filled yet")
            
        # Check order history for fills
        logger.info(f"\n📜 CHECKING ORDER HISTORY:")
        history_response = await asyncio.to_thread(
            bybit_client.get_order_history,
            category="linear",
            symbol=symbol,
            limit=20
        )
        
        if history_response['retCode'] == 0:
            filled_tps = []
            for order in history_response['result']['list']:
                if (order.get('orderStatus') == 'Filled' and 
                    order.get('reduceOnly') and
                    'TP' in order.get('orderLinkId', '')):
                    filled_tps.append(order)
            
            if filled_tps:
                logger.info(f"   Found {len(filled_tps)} filled TP orders:")
                for order in filled_tps[:3]:  # Show last 3
                    qty = float(order['qty'])
                    price = float(order['price'])
                    update_time = order.get('updatedTime', '')
                    logger.info(f"   - {qty} @ ${price} - Filled at {update_time}")
        
    except Exception as e:
        logger.error(f"Error getting orders: {e}")

async def main():
    """Main execution"""
    await check_ldousdt_status()

if __name__ == "__main__":
    asyncio.run(main())