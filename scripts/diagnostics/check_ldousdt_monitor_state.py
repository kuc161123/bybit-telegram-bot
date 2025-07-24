#!/usr/bin/env python3
"""
Check LDOUSDT monitor state and phase
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

def check_ldousdt_monitor():
    """Check LDOUSDT monitor state"""
    
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
    
    # Look for LDOUSDT monitors
    ldousdt_monitors = {}
    for key, monitor in enhanced_monitors.items():
        if 'LDOUSDT' in key:
            ldousdt_monitors[key] = monitor
    
    logger.info(f"\n{'='*60}")
    logger.info(f"🔍 LDOUSDT Monitor Analysis")
    logger.info(f"{'='*60}")
    
    for key, monitor in ldousdt_monitors.items():
        logger.info(f"\n📊 Monitor: {key}")
        logger.info(f"   Symbol: {monitor.get('symbol')}")
        logger.info(f"   Side: {monitor.get('side')}")
        logger.info(f"   Account: {'Mirror' if key.endswith('_mirror') else 'Main'}")
        logger.info(f"   Position Size: {monitor.get('position_size')}")
        logger.info(f"   Phase: {monitor.get('phase', 'UNKNOWN')}")
        logger.info(f"   TP1 Hit: {monitor.get('tp1_hit', False)}")
        logger.info(f"   Approach: {monitor.get('approach', 'Unknown')}")
        
        # Check limit orders
        limit_orders = monitor.get('limit_orders', [])
        active_limits = [o for o in limit_orders if o.get('status') == 'ACTIVE']
        logger.info(f"   Limit Orders: {len(limit_orders)} total, {len(active_limits)} active")
        
        # Check if limit orders were cancelled
        cancelled_limits = monitor.get('limit_orders_cancelled', False)
        logger.info(f"   Limit Orders Cancelled Flag: {cancelled_limits}")
        
        # Check filled TPs
        filled_tps = monitor.get('filled_tps', [])
        logger.info(f"   Filled TPs: {filled_tps}")
        
        # Check TP orders
        tp_orders = monitor.get('tp_orders', {})
        logger.info(f"   TP Orders Tracked: {len(tp_orders)}")
        
        # If TP1 was hit but phase is wrong
        if monitor.get('tp1_hit') and monitor.get('phase') != 'PROFIT_TAKING':
            logger.warning(f"   ⚠️ INCONSISTENCY: TP1 hit but phase is {monitor.get('phase')}")
        
        # If in BUILDING phase with no active limits
        if monitor.get('phase') == 'BUILDING' and len(active_limits) == 0:
            logger.warning(f"   ⚠️ In BUILDING phase but no active limit orders")

if __name__ == "__main__":
    check_ldousdt_monitor()