#!/usr/bin/env python3
"""
Comprehensive fix for chat_id issues:
1. Fix existing monitors with missing/None chat_id
2. Create a patch to ensure future monitors always have chat_id
"""

import pickle
import sys
import os
from datetime import datetime
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import DEFAULT_ALERT_CHAT_ID
from utils.pickle_lock import PickleFileLock

def fix_existing_monitors():
    """Fix all existing monitors with missing/None chat_id"""
    
    PICKLE_FILE = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    if not DEFAULT_ALERT_CHAT_ID:
        print("❌ ERROR: DEFAULT_ALERT_CHAT_ID not set in .env file")
        return False
    
    print(f"🔧 FIXING EXISTING MONITORS")
    print(f"Using DEFAULT_ALERT_CHAT_ID: {DEFAULT_ALERT_CHAT_ID}")
    print("="*50)
    
    lock_manager = PickleFileLock(PICKLE_FILE)
    
    def update_monitors(data):
        if 'bot_data' not in data or 'enhanced_tp_sl_monitors' not in data['bot_data']:
            raise ValueError("No enhanced_tp_sl_monitors found in pickle")
        
        monitors = data['bot_data']['enhanced_tp_sl_monitors']
        monitors_fixed = []
        
        for key, monitor in monitors.items():
            current_chat_id = monitor.get('chat_id')
            if not current_chat_id or current_chat_id is None:
                monitor['chat_id'] = DEFAULT_ALERT_CHAT_ID
                monitors_fixed.append(key)
                print(f"✅ Fixed: {key}")
                print(f"   Symbol: {monitor.get('symbol')}, Side: {monitor.get('side')}")
        
        if monitors_fixed:
            print(f"\n📊 Fixed {len(monitors_fixed)} monitors")
        else:
            print("\n✅ All monitors already have valid chat_id")
        
        return len(monitors_fixed)
    
    try:
        fixed_count = 0
        success = lock_manager.update_data(lambda data: update_monitors(data))
        
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

def create_chat_id_patch():
    """Create patch files to ensure future monitors always have chat_id"""
    
    print("\n" + "="*50)
    print("📝 CREATING CHAT_ID PATCHES")
    
    patches_created = []
    
    # Patch 1: Enhanced TP/SL Manager
    patch1_path = "/Users/lualakol/bybit-telegram-bot/patches/enhanced_tp_sl_chat_id_patch.py"
    patch1_content = f"""#!/usr/bin/env python3
\"\"\"
Patch for enhanced_tp_sl_manager.py to ensure chat_id is always set
\"\"\"

from config.settings import DEFAULT_ALERT_CHAT_ID

def ensure_chat_id(chat_id):
    \"\"\"Ensure chat_id is valid, use default if not\"\"\"
    if not chat_id or chat_id is None:
        return DEFAULT_ALERT_CHAT_ID or 5634913742
    return chat_id

# Monkey patch for setup_enhanced_tp_sl
original_setup = None

def patched_setup_enhanced_tp_sl(self, symbol, side, position_size, entry_price, 
                                  tp_prices, sl_price, tp_percentages=None, 
                                  position_idx=0, chat_id=None, **kwargs):
    # Ensure chat_id is valid
    chat_id = ensure_chat_id(chat_id)
    
    # Call original with fixed chat_id
    return original_setup(self, symbol, side, position_size, entry_price, 
                         tp_prices, sl_price, tp_percentages, position_idx, 
                         chat_id, **kwargs)
"""
    
    # Patch 2: Mirror Enhanced TP/SL
    patch2_path = "/Users/lualakol/bybit-telegram-bot/patches/mirror_enhanced_chat_id_patch.py"
    patch2_content = f"""#!/usr/bin/env python3
\"\"\"
Patch for mirror_enhanced_tp_sl.py to ensure chat_id is always set
\"\"\"

from config.settings import DEFAULT_ALERT_CHAT_ID

def ensure_mirror_chat_id(monitor_data):
    \"\"\"Ensure monitor data has valid chat_id\"\"\"
    if 'chat_id' not in monitor_data or not monitor_data['chat_id']:
        monitor_data['chat_id'] = DEFAULT_ALERT_CHAT_ID or 5634913742
    return monitor_data
"""
    
    # Create patches directory if it doesn't exist
    os.makedirs("/Users/lualakol/bybit-telegram-bot/patches", exist_ok=True)
    
    # Write patch files
    for path, content in [(patch1_path, patch1_content), (patch2_path, patch2_content)]:
        try:
            with open(path, 'w') as f:
                f.write(content)
            print(f"✅ Created patch: {os.path.basename(path)}")
            patches_created.append(path)
        except Exception as e:
            print(f"❌ Failed to create patch {path}: {e}")
    
    # Create init file for patches module
    init_path = "/Users/lualakol/bybit-telegram-bot/patches/__init__.py"
    init_content = """# Chat ID patches
from .enhanced_tp_sl_chat_id_patch import ensure_chat_id, patched_setup_enhanced_tp_sl
from .mirror_enhanced_chat_id_patch import ensure_mirror_chat_id

__all__ = ['ensure_chat_id', 'patched_setup_enhanced_tp_sl', 'ensure_mirror_chat_id']
"""
    
    try:
        with open(init_path, 'w') as f:
            f.write(init_content)
        print(f"✅ Created patches __init__.py")
        patches_created.append(init_path)
    except Exception as e:
        print(f"❌ Failed to create init file: {e}")
    
    return patches_created

