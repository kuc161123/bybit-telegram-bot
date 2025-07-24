#!/usr/bin/env python3
"""
Clear the fill tracker to stop false TP fill alerts
"""

import logging
import asyncio

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def clear_fill_tracker():
    """Clear the fill tracker in the enhanced TP/SL manager"""
    try:
        # Import the manager
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        
        # Clear the fill tracker
        logger.info(f"Current fill tracker has {len(enhanced_tp_sl_manager.fill_tracker)} entries")
        for key, data in enhanced_tp_sl_manager.fill_tracker.items():
            logger.info(f"  {key}: total_filled={data.get('total_filled', 0)}, target_size={data.get('target_size', 0)}")
        
        # Clear it
        enhanced_tp_sl_manager.fill_tracker.clear()
        logger.info("✅ Cleared fill tracker")
        
        # Also clear the position monitors to force reload
        logger.info(f"Current monitors: {len(enhanced_tp_sl_manager.position_monitors)}")
        enhanced_tp_sl_manager.position_monitors.clear()
        logger.info("✅ Cleared position monitors to force reload")
        
        # Create signal file to force reload
        with open('/Users/lualakol/bybit-telegram-bot/reload_enhanced_monitors.signal', 'w') as f:
            f.write("Force reload after clearing tracker")
        logger.info("✅ Created reload signal")
        
    except Exception as e:
        logger.error(f"Error clearing tracker: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(clear_fill_tracker())