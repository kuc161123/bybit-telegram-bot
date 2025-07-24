#!/usr/bin/env python3
"""
Simple Mirror Sync Status Check
"""

import asyncio
from decimal import Decimal
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_client import bybit_client as bybit_client_1
from execution.mirror_trader import bybit_client_2
from config.settings import ENABLE_MIRROR_TRADING

async def main():
    print("=" * 80)
    print("🔍 MIRROR SYNC STATUS CHECK")
    print("=" * 80)
    
    print(f"\nMirror Trading Enabled: {ENABLE_MIRROR_TRADING}")
    
    # Get all positions
    print("\n📊 Main Account Positions:")
    print("-" * 40)
    
    main_positions = {}
    response = bybit_client_1.get_positions(category="linear", settleCoin="USDT", limit=200)
    if response['retCode'] == 0:
        for pos in response['result']['list']:
            if float(pos['size']) > 0:
                key = f"{pos['symbol']}_{pos['side']}"
                main_positions[key] = {
                    'size': Decimal(pos['size']),
                    'avgPrice': Decimal(pos['avgPrice']),
                    'unrealisedPnl': Decimal(pos['unrealisedPnl'])
                }
                print(f"  {pos['symbol']} {pos['side']}: {pos['size']} @ {pos['avgPrice']}")
    
    print(f"\nTotal Main Positions: {len(main_positions)}")
    
    print("\n📊 Mirror Account Positions:")
    print("-" * 40)
    
    mirror_positions = {}
    response = bybit_client_2.get_positions(category="linear", settleCoin="USDT", limit=200)
    if response['retCode'] == 0:
        for pos in response['result']['list']:
            if float(pos['size']) > 0:
                key = f"{pos['symbol']}_{pos['side']}"
                mirror_positions[key] = {
                    'size': Decimal(pos['size']),
                    'avgPrice': Decimal(pos['avgPrice']),
                    'unrealisedPnl': Decimal(pos['unrealisedPnl'])
                }
                print(f"  {pos['symbol']} {pos['side']}: {pos['size']} @ {pos['avgPrice']}")
    
    print(f"\nTotal Mirror Positions: {len(mirror_positions)}")
    
    # Compare
    print("\n📊 COMPARISON:")
    print("-" * 40)
    
    all_keys = set(main_positions.keys()) | set(mirror_positions.keys())
    
    for key in sorted(all_keys):
        main = main_positions.get(key)
        mirror = mirror_positions.get(key)
        
        if main and mirror:
            main_size = main['size']
            mirror_size = mirror['size']
            diff_pct = ((main_size - mirror_size) / main_size * 100) if main_size > 0 else 0
            
            if abs(diff_pct) < 0.1:
                print(f"✅ {key}: Main={main_size} Mirror={mirror_size} [MATCHED]")
            else:
                print(f"⚠️  {key}: Main={main_size} Mirror={mirror_size} [DIFF: {diff_pct:.1f}%]")
        elif main and not mirror:
            print(f"❌ {key}: Main={main['size']} Mirror=NONE")
        elif mirror and not main:
            print(f"❌ {key}: Main=NONE Mirror={mirror['size']}")
    
    # Check some orders
    print("\n📊 Sample Orders (WIFUSDT):")
    print("-" * 40)
    
    # Main account orders
    orders = bybit_client_1.get_open_orders(category="linear", symbol="WIFUSDT")
    if orders['retCode'] == 0:
        print(f"Main Account WIFUSDT Orders: {len(orders['result']['list'])}")
        for order in orders['result']['list'][:5]:
            print(f"  {order['orderType']}: {order['qty']} @ {order.get('triggerPrice', order.get('price'))}")
    
    # Mirror account orders
    orders = bybit_client_2.get_open_orders(category="linear", symbol="WIFUSDT")
    if orders['retCode'] == 0:
        print(f"\nMirror Account WIFUSDT Orders: {len(orders['result']['list'])}")
        for order in orders['result']['list'][:5]:
            print(f"  {order['orderType']}: {order['qty']} @ {order.get('triggerPrice', order.get('price'))}")

if __name__ == "__main__":
    asyncio.run(main())