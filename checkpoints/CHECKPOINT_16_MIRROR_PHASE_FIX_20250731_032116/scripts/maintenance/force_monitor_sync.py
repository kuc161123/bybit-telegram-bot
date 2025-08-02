#!/usr/bin/env python3
"""
Force the bot to sync and recognize all monitors including LDOUSDT_Sell_mirror
"""

import pickle
import time
from decimal import Decimal

def force_monitor_sync():
    """Force immediate monitor sync by updating pickle state"""
    
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    # Load current data
    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)
    
    monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
    
    print("📊 Current Enhanced TP/SL monitors:")
    print(f"Total count: {len(monitors)}")
    
    # Count by account type
    main_count = sum(1 for k in monitors if k.endswith('_main'))
    mirror_count = sum(1 for k in monitors if k.endswith('_mirror'))
    
    print(f"Main account: {main_count}")
    print(f"Mirror account: {mirror_count}")
    print(f"Total: {main_count + mirror_count}")
    
    # List all monitors
    print("\nAll monitors:")
    for key in sorted(monitors.keys()):
        m = monitors[key]
        print(f"  - {key}: {m.get('position_size', 'N/A')} @ {m.get('entry_price', 'N/A')}")
    
    # Force all monitors to need immediate check
    print("\n🔄 Forcing immediate check on all monitors...")
    for key, monitor in monitors.items():
        monitor['last_check'] = 0  # Force immediate check
        monitor['phase'] = 'MONITORING'  # Ensure monitoring phase
    
    # Update monitor_tasks to match
    if 'monitor_tasks' not in data['bot_data']:
        data['bot_data']['monitor_tasks'] = {}
    
    # Clear and rebuild monitor_tasks
    print("\n🔄 Rebuilding monitor_tasks...")
    tasks = data['bot_data']['monitor_tasks']
    
    # Add all monitors to tasks
    for monitor_key, monitor_data in monitors.items():
        # Parse monitor key
        parts = monitor_key.split('_')
        if len(parts) >= 3:
            symbol = parts[0] + 'USDT'  # e.g., LDO -> LDOUSDT
            side = parts[1]
            account = parts[2]
            
            # Determine approach from monitor data
            approach = monitor_data.get('approach', 'fast')
            
            # Create task key
            task_key = f"None_{symbol}_{approach}"
            if account == 'mirror':
                task_key += '_mirror'
            
            # Create/update task
            tasks[task_key] = {
                'chat_id': None,
                'symbol': symbol,
                'approach': approach,
                'monitoring_mode': 'ENHANCED_TP_SL',
                'started_at': time.time(),
                'active': True,
                'account_type': account,
                'system_type': 'enhanced_tp_sl',
                'side': side
            }
    
    print(f"\nCreated/updated {len(tasks)} monitor tasks")
    
    # Save back
    with open(pkl_path, 'wb') as f:
        pickle.dump(data, f)
    
    print("\n✅ Pickle file updated with forced sync")
    print("✅ The bot should recognize all 15 monitors immediately")
    
    # Create a trigger file to force reload
    trigger_file = '.monitor_sync_trigger'
    with open(trigger_file, 'w') as f:
        f.write(str(time.time()))
    print(f"✅ Created trigger file: {trigger_file}")
    
    return len(monitors)

if __name__ == "__main__":
    total = force_monitor_sync()
    print(f"\n📊 Final count: {total} monitors")