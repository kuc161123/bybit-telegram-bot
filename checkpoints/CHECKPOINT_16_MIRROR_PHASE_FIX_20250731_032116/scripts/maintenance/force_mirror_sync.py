#!/usr/bin/env python3
"""
Force sync of mirror account positions
"""

import asyncio
import logging
from decimal import Decimal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def force_mirror_sync():
    """Force sync of mirror positions"""
    
    # Import both managers
    from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
    from execution.mirror_enhanced_tp_sl import mirror_enhanced_tp_sl_manager
    
    logger.info("🔄 Forcing mirror account sync...")
    
    # First sync main account
    logger.info("📊 Syncing main account positions...")
    try:
        await enhanced_tp_sl_manager.sync_existing_positions()
        main_count = len(enhanced_tp_sl_manager.position_monitors)
        logger.info(f"✅ Main account: {main_count} monitors active")
    except Exception as e:
        logger.error(f"❌ Error syncing main: {e}")
        main_count = 0
    
    # Now sync mirror account
    logger.info("\n📊 Syncing mirror account positions...")
    try:
        await mirror_enhanced_tp_sl_manager.sync_existing_positions()
        mirror_count = len(mirror_enhanced_tp_sl_manager.position_monitors)
        logger.info(f"✅ Mirror account: {mirror_count} monitors active")
    except Exception as e:
        logger.error(f"❌ Error syncing mirror: {e}")
        mirror_count = 0
    
    # Total count
    total = main_count + mirror_count
    logger.info(f"\n📊 Total monitors active: {total}")
    logger.info(f"   Main: {main_count}")
    logger.info(f"   Mirror: {mirror_count}")
    
    # List all monitors
    if main_count > 0:
        logger.info("\nMain account monitors:")
        for key in sorted(enhanced_tp_sl_manager.position_monitors.keys()):
            logger.info(f"  - {key}")
    
    if mirror_count > 0:
        logger.info("\nMirror account monitors:")
        for key in sorted(mirror_enhanced_tp_sl_manager.position_monitors.keys()):
            logger.info(f"  - {key}")
    
    return total

async def main():
    """Main entry point"""
    total = await force_mirror_sync()
    print(f"\n✅ Total monitors active across both accounts: {total}")

if __name__ == "__main__":
    asyncio.run(main())