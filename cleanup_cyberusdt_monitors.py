#!/usr/bin/env python3
"""
Clean up CYBERUSDT monitors from pickle file since position was manually closed
"""
import pickle
import os
from datetime import datetime

def cleanup_cyberusdt_monitors():
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    backup_file = f'{pickle_file}.backup_cyberusdt_cleanup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    
    try:
        # Create backup
        if os.path.exists(pickle_file):
            with open(pickle_file, 'rb') as src, open(backup_file, 'wb') as dst:
                dst.write(src.read())
            print(f"✅ Created backup: {backup_file}")
        
        # Load current data
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        # Find and remove CYBERUSDT monitors
        monitors_removed = 0
        if 'enhanced_tp_sl_monitors' in data:
            monitors = data['enhanced_tp_sl_monitors']
            keys_to_remove = []
            
            for key in monitors.keys():
                if 'CYBERUSDT' in key:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del monitors[key]
                monitors_removed += 1
                print(f"🗑️  Removed monitor: {key}")
        
        # Save cleaned data
        with open(pickle_file, 'wb') as f:
            pickle.dump(data, f)
        
        print(f"✅ Cleanup complete: Removed {monitors_removed} CYBERUSDT monitors")
        print(f"📁 Backup saved as: {backup_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        return False

if __name__ == "__main__":
    cleanup_cyberusdt_monitors()