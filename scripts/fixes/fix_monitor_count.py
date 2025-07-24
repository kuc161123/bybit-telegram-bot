#!/usr/bin/env python3
"""
Script to fix missing monitor count in the dashboard by adding missing fast monitors to monitor_tasks
"""
import pickle
import os
from datetime import datetime
import time

def fix_monitor_count():
    """Fix the missing fast monitors in monitor_tasks"""
    
    # Load the persistence file
    persistence_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    if not os.path.exists(persistence_file):
        print(f"❌ Persistence file not found: {persistence_file}")
        return
    
    print(f"📂 Loading persistence file: {persistence_file}")
    
    # Create backup
    backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{persistence_file}"
    os.system(f"cp {persistence_file} {backup_file}")
    print(f"✅ Created backup: {backup_file}")
    
    # Load data
    with open(persistence_file, 'rb') as f:
        data = pickle.load(f)
    
    bot_data = data.get('bot_data', {})
    chat_data = data.get('chat_data', {})
    
    # Check current monitor_tasks
    monitor_tasks = bot_data.get('monitor_tasks', {})
    print(f"\n📊 Current monitor_tasks count: {len(monitor_tasks)}")
    for key, value in monitor_tasks.items():
        print(f"  - {key}: approach={value.get('approach', 'unknown')}")
    
    # Look for positions in chat_data
    main_chat_id = 5634913742
    main_chat_data = chat_data.get(main_chat_id, {})
    
    print(f"\n🔍 Checking positions in chat_data...")
    
    # Check for TRBUSDT fast position
    trbusdt_fast_pos = main_chat_data.get('position_TRBUSDT_Sell_fast')
    if trbusdt_fast_pos:
        print(f"  ✓ Found TRBUSDT fast position: size={trbusdt_fast_pos.get('last_known_position_size', 0)}")
        
        # Add to monitor_tasks if missing
        monitor_key = f"{main_chat_id}_TRBUSDT_fast"
        if monitor_key not in monitor_tasks:
            monitor_tasks[monitor_key] = {
                'chat_id': main_chat_id,
                'symbol': 'TRBUSDT',
                'approach': 'fast',
                'monitoring_mode': 'BOT-FAST',
                'started_at': time.time(),
                'active': True
            }
            print(f"  ➕ Added {monitor_key} to monitor_tasks")
    
    # Check for BTCUSDT fast position
    btcusdt_fast_pos = main_chat_data.get('position_BTCUSDT_Sell_fast')
    if btcusdt_fast_pos:
        print(f"  ✓ Found BTCUSDT fast position: size={btcusdt_fast_pos.get('last_known_position_size', 0)}")
        
        # Add to monitor_tasks if missing
        monitor_key = f"{main_chat_id}_BTCUSDT_fast"
        if monitor_key not in monitor_tasks:
            monitor_tasks[monitor_key] = {
                'chat_id': main_chat_id,
                'symbol': 'BTCUSDT',
                'approach': 'fast',
                'monitoring_mode': 'BOT-FAST',
                'started_at': time.time(),
                'active': True
            }
            print(f"  ➕ Added {monitor_key} to monitor_tasks")
    
    # Update bot_data
    bot_data['monitor_tasks'] = monitor_tasks
    data['bot_data'] = bot_data
    
    # Save the updated data
    with open(persistence_file, 'wb') as f:
        pickle.dump(data, f)
    
    print(f"\n✅ Updated monitor_tasks count: {len(monitor_tasks)}")
    
    # Show final counts
    fast_count = sum(1 for v in monitor_tasks.values() if v.get('approach') == 'fast')
    conservative_count = sum(1 for v in monitor_tasks.values() if v.get('approach') == 'conservative')
    
    print(f"\n📊 Final monitor counts:")
    print(f"  - Fast monitors: {fast_count}")
    print(f"  - Conservative monitors: {conservative_count}")
    print(f"  - Total primary monitors: {fast_count + conservative_count} ({fast_count}F/{conservative_count}C)")
    
    print(f"\n✅ Monitor count fix completed!")
    print(f"   The dashboard should now show the correct monitor counts.")

if __name__ == "__main__":
    fix_monitor_count()