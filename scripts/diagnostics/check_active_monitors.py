import pickle
import os
from datetime import datetime

# Load the pickle file
pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'

if os.path.exists(pickle_file):
    with open(pickle_file, 'rb') as f:
        data = pickle.load(f)
    
    # Check active monitors
    active_monitors = data.get('active_monitors', {})
    
    print(f"ACTIVE MONITORS: {len(active_monitors)}")
    print("="*80)
    
    # Focus on fast approach positions
    symbols = ['ENAUSDT', 'TIAUSDT', 'JTOUSDT', 'WIFUSDT', 'JASMYUSDT', 'WLDUSDT', 'KAVAUSDT', 'BTCUSDT']
    
    for monitor_id, monitor_data in active_monitors.items():
        if isinstance(monitor_data, dict):
            symbol = monitor_data.get('symbol', '')
            if symbol in symbols:
                approach = monitor_data.get('approach', monitor_data.get('trading_approach', 'unknown'))
                if approach == 'fast':
                    print(f"\n{symbol} - FAST APPROACH:")
                    print(f"Monitor ID: {monitor_id}")
                    print(f"Side: {monitor_data.get('side')}")
                    print(f"Created: {monitor_data.get('created_at', 'unknown')}")
                    
                    # Check for TP/SL order IDs
                    tp_order_ids = monitor_data.get('tp_order_ids', [])
                    sl_order_id = monitor_data.get('sl_order_id')
                    
                    print(f"TP Order IDs: {tp_order_ids}")
                    print(f"SL Order ID: {sl_order_id}")
                    
                    # Check chat data if available
                    chat_data = monitor_data.get('chat_data', {})
                    if chat_data:
                        print(f"Entry Price: {chat_data.get('primary_entry_price', chat_data.get('entry_price'))}")
                        print(f"TP Price: {chat_data.get('tp1_price')}")
                        print(f"SL Price: {chat_data.get('sl_price')}")
                        print(f"Position Size: {chat_data.get('expected_position_size')}")
else:
    print(f"Pickle file not found: {pickle_file}")