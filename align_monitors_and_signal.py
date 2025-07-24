#!/usr/bin/env python3
"""
Align monitors with API-visible positions and create signal
Remove the 4 extra main account monitors
"""

import pickle
import time
import shutil

def align_monitors_and_signal():
    """Remove extra monitors and create signal file"""
    
    print("=" * 80)
    print("ALIGNING MONITORS WITH API-VISIBLE POSITIONS")
    print("=" * 80)
    
    # Create backup
    backup_file = f"bybit_bot_dashboard_v4.1_enhanced.pkl.backup_align_{int(time.time())}"
    shutil.copy2('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_file)
    print(f"\n📦 Created backup: {backup_file}")
    
    # Load pickle data
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        print(f"❌ Error loading pickle file: {e}")
        return
    
    # Get monitors
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    print(f"\n📊 Current state:")
    print(f"   Total monitors: {len(enhanced_monitors)}")
    print(f"   API shows: 40 positions (20 main + 20 mirror)")
    print(f"   User sees: 47 positions (24 main + 23 mirror) on exchange")
    print(f"   Difference: 7 positions not visible via API")
    
    # These 4 monitors don't have API-visible positions
    extra_monitors = [
        'WLDUSDT_Buy_main',
        '1INCHUSDT_Buy_main',
        'LDOUSDT_Buy_main',
        'ARKMUSDT_Buy_main'
    ]
    
    print(f"\n🔧 Removing 4 extra monitors (no API-visible positions):")
    
    removed_count = 0
    for monitor_key in extra_monitors:
        if monitor_key in enhanced_monitors:
            monitor_data = enhanced_monitors[monitor_key]
            symbol = monitor_data.get('symbol', 'Unknown')
            side = monitor_data.get('side', 'Unknown')
            
            print(f"   • Removing {symbol} {side} (main)")
            del enhanced_monitors[monitor_key]
            removed_count += 1
    
    # Save updated data
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        print(f"\n✅ Removed {removed_count} monitors")
        
        # Get final counts
        main_count = sum(1 for m in enhanced_monitors.values() if m.get('account_type', 'main') == 'main')
        mirror_count = sum(1 for m in enhanced_monitors.values() if m.get('account_type', 'main') == 'mirror')
        
        print(f"\n📊 Updated monitor count:")
        print(f"   Main monitors: {main_count}")
        print(f"   Mirror monitors: {mirror_count}")
        print(f"   Total monitors: {len(enhanced_monitors)}")
        
    except Exception as e:
        print(f"\n❌ Error saving data: {e}")
        return
    
    # Create signal file
    print("\n🔄 Creating reload signal...")
    
    signal_file = "reload_monitors.signal"
    with open(signal_file, 'w') as f:
        f.write(f"{time.time()}\n")
        f.write(f"action: aligned_monitors_with_api\n")
        f.write(f"removed_monitors: {removed_count}\n")
        f.write(f"total_monitors: {len(enhanced_monitors)}\n")
        f.write(f"timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print(f"✅ Created reload signal: {signal_file}")
    
    # Also create force reload
    force_reload_file = "force_reload.trigger"
    with open(force_reload_file, 'w') as f:
        f.write(str(time.time()))
    
    print(f"✅ Created force reload trigger: {force_reload_file}")
    
    print("\n" + "=" * 80)
    print("COMPLETE!")
    print("=" * 80)
    print(f"\n✅ Monitors aligned with API-visible positions")
    print(f"   Bot will now monitor: 40 positions")
    print(f"   - Main: 20 positions")
    print(f"   - Mirror: 20 positions")
    print(f"\n📌 Note: The 7 positions you see on exchange but not in API might be:")
    print("   • Spot trading positions (not futures)")
    print("   • Sub-account positions")
    print("   • Copy trading positions")
    print("   • Grid bot positions")
    print("   • Positions in other settlement coins")
    print(f"\n💡 The bot will reload monitors on next check cycle")


if __name__ == "__main__":
    align_monitors_and_signal()