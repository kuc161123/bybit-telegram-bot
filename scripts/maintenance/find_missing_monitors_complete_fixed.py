#!/usr/bin/env python3
"""
Find missing Enhanced TP/SL monitors for both main and mirror accounts
Uses correct key format: {SYMBOL}_{SIDE}_{ACCOUNT_TYPE}
"""

import asyncio
import logging
from decimal import Decimal
from clients.bybit_helpers import get_position_info
from execution.mirror_trader import get_mirror_client
import pickle

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def find_missing_monitors():
    """Find positions without Enhanced TP/SL monitors"""
    
    # Get main account positions
    logger.info("📊 Fetching main account positions...")
    main_positions = await get_position_info()
    
    # Get mirror account positions
    logger.info("📊 Fetching mirror account positions...")
    mirror_client = get_mirror_client()
    
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
    
    # Check main positions
    main_active = []
    main_missing = []
    
    logger.info("\n📊 MAIN ACCOUNT POSITIONS:")
    for pos in main_positions:
        if float(pos['size']) > 0:
            symbol = pos['symbol']
            side = pos['side']
            size = float(pos['size'])
            avg_price = float(pos['avgPrice'])
            
            # Correct key format
            monitor_key = f"{symbol}_{side}_main"
            
            if monitor_key in monitors:
                logger.info(f"✅ {symbol} {side}: {size} @ ${avg_price} - Monitor exists")
                main_active.append((symbol, side, size, avg_price))
            else:
                logger.warning(f"❌ {symbol} {side}: {size} @ ${avg_price} - MISSING MONITOR!")
                main_missing.append((symbol, side, size, avg_price, monitor_key))
    
    # Check mirror positions
    mirror_active = []
    mirror_missing = []
    
    logger.info("\n📊 MIRROR ACCOUNT POSITIONS:")
    for pos in mirror_positions:
        if float(pos['size']) > 0:
            symbol = pos['symbol']
            side = pos['side']
            size = float(pos['size'])
            avg_price = float(pos['avgPrice'])
            
            # Correct key format
            monitor_key = f"{symbol}_{side}_mirror"
            
            if monitor_key in monitors:
                logger.info(f"✅ {symbol} {side}: {size} @ ${avg_price} - Monitor exists")
                mirror_active.append((symbol, side, size, avg_price))
            else:
                logger.warning(f"❌ {symbol} {side}: {size} @ ${avg_price} - MISSING MONITOR!")
                mirror_missing.append((symbol, side, size, avg_price, monitor_key))
    
    # Summary
    total_positions = len(main_active) + len(main_missing) + len(mirror_active) + len(mirror_missing)
    total_monitors = len([k for k in monitors if k.endswith('_main') or k.endswith('_mirror')])
    
    logger.info(f"\n📊 SUMMARY:")
    logger.info(f"  Main positions: {len(main_active) + len(main_missing)}")
    logger.info(f"  Mirror positions: {len(mirror_active) + len(mirror_missing)}")
    logger.info(f"  Total positions: {total_positions}")
    logger.info(f"  Total monitors: {total_monitors}")
    logger.info(f"  Missing monitors: {len(main_missing) + len(mirror_missing)}")
    
    if main_missing:
        logger.info(f"\n❌ MISSING MAIN MONITORS ({len(main_missing)}):")
        for symbol, side, size, price, key in main_missing:
            logger.info(f"  - {key}: {size} @ ${price}")
    
    if mirror_missing:
        logger.info(f"\n❌ MISSING MIRROR MONITORS ({len(mirror_missing)}):")
        for symbol, side, size, price, key in mirror_missing:
            logger.info(f"  - {key}: {size} @ ${price}")
    
    # Show all existing monitors
    logger.info(f"\n📋 ALL EXISTING MONITORS ({total_monitors}):")
    for key in sorted(monitors.keys()):
        if key.endswith('_main') or key.endswith('_mirror'):
            m = monitors[key]
            logger.info(f"  - {key}: {m.get('position_size', 'N/A')} @ {m.get('entry_price', 'N/A')}")
    
    return {
        'main_missing': main_missing,
        'mirror_missing': mirror_missing,
        'total_positions': total_positions,
        'total_monitors': total_monitors
    }

async def main():
    """Main entry point"""
    result = await find_missing_monitors()
    
    missing_count = len(result['main_missing']) + len(result['mirror_missing'])
    if missing_count > 0:
        print(f"\n⚠️ Found {missing_count} missing monitors!")
        print(f"📊 Should have {result['total_positions']} monitors, but only have {result['total_monitors']}")
    else:
        print(f"\n✅ All {result['total_positions']} positions have monitors!")

if __name__ == "__main__":
    asyncio.run(main())