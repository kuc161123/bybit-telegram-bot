#!/usr/bin/env python3
"""
Properly sync mirror monitors to match current positions
"""

import asyncio
import logging
from decimal import Decimal
from clients.bybit_helpers import get_position_info_for_account
import pickle

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def sync_mirror_monitors():
    """Sync mirror monitors with actual positions"""
    
    # Get current mirror positions
    logger.info("📊 Fetching mirror account positions...")
    positions = await get_position_info_for_account(account='mirror')
    
    if not positions:
        logger.error("❌ No positions found on mirror account")
        return 0
    
    logger.info(f"✅ Found {len(positions)} mirror positions")
    
    # Load pickle
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)
    
    monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
    
    # List current positions
    logger.info("\nMirror positions found:")
    mirror_count = 0
    for pos in positions:
        symbol = pos['symbol']
        side = pos['side']
        size = float(pos['size'])
        avg_price = float(pos['avgPrice'])
        
        if size > 0:
            logger.info(f"  - {symbol} {side}: {size} @ {avg_price}")
            mirror_count += 1
            
            # Check if monitor exists
            monitor_key = f"{symbol}_{side}_mirror"
            if monitor_key not in monitors:
                logger.warning(f"    ⚠️ Missing monitor: {monitor_key}")
            else:
                logger.info(f"    ✅ Monitor exists: {monitor_key}")
    
    # Count all monitors
    main_monitors = [k for k in monitors if k.endswith('_main')]
    mirror_monitors = [k for k in monitors if k.endswith('_mirror')]
    
    logger.info(f"\n📊 Monitor Summary:")
    logger.info(f"  Main monitors: {len(main_monitors)}")
    logger.info(f"  Mirror monitors: {len(mirror_monitors)}")
    logger.info(f"  Total monitors: {len(main_monitors) + len(mirror_monitors)}")
    logger.info(f"  Mirror positions: {mirror_count}")
    
    # Start the mirror enhanced manager to monitor these positions
    try:
        from execution.mirror_enhanced_tp_sl import mirror_enhanced_tp_sl_manager
        
        # Start monitoring for each mirror position
        for pos in positions:
            if float(pos['size']) > 0:
                symbol = pos['symbol']
                side = pos['side']
                monitor_key = f"{symbol}_{side}_mirror"
                
                if monitor_key in monitors:
                    # Start monitoring task
                    task = asyncio.create_task(
                        mirror_enhanced_tp_sl_manager._run_monitor_loop(monitor_key)
                    )
                    logger.info(f"✅ Started monitoring task for {monitor_key}")
    except Exception as e:
        logger.error(f"❌ Error starting mirror monitors: {e}")
    
    return len(main_monitors) + len(mirror_monitors)

async def main():
    """Main entry point"""
    total = await sync_mirror_monitors()
    print(f"\n✅ Total monitors: {total}")

if __name__ == "__main__":
    asyncio.run(main())