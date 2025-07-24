#!/usr/bin/env python3
"""
Fix the position_size vs remaining_size mismatch in monitors
"""

import pickle
import logging
from decimal import Decimal
from datetime import datetime
import shutil

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_monitor_mismatch():
    """Fix position_size to match remaining_size for all monitors"""
    try:
        # Create backup
        backup_file = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_fix_{int(datetime.now().timestamp())}'
        shutil.copy('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_file)
        logger.info(f"Created backup: {backup_file}")
        
        # Load pickle file
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
        
        logger.info(f"\n=== FIXING MONITOR MISMATCHES ===")
        logger.info(f"Total monitors: {len(monitors)}")
        
        fixed_count = 0
        for key, monitor in monitors.items():
            position_size = monitor.get('position_size', Decimal('0'))
            remaining_size = monitor.get('remaining_size', Decimal('0'))
            
            # For all monitors, position_size should equal remaining_size
            # This prevents false TP detection
            if position_size != remaining_size:
                logger.info(f"\nFixing {key}:")
                logger.info(f"  Old position_size: {position_size}")
                logger.info(f"  Setting to match remaining_size: {remaining_size}")
                
                monitor['position_size'] = remaining_size
                fixed_count += 1
        
        if fixed_count > 0:
            # Save updated data
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"\n✅ Fixed {fixed_count} monitors")
            
            # Verify the fix
            logger.info("\n=== VERIFICATION ===")
            for key in ['ICPUSDT_Sell_mirror', 'IDUSDT_Sell_mirror', 'JUPUSDT_Sell_mirror']:
                if key in monitors:
                    monitor = monitors[key]
                    logger.info(f"{key}: position_size={monitor['position_size']}, remaining_size={monitor['remaining_size']}")
        else:
            logger.info("✅ All monitors already have matching sizes")
            
    except Exception as e:
        logger.error(f"Error fixing monitors: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    fix_monitor_mismatch()