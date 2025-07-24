#!/usr/bin/env python3
"""
Create missing SL order for JASMYUSDT on main account
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

async def create_jasmyusdt_sl():
    """Create missing SL order for JASMYUSDT"""
    
    print("🔍 Creating SL order for JASMYUSDT on main account...")
    
    # Create Bybit client
    if USE_TESTNET:
        client = HTTP(testnet=True, api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)
    else:
        client = HTTP(testnet=False, api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)
    
    try:
        # First, get the current position details
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
        
        print(f"\n📊 Position Details:")
        print(f"  Symbol: {symbol}")
        print(f"  Side: {side}")
        print(f"  Size: {size}")
        print(f"  Avg Price: {avg_price}")
        
        # Check if SL already exists by checking conditional orders
        response = client.get_open_orders(
            category="linear",
            symbol="JASMYUSDT",
            orderFilter="StopOrder"
        )
        stop_orders = response.get('result', {}).get('list', [])
        
        # Check for existing SL
        has_sl = False
        for order in stop_orders:
            trigger_price = float(order.get('triggerPrice', '0'))
            if trigger_price > 0:
                if side == 'Buy' and trigger_price < avg_price:
                    has_sl = True
                    print(f"\n✅ SL already exists at trigger price: {trigger_price}")
                    break
                elif side == 'Sell' and trigger_price > avg_price:
                    has_sl = True
                    print(f"\n✅ SL already exists at trigger price: {trigger_price}")
                    break
        
        if has_sl:
            print("\nNo action needed - SL order already exists")
            return
        
        # Calculate SL price (3% below entry for Buy)
        if side == 'Buy':
            sl_price = avg_price * 0.97
            order_side = 'Sell'
            trigger_direction = 1  # MarkPrice <= triggerPrice
        else:
            sl_price = avg_price * 1.03
            order_side = 'Buy'
            trigger_direction = 2  # MarkPrice >= triggerPrice
        
        # Format price to match JASMYUSDT precision (6 decimals)
        sl_price = f"{sl_price:.6f}"
        
        # Generate unique order link ID
        timestamp = int(time.time() * 1000)
        order_link_id = f"BOT_CONS_JASMYUSDT_SL_{timestamp}"
        
        print(f"\n🔧 Creating SL order:")
        print(f"  Order side: {order_side}")
        print(f"  Quantity: {size}")
        print(f"  Trigger price: {sl_price}")
        print(f"  Order type: Market (conditional)")
        
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
            
            # Save summary
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_file = f"jasmyusdt_sl_created_{timestamp}.txt"
            
            with open(summary_file, 'w') as f:
                f.write(f"JASMYUSDT SL Order Created - {datetime.now()}\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"Position: {symbol} {side} {size} @ {avg_price}\n")
                f.write(f"SL Order: {order_side} {size} @ trigger {sl_price}\n")
                f.write(f"Order ID: {order_id}\n")
                f.write(f"Link ID: {order_link_id}\n")
            
            print(f"\n📄 Summary saved to: {summary_file}")
        else:
            print(f"\n❌ Failed to create SL order: {response}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def main():
    await create_jasmyusdt_sl()

if __name__ == "__main__":
    asyncio.run(main())