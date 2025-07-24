#!/usr/bin/env python3
"""
Clean bot state after closing all positions
Removes monitors and clears position tracking
"""

import pickle
import logging
import time
import shutil
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def clean_bot_state():
    """Clean all bot state for fresh start"""
    
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    # Create backup first
    backup_path = f"{pkl_path}.backup_fresh_start_{int(time.time())}"
    shutil.copy2(pkl_path, backup_path)
    logger.info(f"✅ Created backup: {backup_path}")
    
    # Load pickle file
    try:
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        logger.error(f"Error loading pickle file: {e}")
        return False
    
    logger.info(f"\n{'='*60}")
    logger.info(f"🧹 CLEANING BOT STATE FOR FRESH START")
    logger.info(f"{'='*60}")
    
    # Clear Enhanced TP/SL monitors
    if 'bot_data' in data:
        old_monitor_count = len(data['bot_data'].get('enhanced_tp_sl_monitors', {}))
        data['bot_data']['enhanced_tp_sl_monitors'] = {}
        logger.info(f"✅ Cleared {old_monitor_count} Enhanced TP/SL monitors")
        
        # Clear dashboard monitors
        old_dashboard_count = len(data['bot_data'].get('monitor_tasks', {}))
        data['bot_data']['monitor_tasks'] = {}
        logger.info(f"✅ Cleared {old_dashboard_count} dashboard monitors")
        
        # Clear any cached orders
        if 'order_cache' in data['bot_data']:
            data['bot_data']['order_cache'] = {}
            logger.info(f"✅ Cleared order cache")
    
    # Clear user positions
    if 'user_data' in data:
        cleared_users = 0
        for user_id in data['user_data']:
            if 'positions' in data['user_data'][user_id]:
                pos_count = len(data['user_data'][user_id]['positions'])
                data['user_data'][user_id]['positions'] = []
                if pos_count > 0:
                    cleared_users += 1
                    logger.info(f"✅ Cleared {pos_count} positions for user {user_id}")
        
        logger.info(f"✅ Cleared positions for {cleared_users} users")
    
    # Clear any trade logs
    if 'trade_log' in data:
        old_logs = len(data.get('trade_log', []))
        data['trade_log'] = []
        logger.info(f"✅ Cleared {old_logs} trade logs")
    
    # Save cleaned state
    try:
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"\n✅ Successfully saved cleaned state")
    except Exception as e:
        logger.error(f"Error saving pickle file: {e}")
        return False
    
    # Create fresh start marker
    with open('.fresh_start_marker', 'w') as f:
        f.write(f"Fresh start initiated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Backup created at: {backup_path}\n")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ BOT STATE CLEANED SUCCESSFULLY")
    logger.info(f"{'='*60}")
    logger.info(f"- All monitors removed")
    logger.info(f"- All position tracking cleared")
    logger.info(f"- Trade logs cleared")
    logger.info(f"- Backup saved at: {backup_path}")
    logger.info(f"\n🚀 Bot is ready for fresh start!")
    
    return True

def main():
    """Main execution"""
    success = clean_bot_state()
    
    if success:
        logger.info("\n💡 Next steps:")
        logger.info("1. Run close_all_positions_fresh_start.py to close all positions")
        logger.info("2. Restart the bot for a clean start")
        logger.info("3. Open new positions with proper Conservative approach")
    else:
        logger.error("\n❌ Failed to clean bot state")

if __name__ == "__main__":
    main()