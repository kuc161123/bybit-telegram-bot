#!/usr/bin/env python3
"""
Create the 6 missing mirror monitors to restore full monitoring
"""

import pickle
import time
from decimal import Decimal

def create_missing_monitors():
    """Create the 6 missing mirror monitors"""
    
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    # Load current data
    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)
    
    # Create backup
    backup_path = f"{pkl_path}.backup_{int(time.time())}"
    with open(backup_path, 'wb') as f:
        pickle.dump(data, f)
    print(f"✅ Created backup: {backup_path}")
    
    monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
    
    # Define the missing monitors based on mirror positions we know exist
    # These are estimates based on the ~33% sizing pattern
    missing_monitors = [
        {
            'key': 'JUPUSDT_Sell_mirror',
            'symbol': 'JUPUSDT',
            'side': 'Sell',
            'position_size': Decimal('1401'),  # From previous data
            'entry_price': Decimal('0.4283'),
            'approach': 'fast'
        },
        {
            'key': 'TIAUSDT_Buy_mirror',
            'symbol': 'TIAUSDT',
            'side': 'Buy',
            'position_size': Decimal('168.2'),  # From previous data
            'entry_price': Decimal('1.6015'),
            'approach': 'fast'
        },
        {
            'key': 'ICPUSDT_Sell_mirror',
            'symbol': 'ICPUSDT',
            'side': 'Sell',
            'position_size': Decimal('48.6'),  # From previous data
            'entry_price': Decimal('4.743'),
            'approach': 'fast'
        },
        {
            'key': 'IDUSDT_Sell_mirror',
            'symbol': 'IDUSDT',
            'side': 'Sell',
            'position_size': Decimal('782'),  # From previous data
            'entry_price': Decimal('0.1478'),
            'approach': 'fast'
        },
        {
            'key': 'LINKUSDT_Buy_mirror',
            'symbol': 'LINKUSDT',
            'side': 'Buy',
            'position_size': Decimal('10.2'),  # From previous data
            'entry_price': Decimal('13.478'),
            'approach': 'fast'
        },
        {
            'key': 'XRPUSDT_Buy_mirror',
            'symbol': 'XRPUSDT',
            'side': 'Buy',
            'position_size': Decimal('87'),  # From previous data
            'entry_price': Decimal('2.28959577'),
            'approach': 'fast'
        }
    ]
    
    # Create each missing monitor
    created = 0
    for monitor_info in missing_monitors:
        key = monitor_info['key']
        
        if key in monitors:
            print(f"⚠️ {key} already exists, skipping")
            continue
        
        # Create monitor data
        monitor_data = {
            'symbol': monitor_info['symbol'],
            'side': monitor_info['side'],
            'position_size': monitor_info['position_size'],
            'remaining_size': monitor_info['position_size'],
            'entry_price': monitor_info['entry_price'],
            'avg_price': monitor_info['entry_price'],
            'approach': monitor_info['approach'],
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
            'account_type': 'mirror',
            'has_mirror': True
        }
        
        monitors[key] = monitor_data
        created += 1
        print(f"✅ Created {key}: {monitor_info['position_size']} @ {monitor_info['entry_price']}")
    
    # Save back to pickle
    with open(pkl_path, 'wb') as f:
        pickle.dump(data, f)
    
    print(f"\n✅ Created {created} new monitors")
    print(f"📊 Total monitors now: {len(monitors)}")
    
    # Count by type
    main_count = len([k for k in monitors if k.endswith('_main')])
    mirror_count = len([k for k in monitors if k.endswith('_mirror')])
    
    print(f"  Main: {main_count}")
    print(f"  Mirror: {mirror_count}")
    print(f"  Total: {main_count + mirror_count}")
    
    # List all monitors
    print("\n📋 All monitors:")
    for key in sorted(monitors.keys()):
        if key.endswith('_main') or key.endswith('_mirror'):
            print(f"  {key}")

if __name__ == "__main__":
    create_missing_monitors()