#!/usr/bin/env python3
"""
Fix mirror account TP order sequencing
Problem: Several positions have TP orders in wrong sequence (85% is on TP4 instead of TP1)
Targets: XRPUSDT, IDUSDT, JUPUSDT, ICPUSDT, LDOUSDT
"""

import asyncio
import logging
from decimal import Decimal, ROUND_DOWN
from execution.mirror_trader import bybit_client_2 as mirror_client
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Positions to fix (including LDOUSDT which needs 4th TP added)
POSITIONS_TO_FIX = [
    {'symbol': 'XRPUSDT', 'side': 'Buy', 'issue': 'wrong_order'},
    {'symbol': 'IDUSDT', 'side': 'Sell', 'issue': 'wrong_order'},
    {'symbol': 'JUPUSDT', 'side': 'Sell', 'issue': 'wrong_order'},
    {'symbol': 'ICPUSDT', 'side': 'Sell', 'issue': 'wrong_order'},
    {'symbol': 'LDOUSDT', 'side': 'Sell', 'issue': 'missing_tp4'}
]

# Target ratios
TP_RATIOS = [0.85, 0.05, 0.05, 0.05]  # 85%, 5%, 5%, 5%

async def get_position_info(mirror_client, symbol: str, side: str):
    """Get current position information"""
    try:
        response = await asyncio.to_thread(
            mirror_client.get_positions,
            category="linear",
            symbol=symbol
        )
        
        if response['retCode'] == 0:
            for pos in response['result']['list']:
                if pos['symbol'] == symbol and pos['side'] == side and float(pos['size']) > 0:
                    return pos
        return None
    except Exception as e:
        logger.error(f"Error getting position for {symbol}: {e}")
        return None

async def get_instrument_info(mirror_client, symbol: str):
    """Get instrument info for precision"""
    try:
        response = await asyncio.to_thread(
            mirror_client.get_instruments_info,
            category="linear",
            symbol=symbol
        )
        
        if response['retCode'] == 0 and response['result']['list']:
            return response['result']['list'][0]
        return None
    except Exception as e:
        logger.error(f"Error getting instrument info for {symbol}: {e}")
        return None

async def get_existing_tp_orders(mirror_client, symbol: str, side: str, avg_price: Decimal):
    """Get existing TP orders and their details"""
    try:
        response = await asyncio.to_thread(
            mirror_client.get_open_orders,
            category="linear",
            symbol=symbol
        )
        
        if response['retCode'] != 0:
            return []
        
        tp_orders = []
        orders = response['result']['list']
        
        for order in orders:
            # Check if it's a TP order
            if (order.get('reduceOnly') and 
                ((side == 'Buy' and order['side'] == 'Sell' and Decimal(order['price']) > avg_price) or 
                 (side == 'Sell' and order['side'] == 'Buy' and Decimal(order['price']) < avg_price))):
                
                tp_orders.append({
                    'orderId': order['orderId'],
                    'qty': Decimal(order['qty']),
                    'price': Decimal(order['price']),
                    'side': order['side']
                })
        
        # Sort by price (ascending for Buy positions, descending for Sell)
        tp_orders.sort(key=lambda x: x['price'], reverse=(side == 'Sell'))
        
        return tp_orders
        
    except Exception as e:
        logger.error(f"Error getting TP orders: {e}")
        return []

def reorder_quantities_for_85_5_5_5(tp_orders: list, position_size: Decimal) -> list:
    """Reorder quantities to match 85/5/5/5 pattern"""
    if len(tp_orders) < 4:
        logger.warning(f"Only {len(tp_orders)} TP orders found, expected 4")
    
    # Find the order with ~85% of position
    target_85_qty = position_size * Decimal('0.85')
    
    # Find which order has the 85% quantity
    large_order_idx = None
    for i, order in enumerate(tp_orders):
        qty_pct = order['qty'] / position_size
        if qty_pct > Decimal('0.8'):  # Order with >80% is likely the 85% order
            large_order_idx = i
            break
    
    if large_order_idx is None:
        logger.warning("Could not identify the 85% order")
        return tp_orders
    
    # Reorder: put the 85% order first
    reordered = []
    
    # Add the 85% order first
    reordered.append(tp_orders[large_order_idx])
    
    # Add the remaining orders
    for i, order in enumerate(tp_orders):
        if i != large_order_idx:
            reordered.append(order)
    
    return reordered

