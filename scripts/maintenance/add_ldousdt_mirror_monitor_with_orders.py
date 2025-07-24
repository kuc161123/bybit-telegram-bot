#!/usr/bin/env python3
"""
Add the missing LDOUSDT_Sell_mirror monitor with proper TP/SL order references
"""

import pickle
import time
from decimal import Decimal

def add_ldousdt_mirror_monitor():
    """Add the missing LDOUSDT_Sell_mirror monitor to persistence"""
    
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
    
    # Check if already exists
    if 'LDOUSDT_Sell_mirror' in monitors:
        print("⚠️ LDOUSDT_Sell_mirror already exists!")
        return
    
    # Get data from main monitor for chat_id
    main_monitor = monitors.get('LDOUSDT_Sell_main')
    if not main_monitor:
        print("❌ No LDOUSDT_Sell_main monitor found")
        return
    
    # Create mirror monitor with actual position and order data
    # Position: 129.4 @ $0.7226
    # TP orders: 110.0 + 6.5 + 6.5 + 6.5 = 129.5 (matches position)
    mirror_monitor = {
        'symbol': 'LDOUSDT',
        'side': 'Sell',
        'position_size': Decimal('129.4'),
        'remaining_size': Decimal('129.4'),
        'entry_price': Decimal('0.7226'),
        'avg_price': Decimal('0.7226'),
        'approach': 'conservative',  # Has 4 TPs so it's conservative
        'tp_orders': {
            # Order IDs from the check_ldousdt_mirror_orders.py output
            'efccf0a8-de77-4d76-8fc8-e19b3c2f4cf6': {  # TP1
                'price': Decimal('0.7081'),
                'qty': Decimal('110.0'),
                'percentage': 85
            },
            '8dc6c731-f0f9-4b0f-9e00-c096b0f4fba9': {  # TP2
                'price': Decimal('0.6937'),
                'qty': Decimal('6.5'),
                'percentage': 5
            },
            'dcc42b1f-d1fc-4683-a86a-cbfa6cf7c0f6': {  # TP3
                'price': Decimal('0.7009'),
                'qty': Decimal('6.5'),
                'percentage': 5
            },
            '0c1bc5c0-d7c9-4ffd-8f7f-7c36a59f3d45': {  # TP4
                'price': Decimal('0.6865'),
                'qty': Decimal('6.5'),
                'percentage': 5
            }
        },
        'sl_order': {
            'order_id': 'ce5ed90f-f816-4b81-a02f-8dfbc0c11343',
            'price': Decimal('0.7371'),
            'qty': Decimal('129.4')
        },
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
        'chat_id': main_monitor.get('chat_id'),  # Use same chat_id as main
        'account_type': 'mirror',
        'has_mirror': True
    }
    
    # Add to monitors
    monitors['LDOUSDT_Sell_mirror'] = mirror_monitor
    
    # Save back to pickle
    with open(pkl_path, 'wb') as f:
        pickle.dump(data, f)
    
    print(f"✅ Added LDOUSDT_Sell_mirror monitor")
    print(f"   Position size: 129.4")
    print(f"   Entry price: 0.7226")
    print(f"   TP orders: 4 (85/5/5/5 distribution)")
    print(f"   SL order: 1 @ 0.7371")
    print(f"   Total monitors now: {len(monitors)}")
    
    # List all monitors
    print("\nAll monitors:")
    for key in sorted(monitors.keys()):
        print(f"  {key}")

if __name__ == "__main__":
    add_ldousdt_mirror_monitor()