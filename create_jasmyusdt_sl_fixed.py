#!/usr/bin/env python3
"""
Create missing SL order for JASMYUSDT with proper trigger price
"""

import asyncio
import sys
import os
from datetime import datetime
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pybit.unified_trading import HTTP
from config.settings import BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET

async def create_jasmyusdt_sl_fixed():
    """Create missing SL order for JASMYUSDT with correct trigger price"""
    
    print("🔍 Creating SL order for JASMYUSDT on main account...")
    
    # Create Bybit client
    if USE_TESTNET:
        client = HTTP(testnet=True, api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)
    else:
        client = HTTP(testnet=False, api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)
    
    try:
        # Get the current position details
        response = client.get_positions(category="linear", symbol="JASMYUSDT")
        positions = response.get('result', {}).get('list', [])
        
        position = None
        for pos in positions:
            if float(pos.get('size', 0)) > 0:
                position = pos
                break
        
        if not position:
            print("❌ No active JASMYUSDT position found")
            return
        
        symbol = position.get('symbol')
        side = position.get('side')
        size = position.get('size')
        avg_price = float(position.get('avgPrice'))
        mark_price = float(position.get('markPrice'))
        
        print(f"\n📊 Position Details:")
        print(f"  Symbol: {symbol}")
        print(f"  Side: {side}")
        print(f"  Size: {size}")
        print(f"  Avg Price: {avg_price}")
        print(f"  Mark Price: {mark_price}")
        
        # Calculate SL price (3.5% below avg price for Buy)
        # Using 3.5% to ensure it's below current market price
        if side == 'Buy':
            sl_price = avg_price * 0.965  # 3.5% below entry
            order_side = 'Sell'
            trigger_direction = 1  # MarkPrice <= triggerPrice
            
            # Ensure SL is below current mark price
            if sl_price >= mark_price:
                sl_price = mark_price * 0.98  # 2% below current mark
        else:
            sl_price = avg_price * 1.035  # 3.5% above entry
            order_side = 'Buy'
            trigger_direction = 2  # MarkPrice >= triggerPrice
            
            # Ensure SL is above current mark price
            if sl_price <= mark_price:
                sl_price = mark_price * 1.02  # 2% above current mark
        
        # Format price to match JASMYUSDT precision (6 decimals)
        sl_price = f"{sl_price:.6f}"
        
        # Generate unique order link ID with timestamp
        timestamp = int(time.time() * 1000)
        order_link_id = f"BOT_CONS_JASMYUSDT_SL_{timestamp}"
        
        print(f"\n🔧 Creating SL order:")
        print(f"  Order side: {order_side}")
        print(f"  Quantity: {size}")
        print(f"  Trigger price: {sl_price}")
        print(f"  Order type: Market (conditional)")
        print(f"  Trigger direction: {'MarkPrice <= TriggerPrice' if trigger_direction == 1 else 'MarkPrice >= TriggerPrice'}")
        
        # Verify trigger price is valid
        if side == 'Buy' and float(sl_price) >= mark_price:
            print(f"\n❌ Error: SL trigger price {sl_price} must be below mark price {mark_price}")
            return
        elif side == 'Sell' and float(sl_price) <= mark_price:
            print(f"\n❌ Error: SL trigger price {sl_price} must be above mark price {mark_price}")
            return
        
        # Place the SL order
        response = client.place_order(
            category="linear",
            symbol="JASMYUSDT",
            side=order_side,
            orderType="Market",
            qty=str(size),
            triggerPrice=sl_price,
            triggerDirection=trigger_direction,
            orderLinkId=order_link_id,
            reduceOnly=True,
            closeOnTrigger=True
        )
        
        if response.get('retCode') == 0:
            order_id = response.get('result', {}).get('orderId')
            print(f"\n✅ Successfully created SL order!")
            print(f"  Order ID: {order_id}")
            print(f"  Link ID: {order_link_id}")
            
            # Verify the order was created
            await asyncio.sleep(1)
            
            # Check if the order exists
            check_response = client.get_open_orders(
                category="linear",
                symbol="JASMYUSDT",
                orderFilter="StopOrder"
            )
            stop_orders = check_response.get('result', {}).get('list', [])
            
            verified = False
            for order in stop_orders:
                if order.get('orderLinkId') == order_link_id:
                    verified = True
                    print(f"\n✅ Order verified in system!")
                    break
            
            if not verified:
                print(f"\n⚠️  Warning: Could not verify order in system")
            
            # Save summary
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_file = f"jasmyusdt_sl_created_{timestamp_str}.txt"
            
            with open(summary_file, 'w') as f:
                f.write(f"JASMYUSDT SL Order Created - {datetime.now()}\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"Position: {symbol} {side} {size} @ {avg_price}\n")
                f.write(f"Mark Price: {mark_price}\n")
                f.write(f"SL Order: {order_side} {size} @ trigger {sl_price}\n")
                f.write(f"Order ID: {order_id}\n")
                f.write(f"Link ID: {order_link_id}\n")
                f.write(f"Verified: {'Yes' if verified else 'No'}\n")
            
            print(f"\n📄 Summary saved to: {summary_file}")
        else:
            print(f"\n❌ Failed to create SL order: {response}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def main():
    await create_jasmyusdt_sl_fixed()

if __name__ == "__main__":
    asyncio.run(main())