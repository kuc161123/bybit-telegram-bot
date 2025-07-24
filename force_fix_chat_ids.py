#!/usr/bin/env python3
"""
Force fix chat_id values with verification at each step.
"""

import pickle
from datetime import datetime
import shutil

def force_fix_chat_ids():
    """Force fix monitors with None chat_id."""
    
    print("=" * 80)
    print("FORCE FIXING MONITORS WITH NONE CHAT_ID")
    print("=" * 80)
    
    # Load pickle file
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    # Create backup
    backup_file = f"{pickle_file}.backup_force_fix_{int(datetime.now().timestamp())}"
    shutil.copy2(pickle_file, backup_file)
    print(f"✓ Created backup: {backup_file}")
    
    try:
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        print(f"✓ Successfully loaded {pickle_file}")
    except Exception as e:
        print(f"✗ Error loading pickle file: {e}")
        return
    
    # Navigate to enhanced_tp_sl_monitors
    bot_data = data.get('bot_data', {})
    enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
    
    print(f"\n📊 Total enhanced monitors: {len(enhanced_monitors)}")
    
    # Specific monitors to fix
    monitors_to_fix = [
        'AUCTIONUSDT_Buy_main',
        'AUCTIONUSDT_Buy_mirror',
        'CRVUSDT_Buy_mirror',
        'SEIUSDT_Buy_mirror',
        'ARBUSDT_Buy_mirror'
    ]
    
    # The correct chat_id to use
    correct_chat_id = 5634913742
    
    print(f"\n🔧 Forcing chat_id = {correct_chat_id} for specific monitors...")
    
    fixed_count = 0
    for monitor_key in monitors_to_fix:
        if monitor_key in enhanced_monitors:
            monitor = enhanced_monitors[monitor_key]
            
            # Debug: Show current state
            print(f"\n📍 {monitor_key}:")
            print(f"   - Current chat_id: {monitor.get('chat_id')} (type: {type(monitor.get('chat_id'))})")
            
            # Force set the chat_id
            monitor['chat_id'] = correct_chat_id
            fixed_count += 1
            
            # Verify immediately
            print(f"   - New chat_id: {monitor.get('chat_id')} (type: {type(monitor.get('chat_id'))})")
        else:
            print(f"\n❌ Monitor {monitor_key} not found!")
    
    # Also check for any other monitors with None chat_id
    print(f"\n🔍 Checking all monitors for None chat_id...")
    for key, monitor in enhanced_monitors.items():
        if isinstance(monitor, dict):
            chat_id = monitor.get('chat_id')
            if chat_id is None or chat_id == 'None':
                print(f"   - Found {key} with chat_id: {chat_id}")
                monitor['chat_id'] = correct_chat_id
                fixed_count += 1
    
    # Update the data structure
    data['bot_data']['enhanced_tp_sl_monitors'] = enhanced_monitors
    
    # Save the updated data
    print(f"\n💾 Saving changes...")
    try:
        with open(pickle_file, 'wb') as f:
            pickle.dump(data, f)
        print(f"✓ Successfully saved {fixed_count} fixes to {pickle_file}")
    except Exception as e:
        print(f"✗ Error saving pickle file: {e}")
        return
    
    # Re-load and verify
    print(f"\n🔍 Re-loading file to verify fixes...")
    try:
        with open(pickle_file, 'rb') as f:
            verify_data = pickle.load(f)
        
        verify_bot_data = verify_data.get('bot_data', {})
        verify_monitors = verify_bot_data.get('enhanced_tp_sl_monitors', {})
        
        print(f"\n✅ Verification results:")
        for monitor_key in monitors_to_fix:
            if monitor_key in verify_monitors:
                monitor = verify_monitors[monitor_key]
                chat_id = monitor.get('chat_id')
                print(f"   - {monitor_key}: chat_id = {chat_id}")
        
        # Count None chat_ids
        none_count = 0
        for key, monitor in verify_monitors.items():
            if isinstance(monitor, dict) and monitor.get('chat_id') is None:
                none_count += 1
        
        print(f"\n📊 Final statistics:")
        print(f"   - Monitors with None chat_id: {none_count}")
        
    except Exception as e:
        print(f"✗ Error during verification: {e}")
    
    print("\n" + "=" * 80)
    print("FORCE FIX COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    force_fix_chat_ids()