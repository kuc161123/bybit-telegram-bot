#!/usr/bin/env python3
"""
Add the missing LDOUSDT_Sell_mirror monitor
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
    
    # Get data from main monitor
    main_monitor = monitors.get('LDOUSDT_Sell_main')
    if not main_monitor:
        print("❌ No LDOUSDT_Sell_main monitor found")
        return
    
    # Create mirror monitor based on known mirror position data
    # From check_all_mirror_positions.py: Mirror: Sell 64.7 @ $0.7181
    mirror_monitor = {
        'symbol': 'LDOUSDT',
        'side': 'Sell',
        'position_size': Decimal('64.7'),
        'remaining_size': Decimal('64.7'),
        'entry_price': Decimal('0.7181'),
        'avg_price': Decimal('0.7181'),
        'approach': 'fast',
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
    print(f"   Position size: 64.7")
    print(f"   Entry price: 0.7181")
    print(f"   Total monitors now: {len(monitors)}")
    
    # List all monitors
    print("\nAll monitors:")
    for key in sorted(monitors.keys()):
        print(f"  {key}")

if __name__ == "__main__":
    add_ldousdt_mirror_monitor()