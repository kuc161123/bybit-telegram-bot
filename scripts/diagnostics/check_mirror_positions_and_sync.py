#!/usr/bin/env python3
"""
Check mirror positions and ensure monitors are active
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

async def check_and_sync():
    """Check positions and sync monitors"""
    
    # Get positions for both accounts
    logger.info("📊 Fetching positions from both accounts...")
    
    # Main account
    main_positions = await get_position_info_for_account('main')
    logger.info(f"Main account: {len([p for p in main_positions if float(p['size']) > 0])} positions")
    
    # Mirror account
    mirror_positions = await get_position_info_for_account('mirror')
    logger.info(f"Mirror account: {len([p for p in mirror_positions if float(p['size']) > 0])} positions")
    
    # Load pickle to check monitors
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)
    
    monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
    
    # Show actual positions
    total_positions = 0
    logger.info("\n📊 Actual positions:")
    
    logger.info("\nMain Account:")
    for pos in main_positions:
        if float(pos['size']) > 0:
            symbol = pos['symbol']
            side = pos['side']
            size = float(pos['size'])
            avg_price = float(pos['avgPrice'])
            logger.info(f"  - {symbol} {side}: {size} @ {avg_price}")
            total_positions += 1
            
            # Check monitor
            monitor_key = f"{symbol}_{side}_main"
            if monitor_key in monitors:
                logger.info(f"    ✅ Monitor exists")
            else:
                logger.warning(f"    ⚠️ Monitor missing!")
    
    logger.info("\nMirror Account:")
    for pos in mirror_positions:
        if float(pos['size']) > 0:
            symbol = pos['symbol']
            side = pos['side']
            size = float(pos['size'])
            avg_price = float(pos['avgPrice'])
            logger.info(f"  - {symbol} {side}: {size} @ {avg_price}")
            total_positions += 1
            
            # Check monitor
            monitor_key = f"{symbol}_{side}_mirror"
            if monitor_key in monitors:
                logger.info(f"    ✅ Monitor exists")
            else:
                logger.warning(f"    ⚠️ Monitor missing!")
    
    # Summary
    main_monitors = [k for k in monitors if k.endswith('_main')]
    mirror_monitors = [k for k in monitors if k.endswith('_mirror')]
    
    logger.info(f"\n📊 Summary:")
    logger.info(f"  Total positions: {total_positions}")
    logger.info(f"  Total monitors: {len(monitors)}")
    logger.info(f"  Main monitors: {len(main_monitors)}")
    logger.info(f"  Mirror monitors: {len(mirror_monitors)}")
    
    # The bot is probably logging this total
    logger.info(f"\n🤔 Bot is probably showing: {total_positions} positions monitored")
    
    return total_positions

async def main():
    """Main entry point"""
    total = await check_and_sync()
    print(f"\n✅ Total positions across both accounts: {total}")

if __name__ == "__main__":
    asyncio.run(main())