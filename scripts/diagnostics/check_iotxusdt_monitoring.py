#!/usr/bin/env python3
"""
Check IOTXUSDT monitoring status and find the correct monitor key
"""

import pickle

# Load the bot data
persistence_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"

try:
    with open(persistence_file, 'rb') as f:
        bot_data = pickle.load(f)
    print("✅ Loaded bot data")
except Exception as e:
    print(f"❌ Error loading bot data: {e}")
    exit(1)

# Get monitor tasks
monitor_tasks = bot_data.get('monitor_tasks', {})
print(f"\n📊 All monitor tasks ({len(monitor_tasks)} total):")

# Find IOTXUSDT monitors
iotx_monitors = []
for key, task_info in monitor_tasks.items():
    if 'IOTXUSDT' in key:
        iotx_monitors.append(key)
        print(f"  ✅ {key}")

if not iotx_monitors:
    print("  ❌ No IOTXUSDT monitors found!")
    print("\n  All monitors:")
    for key in sorted(monitor_tasks.keys()):
        print(f"    {key}")
else:
    # Check chat data for each monitor
    chat_data_all = bot_data.get('chat_data', {})
    
    for monitor_key in iotx_monitors:
        print(f"\n📋 Checking monitor: {monitor_key}")
        
        # Extract chat_id from monitor key
        parts = monitor_key.split('_')
        if len(parts) >= 3:
            chat_id = parts[0]
            symbol = parts[1]
            approach = parts[2] if len(parts) > 2 else 'unknown'
            
            print(f"  Chat ID: {chat_id}")
            print(f"  Symbol: {symbol}")
            print(f"  Approach: {approach}")
            
            # Get chat data
            chat_data = chat_data_all.get(int(chat_id), {})
            
            # Check for order IDs
            if approach == 'conservative':
                limit_ids = chat_data.get('conservative_limit_order_ids', [])
                tp_ids = chat_data.get('conservative_tp_order_ids', [])
                sl_id = chat_data.get('conservative_sl_order_id')
                
                print(f"\n  Order tracking:")
                print(f"    Limit orders: {len(limit_ids)} IDs")
                if limit_ids:
                    for i, oid in enumerate(limit_ids[:3]):
                        print(f"      {i+1}. {oid[:8]}...")
                print(f"    TP orders: {len(tp_ids)} IDs")
                if tp_ids:
                    for i, oid in enumerate(tp_ids[:4]):
                        print(f"      TP{i+1}: {oid[:8]}...")
                print(f"    SL order: {'Yes' if sl_id else 'No'}")
                if sl_id:
                    print(f"      {sl_id[:8]}...")
                    
                # Check for the special key that might be causing issues
                symbol_key = chat_data.get('symbol')
                if symbol_key and symbol_key == 'IOTXUSDT':
                    print(f"\n  ⚠️  Found IOTXUSDT in chat data with key 'symbol'")
                    
                    # Look for order IDs with different keys
                    for key, value in chat_data.items():
                        if 'order' in key.lower() and 'iotx' in str(value).upper():
                            print(f"    Found related key: {key} = {value}")