#!/usr/bin/env python3
"""
Activate LDOUSDT_Sell_mirror monitor in the live bot without restart
"""

import pickle
import time
from decimal import Decimal

def activate_monitor_live():
    """Update pickle to trigger monitor activation on next check cycle"""
    
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    # Load current data
    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)
    
    monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
    
    # Check if monitor exists
    if 'LDOUSDT_Sell_mirror' not in monitors:
        print("❌ LDOUSDT_Sell_mirror not found in monitors")
        return
    
    # Update the last_check time to trigger immediate processing
    monitor = monitors['LDOUSDT_Sell_mirror']
    monitor['last_check'] = 0  # Force immediate check
    monitor['phase'] = 'MONITORING'  # Ensure it's in monitoring phase
    
    # Ensure monitor_tasks entry exists for dashboard
    if 'monitor_tasks' not in data['bot_data']:
        data['bot_data']['monitor_tasks'] = {}
    
    # Create/update dashboard monitor entry
    dashboard_key = "None_LDOUSDT_conservative_mirror"
    data['bot_data']['monitor_tasks'][dashboard_key] = {
        'chat_id': None,
        'symbol': 'LDOUSDT',
        'approach': 'conservative',
        'monitoring_mode': 'ENHANCED_TP_SL',
        'started_at': time.time(),
        'active': True,
        'account_type': 'mirror',
        'system_type': 'enhanced_tp_sl',
        'side': 'Sell'
    }
    
    # Save back to pickle
    with open(pkl_path, 'wb') as f:
        pickle.dump(data, f)
    
    print("✅ Monitor activation triggered in pickle file")
    print("✅ The running bot will pick up this monitor in the next sync cycle")
    print("📊 Monitor details:")
    print(f"   Symbol: LDOUSDT")
    print(f"   Side: Sell")
    print(f"   Account: mirror")
    print(f"   Position: {monitor['position_size']}")
    print(f"   TP orders: {len(monitor['tp_orders'])}")
    print(f"   SL order: Yes")
    print("\n⏳ The bot's monitor sync should activate this within 30-60 seconds")
    
    # Show all monitors
    print("\n📋 All Enhanced TP/SL monitors:")
    for key in sorted(monitors.keys()):
        m = monitors[key]
        print(f"   - {key}: {m['position_size']} @ {m['entry_price']}")
    
    print(f"\n📋 All Dashboard monitor tasks:")
    tasks = data['bot_data'].get('monitor_tasks', {})
    for key in sorted(tasks.keys()):
        t = tasks[key]
        print(f"   - {key}: {t['symbol']} {t.get('side', 'N/A')} ({t['account_type']})")

if __name__ == "__main__":
    activate_monitor_live()