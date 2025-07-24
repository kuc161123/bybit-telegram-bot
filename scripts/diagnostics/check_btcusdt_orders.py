#!/usr/bin/env python3
"""
Check BTCUSDT orders in detail
"""

from pybit.unified_trading import HTTP
from config.settings import BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET

session = HTTP(
    testnet=USE_TESTNET,
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET
)

# Get all orders for BTCUSDT
orders = session.get_open_orders(category="linear", symbol="BTCUSDT").get("result", {}).get("list", [])

print(f"Total orders for BTCUSDT: {len(orders)}")
print("\nDetailed order info:")

for i, order in enumerate(orders):
    print(f"\n--- Order {i+1} ---")
    print(f"Order ID: {order.get('orderId')}")
    print(f"Order Link ID: {order.get('orderLinkId')}")
    print(f"Order Type: {order.get('orderType')}")
    print(f"Stop Order Type: {order.get('stopOrderType')}")
    print(f"Side: {order.get('side')}")
    print(f"Trigger Price: {order.get('triggerPrice')}")
    print(f"Quantity: {order.get('qty')}")
    print(f"Trigger Direction: {order.get('triggerDirection')}")
    
# Check position
positions = session.get_positions(category="linear", symbol="BTCUSDT").get("result", {}).get("list", [])
if positions and float(positions[0].get("size", 0)) > 0:
    position = positions[0]
    print(f"\n📊 Position: {position.get('side')} {position.get('size')} @ {position.get('avgPrice')}")
    
    # Look for TP and SL orders
    tp_orders = [o for o in orders if o.get('stopOrderType') == 'TakeProfit' or 'TP' in o.get('orderLinkId', '')]
    sl_orders = [o for o in orders if o.get('stopOrderType') == 'Stop' or 'SL' in o.get('orderLinkId', '')]
    print(f"\nTP Orders found: {len(tp_orders)}")
    print(f"SL Orders found: {len(sl_orders)}")