async def cancel_all_tp_orders(mirror_client, symbol: str, tp_orders: list):
    """Cancel all existing TP orders"""
    cancelled_count = 0
    
    for order in tp_orders:
        try:
            response = await asyncio.to_thread(
                mirror_client.cancel_order,
                category="linear",
                symbol=symbol,
                orderId=order['orderId']
            )
            
            if response['retCode'] == 0:
                cancelled_count += 1
                logger.info(f"✅ Cancelled order: {order['orderId']}")
            else:
                logger.error(f"Failed to cancel order: {response.get('retMsg', '')}")
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
    
    return cancelled_count

async def place_reordered_tp_orders(mirror_client, symbol: str, side: str, position: dict, 
                                   reordered_orders: list, qty_step: Decimal):
    """Place TP orders in correct sequence"""
    placed_count = 0
    position_idx = int(position.get('positionIdx', 0))
    position_size = Decimal(position['size'])
    
    # Calculate proper quantities based on 85/5/5/5
    quantities = []
    for i, ratio in enumerate(TP_RATIOS):
        qty = position_size * Decimal(str(ratio))
        qty = (qty / qty_step).quantize(Decimal('1'), rounding=ROUND_DOWN) * qty_step
        quantities.append(qty)
    
    # Adjust last quantity for full coverage
    total_qty = sum(quantities)
    if total_qty < position_size:
        quantities[-1] += (position_size - total_qty)
    
    # Place orders with correct quantities
    for i, (qty, order) in enumerate(zip(quantities, reordered_orders)):
        if i >= len(reordered_orders):
            break
        
        # Skip if price is 0 or invalid
        if order['price'] <= 0:
            logger.warning(f"Skipping order with invalid price: {order['price']}")
            continue
            
        order_params = {
            'category': 'linear',
            'symbol': symbol,
            'side': order['side'],
            'orderType': 'Limit',
            'qty': str(qty),
            'price': str(order['price']),
            'reduceOnly': True,
            'timeInForce': 'GTC',
            'positionIdx': position_idx,
            'orderLinkId': f"Mirror_TP{i+1}_{symbol}_{int(time.time()*1000)}"
        }
        
        try:
            response = await asyncio.to_thread(
                mirror_client.place_order,
                **order_params
            )
            
            if response['retCode'] == 0:
                placed_count += 1
                pct = (qty / position_size * 100)
                logger.info(f"✅ Placed TP{i+1}: {qty} ({pct:.2f}%) @ {order['price']}")
            else:
                logger.error(f"Failed to place TP{i+1}: {response.get('retMsg', '')}")
        except Exception as e:
            logger.error(f"Error placing order: {e}")
    
    return placed_count

