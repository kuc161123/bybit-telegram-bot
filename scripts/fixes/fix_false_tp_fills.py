#!/usr/bin/env python3
"""
Fix false TP fill issue by ensuring monitors match actual positions
"""

import pickle
import logging
from decimal import Decimal

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_monitor_positions():
    """Update all monitor position sizes to match their current remaining sizes"""
    try:
        # Load pickle file
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
        
        logger.info(f"Found {len(monitors)} monitors to check")
        
        updated_count = 0
        for key, monitor in monitors.items():
            # Ensure position_size matches remaining_size to prevent false TP detections
            if monitor['position_size'] != monitor['remaining_size']:
                logger.info(f"Updating {key}: position_size {monitor['position_size']} -> {monitor['remaining_size']}")
                monitor['position_size'] = monitor['remaining_size']
                updated_count += 1
        
        if updated_count > 0:
            # Save updated data
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"✅ Updated {updated_count} monitors")
        else:
            logger.info("✅ All monitors already have correct position sizes")
            
    except Exception as e:
        logger.error(f"Error fixing monitors: {e}")

if __name__ == "__main__":
    fix_monitor_positions()