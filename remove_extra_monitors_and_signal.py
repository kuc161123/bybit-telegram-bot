#!/usr/bin/env python3
"""
Remove extra monitors and create signal file for bot reload
"""

import pickle
import time
import shutil
import os


def remove_extra_monitors_and_signal():
    """Remove extra monitors and create reload signal"""
    
    print("=" * 80)
    print("REMOVING EXTRA MONITORS AND CREATING SIGNAL")
    print("=" * 80)
    
    # Create backup
    backup_file = f"bybit_bot_dashboard_v4.1_enhanced.pkl.backup_remove_extra_{int(time.time())}"
    shutil.copy2('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_file)
    print(f"\n📦 Created backup: {backup_file}")
    
    # Load extra monitors list
    try:
        with open('extra_monitors.txt', 'r') as f:
            lines = f.readlines()
        
        extra_keys = []
        for line in lines[2:]:  # Skip header lines
            key = line.strip()
            if key:
                extra_keys.append(key)
                
    except Exception as e:
        print(f"❌ Error reading extra monitors list: {e}")
        return
    
    print(f"\n📋 Found {len(extra_keys)} extra monitors to remove")
    
    # Load pickle data
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        print(f"❌ Error loading pickle file: {e}")
        return
    
    # Get monitors
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    initial_count = len(enhanced_monitors)
    
    removed_count = 0
    
    for monitor_key in extra_keys:
        if monitor_key in enhanced_monitors:
            monitor_data = enhanced_monitors[monitor_key]
            symbol = monitor_data.get('symbol', 'Unknown')
            side = monitor_data.get('side', 'Unknown')
            
            print(f"\n🗑️  Removing {symbol} {side} (main)")
            del enhanced_monitors[monitor_key]
            removed_count += 1
    
    # Save updated data
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        print(f"\n✅ Removed {removed_count} extra monitors")
        
        # Get final counts
        main_count = sum(1 for m in enhanced_monitors.values() if m.get('account_type', 'main') == 'main')
        mirror_count = sum(1 for m in enhanced_monitors.values() if m.get('account_type', 'main') == 'mirror')
        
        print(f"\n📊 Updated Monitor Count:")
        print(f"   Main monitors: {main_count} (was 24)")
        print(f"   Mirror monitors: {mirror_count} (was 20)")
        print(f"   Total monitors: {len(enhanced_monitors)} (was {initial_count})")
        
    except Exception as e:
        print(f"\n❌ Error saving data: {e}")
        return
    
    # Create reload signal file
    print("\n🔄 Creating reload signal...")
    
    signal_file = "reload_monitors.signal"
    with open(signal_file, 'w') as f:
        f.write(f"{time.time()}\n")
        f.write(f"removed_extra_monitors: {removed_count}\n")
        f.write(f"timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print(f"✅ Created reload signal: {signal_file}")
    
    # Also create a force reload trigger
    force_reload_file = "force_reload.trigger"
    with open(force_reload_file, 'w') as f:
        f.write(str(time.time()))
    
    print(f"✅ Created force reload trigger: {force_reload_file}")
    
    print("\n" + "=" * 80)
    print("COMPLETE!")
    print("=" * 80)
    print(f"\n✅ Successfully removed {removed_count} extra monitors")
    print("✅ Created signal files for bot reload")
    print("\n💡 The bot will now:")
    print("   • Reload monitors on next check cycle")
    print("   • Show correct count: 40 positions (20 main + 20 mirror)")
    print("   • Monitor only active positions")


if __name__ == "__main__":
    remove_extra_monitors_and_signal()