#!/usr/bin/env python3
"""
Check the bot_data contents to find monitors
"""
import pickle

def check_bot_data():
    """Check what's in bot_data"""
    
    print("BOT DATA CONTENTS")
    print("=" * 50)
    
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        print(f"Bot data keys: {list(bot_data.keys())}")
        
        # Look for anything monitor-related
        for key, value in bot_data.items():
            if 'monitor' in key.lower() or 'tp' in key.lower() or 'sl' in key.lower():
                print(f"\n{key}: {type(value).__name__}")
                if isinstance(value, dict):
                    print(f"  Items: {len(value)}")
                    if len(value) <= 10:
                        for subkey in value.keys():
                            print(f"    - {subkey}")
    
    except Exception as e:
        print(f"Error reading pickle file: {e}")

if __name__ == "__main__":
    check_bot_data()