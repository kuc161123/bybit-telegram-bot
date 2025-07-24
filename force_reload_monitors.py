#!/usr/bin/env python3
"""
Force reload monitors and ensure mirror monitors are loaded
"""
import os
import pickle
import shutil
from datetime import datetime
import time
from decimal import Decimal

def check_and_fix_monitors():
    """Check current monitors and add missing ones"""
    print("="*60)
    print("FORCE RELOAD MONITORS")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Create backup
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    backup_name = f'{pickle_file}.backup_force_reload_{int(time.time())}'
    shutil.copy(pickle_file, backup_name)
    print(f"✅ Created backup: {backup_name}")
    
    # Load current data
    with open(pickle_file, 'rb') as f:
        data = pickle.load(f)
    
    # Get current monitors
    if 'bot_data' not in data:
        data['bot_data'] = {}
    
    if 'enhanced_tp_sl_monitors' not in data['bot_data']:
        data['bot_data']['enhanced_tp_sl_monitors'] = {}
    
    monitors = data['bot_data']['enhanced_tp_sl_monitors']
    
    print(f"\nCurrent monitors: {len(monitors)}")
    for key in monitors.keys():
        print(f"  - {key}")
    
    # Define mirror monitors to add
    mirror_monitors = {
        'COTIUSDT_Buy_mirror': {
            'symbol': 'COTIUSDT',
            'side': 'Buy',
            'position_size': Decimal('124'),
            'remaining_size': Decimal('124'),
            'entry_price': Decimal('0.05125'),
            'avg_price': Decimal('0.05125'),
            'approach': 'conservative',
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
            'chat_id': None,
            'account_type': 'mirror'
        },
        'CAKEUSDT_Buy_mirror': {
            'symbol': 'CAKEUSDT',
            'side': 'Buy',
            'position_size': Decimal('27.5'),
            'remaining_size': Decimal('27.5'),
            'entry_price': Decimal('2.29'),
            'avg_price': Decimal('2.29'),
            'approach': 'conservative',
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
            'chat_id': None,
            'account_type': 'mirror'
        },
        'SNXUSDT_Buy_mirror': {
            'symbol': 'SNXUSDT',
            'side': 'Buy',
            'position_size': Decimal('112'),
            'remaining_size': Decimal('112'),
            'entry_price': Decimal('0.57089098'),
            'avg_price': Decimal('0.57089098'),
            'approach': 'conservative',
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
            'chat_id': None,
            'account_type': 'mirror'
        },
        '1INCHUSDT_Buy_mirror': {
            'symbol': '1INCHUSDT',
            'side': 'Buy',
            'position_size': Decimal('328.7'),
            'remaining_size': Decimal('328.7'),
            'entry_price': Decimal('0.2012'),
            'avg_price': Decimal('0.2012'),
            'approach': 'conservative',
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
            'chat_id': None,
            'account_type': 'mirror'
        },
        'SUSHIUSDT_Buy_mirror': {
            'symbol': 'SUSHIUSDT',
            'side': 'Buy',
            'position_size': Decimal('107.7'),
            'remaining_size': Decimal('107.7'),
            'entry_price': Decimal('0.6166'),
            'avg_price': Decimal('0.6166'),
            'approach': 'conservative',
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
            'chat_id': None,
            'account_type': 'mirror'
        }
    }
    
    # Add mirror monitors
    print("\nAdding mirror monitors...")
    added = 0
    for key, monitor_data in mirror_monitors.items():
        if key not in monitors:
            monitors[key] = monitor_data
            added += 1
            print(f"  ✅ Added {key}")
    
    # Save updated data
    with open(pickle_file, 'wb') as f:
        pickle.dump(data, f)
    
    print(f"\n✅ Added {added} mirror monitors")
    print(f"✅ Total monitors now: {len(monitors)}")
    
    # Create force reload signal
    signal_content = f"""# FORCE RELOAD SIGNAL
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# This file signals the bot to force reload monitors

FORCE_RELOAD = True
TIMESTAMP = {int(time.time())}
EXPECTED_MONITORS = 10
ACTION = "RELOAD_ALL_MONITORS"

# Monitor breakdown
MAIN_MONITORS = 5
MIRROR_MONITORS = 5

# Positions
POSITIONS = [
    "COTIUSDT_Buy_main",
    "CAKEUSDT_Buy_main", 
    "SNXUSDT_Buy_main",
    "1INCHUSDT_Buy_main",
    "SUSHIUSDT_Buy_main",
    "COTIUSDT_Buy_mirror",
    "CAKEUSDT_Buy_mirror",
    "SNXUSDT_Buy_mirror", 
    "1INCHUSDT_Buy_mirror",
    "SUSHIUSDT_Buy_mirror"
]
"""
    
    with open('force_reload_monitors.signal', 'w') as f:
        f.write(signal_content)
    
    print("\n✅ Created force_reload_monitors.signal")
    
    # Also update the monitor_tasks if they exist
    if 'monitor_tasks' in data['bot_data']:
        print("\nChecking monitor_tasks...")
        monitor_tasks = data['bot_data']['monitor_tasks']
        print(f"Found {len(monitor_tasks)} monitor tasks")

def main():
    """Main execution"""
    check_and_fix_monitors()
    
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("1. The pickle file now contains 10 monitors")
    print("2. The bot should reload them on the next cycle")
    print("3. If not showing 10 monitors, restart the bot")
    print("\nTo restart the bot:")
    print("  1. Press Ctrl+C in the terminal")
    print("  2. Run: python3 main.py")

if __name__ == "__main__":
    main()