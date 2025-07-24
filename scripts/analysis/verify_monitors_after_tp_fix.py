#!/usr/bin/env python3
"""
Verify monitors are tracking correctly after TP order fixes
"""

import pickle
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_monitors():
    """Check monitor status after TP fixes"""
    
    # Load pickle file
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    try:
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        logger.error(f"Error loading pickle file: {e}")
        return
    
    # Check Enhanced TP/SL monitors
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 ENHANCED TP/SL MONITORS")
    logger.info(f"{'='*60}")
    logger.info(f"Total monitors: {len(enhanced_monitors)}")
    
    # Group by account type
    main_monitors = []
    mirror_monitors = []
    
    for key, monitor in enhanced_monitors.items():
        if key.endswith('_mirror'):
            mirror_monitors.append((key, monitor))
        else:
            main_monitors.append((key, monitor))
    
    logger.info(f"\n📈 Main Account Monitors: {len(main_monitors)}")
    for key, monitor in sorted(main_monitors):
        symbol = monitor.get('symbol', 'Unknown')
        side = monitor.get('side', 'Unknown')
        position_size = monitor.get('position_size', 0)
        tp_orders = monitor.get('tp_orders', {})
        logger.info(f"   {symbol} {side}: {position_size} units, {len(tp_orders)} TP orders")
    
    logger.info(f"\n📉 Mirror Account Monitors: {len(mirror_monitors)}")
    for key, monitor in sorted(mirror_monitors):
        symbol = monitor.get('symbol', 'Unknown')
        side = monitor.get('side', 'Unknown')
        position_size = monitor.get('position_size', 0)
        tp_orders = monitor.get('tp_orders', {})
        logger.info(f"   {symbol} {side}: {position_size} units, {len(tp_orders)} TP orders")
    
    # Positions that were fixed
    fixed_main = ['ICPUSDT_Sell', 'LDOUSDT_Sell', 'IDUSDT_Sell']
    fixed_mirror = ['XRPUSDT_Buy_mirror', 'IDUSDT_Sell_mirror', 'JUPUSDT_Sell_mirror', 
                   'ICPUSDT_Sell_mirror', 'LDOUSDT_Sell_mirror']
    
    # Check if fixed positions have monitors
    logger.info(f"\n🔧 Fixed Positions Check:")
    
    logger.info(f"\nMain Account Fixed Positions:")
    for pos_key in fixed_main:
        if pos_key in enhanced_monitors:
            monitor = enhanced_monitors[pos_key]
            tp_count = len(monitor.get('tp_orders', {}))
            logger.info(f"   ✅ {pos_key}: Monitor active, {tp_count} TP orders tracked")
        else:
            logger.error(f"   ❌ {pos_key}: No monitor found!")
    
    logger.info(f"\nMirror Account Fixed Positions:")
    for pos_key in fixed_mirror:
        if pos_key in enhanced_monitors:
            monitor = enhanced_monitors[pos_key]
            tp_count = len(monitor.get('tp_orders', {}))
            logger.info(f"   ✅ {pos_key}: Monitor active, {tp_count} TP orders tracked")
        else:
            logger.error(f"   ❌ {pos_key}: No monitor found!")
    
    # Check dashboard monitors
    dashboard_monitors = data.get('bot_data', {}).get('monitor_tasks', {})
    active_dashboard = len([m for m in dashboard_monitors.values() 
                           if m.get('status') == 'active'])
    
    logger.info(f"\n📱 Dashboard Monitors:")
    logger.info(f"   Total: {len(dashboard_monitors)}")
    logger.info(f"   Active: {active_dashboard}")
    
    # Summary
    total_positions = len(main_monitors) + len(mirror_monitors)
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total Enhanced Monitors: {total_positions}")
    logger.info(f"Main Account: {len(main_monitors)}")
    logger.info(f"Mirror Account: {len(mirror_monitors)}")
    logger.info(f"Expected: 15 (8 main + 7 mirror)")
    
    if total_positions == 15:
        logger.info(f"✅ Monitor count is correct!")
    else:
        logger.warning(f"⚠️ Monitor count mismatch: {total_positions} vs 15 expected")
    
    logger.info(f"\n💡 The TP order fixes do not require monitor updates.")
    logger.info(f"   Monitors track positions, not individual orders.")
    logger.info(f"   The monitoring logic will use the new TP orders automatically.")

if __name__ == "__main__":
    check_monitors()