async def add_missing_tp4(mirror_client, symbol: str, side: str, position: dict, 
                         existing_orders: list, instrument: dict):
    """Add missing 4th TP order for LDOUSDT"""
    position_size = Decimal(position['size'])
    avg_price = Decimal(position['avgPrice'])
    tick_size = Decimal(instrument['priceFilter']['tickSize'])
    qty_step = Decimal(instrument['lotSizeFilter']['qtyStep'])
    
    # Calculate TP4 price (5% from entry)
    if side == 'Buy':
        tp4_price = avg_price * Decimal('1.05')
    else:
        tp4_price = avg_price * Decimal('0.95')
    
    tp4_price = (tp4_price / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size
    
    # Calculate TP4 quantity (5% of position)
    tp4_qty = position_size * Decimal('0.05')
    tp4_qty = (tp4_qty / qty_step).quantize(Decimal('1'), rounding=ROUND_DOWN) * qty_step
    
    # Place TP4 order
    order_params = {
        'category': 'linear',
        'symbol': symbol,
        'side': 'Buy' if side == 'Sell' else 'Sell',
        'orderType': 'Limit',
        'qty': str(tp4_qty),
        'price': str(tp4_price),
        'reduceOnly': True,
        'timeInForce': 'GTC',
        'positionIdx': int(position.get('positionIdx', 0)),
        'orderLinkId': f"Mirror_TP4_{symbol}_{int(time.time()*1000)}"
    }
    
    try:
        response = await asyncio.to_thread(
            mirror_client.place_order,
            **order_params
        )
        
        if response['retCode'] == 0:
            logger.info(f"✅ Added missing TP4: {tp4_qty} @ {tp4_price}")
            return True
        else:
            logger.error(f"Failed to add TP4: {response.get('retMsg', '')}")
            return False
    except Exception as e:
        logger.error(f"Error adding TP4: {e}")
        return False

async def fix_position_tp_sequencing(mirror_client, symbol: str, side: str, issue: str):
    """Fix TP sequencing for a single position"""
    logger.info(f"\n{'='*60}")
    logger.info(f"🔧 Fixing {symbol} {side} position (Issue: {issue})")
    logger.info(f"{'='*60}")
    
    # Get position info
    position = await get_position_info(mirror_client, symbol, side)
    if not position:
        logger.error(f"❌ No position found for {symbol} {side}")
        return False
    
    position_size = Decimal(position['size'])
    avg_price = Decimal(position['avgPrice'])
    logger.info(f"📊 Position: {position_size} @ {avg_price}")
    
    # Get instrument info
    instrument = await get_instrument_info(mirror_client, symbol)
    if not instrument:
        logger.error(f"❌ Failed to get instrument info")
        return False
    
    qty_step = Decimal(instrument['lotSizeFilter']['qtyStep'])
    
    # Get existing TP orders
    tp_orders = await get_existing_tp_orders(mirror_client, symbol, side, avg_price)
    logger.info(f"📋 Found {len(tp_orders)} existing TP orders")
    
    # Show current order structure
    logger.info(f"\nCurrent TP structure:")
    for i, order in enumerate(tp_orders):
        pct = (order['qty'] / position_size * 100)
        logger.info(f"   TP{i+1}: {order['qty']} ({pct:.2f}%) @ {order['price']}")
    
    if issue == 'missing_tp4' and len(tp_orders) == 3:
        # Add missing TP4
        logger.info(f"\n➕ Adding missing TP4...")
        if await add_missing_tp4(mirror_client, symbol, side, position, tp_orders, instrument):
            # Re-fetch orders after adding TP4
            tp_orders = await get_existing_tp_orders(mirror_client, symbol, side, avg_price)
        else:
            logger.error("❌ Failed to add TP4")
            return False
    
    # Cancel all existing orders
    logger.info(f"\n🗑️ Cancelling all TP orders...")
    cancelled = await cancel_all_tp_orders(mirror_client, symbol, tp_orders)
    logger.info(f"Cancelled {cancelled} orders")
    
    # Wait for cancellations to process
    await asyncio.sleep(1)
    
    # Reorder based on quantities
    reordered = reorder_quantities_for_85_5_5_5(tp_orders, position_size)
    
    # Place orders in correct sequence
    logger.info(f"\n📝 Placing TP orders in correct sequence...")
    placed = await place_reordered_tp_orders(mirror_client, symbol, side, position, 
                                           reordered, qty_step)
    
    if placed >= min(4, len(reordered)):
        logger.info(f"✅ Successfully fixed TP sequencing for {symbol}")
        return True
    else:
        logger.error(f"❌ Only placed {placed}/{len(reordered)} orders")
        return False

async def main():
    """Main execution"""
    logger.info("🚀 Starting TP sequencing fix for mirror account positions")
    
    # Check if mirror client is available
    if not mirror_client:
        logger.error("❌ Mirror trading not enabled")
        return
    
    success_count = 0
    failed_positions = []
    
    for position in POSITIONS_TO_FIX:
        if await fix_position_tp_sequencing(mirror_client, position['symbol'], 
                                          position['side'], position['issue']):
            success_count += 1
        else:
            failed_positions.append(f"{position['symbol']} {position['side']}")
        
        # Small delay between positions
        await asyncio.sleep(2)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"✅ Successfully fixed: {success_count}/{len(POSITIONS_TO_FIX)} positions")
    
    if failed_positions:
        logger.error(f"❌ Failed positions: {', '.join(failed_positions)}")
    else:
        logger.info(f"🎉 All positions fixed successfully!")
    
    logger.info(f"\n💡 Next steps:")
    logger.info(f"   1. Verify TP orders in Bybit UI")
    logger.info(f"   2. Check that quantities follow 85/5/5/5 pattern")
    logger.info(f"   3. Ensure monitors are tracking correctly")

if __name__ == "__main__":
    asyncio.run(main())