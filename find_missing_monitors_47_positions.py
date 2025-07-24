#!/usr/bin/env python3
"""
Find missing monitors based on actual position count: 24 main + 23 mirror = 47 total
Bot is monitoring 44, so we're missing 3 monitors
"""

import os
import sys
import pickle
from typing import Dict, Set, List

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2


def find_missing_monitors_for_47_positions():
    """Find missing monitors based on user's actual position count"""
    
    print("=" * 80)
    print("FINDING MISSING MONITORS (47 POSITIONS TOTAL)")
    print("=" * 80)
    print("\n📊 User-confirmed position count:")
    print("   Main account: 24 positions")
    print("   Mirror account: 23 positions")
    print("   Total: 47 positions")
    
    # Get all positions from API
    main_positions = {}
    mirror_positions = {}
    
    try:
        # Main account - get ALL positions
        response = bybit_client.get_positions(category="linear")
        if response['retCode'] == 0:
            for pos in response['result']['list']:
                if float(pos['size']) > 0:
                    key = f"{pos['symbol']}_{pos['side']}"
                    main_positions[key] = {
                        'symbol': pos['symbol'],
                        'side': pos['side'],
                        'size': pos['size'],
                        'avgPrice': pos['avgPrice']
                    }
        
        # Mirror account - get ALL positions
        response = bybit_client_2.get_positions(category="linear")
        if response['retCode'] == 0:
            for pos in response['result']['list']:
                if float(pos['size']) > 0:
                    key = f"{pos['symbol']}_{pos['side']}"
                    mirror_positions[key] = {
                        'symbol': pos['symbol'],
                        'side': pos['side'],
                        'size': pos['size'],
                        'avgPrice': pos['avgPrice']
                    }
        
        print(f"\n📊 API returned positions:")
        print(f"   Main: {len(main_positions)}")
        print(f"   Mirror: {len(mirror_positions)}")
        print(f"   Total: {len(main_positions) + len(mirror_positions)}")
        
    except Exception as e:
        print(f"❌ Error fetching positions: {e}")
        return
    
    # Get current monitors
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        # Create sets of monitored positions
        monitored_main = set()
        monitored_mirror = set()
        
        for monitor_key, monitor_data in enhanced_monitors.items():
            symbol = monitor_data.get('symbol')
            side = monitor_data.get('side')
            account_type = monitor_data.get('account_type', 'main')
            pos_key = f"{symbol}_{side}"
            
            if account_type == 'main':
                monitored_main.add(pos_key)
            else:
                monitored_mirror.add(pos_key)
        
        print(f"\n📊 Current monitors:")
        print(f"   Main monitors: {len(monitored_main)}")
        print(f"   Mirror monitors: {len(monitored_mirror)}")
        print(f"   Total: {len(enhanced_monitors)}")
        
        # Find positions without monitors
        missing_main = []
        missing_mirror = []
        
        for pos_key, pos_data in main_positions.items():
            if pos_key not in monitored_main:
                missing_main.append(pos_data)
        
        for pos_key, pos_data in mirror_positions.items():
            if pos_key not in monitored_mirror:
                missing_mirror.append(pos_data)
        
        # Display all positions and missing monitors
        if len(main_positions) > 0:
            print("\n📋 All MAIN positions:")
            for i, (pos_key, pos_data) in enumerate(sorted(main_positions.items()), 1):
                monitored = "✅" if pos_key in monitored_main else "❌"
                print(f"   {i}. {pos_data['symbol']} {pos_data['side']} - Size: {pos_data['size']} {monitored}")
        
        if len(mirror_positions) > 0:
            print("\n📋 All MIRROR positions:")
            for i, (pos_key, pos_data) in enumerate(sorted(mirror_positions.items()), 1):
                monitored = "✅" if pos_key in monitored_mirror else "❌"
                print(f"   {i}. {pos_data['symbol']} {pos_data['side']} - Size: {pos_data['size']} {monitored}")
        
        # Show missing monitors
        total_missing = len(missing_main) + len(missing_mirror)
        
        if missing_main:
            print(f"\n❌ Missing MAIN monitors ({len(missing_main)}):")
            for pos in missing_main:
                print(f"   • {pos['symbol']} {pos['side']} - Size: {pos['size']}")
        
        if missing_mirror:
            print(f"\n❌ Missing MIRROR monitors ({len(missing_mirror)}):")
            for pos in missing_mirror:
                print(f"   • {pos['symbol']} {pos['side']} - Size: {pos['size']}")
        
        print(f"\n📊 Summary:")
        print(f"   Expected monitors: 47 (24 main + 23 mirror)")
        print(f"   Current monitors: {len(enhanced_monitors)}")
        print(f"   Missing monitors: {total_missing}")
        
        # If API doesn't show all positions user sees
        api_total = len(main_positions) + len(mirror_positions)
        if api_total < 47:
            print(f"\n⚠️  API shows {api_total} positions but user sees 47")
            print("   Some positions might be:")
            print("   • In a different settlement coin (not USDT)")
            print("   • In spot/margin instead of linear futures")
            print("   • Very small sizes that API might filter")
        
        return missing_main, missing_mirror, enhanced_monitors
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return [], [], {}


if __name__ == "__main__":
    missing_main, missing_mirror, monitors = find_missing_monitors_for_47_positions()