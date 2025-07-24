#!/usr/bin/env python3
"""
Trigger immediate monitor reload
"""
import os
import time
from datetime import datetime

# Create multiple trigger files to ensure reload
trigger_files = [
    'reload_monitors.signal',
    'force_reload.trigger',
    'force_reload_monitors.signal',
    'monitor_reload_trigger.signal'
]

print("Creating monitor reload triggers...")

for trigger_file in trigger_files:
    with open(trigger_file, 'w') as f:
        f.write(str(datetime.now().timestamp()))
    print(f"✅ Created: {trigger_file}")

print("\n🔄 Reload triggers created.")
print("The bot should reload monitors on the next cycle (within 5-12 seconds).")
print("\nTo verify, check the logs for:")
print("  - 'Loading monitors from persistence'")
print("  - 'Found X persisted monitors'")
print("  - 'ZRXUSDT' with 'tp1_hit'")