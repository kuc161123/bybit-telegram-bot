#!/usr/bin/env python3
"""
Recover Corrupted Pickle File
"""

import os
import shutil
from utils.pickle_lock import main_pickle_lock
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def recover_pickle():
    """Try to recover the corrupted pickle file"""
    try:
        # First, try safe_load which has recovery mechanisms
        logger.info("Attempting to load pickle file with recovery...")
        data = main_pickle_lock.safe_load()
        
        if data:
            logger.info(f"✅ Successfully loaded data with {len(data)} keys")
            
            # Check for essential keys
            if 'bot_data' in data:
                monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
                logger.info(f"Found {len(monitors)} enhanced TP/SL monitors")
                
                # Show monitor details
                for key, monitor in monitors.items():
                    symbol = monitor.get('symbol', 'Unknown')
                    side = monitor.get('side', 'Unknown')
                    limit_orders = monitor.get('limit_orders', [])
                    logger.info(f"  - {symbol} {side}: {len(limit_orders)} limit orders")
            
            return True
        else:
            logger.warning("⚠️ Loaded empty data structure")
            
            # Check for backup
            backup_path = "bybit_bot_dashboard_v4.1_enhanced.pkl.backup"
            if os.path.exists(backup_path):
                logger.info("Found backup file, attempting manual recovery...")
                
                # Try manual recovery
                import pickle
                try:
                    with open(backup_path, 'rb') as f:
                        backup_data = pickle.load(f)
                    
                    logger.info(f"✅ Backup loaded successfully with {len(backup_data)} keys")
                    
                    # Save using safe_save
                    if main_pickle_lock.safe_save(backup_data):
                        logger.info("✅ Successfully restored from backup")
                        return True
                    else:
                        logger.error("❌ Failed to save restored data")
                        
                except Exception as e:
                    logger.error(f"❌ Backup recovery failed: {e}")
            
            return False
            
    except Exception as e:
        logger.error(f"Recovery failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if recover_pickle():
        print("\n✅ Pickle file recovery successful!")
    else:
        print("\n❌ Pickle file recovery failed. You may need to start fresh.")