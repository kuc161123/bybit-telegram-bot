#!/usr/bin/env python3
"""
Check current monitor status
"""

import pickle

def check_monitors():
    print("\n📊 MONITOR STATUS CHECK")
    print("=" * 60)
    
    # Load persistence
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        print(f"❌ Error loading persistence: {e}")
        return
    
    # Check Enhanced TP/SL monitors
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    print(f"\n✅ Enhanced TP/SL Monitors: {len(enhanced_monitors)}")
    for key, monitor in enhanced_monitors.items():
        symbol = monitor.get('symbol')
        side = monitor.get('side')
        account = monitor.get('account_type', 'main')
        chat_id = monitor.get('chat_id', 'N/A')
        print(f"   • {key}: {symbol} {side} ({account}) - Chat: {chat_id}")
        
        # Check tp_orders format
        tp_orders = monitor.get('tp_orders', {})
        if isinstance(tp_orders, list):
            print(f"     ⚠️  tp_orders is LIST format (needs fix)")
        else:
            print(f"     ✅ tp_orders is DICT format")
    
    # Check dashboard monitor_tasks
    monitor_tasks = data.get('bot_data', {}).get('monitor_tasks', {})
    print(f"\n📊 Dashboard Monitor Tasks: {len(monitor_tasks)}")
    for key, task in monitor_tasks.items():
        if task.get('active', False):
            print(f"   • {key}: {task.get('symbol')} - {task.get('monitoring_mode')}")
    
    # Check user positions
    print(f"\n👤 User Positions:")
    user_data = data.get('user_data', {})
    for chat_id, user_info in user_data.items():
        positions = user_info.get('positions', {})
        if positions:
            print(f"   Chat ID {chat_id}: {len(positions)} positions")
            for pos_key, pos_data in positions.items():
                print(f"     • {pos_key}: Size={pos_data.get('size')}")

if __name__ == "__main__":
    check_monitors()