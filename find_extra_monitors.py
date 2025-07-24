#!/usr/bin/env python3
"""
Find extra monitors that don't have corresponding positions
"""

import os
import sys
import pickle
from typing import Dict, Set, List

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2


def find_extra_monitors():
    """Find monitors without corresponding positions"""
    
    print("=" * 80)
    print("FINDING EXTRA MONITORS WITHOUT POSITIONS")
    print("=" * 80)
    
    # Get all active positions
    main_positions = set()
    mirror_positions = set()
    
    try:
        # Main account
        response = bybit_client.get_positions(category="linear", settleCoin="USDT")
        if response['retCode'] == 0:
            for pos in response['result']['list']:
                if float(pos['size']) > 0:
                    main_positions.add(f"{pos['symbol']}_{pos['side']}")
        print(f"\n✅ Found {len(main_positions)} active positions on MAIN")
        
        # Mirror account
        response = bybit_client_2.get_positions(category="linear", settleCoin="USDT")
        if response['retCode'] == 0:
            for pos in response['result']['list']:
                if float(pos['size']) > 0:
                    mirror_positions.add(f"{pos['symbol']}_{pos['side']}")
        print(f"✅ Found {len(mirror_positions)} active positions on MIRROR")
        
    except Exception as e:
        print(f"❌ Error fetching positions: {e}")
        return
    
    # Get monitors
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        # Find extra monitors
        extra_main_monitors = []
        extra_mirror_monitors = []
        
        for monitor_key, monitor_data in enhanced_monitors.items():
            symbol = monitor_data.get('symbol')
            side = monitor_data.get('side')
            account_type = monitor_data.get('account_type', 'main')
            pos_key = f"{symbol}_{side}"
            
            if account_type == 'main' and pos_key not in main_positions:
                extra_main_monitors.append({
                    'key': monitor_key,
                    'symbol': symbol,
                    'side': side,
                    'position_size': monitor_data.get('position_size', 0),
                    'remaining_size': monitor_data.get('remaining_size', 0)
                })
            elif account_type == 'mirror' and pos_key not in mirror_positions:
                extra_mirror_monitors.append({
                    'key': monitor_key,
                    'symbol': symbol,
                    'side': side,
                    'position_size': monitor_data.get('position_size', 0),
                    'remaining_size': monitor_data.get('remaining_size', 0)
                })
        
        # Display results
        print(f"\n📊 Monitor Analysis:")
        print(f"   Total monitors: {len(enhanced_monitors)}")
        print(f"   Main monitors: {sum(1 for m in enhanced_monitors.values() if m.get('account_type', 'main') == 'main')}")
        print(f"   Mirror monitors: {sum(1 for m in enhanced_monitors.values() if m.get('account_type', 'main') == 'mirror')}")
        
        if extra_main_monitors:
            print(f"\n❌ Extra MAIN monitors without positions ({len(extra_main_monitors)}):")
            for monitor in extra_main_monitors:
                print(f"   • {monitor['symbol']} {monitor['side']}")
                print(f"     Key: {monitor['key']}")
                print(f"     Size: {monitor['position_size']} (remaining: {monitor['remaining_size']})")
        
        if extra_mirror_monitors:
            print(f"\n❌ Extra MIRROR monitors without positions ({len(extra_mirror_monitors)}):")
            for monitor in extra_mirror_monitors:
                print(f"   • {monitor['symbol']} {monitor['side']}")
                print(f"     Key: {monitor['key']}")
                print(f"     Size: {monitor['position_size']} (remaining: {monitor['remaining_size']})")
        
        total_extra = len(extra_main_monitors) + len(extra_mirror_monitors)
        
        if total_extra > 0:
            # Save to file
            with open('extra_monitors.txt', 'w') as f:
                f.write("Extra Monitors Without Positions:\n")
                f.write("=" * 50 + "\n")
                for monitor in extra_main_monitors + extra_mirror_monitors:
                    f.write(f"{monitor['key']}\n")
            
            print(f"\n📄 Saved {total_extra} extra monitor keys to: extra_monitors.txt")
            print("\n💡 These monitors should be removed to match actual positions")
        else:
            print("\n✅ No extra monitors found!")
            
            # Check if we're counting differently
            print("\n🔍 Double-checking position counts...")
            print("\nMain positions:")
            for pos in sorted(main_positions):
                print(f"   • {pos}")
            print("\nMirror positions:")
            for pos in sorted(mirror_positions):
                print(f"   • {pos}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    find_extra_monitors()