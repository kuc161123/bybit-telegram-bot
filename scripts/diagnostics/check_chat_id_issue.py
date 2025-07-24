#!/usr/bin/env python3
"""
Check Chat ID Issue

Investigates why chat_id is empty for alerts
"""

import pickle
import os

def check_chat_id():
    """Check chat IDs in persistence file"""
    print("=" * 80)
    print("🔍 CHECKING CHAT ID ISSUE")
    print("=" * 80)
    
    pkl_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    if not os.path.exists(pkl_file):
        print(f"❌ Persistence file not found: {pkl_file}")
        return
    
    try:
        with open(pkl_file, 'rb') as f:
            data = pickle.load(f)
        
        print("\n📊 Persistence File Structure:")
        print(f"Keys: {list(data.keys())}")
        
        # Check bot_data
        bot_data = data.get('bot_data', {})
        print(f"\nBot Data Keys: {list(bot_data.keys())}")
        
        # Check monitors
        if 'enhanced_tp_sl_monitors' in bot_data:
            monitors = bot_data['enhanced_tp_sl_monitors']
            print(f"\n📊 Enhanced TP/SL Monitors: {len(monitors)}")
            
            for key, monitor in monitors.items():
                chat_id = monitor.get('chat_id', 'NOT SET')
                print(f"  {key}: chat_id = {chat_id}")
        
        # Check user_data
        user_data = data.get('user_data', {})
        print(f"\n📊 User Data Entries: {len(user_data)}")
        
        for chat_id, user_info in user_data.items():
            print(f"\nChat ID: {chat_id}")
            if isinstance(user_info, dict):
                positions = user_info.get('positions', {})
                print(f"  Positions: {len(positions)}")
                for pos_key in list(positions.keys())[:3]:  # Show first 3
                    print(f"    - {pos_key}")
        
        # Check chat_data
        chat_data = data.get('chat_data', {})
        print(f"\n📊 Chat Data Entries: {len(chat_data)}")
        
        for chat_id, chat_info in chat_data.items():
            print(f"\nChat ID: {chat_id}")
            if isinstance(chat_info, dict):
                print(f"  Keys: {list(chat_info.keys())[:5]}")  # Show first 5 keys
        
        # Look for any stored chat IDs
        print("\n📊 All Chat IDs Found:")
        all_chat_ids = set()
        
        # From user_data
        all_chat_ids.update(user_data.keys())
        
        # From chat_data
        all_chat_ids.update(chat_data.keys())
        
        # From monitors
        for monitor in bot_data.get('enhanced_tp_sl_monitors', {}).values():
            if 'chat_id' in monitor and monitor['chat_id']:
                all_chat_ids.add(monitor['chat_id'])
        
        print(f"Total unique chat IDs: {len(all_chat_ids)}")
        for cid in all_chat_ids:
            print(f"  - {cid}")
        
        # Check if there's a default chat ID
        default_chat_id = bot_data.get('default_chat_id')
        print(f"\nDefault Chat ID: {default_chat_id}")
        
    except Exception as e:
        print(f"❌ Error reading persistence file: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_chat_id()