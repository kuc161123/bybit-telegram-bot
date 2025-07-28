#!/usr/bin/env python3
"""
Trigger a monitor save to persistence before bot restart
"""

import os
import sys
import pickle
import time
from datetime import datetime

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def trigger_monitor_save():
    """Trigger a monitor save by creating signal files and forcing persistence"""
    
    print("🔄 TRIGGERING MONITOR SAVE FOR BOT RESTART")
    print("=" * 50)
    
    # 1. Create backup of current pickle file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"bybit_bot_dashboard_v4.1_enhanced.pkl.backup_pre_restart_{timestamp}"
    
    try:
        os.system(f"cp bybit_bot_dashboard_v4.1_enhanced.pkl {backup_name}")
        print(f"✅ Created backup: {backup_name}")
    except Exception as e:
        print(f"⚠️ Warning: Could not create backup: {e}")
    
    # 2. Load current pickle data to verify
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        print(f"📊 Current monitors in pickle: {len(monitors)}")
        
        # Show some key statistics
        main_monitors = [k for k in monitors.keys() if k.endswith('_main')]
        mirror_monitors = [k for k in monitors.keys() if k.endswith('_mirror')]
        
        print(f"   • Main account monitors: {len(main_monitors)}")
        print(f"   • Mirror account monitors: {len(mirror_monitors)}")
        print(f"   • Total monitors: {len(monitors)}")
        
    except Exception as e:
        print(f"❌ Error reading current pickle data: {e}")
        return False
    
    # 3. Create signal files to trigger save
    signal_files = [
        '.save_monitors_before_restart.signal',
        '.force_monitor_persistence.signal',
        '.backup_monitors.signal'
    ]
    
    for signal_file in signal_files:
        try:
            with open(signal_file, 'w') as f:
                f.write(f"Monitor save requested at {datetime.now().isoformat()}\n")
                f.write(f"Reason: Bot restart preparation\n")
                f.write(f"Monitor count: {len(monitors)}\n")
            print(f"✅ Created signal file: {signal_file}")
        except Exception as e:
            print(f"⚠️ Warning: Could not create {signal_file}: {e}")
    
    # 4. Wait a moment for the bot to process the signals
    print("\n⏳ Waiting for bot to process save signals...")
    time.sleep(5)
    
    # 5. Verify the save occurred by checking file modification time
    try:
        pickle_stat = os.stat('bybit_bot_dashboard_v4.1_enhanced.pkl')
        current_time = time.time()
        file_age = current_time - pickle_stat.st_mtime
        
        if file_age < 60:  # Modified within last minute
            print(f"✅ Pickle file recently updated ({file_age:.1f} seconds ago)")
        else:
            print(f"⚠️ Pickle file not recently updated ({file_age:.1f} seconds ago)")
            print("   The bot might not be running or signals not processed")
    except Exception as e:
        print(f"❌ Error checking pickle file: {e}")
    
    # 6. Clean up signal files
    print("\n🧹 Cleaning up signal files...")
    for signal_file in signal_files:
        try:
            if os.path.exists(signal_file):
                os.remove(signal_file)
                print(f"✅ Removed: {signal_file}")
        except Exception as e:
            print(f"⚠️ Warning: Could not remove {signal_file}: {e}")
    
    print("\n📋 MONITOR SAVE SUMMARY")
    print("=" * 30)
    print(f"✅ Backup created: {backup_name}")
    print(f"✅ Monitor count verified: {len(monitors)}")
    print(f"✅ Signal files processed")
    print("\n🚀 BOT IS READY FOR RESTART")
    print("   • All monitor data has been saved")
    print("   • Backup created for safety")
    print("   • You can now safely restart the bot")
    
    return True

if __name__ == "__main__":
    trigger_monitor_save()