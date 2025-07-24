#!/usr/bin/env python3
"""
Trigger Monitor Reload Signal
Forces the bot to reload and recreate monitors for all positions
"""

import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Create reload signal file"""
    try:
        logger.info("🔄 Creating monitor reload signal...")
        
        # Create multiple signal files to ensure bot picks it up
        signal_files = [
            'reload_monitors.signal',
            'monitor_reload_trigger.signal',
            'force_reload.trigger'
        ]
        
        for signal_file in signal_files:
            with open(signal_file, 'w') as f:
                f.write(str(time.time()))
            logger.info(f"✅ Created signal: {signal_file}")
        
        logger.info("\n✅ Monitor reload signals created!")
        logger.info("   The bot should detect these and reload all monitors")
        logger.info("   This will create any missing monitors automatically")
        
    except Exception as e:
        logger.error(f"❌ Error creating signals: {e}")

if __name__ == "__main__":
    main()