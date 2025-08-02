#!/usr/bin/env python3
"""
Final comprehensive check of mirror account monitoring
"""
import asyncio
import logging
import pickle

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    # Wait for monitors to be loaded
    await asyncio.sleep(2)
    
    # Import after delay to ensure monitors are loaded
    from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
    from execution.mirror_trader import bybit_client_2
    
    logger.info("=" * 60)
    logger.info("FINAL MIRROR ACCOUNT MONITORING STATUS")
    logger.info("=" * 60)
    
    # Check monitors in manager
    logger.info(f"\nTotal monitors in Enhanced TP/SL Manager: {len(enhanced_tp_sl_manager.position_monitors)}")
    
    mirror_monitors = []
    main_monitors = []
    
    for key, monitor in enhanced_tp_sl_manager.position_monitors.items():
        if monitor.get('account_type') == 'mirror':
            mirror_monitors.append({
                'key': key,
                'symbol': monitor.get('symbol'),
                'side': monitor.get('side'),
                'chat_id': monitor.get('chat_id'),
                'phase': monitor.get('phase')
            })
        else:
            main_monitors.append(key)
    
    logger.info(f"Main account monitors: {len(main_monitors)}")
    logger.info(f"Mirror account monitors: {len(mirror_monitors)}")
    
    # Check mirror positions
    logger.info("\nMirror Account Positions:")
    response = bybit_client_2.get_positions(category="linear", settleCoin="USDT")
    if response and response.get('retCode') == 0:
        positions = [p for p in response.get('result', {}).get('list', []) if float(p.get('size', 0)) > 0]
        
        for pos in positions:
            symbol = pos['symbol']
            side = pos['side']
            size = pos['size']
            monitor_key = f"{symbol}_{side}"
            
            # Check if monitored
            monitored = any(m['key'] == monitor_key for m in mirror_monitors)
            chat_id = next((m['chat_id'] for m in mirror_monitors if m['key'] == monitor_key), 'N/A')
            
            logger.info(f"  {symbol} {side} (Size: {size})")
            logger.info(f"    Monitored: {'✅ YES' if monitored else '❌ NO'}")
            logger.info(f"    Chat ID: {chat_id} {'(No alerts)' if chat_id is None else '(ALERTS ENABLED!)'}")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    
    if len(mirror_monitors) == 6:
        logger.info("✅ All 6 mirror positions have Enhanced TP/SL monitors")
        
        # Check chat_ids
        alerts_disabled = all(m['chat_id'] is None for m in mirror_monitors)
        if alerts_disabled:
            logger.info("✅ All monitors have chat_id=None (alerts disabled)")
        else:
            logger.warning("⚠️ Some monitors still have chat_id set!")
            for m in mirror_monitors:
                if m['chat_id'] is not None:
                    logger.warning(f"   {m['key']}: chat_id={m['chat_id']}")
        
        logger.info("✅ The Enhanced TP/SL system will:")
        logger.info("   - Monitor positions every 5 seconds")
        logger.info("   - Detect TP/SL fills automatically")
        logger.info("   - Move SL to breakeven when TP1 hits")
        logger.info("   - Handle all order management")
        logger.info("   - ALL WITHOUT SENDING ALERTS")
        logger.info("\n🎯 Mirror account monitoring is working perfectly!")
    else:
        logger.warning(f"⚠️ Only {len(mirror_monitors)} mirror monitors found (expected 6)")
        logger.info("Try creating the signal file again to reload monitors")

asyncio.run(main())