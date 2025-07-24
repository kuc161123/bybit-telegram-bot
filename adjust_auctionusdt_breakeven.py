#!/usr/bin/env python3
"""
Adjust AUCTIONUSDT SL to breakeven since TP(s) have already hit
"""
import asyncio
import sys
import time
from decimal import Decimal

# Add project root to path
sys.path.append('.')

from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
from clients.bybit_helpers import get_all_open_orders, get_all_positions
from utils.helpers import value_adjusted_to_step

async def adjust_auctionusdt_breakeven():
    """Adjust AUCTIONUSDT SL to breakeven for both main and mirror accounts"""
    
    print("=== ADJUSTING AUCTIONUSDT SL TO BREAKEVEN ===")
    
    # Get current positions
    positions = await get_all_positions()
    
    # Process main account
    main_pos = None
    for pos in positions:
        if pos.get('symbol') == 'AUCTIONUSDT' and float(pos.get('size', 0)) > 0:
            if bybit_client == bybit_client:  # Main account check
                main_pos = pos
                break
    
    if main_pos:
        await adjust_sl_to_breakeven('AUCTIONUSDT', main_pos, bybit_client, 'main')
    else:
        print("  ❌ No AUCTIONUSDT position found on main account")
    
    # Process mirror account
    if is_mirror_trading_enabled() and bybit_client_2:
        # Get mirror positions
        mirror_positions = await get_all_positions(client=bybit_client_2)
        mirror_pos = None
        
        for pos in mirror_positions:
            if pos.get('symbol') == 'AUCTIONUSDT' and float(pos.get('size', 0)) > 0:
                mirror_pos = pos
                break
        
        if mirror_pos:
            await adjust_sl_to_breakeven('AUCTIONUSDT', mirror_pos, bybit_client_2, 'mirror')
        else:
            print("  ❌ No AUCTIONUSDT position found on mirror account")

async def adjust_sl_to_breakeven(symbol: str, position: dict, client, account: str):
    """Adjust SL order to breakeven price"""
    
    entry_price = float(position.get('avgPrice', 0))
    current_size = float(position.get('size', 0))
    side = position.get('side')
    
    if entry_price <= 0 or current_size <= 0:
        print(f"  ❌ Invalid position data for {symbol} {account}")
        return
    
    print(f"  📊 {symbol} {account}: {side} {current_size} @ ${entry_price:.6f}")
    
    # Get current SL orders
    orders = await get_all_open_orders(client=client)
    current_sl_orders = []
    
    for order in orders:
        if (order.get('symbol') == symbol and 
            order.get('orderType') == 'Market' and
            order.get('triggerPrice') and
            order.get('orderStatus') == 'Untriggered'):
            current_sl_orders.append(order)
    
    print(f"  📋 Found {len(current_sl_orders)} existing SL orders")
    
    # Cancel existing SL orders
    for order in current_sl_orders:
        try:
            result = client.cancel_order(
                category='linear',
                symbol=symbol,
                orderId=order.get('orderId')
            )
            if result.get('retCode') == 0:
                print(f"    ✅ Cancelled SL order: {order.get('orderId')}")
            else:
                print(f"    ❌ Failed to cancel SL: {result.get('retMsg')}")
        except Exception as e:
            print(f"    ❌ Error cancelling SL: {e}")
    
    # Calculate breakeven price (entry price + small buffer for fees)
    fee_buffer = 0.0006  # 0.06% for fees
    if side == 'Buy':
        breakeven_price = entry_price * (1 + fee_buffer)
        sl_side = 'Sell'
    else:
        breakeven_price = entry_price * (1 - fee_buffer)
        sl_side = 'Buy'
    
    # Adjust to tick size (assuming 0.0001 for most symbols like AUCTIONUSDT)
    tick_size = Decimal("0.0001")
    breakeven_price = float(value_adjusted_to_step(Decimal(str(breakeven_price)), tick_size))
    
    print(f"  🎯 Setting breakeven SL: {current_size} @ ${breakeven_price:.4f}")
    
    # Place new breakeven SL order
    try:
        timestamp = int(time.time() * 1000)
        if account == "main":
            order_link_id = f"BE_SL_AUCTIONUSDT_{timestamp}"
        else:
            order_link_id = f"BE_MIR_SL_AUCTIONUSDT_{timestamp}"
        
        result = client.place_order(
            category='linear',
            symbol=symbol,
            side=sl_side,
            orderType='Market',
            qty=str(current_size),
            triggerPrice=str(breakeven_price),
            triggerDirection='2' if side == 'Buy' else '1',  # Below market for Buy, above for Sell
            reduceOnly=True,
            positionIdx=0,  # Hedge mode
            orderLinkId=order_link_id
        )
        
        if result.get('retCode') == 0:
            order_id = result.get('result', {}).get('orderId', 'Unknown')
            print(f"    ✅ Breakeven SL placed: {order_id}")
        else:
            error_msg = result.get('retMsg', 'Unknown error')
            print(f"    ❌ Failed to place breakeven SL: {error_msg}")
            
    except Exception as e:
        print(f"    ❌ Error placing breakeven SL: {e}")

async def main():
    """Main execution function"""
    print("🚀 Adjusting AUCTIONUSDT SL to breakeven...")
    
    try:
        await adjust_auctionusdt_breakeven()
        print("\n✅ AUCTIONUSDT breakeven adjustment complete!")
        
    except Exception as e:
        print(f"\n❌ Error during breakeven adjustment: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())