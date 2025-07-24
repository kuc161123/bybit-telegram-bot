#!/usr/bin/env python3
"""
Safely add chat_id to monitors that are missing it.
Uses the DEFAULT_ALERT_CHAT_ID from settings.
"""

import pickle
import sys
import os
from datetime import datetime
import shutil

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import DEFAULT_ALERT_CHAT_ID

def fix_missing_chat_ids():
    """Add chat_id to monitors that don't have one"""
    
    PICKLE_FILE = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    # Verify DEFAULT_ALERT_CHAT_ID is set
    if not DEFAULT_ALERT_CHAT_ID:
        print("❌ ERROR: DEFAULT_ALERT_CHAT_ID not set in .env file")
        print("Please set DEFAULT_ALERT_CHAT_ID=5634913742 in your .env file")
        return False
    
    print(f"🔧 FIXING MISSING CHAT IDS")
    print(f"Using DEFAULT_ALERT_CHAT_ID: {DEFAULT_ALERT_CHAT_ID}")
    print("="*50)
    
    try:
        # Create backup first
        backup_file = f"{PICKLE_FILE}.backup_chat_id_fix_{int(datetime.now().timestamp())}"
        shutil.copy2(PICKLE_FILE, backup_file)
        print(f"✅ Created backup: {backup_file}")
        
        # Load pickle data
        with open(PICKLE_FILE, 'rb') as f:
            data = pickle.load(f)
        
        # Check enhanced_tp_sl_monitors
        if 'bot_data' not in data or 'enhanced_tp_sl_monitors' not in data['bot_data']:
            print("❌ No enhanced_tp_sl_monitors found in pickle")
            return False
        
        monitors = data['bot_data']['enhanced_tp_sl_monitors']
        monitors_fixed = []
        monitors_already_ok = []
        
        # Fix monitors without chat_id (including None values)
        for key, monitor in monitors.items():
            current_chat_id = monitor.get('chat_id')
            # Check if chat_id is missing, None, or empty
            if not current_chat_id or current_chat_id is None:
                # Add the chat_id
                monitor['chat_id'] = DEFAULT_ALERT_CHAT_ID
                monitors_fixed.append(key)
                print(f"✅ Fixed: {key}")
                print(f"   Symbol: {monitor.get('symbol')}, Side: {monitor.get('side')}, Account: {monitor.get('account', 'main')}")
                print(f"   Previous chat_id value: {current_chat_id}")
            else:
                monitors_already_ok.append(key)
        
        # Save updated data
        if monitors_fixed:
            with open(PICKLE_FILE, 'wb') as f:
                pickle.dump(data, f)
            
            print(f"\n📊 SUMMARY:")
            print(f"  - Monitors fixed: {len(monitors_fixed)}")
            print(f"  - Monitors already had chat_id: {len(monitors_already_ok)}")
            print(f"  - Total monitors: {len(monitors)}")
            
            print(f"\n✅ Successfully added chat_id={DEFAULT_ALERT_CHAT_ID} to {len(monitors_fixed)} monitors")
            print("\n🔔 These monitors will now send alerts to the configured Telegram chat")
            
            # Verify the fix
            print("\n🔍 Verifying fix...")
            with open(PICKLE_FILE, 'rb') as f:
                verify_data = pickle.load(f)
            
            verify_monitors = verify_data['bot_data']['enhanced_tp_sl_monitors']
            missing_chat_id = [k for k, m in verify_monitors.items() if not m.get('chat_id')]
            
            if missing_chat_id:
                print(f"⚠️  WARNING: {len(missing_chat_id)} monitors still missing chat_id")
                for key in missing_chat_id:
                    print(f"  - {key}")
            else:
                print("✅ Verification passed: All monitors now have chat_id!")
            
            return True
        else:
            print("\n✅ All monitors already have chat_id assigned!")
            print(f"   Total monitors checked: {len(monitors)}")
            return True
            
    except FileNotFoundError:
        print(f"❌ Error: {PICKLE_FILE} not found")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Restore backup on error
        if 'backup_file' in locals() and os.path.exists(backup_file):
            print(f"\n🔄 Restoring backup due to error...")
            shutil.copy2(backup_file, PICKLE_FILE)
            print("✅ Backup restored")
        
        return False

if __name__ == "__main__":
    success = fix_missing_chat_ids()
    sys.exit(0 if success else 1)