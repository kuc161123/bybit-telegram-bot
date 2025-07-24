#!/usr/bin/env python3
"""
Check all monitors vs positions
"""

import pickle
import asyncio
from clients.bybit_client import bybit_client, bybit_client_2

async def check_monitors():
    """Check all positions and monitors"""
    
    # Get positions from both accounts
    print("📊 Fetching positions...")
    
    # Main account
    main_resp = await asyncio.to_thread(
        bybit_client.get_positions,
        category="linear",
        settleCoin="USDT"
    )
    main_positions = main_resp.get('result', {}).get('list', [])
    
    # Mirror account
    if bybit_client_2:
        mirror_resp = await asyncio.to_thread(
            bybit_client_2.get_positions,
            category="linear",
            settleCoin="USDT"
        )
        mirror_positions = mirror_resp.get('result', {}).get('list', [])
    else:
        mirror_positions = []
    
    # Load monitors
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
    
    # Count active positions
    main_active = [(p['symbol'], p['side'], float(p['size']), float(p['avgPrice'])) 
                   for p in main_positions if float(p['size']) > 0]
    mirror_active = [(p['symbol'], p['side'], float(p['size']), float(p['avgPrice'])) 
                     for p in mirror_positions if float(p['size']) > 0]
    
    print(f"\n📊 MAIN ACCOUNT: {len(main_active)} positions")
    for symbol, side, size, price in main_active:
        monitor_key = f"{symbol}_{side}_main"
        status = "✅" if monitor_key in monitors else "❌ MISSING"
        print(f"  {symbol} {side}: {size} @ ${price:.4f} - {status}")
    
    print(f"\n📊 MIRROR ACCOUNT: {len(mirror_active)} positions")
    for symbol, side, size, price in mirror_active:
        monitor_key = f"{symbol}_{side}_mirror"
        status = "✅" if monitor_key in monitors else "❌ MISSING"
        print(f"  {symbol} {side}: {size} @ ${price:.4f} - {status}")
    
    # Count monitors
    main_monitors = len([k for k in monitors if k.endswith('_main')])
    mirror_monitors = len([k for k in monitors if k.endswith('_mirror')])
    
    print(f"\n📊 SUMMARY:")
    print(f"  Total positions: {len(main_active) + len(mirror_active)}")
    print(f"  Total monitors: {main_monitors + mirror_monitors}")
    print(f"  Main: {len(main_active)} positions, {main_monitors} monitors")
    print(f"  Mirror: {len(mirror_active)} positions, {mirror_monitors} monitors")
    
    # Find missing
    missing = []
    for symbol, side, size, price in main_active:
        if f"{symbol}_{side}_main" not in monitors:
            missing.append((symbol, side, 'main', size, price))
    
    for symbol, side, size, price in mirror_active:
        if f"{symbol}_{side}_mirror" not in monitors:
            missing.append((symbol, side, 'mirror', size, price))
    
    if missing:
        print(f"\n❌ MISSING MONITORS ({len(missing)}):")
        for symbol, side, account, size, price in missing:
            print(f"  {symbol}_{side}_{account}: {size} @ ${price:.4f}")
    
    return len(missing)

if __name__ == "__main__":
    missing = asyncio.run(check_monitors())
    if missing > 0:
        print(f"\n⚠️ Need to create {missing} monitors")
    else:
        print("\n✅ All positions have monitors")