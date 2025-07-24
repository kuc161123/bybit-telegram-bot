#!/usr/bin/env python3
"""
Create a clean backup of the fixed monitors to ensure they're not overwritten
"""

import shutil
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def protect_fixed_monitors():
    """Create a protected backup of the fixed monitors"""
    try:
        # Create a special backup directory
        backup_dir = 'data/persistence_backups'
        os.makedirs(backup_dir, exist_ok=True)
        
        # Create a backup with current timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"{backup_dir}/backup_write_{timestamp}.pkl"
        
        # Copy the fixed pickle file
        shutil.copy('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_file)
        logger.info(f"✅ Created protected backup: {backup_file}")
        
        # Also create a special "known good" backup
        good_backup = f"{backup_dir}/known_good_monitors_{timestamp}.pkl"
        shutil.copy('bybit_bot_dashboard_v4.1_enhanced.pkl', good_backup)
        logger.info(f"✅ Created known good backup: {good_backup}")
        
        logger.info("\nThe bot should now use the corrected monitor sizes.")
        logger.info("If false TP fills continue, the bot may need to be restarted.")
        
    except Exception as e:
        logger.error(f"Error creating backups: {e}")

if __name__ == "__main__":
    protect_fixed_monitors()