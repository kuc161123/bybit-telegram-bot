#!/usr/bin/env python3
"""
Force restart monitoring with corrected monitor data
"""

import os
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def force_monitor_restart():
    """Create signal file to force monitor reload"""
    signal_file = '/Users/lualakol/bybit-telegram-bot/reload_enhanced_monitors.signal'
    
    # Remove old signal file if exists
    if os.path.exists(signal_file):
        os.remove(signal_file)
        logger.info("Removed old signal file")
        time.sleep(1)
    
    # Create new signal file
    with open(signal_file, 'w') as f:
        f.write(f"Force reload at {time.time()}")
    
    logger.info(f"✅ Created signal file: {signal_file}")
    logger.info("The monitoring system will reload all monitors on next cycle")
    logger.info("This should fix the false TP fill alerts")

if __name__ == "__main__":
    force_monitor_restart()