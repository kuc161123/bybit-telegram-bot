#!/usr/bin/env python3
"""
Clear all monitoring tasks from pickle file for fresh start
"""

import pickle
import os
from datetime import datetime
import shutil

def clear_monitoring_tasks():
    """Clear all monitoring tasks and position data from pickle file"""
    
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    print("🔍 Clearing monitoring tasks from pickle file...")
    
    try:
        # Create backup first
        backup_file = f"{pickle_file}.backup_before_clear_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(pickle_file, backup_file)
        print(f"✅ Created backup: {backup_file}")
        
        # Load current data
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        # Count current items
        enhanced_monitors = len(data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {}))
        monitor_tasks = len(data.get('bot_data', {}).get('monitor_tasks', {}))
        user_positions = 0
        
        for user_data in data.get('user_data', {}).values():
            user_positions += len(user_data.get('positions', {}))
        
        print(f"\n📊 Current state:")
        print(f"  Enhanced TP/SL monitors: {enhanced_monitors}")
        print(f"  Monitor tasks: {monitor_tasks}")
        print(f"  User positions: {user_positions}")
        
        # Clear monitoring data
        if 'bot_data' in data:
            # Clear Enhanced TP/SL monitors
            if 'enhanced_tp_sl_monitors' in data['bot_data']:
                data['bot_data']['enhanced_tp_sl_monitors'] = {}
                print("\n✅ Cleared Enhanced TP/SL monitors")
            
            # Clear monitor tasks
            if 'monitor_tasks' in data['bot_data']:
                data['bot_data']['monitor_tasks'] = {}
                print("✅ Cleared monitor tasks")
            
            # Clear other monitoring-related data
            keys_to_clear = [
                'active_monitors',
                'monitor_positions',
                'monitor_cache',
                'tp_sl_orders',
                'position_monitors'
            ]
            
            for key in keys_to_clear:
                if key in data['bot_data']:
                    data['bot_data'][key] = {}
                    print(f"✅ Cleared {key}")
        
        # Clear user positions and orders
        for chat_id, user_data in data.get('user_data', {}).items():
            if 'positions' in user_data:
                user_data['positions'] = {}
            if 'orders' in user_data:
                user_data['orders'] = {}
            if 'active_trades' in user_data:
                user_data['active_trades'] = {}
            
            # Clear trade-related keys
            keys_to_remove = [
                'SYMBOL', 'SIDE', 'QUANTITY', 'PRICE',
                'STOP_LOSS', 'TAKE_PROFIT', 'TRADING_APPROACH',
                'TP1_PRICE', 'TP2_PRICE', 'TP3_PRICE', 'TP4_PRICE',
                'SL_PRICE', 'ENTRY_PRICE', 'POSITION_SIZE',
                'CONSERVATIVE_ENTRY_ORDER_ID', 'CONSERVATIVE_SL_ORDER_ID',
                'CONSERVATIVE_TP_ORDER_IDS'
            ]
            
            for key in keys_to_remove:
                if key in user_data:
                    del user_data[key]
        
        print("✅ Cleared user positions and orders")
        
        # Save cleaned data
        with open(pickle_file, 'wb') as f:
            pickle.dump(data, f)
        
        print("\n✅ Pickle file cleaned successfully!")
        
        # Verify the clean
        with open(pickle_file, 'rb') as f:
            verify_data = pickle.load(f)
        
        enhanced_monitors = len(verify_data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {}))
        monitor_tasks = len(verify_data.get('bot_data', {}).get('monitor_tasks', {}))
        user_positions = 0
        
        for user_data in verify_data.get('user_data', {}).values():
            user_positions += len(user_data.get('positions', {}))
        
        print(f"\n📊 Verified clean state:")
        print(f"  Enhanced TP/SL monitors: {enhanced_monitors}")
        print(f"  Monitor tasks: {monitor_tasks}")
        print(f"  User positions: {user_positions}")
        
        if enhanced_monitors == 0 and monitor_tasks == 0 and user_positions == 0:
            print("\n✅ All monitoring data successfully cleared!")
        else:
            print("\n⚠️  Some data may still remain")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    clear_monitoring_tasks()

if __name__ == "__main__":
    main()