#!/usr/bin/env python3
"""
Simple fix to prevent false TP detection by clearing fill tracker
"""

import pickle
import logging
from datetime import datetime
import os

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clear_fill_tracker():
    """Clear the fill tracker that's accumulating false data"""
    try:
        # Load pickle file
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
        
        logger.info(f"Clearing fill tracker and resetting monitors...")
        
        # Clear any fill tracking data
        for key, monitor in monitors.items():
            # Clear cumulative tracking
            if 'cumulative_filled' in monitor:
                del monitor['cumulative_filled']
            if 'total_filled' in monitor:
                del monitor['total_filled']
            
            # Reset tp1_hit flag
            monitor['tp1_hit'] = False
            
            # Clear filled_tps list
            monitor['filled_tps'] = []
            
            # Ensure position_size matches remaining_size
            if monitor['position_size'] != monitor['remaining_size']:
                monitor['position_size'] = monitor['remaining_size']
        
        # Save updated data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        logger.info("✅ Cleared fill tracker and reset monitoring data")
        
        # Create fresh backup
        backup_dir = 'data/persistence_backups'
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"{backup_dir}/backup_cleared_{timestamp}.pkl"
        
        with open(backup_file, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"✅ Created backup: {backup_file}")
        
        # Create signal file to force reload
        with open('data/force_monitor_reload.signal', 'w') as f:
            f.write("Force reload after clearing fill tracker")
        logger.info("✅ Created reload signal")
        
    except Exception as e:
        logger.error(f"Error clearing fill tracker: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    clear_fill_tracker()