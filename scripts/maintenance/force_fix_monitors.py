#!/usr/bin/env python3
"""
Force fix the monitors by clearing the fill tracker and resetting position sizes
"""

import pickle
import logging
from decimal import Decimal
import os

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def force_fix_monitors():
    """Force fix all monitors and clear tracking data"""
    try:
        # Load pickle file
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
        
        logger.info(f"\n=== FORCE FIXING MONITORS ===")
        logger.info(f"Total monitors: {len(monitors)}")
        
        # Fix each monitor completely
        for key, monitor in monitors.items():
            # Reset position_size to match remaining_size
            monitor['position_size'] = monitor['remaining_size']
            
            # Clear any cumulative tracking
            if 'cumulative_filled' in monitor:
                del monitor['cumulative_filled']
            if 'total_filled' in monitor:
                del monitor['total_filled']
            
            # Reset tp1_hit flag
            monitor['tp1_hit'] = False
            
            # Clear filled_tps list
            monitor['filled_tps'] = []
            
            logger.info(f"Fixed {key}: position_size={monitor['position_size']}, remaining_size={monitor['remaining_size']}")
        
        # Save updated data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"\n✅ Force fixed all monitors")
        
        # Create a signal file to force reload
        signal_file = '/Users/lualakol/bybit-telegram-bot/reload_enhanced_monitors.signal'
        with open(signal_file, 'w') as f:
            f.write("Force reload after monitor fix")
        logger.info(f"✅ Created reload signal file")
        
        # Clear any cached fill tracker files
        tracker_files = [
            'fill_tracker.pkl',
            'data/fill_tracker.pkl',
            'enhanced_tp_sl_fill_tracker.pkl'
        ]
        
        for tracker_file in tracker_files:
            if os.path.exists(tracker_file):
                os.remove(tracker_file)
                logger.info(f"✅ Removed {tracker_file}")
                
    except Exception as e:
        logger.error(f"Error fixing monitors: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    force_fix_monitors()