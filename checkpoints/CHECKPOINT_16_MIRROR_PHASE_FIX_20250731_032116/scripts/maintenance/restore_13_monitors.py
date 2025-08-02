#!/usr/bin/env python3
"""
Restore the pickle file with 13 monitors
"""
import pickle
from datetime import datetime
from decimal import Decimal

# First, let's manually create the 13 monitors with new format
print("Creating 13 monitors with account-aware keys...")

# Load current data
with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
    data = pickle.load(f)

# Get the 7 existing monitors (they don't have account suffix)
old_monitors = data['bot_data']['enhanced_tp_sl_monitors']

# Create new monitors dictionary with account-aware keys
new_monitors = {}

# First, migrate existing 7 monitors (they seem to be main account)
for old_key, monitor_data in old_monitors.items():
    # These are main account monitors based on the data
    new_key = f"{old_key}_main"
    monitor_data['account_type'] = 'main'
    monitor_data['chat_id'] = 5634913742  # Set chat_id for alerts
    new_monitors[new_key] = monitor_data
    print(f"Migrated: {old_key} → {new_key}")

# Now add the 6 mirror monitors (same positions but for mirror account)
mirror_positions = [
    ('ICPUSDT', 'Sell', '24.3', '4.743'),
    ('IDUSDT', 'Sell', '391', '0.1478'),
    ('JUPUSDT', 'Sell', '1401', '0.4283'),
    ('TIAUSDT', 'Buy', '168.2', '1.6015'),
    ('LINKUSDT', 'Buy', '10.2', '13.478'),
    ('XRPUSDT', 'Buy', '87', '2.28959577')
]

for symbol, side, size, price in mirror_positions:
    monitor_key = f"{symbol}_{side}_mirror"
    
    # Check if we already have this monitor from main
    main_key = f"{symbol}_{side}"
    if main_key in old_monitors:
        # Copy from main monitor
        monitor_data = old_monitors[main_key].copy()
        # Update for mirror
        monitor_data['position_size'] = Decimal(size)
        monitor_data['remaining_size'] = Decimal(size)
        monitor_data['account_type'] = 'mirror'
        monitor_data['chat_id'] = None  # No alerts for mirror
        monitor_data['has_mirror'] = False
    else:
        # Create new monitor
        monitor_data = {
            'symbol': symbol,
            'side': side,
            'position_size': Decimal(size),
            'remaining_size': Decimal(size),
            'entry_price': Decimal(price),
            'avg_price': Decimal(price),
            'approach': 'fast',
            'tp_orders': {},
            'sl_order': None,
            'filled_tps': [],
            'cancelled_limits': False,
            'tp1_hit': False,
            'tp1_info': None,
            'sl_moved_to_be': False,
            'sl_move_attempts': 0,
            'created_at': datetime.now().timestamp(),
            'last_check': datetime.now().timestamp(),
            'limit_orders': [],
            'limit_orders_cancelled': False,
            'phase': 'MONITORING',
            'chat_id': None,  # No alerts for mirror
            'account_type': 'mirror',
            'has_mirror': False
        }
    
    new_monitors[monitor_key] = monitor_data
    print(f"Created mirror: {monitor_key}")

# Update the data
data['bot_data']['enhanced_tp_sl_monitors'] = new_monitors

# Save
with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
    pickle.dump(data, f)

print(f"\n✅ Successfully created {len(new_monitors)} monitors!")
print(f"   Main account: {sum(1 for k in new_monitors if k.endswith('_main'))}")
print(f"   Mirror account: {sum(1 for k in new_monitors if k.endswith('_mirror'))}")

# Create signal file
with open('reload_enhanced_monitors.signal', 'w') as f:
    f.write(str(datetime.now().timestamp()))
print("\n✅ Created signal file for reload")