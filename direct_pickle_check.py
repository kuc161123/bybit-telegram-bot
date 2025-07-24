#!/usr/bin/env python3
"""
Direct check of pickle file content.
"""

import pickle

def direct_check():
    """Direct check of pickle file."""
    
    print("=" * 80)
    print("DIRECT PICKLE CHECK")
    print("=" * 80)
    
    # Load pickle file
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    with open(pickle_file, 'rb') as f:
        data = pickle.load(f)
    
    # Navigate directly to the monitors
    monitors = data['bot_data']['enhanced_tp_sl_monitors']
    
    # Check specific monitors
    check_monitors = [
        'AUCTIONUSDT_Buy_main',
        'AUCTIONUSDT_Buy_mirror',
        'CRVUSDT_Buy_mirror',
        'SEIUSDT_Buy_mirror',
        'ARBUSDT_Buy_mirror'
    ]
    
    print(f"\n📊 Checking specific monitors:")
    for monitor_key in check_monitors:
        if monitor_key in monitors:
            monitor = monitors[monitor_key]
            chat_id = monitor.get('chat_id')
            
            # Print raw data
            print(f"\n{monitor_key}:")
            print(f"  chat_id value: {repr(chat_id)}")
            print(f"  chat_id type: {type(chat_id)}")
            print(f"  chat_id == None: {chat_id == None}")
            print(f"  chat_id is None: {chat_id is None}")
            
            # Check if it's a string 'None'
            if isinstance(chat_id, str):
                print(f"  chat_id == 'None': {chat_id == 'None'}")
        else:
            print(f"\n{monitor_key}: NOT FOUND")
    
    # Check all monitors for None-like values
    print(f"\n\n📊 Checking all monitors:")
    none_count = 0
    string_none_count = 0
    
    for key, monitor in monitors.items():
        if isinstance(monitor, dict):
            chat_id = monitor.get('chat_id')
            if chat_id is None:
                none_count += 1
                print(f"  {key}: chat_id is None")
            elif chat_id == 'None':
                string_none_count += 1
                print(f"  {key}: chat_id is string 'None'")
    
    print(f"\n📊 Summary:")
    print(f"  Monitors with None: {none_count}")
    print(f"  Monitors with 'None' string: {string_none_count}")
    print(f"  Total monitors: {len(monitors)}")
    
    print("\n" + "=" * 80)
    print("CHECK COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    direct_check()