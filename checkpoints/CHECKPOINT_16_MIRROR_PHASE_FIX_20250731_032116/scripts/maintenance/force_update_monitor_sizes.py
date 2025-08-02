#!/usr/bin/env python3
"""
Force update the CAKEUSDT_Buy_mirror monitor with correct position size
"""

import pickle
import logging
from decimal import Decimal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def force_update_monitor_sizes():
    """Force update monitor sizes"""
    try:
        # Load pickle file
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        if 'bot_data' not in data or 'enhanced_tp_sl_monitors' not in data['bot_data']:
            logger.error("No enhanced_tp_sl_monitors found")
            return False
        
        monitors = data['bot_data']['enhanced_tp_sl_monitors']
        
        # Force update CAKEUSDT_Buy_mirror
        if 'CAKEUSDT_Buy_mirror' in monitors:
            logger.info("Updating CAKEUSDT_Buy_mirror monitor...")
            monitors['CAKEUSDT_Buy_mirror']['position_size'] = Decimal('27.5')
            monitors['CAKEUSDT_Buy_mirror']['remaining_size'] = Decimal('27.5')
            logger.info(f"Updated position_size and remaining_size to 27.5")
        
        # Save back
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        logger.info("✅ Successfully updated and saved monitor data")
        
        # Verify
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            verify_data = pickle.load(f)
        
        cake_monitor = verify_data['bot_data']['enhanced_tp_sl_monitors'].get('CAKEUSDT_Buy_mirror')
        if cake_monitor:
            logger.info(f"Verified CAKEUSDT_Buy_mirror:")
            logger.info(f"  position_size: {cake_monitor['position_size']}")
            logger.info(f"  remaining_size: {cake_monitor['remaining_size']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    force_update_monitor_sizes()