#!/usr/bin/env python3
"""
Comprehensively find all positions and missing monitors
"""

import os
import sys
import pickle
from typing import Dict, Set, List
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2


def get_all_positions_comprehensive(client, account_name: str) -> Dict:
    """Get ALL positions from account, trying multiple methods"""
    all_positions = {}
    
    print(f"\n🔍 Fetching {account_name} positions...")
    
    # Method 1: Try with settleCoin=USDT
    try:
        response = client.get_positions(category="linear", settleCoin="USDT")
        if response['retCode'] == 0:
            for pos in response['result']['list']:
                if float(pos['size']) > 0:
                    key = f"{pos['symbol']}_{pos['side']}"
                    all_positions[key] = {
                        'symbol': pos['symbol'],
                        'side': pos['side'],
                        'size': pos['size'],
                        'avgPrice': pos['avgPrice'],
                        'unrealisedPnl': pos.get('unrealisedPnl', '0')
                    }
            print(f"   Found {len(all_positions)} positions with settleCoin=USDT")
    except Exception as e:
        print(f"   Error with settleCoin method: {e}")
    
    # Method 2: Try without settleCoin, with limit
    try:
        response = client.get_positions(category="linear", limit=200)
        if response['retCode'] == 0:
            count = 0
            for pos in response['result']['list']:
                if float(pos['size']) > 0:
                    key = f"{pos['symbol']}_{pos['side']}"
                    if key not in all_positions:
                        all_positions[key] = {
                            'symbol': pos['symbol'],
                            'side': pos['side'],
                            'size': pos['size'],
                            'avgPrice': pos['avgPrice'],
                            'unrealisedPnl': pos.get('unrealisedPnl', '0')
                        }
                        count += 1
            if count > 0:
                print(f"   Found {count} additional positions with limit=200")
    except Exception as e:
        print(f"   Error with limit method: {e}")
    
    # Method 3: Check active orders that might indicate positions
    try:
        response = client.get_open_orders(category="linear", limit=200)
        if response['retCode'] == 0:
            symbols_with_orders = set()
            for order in response['result']['list']:
                if order.get('reduceOnly', False):
                    symbols_with_orders.add(order['symbol'])
            if symbols_with_orders:
                print(f"   Found {len(symbols_with_orders)} symbols with reduce-only orders")
    except Exception as e:
        print(f"   Error checking orders: {e}")
    
    return all_positions


def find_all_missing_monitors():
    """Find all missing monitors comprehensively"""
    
    print("=" * 80)
    print("COMPREHENSIVE POSITION AND MONITOR CHECK")
    print("=" * 80)
    print("\n📊 User reports:")
    print("   Main account: 24 positions")
    print("   Mirror account: 23 positions")
    print("   Total expected: 47 positions")
    
    # Get positions from both accounts
    main_positions = get_all_positions_comprehensive(bybit_client, "MAIN")
    mirror_positions = get_all_positions_comprehensive(bybit_client_2, "MIRROR")
    
    total_found = len(main_positions) + len(mirror_positions)
    
    print(f"\n📊 API returned:")
    print(f"   Main positions: {len(main_positions)}")
    print(f"   Mirror positions: {len(mirror_positions)}")
    print(f"   Total found: {total_found}")
    
    # Get current monitors
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        # Analyze monitors
        monitored_main = {}
        monitored_mirror = {}
        
        for monitor_key, monitor_data in enhanced_monitors.items():
            symbol = monitor_data.get('symbol')
            side = monitor_data.get('side')
            account_type = monitor_data.get('account_type', 'main')
            pos_key = f"{symbol}_{side}"
            
            if account_type == 'main':
                monitored_main[pos_key] = monitor_data
            else:
                monitored_mirror[pos_key] = monitor_data
        
        print(f"\n📊 Current monitors:")
        print(f"   Main monitors: {len(monitored_main)}")
        print(f"   Mirror monitors: {len(monitored_mirror)}")
        print(f"   Total monitors: {len(enhanced_monitors)}")
        
        # Find missing monitors
        missing_main = []
        missing_mirror = []
        
        for pos_key, pos_data in main_positions.items():
            if pos_key not in monitored_main:
                missing_main.append(pos_data)
        
        for pos_key, pos_data in mirror_positions.items():
            if pos_key not in monitored_mirror:
                missing_mirror.append(pos_data)
        
        # Display results
        if missing_main:
            print(f"\n❌ Missing MAIN monitors ({len(missing_main)}):")
            for pos in missing_main:
                print(f"   • {pos['symbol']} {pos['side']} - Size: {pos['size']}")
        
        if missing_mirror:
            print(f"\n❌ Missing MIRROR monitors ({len(missing_mirror)}):")
            for pos in missing_mirror:
                print(f"   • {pos['symbol']} {pos['side']} - Size: {pos['size']}")
        
        # Also check for extra monitors
        extra_main = []
        extra_mirror = []
        
        for pos_key, monitor_data in monitored_main.items():
            if pos_key not in main_positions:
                extra_main.append({
                    'key': f"{monitor_data['symbol']}_{monitor_data['side']}_main",
                    'symbol': monitor_data['symbol'],
                    'side': monitor_data['side']
                })
        
        for pos_key, monitor_data in monitored_mirror.items():
            if pos_key not in mirror_positions:
                extra_mirror.append({
                    'key': f"{monitor_data['symbol']}_{monitor_data['side']}_mirror",
                    'symbol': monitor_data['symbol'],
                    'side': monitor_data['side']
                })
        
        if extra_main:
            print(f"\n⚠️  Extra MAIN monitors (no position) ({len(extra_main)}):")
            for mon in extra_main:
                print(f"   • {mon['symbol']} {mon['side']}")
        
        if extra_mirror:
            print(f"\n⚠️  Extra MIRROR monitors (no position) ({len(extra_mirror)}):")
            for mon in extra_mirror:
                print(f"   • {mon['symbol']} {mon['side']}")
        
        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY AND RECOMMENDATIONS")
        print("=" * 80)
        
        total_missing = len(missing_main) + len(missing_mirror)
        total_extra = len(extra_main) + len(extra_mirror)
        
        print(f"\n📊 Analysis:")
        print(f"   API shows: {total_found} positions")
        print(f"   User sees: 47 positions")
        print(f"   Difference: {47 - total_found} positions not visible via API")
        print(f"\n   Missing monitors: {total_missing}")
        print(f"   Extra monitors: {total_extra}")
        
        if total_found < 47:
            print(f"\n⚠️  Possible reasons for position discrepancy:")
            print("   1. Some positions might be in spot/margin (not linear futures)")
            print("   2. Positions in other settlement coins (not USDT)")
            print("   3. Sub-accounts or different API permissions")
            print("   4. Very recent positions not yet synced")
        
        # Save results for next step
        results = {
            'missing_main': missing_main,
            'missing_mirror': missing_mirror,
            'extra_main': extra_main,
            'extra_mirror': extra_mirror,
            'found_positions': total_found,
            'expected_positions': 47
        }
        
        with open('position_monitor_analysis.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📄 Saved analysis to: position_monitor_analysis.json")
        
        return results
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


if __name__ == "__main__":
    results = find_all_missing_monitors()
    
    if results and (results['missing_main'] or results['missing_mirror']):
        print("\n💡 Next: Run create_missing_monitors_signal.py to fix")