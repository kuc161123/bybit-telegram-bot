#!/usr/bin/env python3
"""
Final verification that monitor key collision fix is complete
"""
import asyncio
import logging
import pickle
from decimal import Decimal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("=" * 60)
    logger.info("MONITOR KEY COLLISION FIX - FINAL VERIFICATION")
    logger.info("=" * 60)
    
    # Import clients
    from clients.bybit_client import bybit_client
    from execution.mirror_trader import bybit_client_2
    
    # Load monitors from pickle
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    enhanced_monitors = data['bot_data']['enhanced_tp_sl_monitors']
    
    # Get current positions
    logger.info("\n📊 CURRENT POSITIONS:")
    
    # Main account
    main_positions = []
    main_response = bybit_client.get_positions(category="linear", settleCoin="USDT")
    if main_response and main_response.get('retCode') == 0:
        positions = [p for p in main_response.get('result', {}).get('list', []) if float(p.get('size', 0)) > 0]
        for pos in positions:
            main_positions.append({
                'symbol': pos['symbol'],
                'side': pos['side'],
                'size': pos['size'],
                'expected_key': f"{pos['symbol']}_{pos['side']}_main"
            })
    
    logger.info(f"\nMain Account: {len(main_positions)} positions")
    for pos in main_positions:
        logger.info(f"  {pos['symbol']} {pos['side']} - Size: {pos['size']}")
    
    # Mirror account
    mirror_positions = []
    mirror_response = bybit_client_2.get_positions(category="linear", settleCoin="USDT")
    if mirror_response and mirror_response.get('retCode') == 0:
        positions = [p for p in mirror_response.get('result', {}).get('list', []) if float(p.get('size', 0)) > 0]
        for pos in positions:
            mirror_positions.append({
                'symbol': pos['symbol'],
                'side': pos['side'],
                'size': pos['size'],
                'expected_key': f"{pos['symbol']}_{pos['side']}_mirror"
            })
    
    logger.info(f"\nMirror Account: {len(mirror_positions)} positions")
    for pos in mirror_positions:
        logger.info(f"  {pos['symbol']} {pos['side']} - Size: {pos['size']}")
    
    # Check monitors
    logger.info("\n📋 MONITOR VERIFICATION:")
    
    # Check main positions
    logger.info("\nMain Account Monitors:")
    main_missing = []
    for pos in main_positions:
        if pos['expected_key'] in enhanced_monitors:
            monitor = enhanced_monitors[pos['expected_key']]
            alerts = "✓ Alerts ON" if monitor.get('chat_id') else "✗ No alerts"
            logger.info(f"  ✅ {pos['expected_key']} - {alerts}")
        else:
            main_missing.append(pos)
            logger.warning(f"  ❌ {pos['expected_key']} - MISSING!")
    
    # Check mirror positions
    logger.info("\nMirror Account Monitors:")
    mirror_missing = []
    for pos in mirror_positions:
        if pos['expected_key'] in enhanced_monitors:
            monitor = enhanced_monitors[pos['expected_key']]
            alerts = "✓ No alerts" if monitor.get('chat_id') is None else "✗ ALERTS ON!"
            logger.info(f"  ✅ {pos['expected_key']} - {alerts}")
        else:
            mirror_missing.append(pos)
            logger.warning(f"  ❌ {pos['expected_key']} - MISSING!")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    
    total_positions = len(main_positions) + len(mirror_positions)
    total_monitors = len(enhanced_monitors)
    main_monitors = sum(1 for k in enhanced_monitors if k.endswith('_main'))
    mirror_monitors = sum(1 for k in enhanced_monitors if k.endswith('_mirror'))
    
    logger.info(f"Total Positions: {total_positions} ({len(main_positions)} main + {len(mirror_positions)} mirror)")
    logger.info(f"Total Monitors: {total_monitors} ({main_monitors} main + {mirror_monitors} mirror)")
    
    if len(main_missing) == 0 and len(mirror_missing) == 0:
        logger.info("\n✅ ALL POSITIONS HAVE MONITORS!")
        logger.info("✅ Monitor key collision issue is RESOLVED!")
        logger.info("✅ Both accounts can now have the same symbol/side")
        
        # Verify alert settings
        main_alerts_ok = all(
            enhanced_monitors[pos['expected_key']].get('chat_id') is not None 
            for pos in main_positions 
            if pos['expected_key'] in enhanced_monitors
        )
        
        mirror_alerts_ok = all(
            enhanced_monitors[pos['expected_key']].get('chat_id') is None 
            for pos in mirror_positions 
            if pos['expected_key'] in enhanced_monitors
        )
        
        if main_alerts_ok and mirror_alerts_ok:
            logger.info("✅ Alert settings are correct:")
            logger.info("   - Main account: Alerts ENABLED")
            logger.info("   - Mirror account: Alerts DISABLED")
        else:
            if not main_alerts_ok:
                logger.warning("⚠️ Some main account monitors have alerts disabled")
            if not mirror_alerts_ok:
                logger.warning("⚠️ Some mirror account monitors have alerts enabled")
    else:
        logger.warning(f"\n⚠️ Found {len(main_missing) + len(mirror_missing)} positions without monitors")
        if main_missing:
            logger.warning(f"Main account missing: {len(main_missing)}")
        if mirror_missing:
            logger.warning(f"Mirror account missing: {len(mirror_missing)}")
    
    # Show all monitor keys
    logger.info("\n📋 All Monitor Keys:")
    for key in sorted(enhanced_monitors.keys()):
        logger.info(f"  {key}")
    
    logger.info("\n🎯 VERIFICATION COMPLETE!")

asyncio.run(main())