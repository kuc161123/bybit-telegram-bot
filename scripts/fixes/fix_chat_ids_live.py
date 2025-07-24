#!/usr/bin/env python3
"""
Fix chat_ids in Enhanced TP/SL monitors while bot is running.
This script uses the proper locking mechanism to safely update the pickle file.
"""

import pickle
import sys
import os
from datetime import datetime
import shutil
import time
import fcntl

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import DEFAULT_ALERT_CHAT_ID
from utils.pickle_lock import PickleFileLock

def fix_chat_ids_with_lock():
    """Fix chat_ids using proper locking mechanism"""
    
    PICKLE_FILE = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    # Verify DEFAULT_ALERT_CHAT_ID is set
    if not DEFAULT_ALERT_CHAT_ID:
        print("❌ ERROR: DEFAULT_ALERT_CHAT_ID not set in .env file")
        return False
    
    print(f"🔧 FIXING MISSING CHAT IDS (WITH LOCK)")
    print(f"Using DEFAULT_ALERT_CHAT_ID: {DEFAULT_ALERT_CHAT_ID}")
    print("="*50)
    
    # Create lock manager
    lock_manager = PickleFileLock(PICKLE_FILE)
    
    # Define update function
    def update_monitors(data):
        # Check enhanced_tp_sl_monitors
        if 'bot_data' not in data or 'enhanced_tp_sl_monitors' not in data['bot_data']:
            raise ValueError("No enhanced_tp_sl_monitors found in pickle")
        
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
                print(f"   Previous chat_id: {current_chat_id}")
            else:
                monitors_already_ok.append(key)
        
        print(f"\n📊 SUMMARY:")
        print(f"  - Monitors fixed: {len(monitors_fixed)}")
        print(f"  - Monitors already had chat_id: {len(monitors_already_ok)}")
        print(f"  - Total monitors: {len(monitors)}")
        
        if monitors_fixed:
            print(f"\n✅ Successfully updated {len(monitors_fixed)} monitors with chat_id={DEFAULT_ALERT_CHAT_ID}")
        else:
            print("\n✅ All monitors already have chat_id assigned!")
    
    try:
        # Use the lock manager to safely update data
        print("🔒 Acquiring lock and updating data...")
        success = lock_manager.update_data(update_monitors)
        
        if success:
            print("✅ Data saved successfully")
            return True
        else:
            print("❌ Failed to save data")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_fix():
    """Verify the fix worked"""
    time.sleep(1)  # Give bot time to reload
    
    print("\n" + "="*50)
    print("🔍 VERIFYING FIX...")
    
    PICKLE_FILE = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    lock_manager = PickleFileLock(PICKLE_FILE)
    
    try:
        # Load data with lock
        data = lock_manager.safe_load()
        
        if 'bot_data' not in data or 'enhanced_tp_sl_monitors' not in data['bot_data']:
            print("❌ No enhanced_tp_sl_monitors found")
            return False
            
        monitors = data['bot_data']['enhanced_tp_sl_monitors']
        
        missing_chat_id = []
        for key, monitor in monitors.items():
            if not monitor.get('chat_id') or monitor.get('chat_id') is None:
                missing_chat_id.append(key)
        
        if missing_chat_id:
            print(f"⚠️  {len(missing_chat_id)} monitors still missing chat_id:")
            for key in missing_chat_id:
                print(f"  - {key}")
            return False
        else:
            print("✅ All monitors now have chat_id!")
            print(f"   Total monitors verified: {len(monitors)}")
            return True
            
    except Exception as e:
        print(f"❌ Verification error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Fix with lock
    success = fix_chat_ids_with_lock()
    
    if success:
        # Verify the fix
        verify_success = verify_fix()
        
        if verify_success:
            print("\n✅ FIX COMPLETE AND VERIFIED!")
            print("🔔 All monitors will now send alerts to the configured chat")
        else:
            print("\n⚠️  Fix applied but verification failed")
            print("The bot may need a moment to reload the data")
    else:
        print("\n❌ Fix failed")
        
    sys.exit(0 if success else 1)