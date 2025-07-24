#!/usr/bin/env python3
"""
Simple check of all positions and monitors
"""

import asyncio
import logging
from clients.bybit_helpers import get_position_info
import pickle

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def check_positions():
    """Check all positions"""
    
    # Get main account positions
    logger.info("📊 Checking main account positions...")
    main_positions = await get_position_info()
    
    # Import mirror client to get mirror positions
    from execution.mirror_trader import mirror_trader
    
    logger.info("📊 Checking mirror account positions...")
    mirror_client = mirror_trader.client
    
    # Get mirror positions
    try:
        response = await asyncio.to_thread(
            mirror_client.get_positions,
            category="linear",
            settleCoin="USDT"
        )
        mirror_positions = response.get('result', {}).get('list', [])
    except Exception as e:
        logger.error(f"Error getting mirror positions: {e}")
        mirror_positions = []
    
    # Load monitors from pickle
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)
    
    monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
    
    # Count active positions
    main_active = 0
    mirror_active = 0
    
    logger.info("\n📊 MAIN ACCOUNT POSITIONS:")
    for pos in main_positions:
        if float(pos['size']) > 0:
            symbol = pos['symbol']
            side = pos['side']
            size = float(pos['size'])
            avg_price = float(pos['avgPrice'])
            logger.info(f"  {symbol} {side}: {size} @ ${avg_price}")
            main_active += 1
    
    logger.info(f"\n📊 MIRROR ACCOUNT POSITIONS:")
    for pos in mirror_positions:
        if float(pos['size']) > 0:
            symbol = pos['symbol']
            side = pos['side']
            size = float(pos['size'])
            avg_price = float(pos['avgPrice'])
            logger.info(f"  {symbol} {side}: {size} @ ${avg_price}")
            mirror_active += 1
    
    # Count monitors
    main_monitors = len([k for k in monitors if k.endswith('_main')])
    mirror_monitors = len([k for k in monitors if k.endswith('_mirror')])
    
    logger.info(f"\n📊 SUMMARY:")
    logger.info(f"  Main positions: {main_active}")
    logger.info(f"  Mirror positions: {mirror_active}")
    logger.info(f"  Total positions: {main_active + mirror_active}")
    logger.info(f"  Main monitors: {main_monitors}")
    logger.info(f"  Mirror monitors: {mirror_monitors}")
    logger.info(f"  Total monitors: {main_monitors + mirror_monitors}")
    
    # The bot message "14 positions monitored" likely means 14 total positions
    logger.info(f"\n🤔 Bot shows: {main_active + mirror_active} positions monitored")
    
    return main_active + mirror_active

async def main():
    """Main entry point"""
    total = await check_positions()
    print(f"\n✅ Total active positions: {total}")

if __name__ == "__main__":
    asyncio.run(main())