#!/usr/bin/env python3
"""
Check SUSHIUSDT position status
"""

import asyncio
from clients.bybit_client import bybit_client

async def check_position():
    """Check if SUSHIUSDT position exists"""
    
    print("\n📊 CHECKING SUSHIUSDT POSITION")
    print("=" * 60)
    
    try:
        # Get all positions
        result = bybit_client.get_positions(
            category="linear",
            symbol="SUSHIUSDT"
        )
        
        if result and result.get('retCode') == 0:
            positions = result['result']['list']
            
            if not positions:
                print("✅ No SUSHIUSDT positions found")
            else:
                for pos in positions:
                    size = float(pos.get('size', 0))
                    if size > 0:
                        print(f"⚠️  Active position found:")
                        print(f"   Symbol: {pos['symbol']}")
                        print(f"   Side: {pos['side']}")
                        print(f"   Size: {pos['size']}")
                        print(f"   Avg Price: {pos.get('avgPrice', 'N/A')}")
                        print(f"   Mark Price: {pos.get('markPrice', 'N/A')}")
                        print(f"   PnL: {pos.get('unrealisedPnl', 'N/A')}")
                    else:
                        print(f"✅ Position exists but size is 0")
        
        # Check open orders
        print("\n📋 Checking open orders...")
        orders = bybit_client.get_open_orders(
            category="linear",
            symbol="SUSHIUSDT"
        )
        
        if orders and orders.get('retCode') == 0:
            order_list = orders['result']['list']
            if order_list:
                print(f"⚠️  Found {len(order_list)} open orders:")
                for order in order_list:
                    print(f"   - {order['side']} {order['qty']} @ {order.get('price', 'Market')}")
                    print(f"     Type: {order.get('orderType')} | Status: {order.get('orderStatus')}")
                    print(f"     ID: {order['orderId'][:8]}...")
            else:
                print("✅ No open orders")
                
    except Exception as e:
        print(f"❌ Error checking position: {e}")
    
    print("\n" + "=" * 60)
    return True

if __name__ == "__main__":
    asyncio.run(check_position())