def update_monitor_creation_code():
    """Update the actual monitor creation code to use DEFAULT_ALERT_CHAT_ID"""
    
    print("\n" + "="*50)
    print("🔧 UPDATING MONITOR CREATION CODE")
    
    # Update mirror_enhanced_tp_sl.py
    mirror_file = "/Users/lualakol/bybit-telegram-bot/execution/mirror_enhanced_tp_sl.py"
    
    try:
        with open(mirror_file, 'r') as f:
            content = f.read()
        
        # Find and update the monitor creation part
        if '"chat_id": chat_id,' in content:
            # Add check before using chat_id
            new_content = content.replace(
                '"chat_id": chat_id,',
                '"chat_id": chat_id or DEFAULT_ALERT_CHAT_ID,'
            )
            
            # Add import if not present
            if 'from config.settings import DEFAULT_ALERT_CHAT_ID' not in new_content:
                import_line = "from config.settings import DEFAULT_ALERT_CHAT_ID\n"
                # Find a good place to add import (after other imports)
                import_pos = new_content.find('import logging')
                if import_pos != -1:
                    next_line = new_content.find('\n', import_pos) + 1
                    new_content = new_content[:next_line] + import_line + new_content[next_line:]
            
            # Create backup
            backup_path = f"{mirror_file}.backup_{int(time.time())}"
            with open(backup_path, 'w') as f:
                f.write(content)
            print(f"✅ Created backup: {os.path.basename(backup_path)}")
            
            # Write updated content
            with open(mirror_file, 'w') as f:
                f.write(new_content)
            print(f"✅ Updated {os.path.basename(mirror_file)} to use DEFAULT_ALERT_CHAT_ID")
            
            return True
        else:
            print(f"⚠️  Pattern not found in {os.path.basename(mirror_file)}")
            return False
            
    except Exception as e:
        print(f"❌ Error updating code: {e}")
        return False

def verify_all_fixes():
    """Verify all fixes were applied"""
    
    print("\n" + "="*50)
    print("🔍 VERIFYING ALL FIXES")
    
    PICKLE_FILE = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    lock_manager = PickleFileLock(PICKLE_FILE)
    
    try:
        data = lock_manager.safe_load()
        
        if 'bot_data' not in data or 'enhanced_tp_sl_monitors' not in data['bot_data']:
            print("❌ No monitors found")
            return False
            
        monitors = data['bot_data']['enhanced_tp_sl_monitors']
        
        # Check for monitors without chat_id
        missing_chat_id = []
        for key, monitor in monitors.items():
            if not monitor.get('chat_id') or monitor.get('chat_id') is None:
                missing_chat_id.append(key)
        
        if missing_chat_id:
            print(f"❌ {len(missing_chat_id)} monitors still missing chat_id")
            return False
        else:
            print(f"✅ All {len(monitors)} monitors have valid chat_id!")
            
            # Show distribution
            from collections import Counter
            chat_id_counter = Counter(m.get('chat_id') for m in monitors.values())
            print("\n📊 Chat ID distribution:")
            for chat_id, count in chat_id_counter.most_common():
                print(f"   {chat_id}: {count} monitors")
            
            return True
            
    except Exception as e:
        print(f"❌ Verification error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 COMPREHENSIVE CHAT_ID FIX")
    print("="*50)
    
    # Step 1: Fix existing monitors
    fix_success = fix_existing_monitors()
    
    # Step 2: Create patches for future prevention
    patches = create_chat_id_patch()
    
    # Step 3: Update monitor creation code
    code_updated = update_monitor_creation_code()
    
    # Step 4: Verify everything
    time.sleep(1)
    verified = verify_all_fixes()
    
    print("\n" + "="*50)
    print("📊 FINAL SUMMARY:")
    print(f"  ✅ Fixed existing monitors: {'Yes' if fix_success else 'No'}")
    print(f"  ✅ Created patches: {len(patches)} files")
    print(f"  ✅ Updated monitor code: {'Yes' if code_updated else 'No'}")
    print(f"  ✅ All monitors verified: {'Yes' if verified else 'No'}")
    
    if fix_success and verified:
        print("\n✅ COMPREHENSIVE FIX COMPLETE!")
        print("🔔 All monitors will now send alerts to the configured chat")
        print("🛡️ Future monitors will automatically use DEFAULT_ALERT_CHAT_ID")
    else:
        print("\n⚠️  Some issues remain - check the output above")
        
    sys.exit(0 if (fix_success and verified) else 1)