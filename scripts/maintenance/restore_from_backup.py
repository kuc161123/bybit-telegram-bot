#!/usr/bin/env python3
"""
Restore from Persistence Backup
"""

import os
import pickle
import shutil
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def restore_from_backup():
    """Restore pickle file from the most recent backup"""
    backup_dir = "data/persistence_backups"
    main_pickle = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    
    try:
        # Find all backup files
        backups = []
        for f in os.listdir(backup_dir):
            if f.startswith("backup_") and f.endswith(".pkl"):
                filepath = os.path.join(backup_dir, f)
                mtime = os.path.getmtime(filepath)
                backups.append((filepath, mtime, f))
        
        if not backups:
            logger.error("No backup files found")
            return False
        
        # Sort by modification time (newest first)
        backups.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"Found {len(backups)} backup files")
        
        # Try each backup until we find a valid one
        for backup_path, mtime, filename in backups:
            timestamp = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"\nTrying backup: {filename} (modified: {timestamp})")
            
            try:
                # Load the backup
                with open(backup_path, 'rb') as f:
                    data = pickle.load(f)
                
                logger.info(f"✅ Successfully loaded backup with {len(data)} keys")
                
                # Check for essential data
                if 'bot_data' in data:
                    bot_data = data['bot_data']
                    monitors = bot_data.get('enhanced_tp_sl_monitors', {})
                    dashboard_monitors = bot_data.get('monitor_tasks', {})
                    
                    logger.info(f"  - Enhanced TP/SL monitors: {len(monitors)}")
                    logger.info(f"  - Dashboard monitors: {len(dashboard_monitors)}")
                    
                    # Show monitors with limit orders
                    limit_order_count = 0
                    for key, monitor in monitors.items():
                        limit_orders = monitor.get('limit_orders', [])
                        if limit_orders:
                            limit_order_count += len(limit_orders)
                            logger.info(f"    - {monitor.get('symbol')} {monitor.get('side')}: {len(limit_orders)} limit orders")
                    
                    logger.info(f"  - Total limit orders tracked: {limit_order_count}")
                
                # Create a backup of the corrupted file
                if os.path.exists(main_pickle):
                    corrupted_backup = f"{main_pickle}.corrupted_{int(datetime.now().timestamp())}"
                    shutil.move(main_pickle, corrupted_backup)
                    logger.info(f"Moved corrupted file to: {corrupted_backup}")
                
                # Restore the backup
                shutil.copy2(backup_path, main_pickle)
                logger.info(f"✅ Successfully restored from backup: {filename}")
                
                # Verify the restored file
                with open(main_pickle, 'rb') as f:
                    verify_data = pickle.load(f)
                
                logger.info("✅ Verified restored file is readable")
                return True
                
            except Exception as e:
                logger.warning(f"❌ Failed to load backup {filename}: {e}")
                continue
        
        logger.error("❌ All backup files failed to load")
        return False
        
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if restore_from_backup():
        print("\n✅ Successfully restored from backup!")
        print("You can now run the limit order tracking check.")
    else:
        print("\n❌ Failed to restore from backup.")
        print("You may need to start with a fresh pickle file.")