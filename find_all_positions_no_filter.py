#!/usr/bin/env python3
"""
Find ALL positions without any size filtering and create missing monitors
"""

import os
import sys
import pickle
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2


def get_all_positions_no_filter(client, account_name: str):
    """Get ALL positions including very small ones"""
    all_positions = {}
    
    print(f"\n🔍 Fetching ALL {account_name} positions (no size filter)...")
    
    try:
        response = client.get_positions(category="linear", settleCoin="USDT")
        if response['retCode'] == 0:
            for pos in response['result']['list']:
                # Include ALL positions, even with size 0.1 or smaller
                size = float(pos['size'])
                if size > 0:  # Any positive size
                    key = f"{pos['symbol']}_{pos['side']}"
                    all_positions[key] = {
                        'symbol': pos['symbol'],
                        'side': pos['side'],
                        'size': pos['size'],
                        'avgPrice': pos['avgPrice'],
                        'unrealisedPnl': pos.get('unrealisedPnl', '0')
                    }
            
            # Show all positions including tiny ones
            print(f"   Found {len(all_positions)} total positions (including tiny ones)")
            
            # Show positions by size
            sorted_positions = sorted(all_positions.items(), key=lambda x: float(x[1]['size']))
            
            tiny_positions = [p for p in sorted_positions if float(p[1]['size']) < 1]
            if tiny_positions:
                print(f"\n   Tiny positions (size < 1):")
                for key, pos in tiny_positions[:5]:  # Show first 5
                    print(f"     • {pos['symbol']} {pos['side']}: {pos['size']}")
                if len(tiny_positions) > 5:
                    print(f"     ... and {len(tiny_positions) - 5} more tiny positions")
                    
    except Exception as e:
        print(f"   Error: {e}")
    
    return all_positions


def create_missing_monitors_and_signal():
    """Find missing monitors and create them"""
    
    print("=" * 80)
    print("FINDING ALL POSITIONS AND CREATING MISSING MONITORS")
    print("=" * 80)
    
    # Get ALL positions
    main_positions = get_all_positions_no_filter(bybit_client, "MAIN")
    mirror_positions = get_all_positions_no_filter(bybit_client_2, "MIRROR")
    
    total_positions = len(main_positions) + len(mirror_positions)
    
    print(f"\n📊 Total positions found (no filter):")
    print(f"   Main: {len(main_positions)}")
    print(f"   Mirror: {len(mirror_positions)}")
    print(f"   Total: {total_positions}")
    
    # Load monitors
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        # Check which positions have monitors
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
        print(f"   Main: {len(monitored_main)}")
        print(f"   Mirror: {len(monitored_mirror)}")
        print(f"   Total: {len(enhanced_monitors)}")
        
        # Find missing monitors
        missing_main = []
        missing_mirror = []
        
        for pos_key, pos_data in main_positions.items():
            if pos_key not in monitored_main:
                missing_main.append(pos_data)
        
        for pos_key, pos_data in mirror_positions.items():
            if pos_key not in monitored_mirror:
                missing_mirror.append(pos_data)
        
        total_missing = len(missing_main) + len(missing_mirror)
        
        if missing_main:
            print(f"\n❌ Missing MAIN monitors ({len(missing_main)}):")
            for pos in missing_main:
                print(f"   • {pos['symbol']} {pos['side']} - Size: {pos['size']}")
        
        if missing_mirror:
            print(f"\n❌ Missing MIRROR monitors ({len(missing_mirror)}):")
            for pos in missing_mirror:
                print(f"   • {pos['symbol']} {pos['side']} - Size: {pos['size']}")
        
        # Create monitors for missing positions
        if total_missing > 0:
            print(f"\n🔧 Creating {total_missing} missing monitors...")
            
            created_count = 0
            
            # Create main monitors
            for pos in missing_main:
                monitor_key = f"{pos['symbol']}_{pos['side']}_main"
                monitor_data = {
                    'symbol': pos['symbol'],
                    'side': pos['side'],
                    'position_size': pos['size'],
                    'remaining_size': pos['size'],
                    'entry_price': pos['avgPrice'],
                    'avg_price': pos['avgPrice'],
                    'approach': 'enhanced',
                    'tp_orders': {},
                    'sl_order': None,
                    'filled_tps': [],
                    'cancelled_limits': False,
                    'tp1_hit': False,
                    'tp1_info': None,
                    'sl_moved_to_be': False,
                    'sl_move_attempts': 0,
                    'created_at': time.time(),
                    'last_check': time.time(),
                    'limit_orders': [],
                    'limit_orders_cancelled': False,
                    'phase': 'MONITORING',
                    'account_type': 'main',
                    'final_tp_order_id': 'NO_TPS_CONFIGURED',
                    'all_tps_filled': False
                }
                enhanced_monitors[monitor_key] = monitor_data
                created_count += 1
                print(f"   ✅ Created monitor for {pos['symbol']} {pos['side']} (main)")
            
            # Create mirror monitors
            for pos in missing_mirror:
                monitor_key = f"{pos['symbol']}_{pos['side']}_mirror"
                monitor_data = {
                    'symbol': pos['symbol'],
                    'side': pos['side'],
                    'position_size': pos['size'],
                    'remaining_size': pos['size'],
                    'entry_price': pos['avgPrice'],
                    'avg_price': pos['avgPrice'],
                    'approach': 'enhanced',
                    'tp_orders': {},
                    'sl_order': None,
                    'filled_tps': [],
                    'cancelled_limits': False,
                    'tp1_hit': False,
                    'tp1_info': None,
                    'sl_moved_to_be': False,
                    'sl_move_attempts': 0,
                    'created_at': time.time(),
                    'last_check': time.time(),
                    'limit_orders': [],
                    'limit_orders_cancelled': False,
                    'phase': 'MONITORING',
                    'account_type': 'mirror',
                    'final_tp_order_id': 'NO_TPS_CONFIGURED',
                    'all_tps_filled': False
                }
                enhanced_monitors[monitor_key] = monitor_data
                created_count += 1
                print(f"   ✅ Created monitor for {pos['symbol']} {pos['side']} (mirror)")
            
            # Save updated data
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
                pickle.dump(data, f)
            
            print(f"\n✅ Created {created_count} new monitors")
        
        # Create signal file
        print("\n🔄 Creating reload signal...")
        
        signal_file = "reload_monitors.signal"
        with open(signal_file, 'w') as f:
            f.write(f"{time.time()}\n")
            f.write(f"created_missing_monitors: {total_missing}\n")
            f.write(f"total_positions: {total_positions}\n")
            f.write(f"total_monitors: {len(enhanced_monitors)}\n")
            f.write(f"timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        print(f"✅ Created reload signal: {signal_file}")
        
        # Also create force reload
        force_reload_file = "force_reload.trigger"
        with open(force_reload_file, 'w') as f:
            f.write(str(time.time()))
        
        print(f"✅ Created force reload trigger: {force_reload_file}")
        
        # Final summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"\n✅ Successfully synchronized monitors with positions")
        print(f"   Total positions: {total_positions}")
        print(f"   Total monitors: {len(enhanced_monitors)}")
        print(f"   Created: {created_count} new monitors")
        print(f"\n💡 The bot will reload and show the correct count on next cycle")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    create_missing_monitors_and_signal()