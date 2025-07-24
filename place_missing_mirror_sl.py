#!/usr/bin/env python3
"""
Place missing SL orders for mirror account positions
"""
import asyncio
import sys
import time
from decimal import Decimal

# Add project root to path
sys.path.append('.')

from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
from clients.bybit_helpers import get_all_open_orders
import asyncio as aio
from utils.helpers import value_adjusted_to_step

# Mirror positions that need SL orders
MIRROR_POSITIONS_NEEDING_SL = ['AUCTIONUSDT', 'CRVUSDT', 'SEIUSDT', 'ARBUSDT']

async def get_mirror_positions():
    """Get positions from mirror account"""
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client_2.get_positions(
                category="linear",
                settleCoin="USDT"
            )
        )
        
        if response.get("retCode") == 0:
            result = response.get("result", {})
            positions = result.get("list", [])
            return positions
        else:
            print(f"❌ Error getting mirror positions: {response}")
            return []
            
    except Exception as e:
        print(f"❌ Error getting mirror positions: {e}")
        return []

async def get_mirror_orders():
    """Get open orders from mirror account"""
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client_2.get_open_orders(
                category="linear"
            )
        )
        
        if response.get("retCode") == 0:
            result = response.get("result", {})
            orders = result.get("list", [])
            return orders
        else:
            print(f"❌ Error getting mirror orders: {response}")
            return []
            
    except Exception as e:
        print(f"❌ Error getting mirror orders: {e}")
        return []

async def place_mirror_sl_orders():
    """Place missing SL orders for mirror account positions"""
    
    if not is_mirror_trading_enabled() or not bybit_client_2:
        print("❌ Mirror trading not enabled")
        return
    
    print("=== PLACING MISSING MIRROR SL ORDERS ===")
    
    # Get mirror positions
    mirror_positions = await get_mirror_positions()
    
    for symbol in MIRROR_POSITIONS_NEEDING_SL:
        print(f"\n🔧 Processing {symbol} mirror...")
        
        # Find mirror position
        mirror_pos = None
        for pos in mirror_positions:
            if pos.get('symbol') == symbol and float(pos.get('size', 0)) > 0:
                mirror_pos = pos
                break
        
        if not mirror_pos:
            print(f"  ❌ No {symbol} position found on mirror account")
            continue
        
        await place_sl_for_mirror_position(symbol, mirror_pos)

async def place_sl_for_mirror_position(symbol: str, position: dict):
    """Place SL order for a specific mirror position"""
    
    entry_price = float(position.get('avgPrice', 0))
    current_size = float(position.get('size', 0))
    side = position.get('side')
    
    if entry_price <= 0 or current_size <= 0:
        print(f"  ❌ Invalid position data for {symbol} mirror")
        return
    
    print(f"  📊 {symbol} mirror: {side} {current_size} @ ${entry_price:.6f}")
    
    # Check if SL already exists
    orders = await get_mirror_orders()
    existing_sl = []
    
    for order in orders:
        if (order.get('symbol') == symbol and 
            order.get('orderType') == 'Market' and
            order.get('triggerPrice') and
            order.get('orderStatus') == 'Untriggered'):
            existing_sl.append(order)
    
    if existing_sl:
        print(f"  ✅ SL already exists for {symbol} mirror ({len(existing_sl)} orders)")
        return
    
    # Calculate SL price (6% loss from entry)
    if side == 'Buy':
        sl_price = entry_price * 0.94  # 6% below entry for long
        sl_side = 'Sell'
        trigger_direction = '2'  # Below market
    else:
        sl_price = entry_price * 1.06  # 6% above entry for short  
        sl_side = 'Buy'
        trigger_direction = '1'  # Above market
    
    # Get appropriate tick size for each symbol
    tick_sizes = {
        'AUCTIONUSDT': Decimal("0.0001"),
        'CRVUSDT': Decimal("0.0001"), 
        'SEIUSDT': Decimal("0.0001"),
        'ARBUSDT': Decimal("0.0001")
    }
    
    tick_size = tick_sizes.get(symbol, Decimal("0.0001"))
    sl_price = float(value_adjusted_to_step(Decimal(str(sl_price)), tick_size))
    
    print(f"  🎯 Placing SL: {current_size} @ ${sl_price:.4f} (6% loss)")
    
    # Place SL order
    try:
        timestamp = int(time.time() * 1000)
        order_link_id = f"MIRROR_SL_{symbol}_{timestamp}"
        
        result = bybit_client_2.place_order(
            category='linear',
            symbol=symbol,
            side=sl_side,
            orderType='Market',
            qty=str(current_size),
            triggerPrice=str(sl_price),
            triggerDirection=trigger_direction,
            reduceOnly=True,
            positionIdx=0,  # Hedge mode
            orderLinkId=order_link_id
        )
        
        if result.get('retCode') == 0:
            order_id = result.get('result', {}).get('orderId', 'Unknown')
            print(f"    ✅ SL order placed: {order_id}")
        else:
            error_msg = result.get('retMsg', 'Unknown error')
            print(f"    ❌ Failed to place SL: {error_msg}")
            
    except Exception as e:
        print(f"    ❌ Error placing SL: {e}")

async def main():
    """Main execution function"""
    print("🚀 Placing missing SL orders for mirror account positions...")
    print(f"📋 Symbols to check: {', '.join(MIRROR_POSITIONS_NEEDING_SL)}")
    
    try:
        await place_mirror_sl_orders()
        print("\n✅ Mirror SL order placement complete!")
        
    except Exception as e:
        print(f"\n❌ Error during mirror SL placement: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())