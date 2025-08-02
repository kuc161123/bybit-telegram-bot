#!/usr/bin/env python3
"""
FORCE CLEAN ALL MONITORS - Nuclear option to completely reset monitor system
This will remove ALL monitors and force the system to start fresh
"""
import pickle
import os
import sys
import asyncio
from datetime import datetime

async def nuclear_monitor_cleanup():
    """Completely wipe all monitors and force fresh start"""
    
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    # Kill any remaining processes
    os.system("pkill -9 -f 'python.*main.py' 2>/dev/null || true")
    os.system("pkill -9 -f 'bybit.*bot' 2>/dev/null || true")
    
    if not os.path.exists(pickle_file):
        print(f"❌ Pickle file not found: {pickle_file}")
        return
    
    # Create timestamped backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{pickle_file}.backup_nuclear_cleanup_{timestamp}"
    try:
        import shutil
        shutil.copy2(pickle_file, backup_file)
        print(f"🔒 Created nuclear backup: {backup_file}")
    except Exception as e:
        print(f"⚠️ Could not create backup: {e}")
    
    # Load data
    try:
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        print("✅ Loaded bot data for nuclear cleanup")
    except Exception as e:
        print(f"❌ Failed to load pickle data: {e}")
        return
    
    bot_data = data.get('bot_data', {})
    
    # NUCLEAR OPTION: Completely wipe all monitor data
    original_monitor_count = len(bot_data.get('monitor_tasks', {}))
    print(f"🔥 NUCLEAR CLEANUP: Removing ALL {original_monitor_count} monitors")
    
    # Clear all monitor-related data
    bot_data['monitor_tasks'] = {}
    
    # Also clear any cached monitor data that might exist
    for key in list(bot_data.keys()):
        if 'monitor' in key.lower():
            print(f"🗑️ Clearing monitor cache key: {key}")
            del bot_data[key]
    
    # Force clear any position monitor references
    if 'position_monitors' in bot_data:
        print("🗑️ Clearing position_monitors")
        bot_data['position_monitors'] = {}
    
    if 'enhanced_monitors' in bot_data:
        print("🗑️ Clearing enhanced_monitors")
        bot_data['enhanced_monitors'] = {}
    
    # Save the nuclear-cleaned data
    try:
        # Atomic write for safety
        temp_file = f"{pickle_file}.tmp_nuclear_{timestamp}"
        with open(temp_file, 'wb') as f:
            pickle.dump(data, f)
        
        # Verify the file
        with open(temp_file, 'rb') as f:
            test_data = pickle.load(f)
            print(f"✅ Verified nuclear cleanup: {len(test_data.get('bot_data', {}).get('monitor_tasks', {}))} monitors remaining")
        
        # Atomic replace
        os.rename(temp_file, pickle_file)
        
        print(f"🔥 NUCLEAR CLEANUP COMPLETE!")
        print(f"   - Original monitors: {original_monitor_count}")
        print(f"   - Remaining monitors: 0")
        print(f"   - All monitor data wiped")
        
    except Exception as e:
        print(f"❌ Nuclear cleanup failed: {e}")
        return
    
    # Create force reload signals
    try:
        with open('.force_load_all_monitors', 'w') as f:
            f.write(f"Nuclear cleanup completed at {timestamp}\n")
        print("🔄 Created force reload signal")
        
        with open('.reload_enhanced_monitors.signal', 'w') as f:
            f.write(f"Nuclear cleanup reload at {timestamp}\n")
        print("🔄 Created enhanced monitor reload signal")
        
    except Exception as e:
        print(f"⚠️ Could not create signal files: {e}")
    
    print("\n🎉 NUCLEAR MONITOR CLEANUP COMPLETE!")
    print("🔄 The bot will now have to recreate monitors from actual positions")
    print("📊 Expected result: Only monitors for positions that actually exist")

if __name__ == "__main__":
    asyncio.run(nuclear_monitor_cleanup())