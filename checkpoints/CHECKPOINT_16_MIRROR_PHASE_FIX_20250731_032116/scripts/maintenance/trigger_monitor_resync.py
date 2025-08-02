#!/usr/bin/env python3
"""
Trigger the bot to resync all monitors by simulating what sync_existing_positions does
"""

import asyncio
import logging
from decimal import Decimal

# Configure logging to see what happens
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def trigger_resync():
    """Trigger monitor resync"""
    
    # Import the manager
    from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
    
    logger.info("🔄 Triggering monitor resync...")
    
    # Call sync_existing_positions to resync all monitors
    try:
        await enhanced_tp_sl_manager.sync_existing_positions()
        logger.info("✅ Sync completed")
    except Exception as e:
        logger.error(f"❌ Error during sync: {e}", exc_info=True)
    
    # Check the result
    active_count = len(enhanced_tp_sl_manager.position_monitors)
    logger.info(f"📊 Active monitors after sync: {active_count}")
    
    # List all active monitors
    if enhanced_tp_sl_manager.position_monitors:
        logger.info("\nActive monitors:")
        for key in sorted(enhanced_tp_sl_manager.position_monitors.keys()):
            logger.info(f"  - {key}")
    
    return active_count

async def main():
    """Main entry point"""
    count = await trigger_resync()
    print(f"\n✅ Final active monitor count: {count}")

if __name__ == "__main__":
    asyncio.run(main())