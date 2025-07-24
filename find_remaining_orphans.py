#!/usr/bin/env python3
"""
Find remaining orphaned monitors after initial cleanup
"""

import os
import sys
import pickle

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2


def find_remaining_orphans():
    """Find any remaining orphaned monitors"""
    
    print("=" * 80)
    print("FINDING REMAINING ORPHANED MONITORS")
    print("=" * 80)
    
    # Get active positions
    main_positions = set()
    mirror_positions = set()
    
    try:
        # Main account
        response = bybit_client.get_positions(category="linear", settleCoin="USDT")
        if response['retCode'] == 0:
            for pos in response['result']['list']:
                if float(pos['size']) > 0:
                    main_positions.add(f"{pos['symbol']}_{pos['side']}")
        
        # Mirror account
        response = bybit_client_2.get_positions(category="linear", settleCoin="USDT")
        if response['retCode'] == 0:
            for pos in response['result']['list']:
                if float(pos['size']) > 0:
                    mirror_positions.add(f"{pos['symbol']}_{pos['side']}")
                    
    except Exception as e:
        print(f"❌ Error fetching positions: {e}")
        return
    
    # Get monitors
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
    except Exception as e:
        print(f"❌ Error loading pickle file: {e}")
        return
    
    # Find orphans
    orphaned_main = []
    orphaned_mirror = []
    
    for monitor_key, monitor_data in enhanced_monitors.items():
        symbol = monitor_data.get('symbol')
        side = monitor_data.get('side')
        account_type = monitor_data.get('account_type', 'main')
        position_key = f"{symbol}_{side}"
        
        if account_type == 'main' and position_key not in main_positions:
            orphaned_main.append({
                'key': monitor_key,
                'symbol': symbol,
                'side': side,
                'remaining_size': monitor_data.get('remaining_size', 0),
                'position_size': monitor_data.get('position_size', 0)
            })
        elif account_type == 'mirror' and position_key not in mirror_positions:
            orphaned_mirror.append({
                'key': monitor_key,
                'symbol': symbol,
                'side': side,
                'remaining_size': monitor_data.get('remaining_size', 0),
                'position_size': monitor_data.get('position_size', 0)
            })
    
    # Display results
    print(f"\n📊 Active Positions:")
    print(f"   Main: {len(main_positions)}")
    print(f"   Mirror: {len(mirror_positions)}")
    
    if orphaned_main:
        print(f"\n❌ Orphaned MAIN monitors ({len(orphaned_main)}):")
        for monitor in orphaned_main:
            print(f"   • {monitor['symbol']} {monitor['side']}")
            print(f"     Key: {monitor['key']}")
            print(f"     Size: {monitor['position_size']} (remaining: {monitor['remaining_size']})")
    
    if orphaned_mirror:
        print(f"\n❌ Orphaned MIRROR monitors ({len(orphaned_mirror)}):")
        for monitor in orphaned_mirror:
            print(f"   • {monitor['symbol']} {monitor['side']}")
            print(f"     Key: {monitor['key']}")
            print(f"     Size: {monitor['position_size']} (remaining: {monitor['remaining_size']})")
    
    if not orphaned_main and not orphaned_mirror:
        print("\n✅ No orphaned monitors found!")
    else:
        # Save to file for cleanup
        with open('remaining_orphans.txt', 'w') as f:
            f.write("Remaining Orphaned Monitors:\n")
            f.write("=" * 50 + "\n")
            for monitor in orphaned_main + orphaned_mirror:
                f.write(f"{monitor['key']}\n")
        print(f"\n📄 Saved to: remaining_orphans.txt")
        print("\n💡 Run close_remaining_orphans.py to clean these up")


if __name__ == "__main__":
    find_remaining_orphans()