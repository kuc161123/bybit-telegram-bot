#!/usr/bin/env python3
"""
Fix POPCATUSDT repeated cancellation loop by marking orders as already cancelled
"""

import pickle
import logging
from config.constants import CONSERVATIVE_ORDERS_CANCELLED, CONSERVATIVE_TP1_HIT_BEFORE_LIMITS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def fix_popcatusdt_loop():
    """Fix the POPCATUSDT cancellation loop"""
    
    # Load persistence file
    persistence_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    
    try:
        with open(persistence_file, 'rb') as f:
            data = pickle.load(f)
        logger.info("✅ Loaded persistence file")
    except Exception as e:
        logger.error(f"❌ Error loading persistence file: {e}")
        return
    
    # Get chat data
    chat_data_dict = data.get('chat_data', {})
    fixed_count = 0
    
    for chat_id, chat_data in chat_data_dict.items():
        # Look for POPCATUSDT position data
        position_key = "position_POPCATUSDT_Buy_conservative"
        if position_key in chat_data:
            position_data = chat_data[position_key]
            
            # Check if already marked as cancelled
            if position_data.get(CONSERVATIVE_ORDERS_CANCELLED):
                logger.info(f"✅ POPCATUSDT in chat {chat_id} already marked as cancelled")
            else:
                # Mark as cancelled to prevent repeated attempts
                position_data[CONSERVATIVE_ORDERS_CANCELLED] = True
                position_data[CONSERVATIVE_TP1_HIT_BEFORE_LIMITS] = True
                fixed_count += 1
                logger.info(f"✅ Fixed POPCATUSDT in chat {chat_id} - marked as cancelled")
    
    # Save updated persistence
    if fixed_count > 0:
        try:
            with open(persistence_file, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"\n✅ Successfully fixed {fixed_count} POPCATUSDT positions")
        except Exception as e:
            logger.error(f"❌ Error saving persistence file: {e}")
    else:
        logger.info("\n✅ No POPCATUSDT positions needed fixing")

if __name__ == "__main__":
    fix_popcatusdt_loop()