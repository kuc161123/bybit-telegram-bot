#!/usr/bin/env python3
"""Ensure all 6 monitors exist with correct data from exchange"""

import pickle
import shutil
import time
from decimal import Decimal
import os
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

# Load environment
load_dotenv()

def ensure_all_6_monitors():
    print("=" * 60)
    print("ENSURING ALL 6 MONITORS WITH CORRECT DATA")
    print("=" * 60)
    
    # Initialize Bybit clients
    bybit_client = HTTP(
        api_key=os.getenv('BYBIT_API_KEY'),
        api_secret=os.getenv('BYBIT_API_SECRET'),
        testnet=os.getenv('BYBIT_DEMO_TRADING', 'False').lower() == 'true'
    )
    
    bybit_client_2 = HTTP(
        api_key=os.getenv('BYBIT_API_KEY_2'),
        api_secret=os.getenv('BYBIT_API_SECRET_2'),
        testnet=os.getenv('BYBIT_DEMO_TRADING', 'False').lower() == 'true'
    )
    
    # Get positions from both accounts
    print("\n📊 Fetching positions from exchange...")
    
    try:
        # Main account positions
        main_response = bybit_client.get_positions(category="linear", settleCoin="USDT")
        if main_response['retCode'] != 0:
            print(f"❌ Main API error: {main_response['retMsg']}")
            return
        
        main_positions = {}
        for pos in main_response['result']['list']:
            if float(pos['size']) > 0:
                key = f"{pos['symbol']}_{pos['side']}"
                main_positions[key] = {
                    'size': Decimal(str(pos['size'])),
                    'avgPrice': Decimal(str(pos['avgPrice']))
                }
        
        print(f"\nMain account positions: {len(main_positions)}")
        for key, data in main_positions.items():
            print(f"  - {key}: size={data['size']}")
        
        # Mirror account positions
        mirror_response = bybit_client_2.get_positions(category="linear", settleCoin="USDT")
        if mirror_response['retCode'] != 0:
            print(f"❌ Mirror API error: {mirror_response['retMsg']}")
            return
            
        mirror_positions = {}
        for pos in mirror_response['result']['list']:
            if float(pos['size']) > 0:
                key = f"{pos['symbol']}_{pos['side']}"
                mirror_positions[key] = {
                    'size': Decimal(str(pos['size'])),
                    'avgPrice': Decimal(str(pos['avgPrice']))
                }
        
        print(f"\nMirror account positions: {len(mirror_positions)}")
        for key, data in mirror_positions.items():
            print(f"  - {key}: size={data['size']}")
            
    except Exception as e:
        print(f"❌ Error fetching positions: {e}")
        return
    
    # Create backup
    backup_file = f"bybit_bot_dashboard_v4.1_enhanced.pkl.backup_6monitors_{int(time.time())}"
    shutil.copy2('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_file)
    print(f"\n📦 Created backup: {backup_file}")
    
    # Load and update pickle
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        print(f"\n📊 Current monitors: {len(monitors)}")
        
        # Expected monitors
        expected_monitors = {
            # Main account
            'ONTUSDT_Buy_main': main_positions.get('ONTUSDT_Buy'),
            'SNXUSDT_Buy_main': main_positions.get('SNXUSDT_Buy'),
            'SOLUSDT_Buy_main': main_positions.get('SOLUSDT_Buy'),
            # Mirror account
            'ONTUSDT_Buy_mirror': mirror_positions.get('ONTUSDT_Buy'),
            'SNXUSDT_Buy_mirror': mirror_positions.get('SNXUSDT_Buy'),
            'SOLUSDT_Buy_mirror': mirror_positions.get('SOLUSDT_Buy')
        }
        
        # Update or create monitors
        for monitor_key, position_data in expected_monitors.items():
            if position_data:  # Only if position exists
                symbol, side, account = monitor_key.split('_')
                
                if monitor_key in monitors:
                    # Update existing monitor with correct size
                    old_size = monitors[monitor_key].get('position_size', 'N/A')
                    monitors[monitor_key]['position_size'] = position_data['size']
                    monitors[monitor_key]['remaining_size'] = position_data['size']
                    monitors[monitor_key]['avg_price'] = position_data['avgPrice']
                    monitors[monitor_key]['entry_price'] = position_data['avgPrice']
                    
                    print(f"\n✅ Updated {monitor_key}:")
                    print(f"   Old size: {old_size}")
                    print(f"   New size: {position_data['size']}")
                else:
                    # Create new monitor
                    monitors[monitor_key] = {
                        'symbol': symbol,
                        'side': side,
                        'position_size': position_data['size'],
                        'remaining_size': position_data['size'],
                        'entry_price': position_data['avgPrice'],
                        'avg_price': position_data['avgPrice'],
                        'approach': 'conservative',
                        'tp_orders': {},
                        'sl_order': None,
                        'filled_tps': [],
                        'cancelled_limits': False,
                        'tp1_hit': False,
                        'tp1_info': None,
                        'sl_moved_to_be': False,
                        'sl_move_attempts': 0,
                        'created_at': time.time(),
                        'last_check': time.time(),
                        'limit_orders': [],
                        'limit_orders_cancelled': False,
                        'phase': 'MONITORING',
                        'chat_id': 5634913742,
                        'account_type': account,
                        'close_detections': 0
                    }
                    print(f"\n✅ Created {monitor_key}:")
                    print(f"   Size: {position_data['size']}")
                    print(f"   Avg Price: {position_data['avgPrice']}")
        
        # Save updated data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        print(f"\n✅ Updated monitors successfully!")
        print(f"Total monitors now: {len(monitors)}")
        
        # Trigger reload
        with open('.reload_enhanced_monitors.signal', 'w') as f:
            f.write(str(time.time()))
        print("\n🔄 Created reload signal file")
        
    except Exception as e:
        print(f"\n❌ Error updating pickle: {e}")

if __name__ == "__main__":
    ensure_all_6_monitors()