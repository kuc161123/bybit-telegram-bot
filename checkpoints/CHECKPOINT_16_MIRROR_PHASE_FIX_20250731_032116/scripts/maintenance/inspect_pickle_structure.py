#!/usr/bin/env python3
"""
Inspect pickle file structure to understand how chat IDs are stored
"""
import pickle
import json

pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'

with open(pkl_path, 'rb') as f:
    data = pickle.load(f)

# Check top-level keys
print("Top-level keys:", list(data.keys()))
print()

# Check user_data structure
user_data = data.get('user_data', {})
print(f"User data keys (chat IDs): {list(user_data.keys())}")

# Check first user's data structure
for chat_id, udata in user_data.items():
    print(f"\nChat ID {chat_id} data keys: {list(udata.keys())}")
    if 'positions' in udata:
        print(f"  Positions: {len(udata['positions'])}")
        for i, pos in enumerate(udata['positions'][:2]):
            print(f"    Position {i}: {pos.get('symbol')} {pos.get('side')}")
    break

# Check bot_data structure
bot_data = data.get('bot_data', {})
print(f"\nBot data keys: {list(bot_data.keys())}")

# Check monitor_tasks
monitor_tasks = bot_data.get('monitor_tasks', {})
print(f"\nMonitor tasks ({len(monitor_tasks)} total):")
for k, v in list(monitor_tasks.items())[:5]:
    print(f"  {k}: chat_id={v.get('chat_id')}, symbol={v.get('symbol')}")

# Check enhanced_tp_sl_monitors
enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
print(f"\nEnhanced monitors ({len(enhanced_monitors)} total):")
for k, v in list(enhanced_monitors.items())[:5]:
    print(f"  {k}: chat_id={v.get('chat_id')}, symbol={v.get('symbol')}")

# Check chat_data for active chat IDs
chat_data = data.get('chat_data', {})
print(f"\nChat data keys (active chats): {list(chat_data.keys())}")

# Look for any stored trade data that might have chat IDs
if 'trades' in bot_data:
    trades = bot_data['trades']
    print(f"\nTrades data: {len(trades)} trades")
    for k, v in list(trades.items())[:3]:
        print(f"  {k}: chat_id={v.get('chat_id')}")

# Check for other potential sources of chat ID
for key in bot_data:
    if 'chat' in key.lower() or 'user' in key.lower():
        print(f"\nFound potential chat data in bot_data['{key}']: {type(bot_data[key])}")