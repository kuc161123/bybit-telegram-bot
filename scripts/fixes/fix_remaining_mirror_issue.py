#!/usr/bin/env python3
"""
Fix remaining mirror monitor issue (XRPUSDT)
"""

import pickle
import logging
from decimal import Decimal

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_xrpusdt_mirror():
    """Fix XRPUSDT mirror monitor that still has wrong remaining_size"""
    try:
        # Load pickle file
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
        
        # Fix XRPUSDT_Buy_mirror
        if 'XRPUSDT_Buy_mirror' in monitors:
            monitor = monitors['XRPUSDT_Buy_mirror']
            logger.info(f"Fixing XRPUSDT_Buy_mirror:")
            logger.info(f"  Current: position_size={monitor['position_size']}, remaining_size={monitor['remaining_size']}")
            
            # Set correct values
            monitor['position_size'] = Decimal('87')
            monitor['remaining_size'] = Decimal('87')
            
            logger.info(f"  New: position_size={monitor['position_size']}, remaining_size={monitor['remaining_size']}")
        
        # Save updated data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        logger.info("✅ Fixed XRPUSDT mirror monitor")
        
    except Exception as e:
        logger.error(f"Error fixing monitor: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    fix_xrpusdt_mirror()