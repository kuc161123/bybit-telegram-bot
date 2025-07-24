#!/usr/bin/env python3
"""
Final check of positions and orders
"""

import asyncio
from clients.bybit_client import bybit_client
from config.settings import ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2

async def check_status():
    """Check final status"""
    print("\n📊 FINAL STATUS CHECK")
    print("=" * 60)
    
    # Main account
    try:
        print("\n📌 MAIN ACCOUNT:")
        
        # Check positions
        result = bybit_client.get_positions(
            category="linear",
            settleCoin="USDT"
        )
        
        if result and result.get('retCode') == 0:
            positions = result['result']['list']
            active = [p for p in positions if float(p.get('size', 0)) > 0]
            
            if active:
                print(f"  ⚠️  {len(active)} active positions:")
                for p in active:
                    print(f"    - {p['symbol']} {p['side']}: {p['size']}")
            else:
                print("  ✅ No active positions")
        
        # Check orders
        orders = bybit_client.get_open_orders(
            category="linear",
            settleCoin="USDT"
        )
        
        if orders and orders.get('retCode') == 0:
            order_list = orders['result']['list']
            if order_list:
                print(f"  ⚠️  {len(order_list)} open orders:")
                for o in order_list:
                    print(f"    - {o['symbol']} {o['side']}: {o['qty']} @ {o.get('price', 'Market')}")
            else:
                print("  ✅ No open orders")
                
    except Exception as e:
        print(f"  ❌ Error checking main account: {e}")
    
    # Mirror account
    if ENABLE_MIRROR_TRADING and BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
        try:
            print("\n📌 MIRROR ACCOUNT:")
            from pybit.unified_trading import HTTP
            mirror_client = HTTP(
                testnet=False,
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2
            )
            
            # Check positions
            result = mirror_client.get_positions(
                category="linear",
                settleCoin="USDT"
            )
            
            if result and result.get('retCode') == 0:
                positions = result['result']['list']
                active = [p for p in positions if float(p.get('size', 0)) > 0]
                
                if active:
                    print(f"  ⚠️  {len(active)} active positions:")
                    for p in active:
                        print(f"    - {p['symbol']} {p['side']}: {p['size']}")
                else:
                    print("  ✅ No active positions")
            
            # Check orders
            orders = mirror_client.get_open_orders(
                category="linear",
                settleCoin="USDT"
            )
            
            if orders and orders.get('retCode') == 0:
                order_list = orders['result']['list']
                if order_list:
                    print(f"  ⚠️  {len(order_list)} open orders:")
                    for o in order_list:
                        print(f"    - {o['symbol']} {o['side']}: {o['qty']} @ {o.get('price', 'Market')}")
                else:
                    print("  ✅ No open orders")
                    
        except Exception as e:
            print(f"  ❌ Error checking mirror account: {e}")
    
    # Check persistence
    import os
    import pickle
    
    print("\n📌 BOT MEMORY STATUS:")
    if os.path.exists('bybit_bot_dashboard_v4.1_enhanced.pkl'):
        size = os.path.getsize('bybit_bot_dashboard_v4.1_enhanced.pkl')
        print(f"  ✅ Persistence file: {size} bytes")
        
        # Check content
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
            monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
            print(f"  📊 Active monitors: {len(monitors)}")
            if monitors:
                print("  ⚠️  Monitors should be empty for fresh start!")
    
    # Check markers
    markers = ['.fresh_start', '.no_backup_restore', '.disable_persistence_recovery']
    print("\n📌 FRESH START MARKERS:")
    for marker in markers:
        if os.path.exists(marker):
            print(f"  ✅ {marker}")
        else:
            print(f"  ❌ {marker} missing")
    
    print("\n" + "=" * 60)
    print("✅ STATUS CHECK COMPLETE")

if __name__ == "__main__":
    asyncio.run(check_status())