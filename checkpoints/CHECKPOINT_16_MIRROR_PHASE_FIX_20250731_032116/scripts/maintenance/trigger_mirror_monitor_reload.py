#!/usr/bin/env python3
"""
Trigger reload of mirror monitors in the Enhanced TP/SL manager
"""
import os
import logging
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def trigger_reload():
    """Create signal file to trigger monitor reload"""
    signal_file = '/Users/lualakol/bybit-telegram-bot/reload_enhanced_monitors.signal'
    
    logger.info("Creating signal file to trigger monitor reload...")
    with open(signal_file, 'w') as f:
        f.write("reload")
    
    logger.info(f"✅ Signal file created: {signal_file}")
    logger.info("The Enhanced TP/SL monitoring loop will reload monitors on next cycle (within 5 seconds)")
    
    # Wait a bit and check if monitors are loaded
    await asyncio.sleep(10)
    
    try:
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        
        mirror_count = 0
        for key, monitor in enhanced_tp_sl_manager.position_monitors.items():
            if monitor.get('account_type') == 'mirror':
                mirror_count += 1
                logger.info(f"✅ Mirror monitor active: {key}")
        
        logger.info(f"\nTotal mirror monitors now active: {mirror_count}")
        
        if mirror_count == 6:
            logger.info("✅ All 6 mirror monitors are now active!")
        
    except Exception as e:
        logger.error(f"Error checking monitors: {e}")

async def main():
    await trigger_reload()

if __name__ == "__main__":
    asyncio.run(main())