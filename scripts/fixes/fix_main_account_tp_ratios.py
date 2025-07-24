#!/usr/bin/env python3
"""
Fix main account positions with incorrect TP ratios
Targets: ICPUSDT, LDOUSDT, IDUSDT - all have ~50% coverage with 42.5/2.5/2.5/2.5 ratios
Goal: Update to proper 85/5/5/5 ratios with 100% coverage
"""

import asyncio
import logging
from decimal import Decimal, ROUND_DOWN
from clients.bybit_client import bybit_client
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Positions to fix
POSITIONS_TO_FIX = [
    {'symbol': 'ICPUSDT', 'side': 'Sell'},
    {'symbol': 'LDOUSDT', 'side': 'Sell'},
    {'symbol': 'IDUSDT', 'side': 'Sell'}
]

# Target ratios
TP_RATIOS = [0.85, 0.05, 0.05, 0.05]  # 85%, 5%, 5%, 5%

async def get_position_info(symbol: str, side: str):
    """Get current position information"""
    try:
        response = await asyncio.to_thread(
            bybit_client.get_positions,
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

async def get_instrument_info(symbol: str):
    """Get instrument info for precision"""
    try:
        response = await asyncio.to_thread(
            bybit_client.get_instruments_info,
            category="linear",
            symbol=symbol
        )
        
        if response['retCode'] == 0 and response['result']['list']:
            return response['result']['list'][0]
        return None
    except Exception as e:
        logger.error(f"Error getting instrument info for {symbol}: {e}")
        return None

def calculate_tp_quantities(position_size: Decimal, ratios: list, qty_step: Decimal) -> list:
    """Calculate TP quantities based on ratios"""
    quantities = []
    
    for ratio in ratios:
        qty = position_size * Decimal(str(ratio))
        # Round down to qty_step
        qty = (qty / qty_step).quantize(Decimal('1'), rounding=ROUND_DOWN) * qty_step
        quantities.append(qty)
    
    # Adjust last TP to ensure full coverage
    total_qty = sum(quantities)
    if total_qty < position_size:
        quantities[-1] += (position_size - total_qty)
    
    return quantities

def calculate_tp_prices(avg_price: Decimal, side: str, tick_size: Decimal) -> list:
    """Calculate TP prices for 4 levels"""
    tp_percentages = [0.01, 0.02, 0.03, 0.05]  # 1%, 2%, 3%, 5%
    tp_prices = []
    
    for pct in tp_percentages:
        if side == 'Buy':
            tp_price = avg_price * (Decimal('1') + Decimal(str(pct)))
        else:  # Sell
            tp_price = avg_price * (Decimal('1') - Decimal(str(pct)))
        
        # Round to tick size
        tp_price = (tp_price / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size
        tp_prices.append(tp_price)
    
    return tp_prices

async def cancel_existing_tp_orders(symbol: str, side: str):
    """Cancel all existing TP orders for a position"""
    try:
        # Get open orders
        response = await asyncio.to_thread(
            bybit_client.get_open_orders,
            category="linear",
            symbol=symbol
        )
        
        if response['retCode'] != 0:
            logger.error(f"Failed to get orders: {response.get('retMsg', '')}")
            return False
        
        cancelled_count = 0
        orders = response['result']['list']
        
        for order in orders:
            # Check if it's a TP order (reduceOnly and opposite side)
            if (order.get('reduceOnly') and 
                ((side == 'Buy' and order['side'] == 'Sell') or 
                 (side == 'Sell' and order['side'] == 'Buy'))):
                
                # Cancel the order
                cancel_resp = await asyncio.to_thread(
                    bybit_client.cancel_order,
                    category="linear",
                    symbol=symbol,
                    orderId=order['orderId']
                )
                
                if cancel_resp['retCode'] == 0:
                    cancelled_count += 1
                    logger.info(f"✅ Cancelled TP order: {order['orderId']}")
                else:
                    logger.error(f"Failed to cancel order: {cancel_resp.get('retMsg', '')}")
        
        logger.info(f"Cancelled {cancelled_count} TP orders for {symbol}")
        return True
        
    except Exception as e:
        logger.error(f"Error cancelling TP orders: {e}")
        return False

async def place_tp_orders(symbol: str, side: str, position: dict, quantities: list, tp_prices: list):
    """Place new TP orders with correct ratios"""
    try:
        placed_count = 0
        position_idx = int(position.get('positionIdx', 0))
        
        for i, (qty, price) in enumerate(zip(quantities, tp_prices)):
            if qty <= 0:
                continue
                
            order_params = {
                'category': 'linear',
                'symbol': symbol,
                'side': 'Sell' if side == 'Buy' else 'Buy',
                'orderType': 'Limit',
                'qty': str(qty),
                'price': str(price),
                'reduceOnly': True,
                'timeInForce': 'GTC',
                'positionIdx': position_idx,
                'orderLinkId': f"Main_TP{i+1}_{symbol}_{int(time.time()*1000)}"
            }
            
            response = await asyncio.to_thread(
                bybit_client.place_order,
                **order_params
            )
            
            if response['retCode'] == 0:
                placed_count += 1
                logger.info(f"✅ Placed TP{i+1}: {qty} @ {price}")
            else:
                logger.error(f"Failed to place TP{i+1}: {response.get('retMsg', '')}")
        
        logger.info(f"Successfully placed {placed_count}/{len(quantities)} TP orders")
        return placed_count == len(quantities)
        
    except Exception as e:
        logger.error(f"Error placing TP orders: {e}")
        return False

async def fix_position_tp_ratios(symbol: str, side: str):
    """Fix TP ratios for a single position"""
    logger.info(f"\n{'='*60}")
    logger.info(f"🔧 Fixing {symbol} {side} position")
    logger.info(f"{'='*60}")
    
    # Get position info
    position = await get_position_info(symbol, side)
    if not position:
        logger.error(f"❌ No position found for {symbol} {side}")
        return False
    
    position_size = Decimal(position['size'])
    avg_price = Decimal(position['avgPrice'])
    logger.info(f"📊 Position: {position_size} @ {avg_price}")
    
    # Get instrument info for precision
    instrument = await get_instrument_info(symbol)
    if not instrument:
        logger.error(f"❌ Failed to get instrument info")
        return False
    
    qty_step = Decimal(instrument['lotSizeFilter']['qtyStep'])
    tick_size = Decimal(instrument['priceFilter']['tickSize'])
    
    # Calculate new quantities with 85/5/5/5 ratios
    quantities = calculate_tp_quantities(position_size, TP_RATIOS, qty_step)
    
    # Calculate TP prices
    tp_prices = calculate_tp_prices(avg_price, side, tick_size)
    
    # Log the plan
    logger.info(f"\n📋 New TP Order Plan:")
    total_pct = 0
    for i, (qty, price, ratio) in enumerate(zip(quantities, tp_prices, TP_RATIOS)):
        pct = (qty / position_size * 100)
        total_pct += pct
        logger.info(f"   TP{i+1}: {qty} ({pct:.2f}%) @ {price} [Target: {ratio*100}%]")
    logger.info(f"   Total Coverage: {total_pct:.2f}%")
    
    # Cancel existing TP orders
    logger.info(f"\n🗑️ Cancelling existing TP orders...")
    if not await cancel_existing_tp_orders(symbol, side):
        logger.error("❌ Failed to cancel existing orders")
        return False
    
    # Wait a moment for order cancellation to process
    await asyncio.sleep(1)
    
    # Place new TP orders
    logger.info(f"\n📝 Placing new TP orders...")
    if await place_tp_orders(symbol, side, position, quantities, tp_prices):
        logger.info(f"✅ Successfully fixed TP ratios for {symbol}")
        return True
    else:
        logger.error(f"❌ Failed to place all TP orders")
        return False

async def main():
    """Main execution"""
    logger.info("🚀 Starting TP ratio fix for main account positions")
    logger.info(f"Target positions: {[p['symbol'] for p in POSITIONS_TO_FIX]}")
    logger.info(f"Target ratios: 85/5/5/5")
    
    success_count = 0
    failed_positions = []
    
    for position in POSITIONS_TO_FIX:
        if await fix_position_tp_ratios(position['symbol'], position['side']):
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
    logger.info(f"   2. Check that monitors are tracking correctly")
    logger.info(f"   3. Run mirror account fixes if needed")

if __name__ == "__main__":
    asyncio.run(main())