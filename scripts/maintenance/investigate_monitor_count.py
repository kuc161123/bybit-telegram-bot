#!/usr/bin/env python3
"""
Investigate why only 7 monitors are showing instead of 13
"""
import asyncio
import pickle
import logging
from decimal import Decimal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    # First check positions on both accounts
    from clients.bybit_client import bybit_client
    from execution.mirror_trader import bybit_client_2
    
    logger.info("=" * 60)
    logger.info("MONITOR COUNT INVESTIGATION")
    logger.info("=" * 60)
    
    # Get main account positions
    logger.info("\n📊 MAIN ACCOUNT POSITIONS:")
    main_response = bybit_client.get_positions(category="linear", settleCoin="USDT")
    main_positions = []
    if main_response and main_response.get('retCode') == 0:
        positions = [p for p in main_response.get('result', {}).get('list', []) if float(p.get('size', 0)) > 0]
        for pos in positions:
            main_positions.append({
                'symbol': pos['symbol'],
                'side': pos['side'],
                'size': pos['size'],
                'key': f"{pos['symbol']}_{pos['side']}"
            })
            logger.info(f"  {pos['symbol']} {pos['side']} - Size: {pos['size']}")
    
    logger.info(f"\nTotal main positions: {len(main_positions)}")
    
    # Get mirror account positions  
    logger.info("\n📊 MIRROR ACCOUNT POSITIONS:")
    mirror_response = bybit_client_2.get_positions(category="linear", settleCoin="USDT")
    mirror_positions = []
    if mirror_response and mirror_response.get('retCode') == 0:
        positions = [p for p in mirror_response.get('result', {}).get('list', []) if float(p.get('size', 0)) > 0]
        for pos in positions:
            mirror_positions.append({
                'symbol': pos['symbol'],
                'side': pos['side'],
                'size': pos['size'],
                'key': f"{pos['symbol']}_{pos['side']}"
            })
            logger.info(f"  {pos['symbol']} {pos['side']} - Size: {pos['size']}")
    
    logger.info(f"\nTotal mirror positions: {len(mirror_positions)}")
    
    # Check monitors in pickle
    logger.info("\n📁 ENHANCED MONITORS IN PICKLE:")
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    main_monitors = []
    mirror_monitors = []
    
    for key, monitor in enhanced_monitors.items():
        account = monitor.get('account_type', 'main')
        if account == 'mirror':
            mirror_monitors.append(key)
        else:
            main_monitors.append(key)
    
    logger.info(f"Main account monitors: {len(main_monitors)} - {main_monitors}")
    logger.info(f"Mirror account monitors: {len(mirror_monitors)} - {mirror_monitors}")
    
    # Check for missing monitors
    logger.info("\n🔍 MISSING MONITORS:")
    
    # Main positions without monitors
    main_keys = {p['key'] for p in main_positions}
    monitored_main_keys = set(main_monitors)
    missing_main = main_keys - monitored_main_keys
    
    if missing_main:
        logger.warning(f"\n❌ Main positions WITHOUT monitors: {len(missing_main)}")
        for key in missing_main:
            pos = next(p for p in main_positions if p['key'] == key)
            logger.warning(f"  - {pos['symbol']} {pos['side']}")
    else:
        logger.info("✅ All main positions have monitors")
    
    # Mirror positions without monitors
    mirror_keys = {p['key'] for p in mirror_positions}
    monitored_mirror_keys = set(mirror_monitors)
    missing_mirror = mirror_keys - monitored_mirror_keys
    
    if missing_mirror:
        logger.warning(f"\n❌ Mirror positions WITHOUT monitors: {len(missing_mirror)}")
        for key in missing_mirror:
            pos = next(p for p in mirror_positions if p['key'] == key)
            logger.warning(f"  - {pos['symbol']} {pos['side']}")
    else:
        logger.info("✅ All mirror positions have monitors")
    
    # Check for key collisions
    logger.info("\n🔑 KEY COLLISION CHECK:")
    all_position_keys = main_keys | mirror_keys
    colliding_keys = main_keys & mirror_keys
    
    if colliding_keys:
        logger.warning(f"⚠️ Found {len(colliding_keys)} positions on BOTH accounts:")
        for key in colliding_keys:
            logger.warning(f"  - {key}")
            logger.warning(f"    This explains why you can't have monitors for both!")
    else:
        logger.info("✅ No key collisions found")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total positions: {len(main_positions)} main + {len(mirror_positions)} mirror = {len(main_positions) + len(mirror_positions)}")
    logger.info(f"Total monitors: {len(enhanced_monitors)} ({len(main_monitors)} main + {len(mirror_monitors)} mirror)")
    logger.info(f"Missing monitors: {len(missing_main)} main + {len(missing_mirror)} mirror = {len(missing_main) + len(missing_mirror)}")
    
    if len(enhanced_monitors) < len(main_positions) + len(mirror_positions):
        logger.warning(f"\n⚠️ You have {len(main_positions) + len(mirror_positions)} positions but only {len(enhanced_monitors)} monitors!")
        logger.warning("This is likely due to:")
        logger.warning("1. Missing monitors for some positions")
        logger.warning("2. Key collisions (same symbol/side on both accounts)")
        logger.warning("3. Recently opened positions without monitors")

asyncio.run(main())