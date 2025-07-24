#!/usr/bin/env python3
"""Check JASMYUSDT position and orders"""
import asyncio
import logging
from clients.bybit_client import bybit_client
from clients.bybit_helpers import get_all_open_positions_with_pagination
from utils.helpers import safe_decimal_conversion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_position():
    # Get position
    positions = await get_all_open_positions_with_pagination()
    jasmy_positions = [p for p in positions if p.get('symbol') == 'JASMYUSDT']
    
    if jasmy_positions:
        for pos in jasmy_positions:
            print(f"\n📊 JASMYUSDT Position:")
            print(f"  Side: {pos.get('side')}")
            print(f"  Size: {pos.get('size')}")
            print(f"  Entry: {pos.get('avgPrice')}")
            print(f"  PnL: {pos.get('unrealisedPnl')}")
            print(f"  PositionIdx: {pos.get('positionIdx')}")
    else:
        print("No JASMYUSDT position found")
        return
    
    # Get all orders
    try:
        # Get open orders (including stop orders)
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: bybit_client.get_open_orders(
                category="linear",
                symbol="JASMYUSDT",
                limit=50
            )
        )
        
        if response and response.get("retCode") == 0:
            orders = response.get("result", {}).get("list", [])
            
            print(f"\n📋 Open Orders for JASMYUSDT: {len(orders)}")
            
            stop_orders = [o for o in orders if o.get('stopOrderType')]
            regular_orders = [o for o in orders if not o.get('stopOrderType')]
            
            if stop_orders:
                print(f"\n🛡️ Stop Orders: {len(stop_orders)}")
                for order in stop_orders:
                    print(f"  - {order.get('side')} {order.get('orderType')} @ {order.get('triggerPrice')}")
                    print(f"    Type: {order.get('stopOrderType')}, Status: {order.get('orderStatus')}")
                    print(f"    OrderID: {order.get('orderId')[:8]}...")
                    print(f"    LinkID: {order.get('orderLinkId', 'None')}")
            else:
                print("\n⚠️ No stop orders found!")
            
            if regular_orders:
                print(f"\n📝 Regular Orders: {len(regular_orders)}")
                for order in regular_orders:
                    print(f"  - {order.get('side')} {order.get('orderType')} @ {order.get('price')}")
                    print(f"    Status: {order.get('orderStatus')}")
    except Exception as e:
        logger.error(f"Error getting orders: {e}")

if __name__ == "__main__":
    asyncio.run(check_position())