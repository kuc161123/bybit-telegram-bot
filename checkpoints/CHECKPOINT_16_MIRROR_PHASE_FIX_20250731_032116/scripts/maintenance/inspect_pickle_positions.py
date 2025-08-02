#!/usr/bin/env python3
"""
Inspect pickle file structure to understand where positions are stored.
"""

import pickle
import os
from pprint import pprint

def inspect_pickle():
    """Inspect the pickle file structure."""
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    if not os.path.exists(pickle_file):
        print(f"❌ Pickle file not found: {pickle_file}")
        return
    
    try:
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        print(f"❌ Error loading pickle file: {e}")
        return
    
    print("=" * 80)
    print("PICKLE FILE STRUCTURE")
    print("=" * 80)
    print()
    
    # Top level keys
    print("Top-level keys:")
    for key in data.keys():
        print(f"  - {key}")
    print()
    
    # Check bot_data
    if 'bot_data' in data:
        print("bot_data keys:")
        bot_data = data['bot_data']
        for key in bot_data.keys():
            print(f"  - {key}: {type(bot_data[key])}")
            if isinstance(bot_data[key], (list, dict)):
                print(f"    Length/Size: {len(bot_data[key])}")
    print()
    
    # Check user_data
    if 'user_data' in data:
        print("user_data structure:")
        user_data = data['user_data']
        print(f"  Number of users: {len(user_data)}")
        
        # Sample first user
        if user_data:
            first_chat_id = list(user_data.keys())[0]
            print(f"\n  Sample user data (chat_id: {first_chat_id}):")
            first_user = user_data[first_chat_id]
            for key in first_user.keys():
                print(f"    - {key}: {type(first_user[key])}")
                if key == 'positions' and isinstance(first_user[key], dict):
                    print(f"      Number of positions: {len(first_user[key])}")
                    # Show position structure
                    if first_user[key]:
                        first_pos_key = list(first_user[key].keys())[0]
                        print(f"      Sample position key: {first_pos_key}")
                        first_pos = first_user[key][first_pos_key]
                        if isinstance(first_pos, dict):
                            print("      Position structure:")
                            for pk, pv in first_pos.items():
                                print(f"        - {pk}: {type(pv)}")
    
    # Look for positions in other places
    print("\n" + "=" * 80)
    print("SEARCHING FOR POSITIONS")
    print("=" * 80)
    
    # Check all user positions
    total_positions = 0
    open_positions = 0
    
    if 'user_data' in data:
        for chat_id, user_info in data['user_data'].items():
            if 'positions' in user_info and isinstance(user_info['positions'], dict):
                for pos_key, pos_data in user_info['positions'].items():
                    total_positions += 1
                    if isinstance(pos_data, dict) and pos_data.get('status') == 'open':
                        open_positions += 1
                        print(f"\nOpen position found:")
                        print(f"  Chat ID: {chat_id}")
                        print(f"  Position Key: {pos_key}")
                        print(f"  Symbol: {pos_data.get('symbol')}")
                        print(f"  Side: {pos_data.get('side')}")
                        print(f"  Account: {pos_data.get('account_type', 'main')}")
                        print(f"  Size: {pos_data.get('size')}")
    
    print(f"\n📊 Summary:")
    print(f"  Total positions in user_data: {total_positions}")
    print(f"  Open positions: {open_positions}")

if __name__ == "__main__":
    inspect_pickle()