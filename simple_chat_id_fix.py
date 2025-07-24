#!/usr/bin/env python3
"""
Simple script to fix chat_id for 5 specific monitors.
Keeps it straightforward with basic pickle operations.
"""

import pickle
import shutil
from datetime import datetime
import time
from pathlib import Path

def main():
    """Fix chat_id for 5 specific monitors."""
    
    # File paths
    pickle_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    
    # The 5 monitors that need chat_id
    monitors_to_fix = [
        "AUCTIONUSDT_Buy_main",
        "AUCTIONUSDT_Buy_mirror",
        "CRVUSDT_Buy_mirror",
        "SEIUSDT_Buy_mirror",
        "ARBUSDT_Buy_mirror"
    ]
    
    chat_id = 5634913742
    
    print("Starting simple chat_id fix for 5 monitors...")
    
    # Step 1: Create backup
    backup_name = f"{pickle_file}.backup_{int(time.time())}"
    print(f"Creating backup: {backup_name}")
    shutil.copy2(pickle_file, backup_name)
    print("✓ Backup created")
    
    # Step 2: Load pickle data
    print("\nLoading pickle data...")
    with open(pickle_file, 'rb') as f:
        data = pickle.load(f)
    print("✓ Data loaded")
    
    # Step 3: Update the 5 monitors
    print("\nUpdating monitors...")
    bot_data = data.get('bot_data', {})
    monitor_tasks = bot_data.get('monitor_tasks', {})
    
    updated_count = 0
    for monitor_key in monitors_to_fix:
        if monitor_key in monitor_tasks:
            print(f"  Updating {monitor_key}...")
            monitor_tasks[monitor_key]['chat_id'] = chat_id
            updated_count += 1
            print(f"  ✓ {monitor_key} updated with chat_id: {chat_id}")
        else:
            print(f"  ⚠️  {monitor_key} not found in monitor_tasks")
    
    print(f"\nUpdated {updated_count} monitors")
    
    # Step 4: Save pickle (simple save)
    print("\nSaving changes...")
    with open(pickle_file, 'wb') as f:
        pickle.dump(data, f)
    print("✓ Changes saved")
    
    # Step 5: Create reload signal files
    print("\nCreating reload signals...")
    Path("force_reload.trigger").touch()
    Path("reload_monitors.signal").touch() 
    Path("force_reload_monitors.signal").touch()
    print("✓ Reload signals created")
    
    # Step 6: Verify changes
    print("\nVerifying changes...")
    with open(pickle_file, 'rb') as f:
        verify_data = pickle.load(f)
    
    verify_bot_data = verify_data.get('bot_data', {})
    verify_monitor_tasks = verify_bot_data.get('monitor_tasks', {})
    
    print("\nVerification results:")
    all_good = True
    for monitor_key in monitors_to_fix:
        if monitor_key in verify_monitor_tasks:
            monitor = verify_monitor_tasks[monitor_key]
            has_chat_id = monitor.get('chat_id') == chat_id
            print(f"  {monitor_key}: {'✓' if has_chat_id else '✗'} chat_id = {monitor.get('chat_id')}")
            if not has_chat_id:
                all_good = False
        else:
            print(f"  {monitor_key}: ✗ Not found")
            all_good = False
    
    if all_good:
        print("\n✅ All monitors successfully updated!")
        print(f"\nBackup saved as: {backup_name}")
        print("Reload signals created - bot should reload monitors on next cycle")
    else:
        print("\n❌ Some monitors were not updated correctly")
        print(f"You can restore from backup: {backup_name}")
    
    return all_good

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)