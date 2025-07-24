#!/usr/bin/env python3
"""
Create missing SL order for JASMYUSDT using bot's standard method
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
from clients.bybit_helpers import place_order_with_retry

async def create_jasmyusdt_sl_final():
    """Create missing SL order for JASMYUSDT using bot's method"""
    
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
        position_idx = int(position.get('positionIdx', 0))
        
        print(f"\n📊 Position Details:")
        print(f"  Symbol: {symbol}")
        print(f"  Side: {side}")
        print(f"  Size: {size}")
        print(f"  Avg Price: {avg_price}")
        print(f"  Mark Price: {mark_price}")
        print(f"  Position Index: {position_idx}")
        
        # Calculate SL price (4.5% below avg price for Buy to match bot's approach)
        if side == 'Buy':
            sl_price = avg_price * 0.955  # 4.5% below entry
            order_side = 'Sell'
        else:
            sl_price = avg_price * 1.045  # 4.5% above entry
            order_side = 'Buy'
        
        # Format price to match JASMYUSDT precision (6 decimals)
        sl_price = f"{sl_price:.6f}"
        
        # Generate unique order link ID
        timestamp = int(time.time() * 1000)
        order_link_id = f"BOT_CONS_JASMYUSDT_SL_{timestamp}"
        
        print(f"\n🔧 Creating SL order using bot's standard method:")
        print(f"  Order side: {order_side}")
        print(f"  Quantity: {size}")
        print(f"  Trigger price: {sl_price}")
        print(f"  Stop order type: StopLoss")
        print(f"  Position index: {position_idx}")
        
        # Use the bot's standard order placement method
        sl_result = await place_order_with_retry(
            symbol=symbol,
            side=order_side,
            order_type="Market",
            qty=str(size),
            trigger_price=str(sl_price),
            position_idx=position_idx,
            reduce_only=True,
            order_link_id=order_link_id,
            stop_order_type="StopLoss"
        )
        
        if sl_result and sl_result.get("orderId"):
            order_id = sl_result.get("orderId")
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
                    print(f"  Trigger Price: {order.get('triggerPrice')}")
                    print(f"  Quantity: {order.get('qty')}")
                    break
            
            if not verified:
                print(f"\n⚠️  Warning: Could not verify order in system (may take a moment to appear)")
            
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
                f.write(f"Verified: {'Yes' if verified else 'Checking...'}\n")
            
            print(f"\n📄 Summary saved to: {summary_file}")
        else:
            print(f"\n❌ Failed to create SL order")
            if sl_result:
                print(f"Response: {sl_result}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def main():
    await create_jasmyusdt_sl_final()

if __name__ == "__main__":
    asyncio.run(main())