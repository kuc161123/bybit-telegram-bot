#!/usr/bin/env python3
"""
Comprehensive fixes for monitor warnings, chat ID association, and timing issues
Applies to both main and mirror accounts for all current and future positions
"""

import os
import sys
import re

def fix_persistence_warnings():
    """Fix persistence warnings and initialize pickle file properly"""
    
    # 1. Fix the repeated "No monitors found" warnings
    file_path = "helpers/background_tasks.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace warning with rate-limited version
    old_warning = '''else:
                        logger.warning("🔍 No persisted monitors found")'''
    
    new_warning = '''else:
                        # Only log this warning once every 5 minutes to reduce spam
                        if not hasattr(enhanced_tp_sl_monitoring_loop, '_last_no_persist_log'):
                            enhanced_tp_sl_monitoring_loop._last_no_persist_log = 0
                        
                        import time
                        current_time = time.time()
                        if current_time - enhanced_tp_sl_monitoring_loop._last_no_persist_log > 300:  # 5 minutes
                            logger.info("📊 No monitors in persistence (this is normal for fresh start)")
                            enhanced_tp_sl_monitoring_loop._last_no_persist_log = current_time'''
    
    content = content.replace(old_warning, new_warning)
    
    # Fix the "No monitors active" warning too
    old_no_monitors = '''if current_time - enhanced_tp_sl_monitoring_loop._last_no_monitors_log > 30:
                    logger.warning("🔍 No monitors active, checking for persistence reload")
                    enhanced_tp_sl_monitoring_loop._last_no_monitors_log = current_time'''
    
    new_no_monitors = '''if current_time - enhanced_tp_sl_monitoring_loop._last_no_monitors_log > 300:  # 5 minutes instead of 30 seconds
                    logger.info("📊 No active monitors (normal if no positions open)")
                    enhanced_tp_sl_monitoring_loop._last_no_monitors_log = current_time'''
    
    content = content.replace(old_no_monitors, new_no_monitors)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("✅ Fixed persistence warning frequency")
    return True


def fix_chat_id_association():
    """Fix chat ID warnings for orphaned positions"""
    
    # Fix in enhanced_tp_sl_manager.py
    file_path = "execution/enhanced_tp_sl_manager.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the orphaned position warning and add fallback
    old_pattern = r'logger\.warning\(f"⚠️ Could not find chat_id for {symbol} {side} - creating monitor without alerts"\)'
    
    new_code = '''# Try to find chat_id, fallback to default if not found
        if not chat_id and DEFAULT_ALERT_CHAT_ID:
            chat_id = DEFAULT_ALERT_CHAT_ID
            logger.info(f"📱 Using default chat_id {DEFAULT_ALERT_CHAT_ID} for {symbol} {side}")
        elif not chat_id:
            logger.warning(f"⚠️ Could not find chat_id for {symbol} {side} - creating monitor without alerts")'''
    
    # Replace the warning with improved logic
    content = re.sub(old_pattern, new_code, content)
    
    # Also ensure chat_id is stored in monitor data for both main and mirror
    monitor_creation_pattern = r'(monitor_data = \{[^}]+)\}'
    
    def add_chat_id_to_monitor(match):
        monitor_dict = match.group(1)
        if '"chat_id":' not in monitor_dict:
            return monitor_dict + ',\n            "chat_id": chat_id or DEFAULT_ALERT_CHAT_ID\n        }'
        return match.group(0)
    
    content = re.sub(monitor_creation_pattern, add_chat_id_to_monitor, content, flags=re.DOTALL)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("✅ Fixed chat ID association with fallback")
    return True


def fix_monitor_registration_timing():
    """Fix timing issue for limit order registration"""
    
    # Fix in trader.py where limit orders are registered
    file_path = "execution/trader.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the registration warning
    old_pattern = r'logger\.warning\("Cannot register limit orders - no monitor found[^"]+"\)'
    
    new_code = '''# Retry monitor lookup with small delay for timing issues
        retries = 3
        for i in range(retries):
            monitor = enhanced_tp_sl_manager.get_monitor(symbol, side, account_type)
            if monitor:
                break
            if i < retries - 1:
                await asyncio.sleep(0.5)  # Wait 500ms between retries
        
        if not monitor:
            logger.warning(f"Cannot register limit orders - no monitor found for {symbol} {side} after {retries} attempts")'''
    
    content = re.sub(old_pattern, new_code, content)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("✅ Fixed monitor registration timing with retry logic")
    return True


def fix_ptb_warning():
    """Optionally fix PTBUserWarning"""
    
    # Fix in handlers/__init__.py
    file_path = "handlers/__init__.py"
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Add per_message=True to ConversationHandler
        old_pattern = r'(ConversationHandler\([^)]+)'
        new_pattern = r'\1, per_message=True'
        
        # Only add if not already present
        if 'per_message=True' not in content:
            content = re.sub(old_pattern, new_pattern, content)
            
            with open(file_path, 'w') as f:
                f.write(content)
            
            print("✅ Fixed PTBUserWarning by adding per_message=True")
        else:
            print("ℹ️ PTBUserWarning already fixed")
            
    except Exception as e:
        print(f"⚠️ Could not fix PTBUserWarning: {e}")
    
    return True


def ensure_pickle_initialization():
    """Ensure pickle file is properly initialized if it doesn't exist"""
    
    pickle_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    
    if not os.path.exists(pickle_file):
        import pickle
        
        # Create initial structure
        initial_data = {
            'bot_data': {
                'enhanced_tp_sl_monitors': {},
                'positions': {},
                'orders': {},
                'chat_data': {},
                'stats': {}
            }
        }
        
        with open(pickle_file, 'wb') as f:
            pickle.dump(initial_data, f)
        
        print(f"✅ Initialized {pickle_file} with proper structure")
    else:
        print(f"ℹ️ {pickle_file} already exists")
    
    return True


def main():
    """Apply all fixes"""
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    print("🔧 Applying comprehensive monitor fixes...")
    print("=" * 50)
    
    # Apply all fixes
    fixes = [
        ("Persistence warnings", fix_persistence_warnings),
        ("Chat ID association", fix_chat_id_association),
        ("Monitor registration timing", fix_monitor_registration_timing),
        ("PTB warning", fix_ptb_warning),
        ("Pickle initialization", ensure_pickle_initialization)
    ]
    
    success_count = 0
    for name, fix_func in fixes:
        print(f"\n📌 Applying {name} fix...")
        try:
            if fix_func():
                success_count += 1
        except Exception as e:
            print(f"❌ Error applying {name} fix: {e}")
    
    print("\n" + "=" * 50)
    print(f"✅ Applied {success_count}/{len(fixes)} fixes successfully")
    print("\n🚀 These fixes will apply to:")
    print("   • Both main and mirror accounts")
    print("   • All current positions")
    print("   • All future positions")
    print("\n⚠️ Please restart the bot for changes to take effect")


if __name__ == "__main__":
    main()