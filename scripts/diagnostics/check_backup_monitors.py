#!/usr/bin/env python3
"""
Check monitors in backup file
"""
import pickle

# Check backup file
with open('bybit_bot_dashboard_v4.1_enhanced.pkl.backup_collision_fix_1751961750', 'rb') as f:
    data = pickle.load(f)

monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
print(f"Monitors in backup: {len(monitors)}")
for key in sorted(monitors.keys()):
    print(f"  {key}")

# Also check if they have the new format
new_format = sum(1 for k in monitors if '_main' in k or '_mirror' in k)
print(f"\nMonitors with new format: {new_format}")

if new_format == 13:
    print("\n✅ This backup has all 13 monitors with new format!")
    # Restore it
    import shutil
    shutil.copy('bybit_bot_dashboard_v4.1_enhanced.pkl.backup_collision_fix_1751961750', 
                'bybit_bot_dashboard_v4.1_enhanced.pkl')
    print("✅ Restored backup with 13 monitors!")