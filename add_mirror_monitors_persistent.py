#!/usr/bin/env python3
"""
Add mirror monitors and ensure they persist
"""
import pickle
import shutil
import time
from datetime import datetime
from decimal import Decimal

def add_mirror_monitors_persistent():
    """Add mirror monitors to pickle file with persistence check"""
    print("="*60)
    print("ADDING MIRROR MONITORS WITH PERSISTENCE")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Create backup
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    backup_name = f'{pickle_file}.backup_with_mirrors_{int(time.time())}'
    shutil.copy(pickle_file, backup_name)
    print(f"✅ Created backup: {backup_name}")
    
    # Load current data
    with open(pickle_file, 'rb') as f:
        data = pickle.load(f)
    
    # Ensure structure exists
    if 'bot_data' not in data:
        data['bot_data'] = {}
    
    if 'enhanced_tp_sl_monitors' not in data['bot_data']:
        data['bot_data']['enhanced_tp_sl_monitors'] = {}
    
    monitors = data['bot_data']['enhanced_tp_sl_monitors']
    
    print(f"\nCurrent monitors: {len(monitors)}")
    
    # Check why monitors might be missing
    print("\nChecking for issues:")
    
    # Look for any flags that might cause monitor removal
    if 'force_monitor_reload' in data.get('bot_data', {}):
        print("  ⚠️  Found force_monitor_reload flag")
        del data['bot_data']['force_monitor_reload']
    
    if 'reload_timestamp' in data.get('bot_data', {}):
        print("  ⚠️  Found reload_timestamp")
        del data['bot_data']['reload_timestamp']
    
    # Define all mirror monitors
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
    
    # Save the updated pickle file
    with open(pickle_file, 'wb') as f:
        pickle.dump(data, f)
    
    print(f"\n✅ Added {added} mirror monitors")
    print(f"✅ Total monitors now: {len(monitors)}")
    
    # Verify the save
    with open(pickle_file, 'rb') as f:
        verify_data = pickle.load(f)
    
    verify_monitors = verify_data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    print(f"\n✅ Verification: Pickle file contains {len(verify_monitors)} monitors")
    
    # Create a protection file
    protection_content = f"""# Mirror Monitor Protection
# Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# This file indicates mirror monitors should be preserved

PRESERVE_MIRROR_MONITORS = True
MIRROR_MONITOR_COUNT = 5
TOTAL_EXPECTED_MONITORS = 10
"""
    
    with open('.preserve_mirror_monitors', 'w') as f:
        f.write(protection_content)
    
    print("\n✅ Created .preserve_mirror_monitors protection file")

def check_why_monitors_removed():
    """Check why mirror monitors might be getting removed"""
    print("\n" + "="*60)
    print("INVESTIGATING MONITOR REMOVAL")
    print("="*60)
    
    print("\nPossible causes:")
    print("1. Position sync only checks main account")
    print("2. Orphan cleanup might remove monitors without positions")
    print("3. Integrity check might be reverting changes")
    print("4. Enhanced TP/SL manager only loads main monitors")
    
    print("\nThe key issue:")
    print("The bot logs show:")
    print('  INFO - 🔍 Found 5 persisted monitors')
    print('  INFO - 🔍 Monitor keys: [only main monitors listed]')
    print("\nThis means the loading logic is filtering out mirror monitors!")

def main():
    """Main execution"""
    add_mirror_monitors_persistent()
    check_why_monitors_removed()
    
    print("\n" + "="*60)
    print("SOLUTION")
    print("="*60)
    print("The enhanced TP/SL manager is filtering out mirror monitors during load.")
    print("Even though they're in the pickle file, they're not being loaded.")
    print("\nTo fix this permanently, the loading logic needs to be modified")
    print("to include mirror monitors, not just main monitors.")

if __name__ == "__main__":
    main()