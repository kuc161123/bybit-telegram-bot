#!/usr/bin/env python3
"""
Check what the bot is actually monitoring
"""

import pickle
import asyncio
from datetime import datetime

async def check_monitor_count():
    """Check actual monitor count from bot's perspective"""
    
    # Import the enhanced TP/SL manager as the bot would
    try:
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        
        # Check active monitors in the manager
        active_monitors = enhanced_tp_sl_manager.position_monitors
        print(f"🔍 Active monitors in enhanced_tp_sl_manager: {len(active_monitors)}")
        
        if active_monitors:
            print("\nActive monitor tasks:")
            for key, info in active_monitors.items():
                task = info.get('task')
                status = "Running" if task and not task.done() else "Stopped"
                print(f"  - {key}: {status}")
    except Exception as e:
        print(f"❌ Could not import enhanced_tp_sl_manager: {e}")
    
    # Check pickle file
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)
    
    monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
    print(f"\n📊 Monitors in pickle file: {len(monitors)}")
    
    # Group by account
    main_monitors = [k for k in monitors if k.endswith('_main')]
    mirror_monitors = [k for k in monitors if k.endswith('_mirror')]
    
    print(f"  Main account: {len(main_monitors)}")
    print(f"  Mirror account: {len(mirror_monitors)}")
    
    # Check for LDOUSDT specifically
    ldousdt_monitors = [k for k in monitors if k.startswith('LDOUSDT')]
    print(f"\n🔍 LDOUSDT monitors found: {len(ldousdt_monitors)}")
    for monitor in ldousdt_monitors:
        m = monitors[monitor]
        print(f"  - {monitor}: size={m.get('position_size')}, last_check={m.get('last_check')}")
    
    # Check monitor_tasks
    tasks = data['bot_data'].get('monitor_tasks', {})
    print(f"\n📋 Dashboard monitor tasks: {len(tasks)}")
    
    # The bot might be counting differently
    # Let's simulate how the bot counts
    print("\n🤔 Possible counting methods:")
    
    # Method 1: Count enhanced monitors with phase=MONITORING
    monitoring_count = sum(1 for m in monitors.values() if m.get('phase') == 'MONITORING')
    print(f"1. Monitors in MONITORING phase: {monitoring_count}")
    
    # Method 2: Count monitors with last_check > 0
    checked_count = sum(1 for m in monitors.values() if m.get('last_check', 0) > 0)
    print(f"2. Monitors with last_check > 0: {checked_count}")
    
    # Method 3: Count unique symbols
    unique_symbols = set()
    for key in monitors:
        parts = key.split('_')
        if len(parts) >= 2:
            symbol = parts[0]
            unique_symbols.add(symbol)
    print(f"3. Unique symbols being monitored: {len(unique_symbols)}")
    
    # Method 4: Count by checking for active positions
    print("\n🔍 Let's check what the sync_existing_positions might see...")
    
    # The bot might be looking at dashboard tasks instead
    active_tasks = sum(1 for t in tasks.values() if t.get('active', False))
    print(f"4. Active dashboard tasks: {active_tasks}")
    
    return len(monitors)

if __name__ == "__main__":
    count = asyncio.run(check_monitor_count())
    print(f"\n✅ Total monitors in pickle: {count}")