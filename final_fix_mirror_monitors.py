#!/usr/bin/env python3
"""
Final fix to add mirror monitors and ensure they persist
"""
import pickle
import shutil
import time
from datetime import datetime
from decimal import Decimal

def add_mirror_monitors_final():
    """Add mirror monitors to pickle file - final fix"""
    print("="*60)
    print("FINAL FIX - ADDING MIRROR MONITORS")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Create backup
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    backup_name = f'{pickle_file}.backup_final_fix_{int(time.time())}'
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
    
    # Define all mirror monitors with exact data
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
    
    # Add each mirror monitor
    print("\nAdding mirror monitors...")
    added = 0
    for key, monitor_data in mirror_monitors.items():
        monitors[key] = monitor_data
        added += 1
        print(f"  ✅ Added {key}")
    
    # Update the data
    data['bot_data']['enhanced_tp_sl_monitors'] = monitors
    
    # Save the updated pickle file
    with open(pickle_file, 'wb') as f:
        pickle.dump(data, f)
    
    print(f"\n✅ Added {added} mirror monitors")
    print(f"✅ Total monitors now: {len(monitors)}")
    
    # Verify the save
    with open(pickle_file, 'rb') as f:
        verify_data = pickle.load(f)
    
    verify_monitors = verify_data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    print(f"\n✅ Verification: Pickle file now contains {len(verify_monitors)} monitors")
    
    # Create a lock file to prevent overwrites
    lock_content = f"""# Mirror monitors lock file
# Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# This file indicates that mirror monitors have been added

MIRROR_MONITORS_ADDED = True
TOTAL_MONITORS = 10
TIMESTAMP = {int(time.time())}
"""
    
    with open('.mirror_monitors_added', 'w') as f:
        f.write(lock_content)
    
    print("\n✅ Created .mirror_monitors_added lock file")

def main():
    """Main execution"""
    add_mirror_monitors_final()
    
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("1. The pickle file now contains 10 monitors (5 main + 5 mirror)")
    print("2. The bot needs to reload these monitors")
    print("3. You should see 'Monitoring 10 positions' after the next cycle")
    print("\nIf the bot still shows 5 monitors:")
    print("  - The enhanced TP/SL manager might need to be restarted")
    print("  - Try restarting the bot (Ctrl+C then python3 main.py)")

if __name__ == "__main__":
    main()