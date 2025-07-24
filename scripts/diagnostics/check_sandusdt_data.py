#!/usr/bin/env python3
"""
Check SANDUSDT position data in persistence
"""

import pickle
import json

# Load persistence file
with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
    data = pickle.load(f)

# Check chat_data
chat_data = data.get('chat_data', {})
print(f'Chat data keys: {list(chat_data.keys())}')

# Check the actual chat data for 5634913742
if 5634913742 in chat_data:
    cd = chat_data[5634913742]
    print(f'\nAll keys in chat 5634913742:')
    
    # Look for position keys
    position_keys = []
    sandusdt_keys = []
    
    for key in cd.keys():
        key_str = str(key)
        if 'position' in key_str.lower():
            position_keys.append(key)
        if 'SANDUSDT' in key_str:
            sandusdt_keys.append(key)
    
    print(f'\nPosition keys: {position_keys}')
    print(f'SANDUSDT keys: {sandusdt_keys}')
    
    # Check for specific position key
    sandusdt_position_key = 'position_SANDUSDT_Buy_conservative'
    if sandusdt_position_key in cd:
        print(f'\nFound {sandusdt_position_key}:')
        position_data = cd[sandusdt_position_key]
        print(json.dumps(position_data, indent=2, default=str))
    else:
        print(f'\n{sandusdt_position_key} not found in chat data')
        
    # Look for any SANDUSDT related data
    print('\nLooking for any SANDUSDT related data:')
    for key, value in cd.items():
        if 'SANDUSDT' in str(key) or (isinstance(value, dict) and 'SANDUSDT' in str(value)):
            print(f'  Key: {key}')
            if isinstance(value, dict) and 'symbol' in value and value['symbol'] == 'SANDUSDT':
                print(f'  Value: {json.dumps(value, indent=4, default=str)}')

# Check monitor tasks
monitor_tasks = data.get('bot_data', {}).get('monitor_tasks', {})
print('\n\nSANDUSDT Monitor Tasks:')
for task_key, task_data in monitor_tasks.items():
    if 'SANDUSDT' in task_key:
        print(f'\nTask: {task_key}')
        print(json.dumps(task_data, indent=2, default=str))