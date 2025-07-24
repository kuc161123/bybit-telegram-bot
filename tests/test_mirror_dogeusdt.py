#!/usr/bin/env python3
"""Test script to check DOGEUSDT on mirror account"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pybit.unified_trading import HTTP
from config.settings import USE_TESTNET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2

print(f"Mirror API Key: {BYBIT_API_KEY_2[:8] if BYBIT_API_KEY_2 else 'NOT SET'}...")
print(f"Mirror API Secret: {'SET' if BYBIT_API_SECRET_2 else 'NOT SET'}")
print(f"Testnet: {USE_TESTNET}")

if not BYBIT_API_KEY_2 or not BYBIT_API_SECRET_2:
    print("❌ Mirror account credentials not configured!")
    exit(1)

try:
    # Create mirror client
    mirror_client = HTTP(
        api_key=BYBIT_API_KEY_2,
        api_secret=BYBIT_API_SECRET_2,
        testnet=USE_TESTNET
    )
    
    print("\n🔍 Checking DOGEUSDT position on mirror account...")
    
    # Get position
    response = mirror_client.get_positions(
        category="linear",
        symbol="DOGEUSDT"
    )
    
    print(f"Response code: {response.get('retCode')}")
    print(f"Response msg: {response.get('retMsg')}")
    
    positions = response.get("result", {}).get("list", [])
    
    if positions:
        pos = positions[0]
        print(f"\n📊 DOGEUSDT Position Found:")
        print(f"  Side: {pos.get('side')}")
        print(f"  Size: {pos.get('size')}")
        print(f"  Avg Price: {pos.get('avgPrice')}")
        print(f"  Mark Price: {pos.get('markPrice')}")
        print(f"  Unrealized P&L: ${pos.get('unrealisedPnl')}")
    else:
        print("\n✅ No DOGEUSDT position on mirror account")
    
    # Check orders
    print("\n🔍 Checking DOGEUSDT orders...")
    orders_response = mirror_client.get_open_orders(
        category="linear",
        symbol="DOGEUSDT"
    )
    
    orders = orders_response.get("result", {}).get("list", [])
    print(f"\n📋 Found {len(orders)} open orders")
    
    for i, order in enumerate(orders):
        print(f"\nOrder {i+1}:")
        print(f"  Order ID: {order.get('orderId')}")
        print(f"  Link ID: {order.get('orderLinkId')}")
        print(f"  Side: {order.get('side')}")
        print(f"  Qty: {order.get('qty')}")
        print(f"  Price: {order.get('price')}")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()