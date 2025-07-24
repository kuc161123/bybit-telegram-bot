#!/usr/bin/env python3
"""
Check the alert status for all monitored positions
"""

import pickle
import os
from datetime import datetime

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
print(f"\n📊 Active Monitors: {len(monitor_tasks)}")

# Get chat data for order tracking
chat_data_all = bot_data.get('chat_data', {})

print("\n" + "="*80)
print("📱 MONITOR ALERT STATUS REPORT")
print("="*80)

for monitor_key, task_info in sorted(monitor_tasks.items()):
    print(f"\n🔍 Monitor: {monitor_key}")
    
    # Parse monitor key
    parts = monitor_key.split('_')
    if len(parts) >= 3:
        chat_id = parts[0]
        symbol = parts[1]
        approach = parts[2] if len(parts) > 2 else 'unknown'
        
        print(f"   Symbol: {symbol}")
        print(f"   Approach: {approach}")
        print(f"   Chat ID: {chat_id}")
        
        # Get chat data
        chat_data = chat_data_all.get(int(chat_id), {})
        
        # Check order tracking
        print(f"\n   📋 Order Tracking:")
        
        if approach == 'conservative':
            limit_ids = chat_data.get('conservative_limit_order_ids', [])
            tp_ids = chat_data.get('conservative_tp_order_ids', [])
            sl_id = chat_data.get('conservative_sl_order_id')
            
            print(f"      Limit Orders: {len(limit_ids)} tracked")
            print(f"      TP Orders: {len(tp_ids)} tracked")
            print(f"      SL Order: {'✅ Tracked' if sl_id else '❌ NOT TRACKED'}")
            
            # Alert status
            print(f"\n   🔔 Alert Status:")
            if limit_ids:
                print(f"      ✅ Limit fill alerts: ENABLED")
            else:
                print(f"      ⚠️  Limit fill alerts: DISABLED (no order IDs)")
                
            if tp_ids:
                print(f"      ✅ TP hit alerts: ENABLED")
            else:
                print(f"      ⚠️  TP hit alerts: DISABLED (no order IDs)")
                
            if sl_id:
                print(f"      ✅ SL hit alerts: ENABLED")
            else:
                print(f"      ⚠️  SL hit alerts: DISABLED (no order ID)")
                
        elif approach == 'fast':
            tp_id = chat_data.get('fast_tp_order_id')
            sl_id = chat_data.get('fast_sl_order_id')
            
            print(f"      TP Order: {'✅ Tracked' if tp_id else '❌ NOT TRACKED'}")
            print(f"      SL Order: {'✅ Tracked' if sl_id else '❌ NOT TRACKED'}")
            
            # Alert status
            print(f"\n   🔔 Alert Status:")
            if tp_id:
                print(f"      ✅ TP hit alerts: ENABLED")
            else:
                print(f"      ⚠️  TP hit alerts: DISABLED (no order ID)")
                
            if sl_id:
                print(f"      ✅ SL hit alerts: ENABLED")
            else:
                print(f"      ⚠️  SL hit alerts: DISABLED (no order ID)")
        else:
            print(f"      ⚠️  Unknown approach: {approach}")
            
        # Check for active_monitor_task_data_v2
        active_monitors_v2 = chat_data.get('active_monitor_task_data_v2', {})
        if any(symbol in k for k in active_monitors_v2.keys()):
            print(f"\n   📊 Monitor Data V2: ✅ Present")
            for k, v in active_monitors_v2.items():
                if symbol in k:
                    if isinstance(v, dict):
                        print(f"      - {k}: {len(v)} fields")

print("\n" + "="*80)
print("📊 SUMMARY")
print("="*80)

# Count working vs non-working
total_monitors = len(monitor_tasks)
working_monitors = 0

for monitor_key in monitor_tasks:
    parts = monitor_key.split('_')
    if len(parts) >= 3:
        chat_id = parts[0]
        approach = parts[2] if len(parts) > 2 else 'unknown'
        chat_data = chat_data_all.get(int(chat_id), {})
        
        if approach == 'conservative':
            if (chat_data.get('conservative_limit_order_ids') and 
                chat_data.get('conservative_tp_order_ids') and 
                chat_data.get('conservative_sl_order_id')):
                working_monitors += 1
        elif approach == 'fast':
            if (chat_data.get('fast_tp_order_id') and 
                chat_data.get('fast_sl_order_id')):
                working_monitors += 1

print(f"✅ Fully Working Monitors: {working_monitors}/{total_monitors}")
print(f"⚠️  Monitors with Issues: {total_monitors - working_monitors}/{total_monitors}")

if working_monitors == total_monitors:
    print("\n🎉 ALL MONITORS ARE WORKING PROPERLY!")
    print("✅ You will receive alerts for all TP hits, SL hits, and limit fills")
else:
    print("\n⚠️  Some monitors need attention")
    print("Run the appropriate fix script for positions without proper tracking")