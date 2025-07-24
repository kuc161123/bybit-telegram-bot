#!/usr/bin/env python3
"""
Verify limit order tracking is properly configured
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

def verify_limit_order_setup():
    """Verify all monitors are ready to cancel limits on TP1"""
    
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    # Load pickle file
    try:
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        logger.error(f"Error loading pickle file: {e}")
        return
    
    # Get Enhanced TP/SL monitors
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ LIMIT ORDER TRACKING VERIFICATION")
    logger.info(f"{'='*60}")
    
    all_conservative = True
    all_have_limit_arrays = True
    positions_with_limits = 0
    total_limits = 0
    
    # Check each monitor
    for key, monitor in enhanced_monitors.items():
        symbol = monitor.get('symbol')
        side = monitor.get('side')
        approach = monitor.get('approach')
        phase = monitor.get('phase')
        tp1_hit = monitor.get('tp1_hit', False)
        limit_orders = monitor.get('limit_orders', [])
        active_limits = [o for o in limit_orders if o.get('status') == 'ACTIVE']
        account = 'Mirror' if key.endswith('_mirror') else 'Main'
        
        # Verify approach
        if approach != 'conservative':
            all_conservative = False
            logger.error(f"❌ {symbol} {side} ({account}) - Not Conservative approach!")
        
        # Verify limit_orders field exists
        if 'limit_orders' not in monitor:
            all_have_limit_arrays = False
            logger.error(f"❌ {symbol} {side} ({account}) - Missing limit_orders field!")
        
        # Count positions with limits
        if active_limits:
            positions_with_limits += 1
            total_limits += len(active_limits)
        
        # Log status
        status_icon = "✅" if approach == 'conservative' and 'limit_orders' in monitor else "❌"
        logger.info(f"\n{status_icon} {symbol} {side} ({account}):")
        logger.info(f"   Approach: {approach}")
        logger.info(f"   Phase: {phase}")
        logger.info(f"   TP1 Hit: {tp1_hit}")
        logger.info(f"   Limit Orders: {len(active_limits)} active")
        
        if tp1_hit and active_limits:
            logger.warning(f"   ⚠️ TP1 already hit but still has {len(active_limits)} active limits!")
    
    # Overall verification
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 VERIFICATION SUMMARY")
    logger.info(f"{'='*60}")
    
    # Check configuration
    from config.settings import CANCEL_LIMITS_ON_TP1
    logger.info(f"\n⚙️ CONFIGURATION:")
    logger.info(f"   CANCEL_LIMITS_ON_TP1: {CANCEL_LIMITS_ON_TP1}")
    
    # Check monitors
    logger.info(f"\n📈 MONITORS:")
    logger.info(f"   Total Monitors: {len(enhanced_monitors)}")
    logger.info(f"   All Conservative: {'✅ Yes' if all_conservative else '❌ No'}")
    logger.info(f"   All Have Limit Arrays: {'✅ Yes' if all_have_limit_arrays else '❌ No'}")
    logger.info(f"   Positions with Limits: {positions_with_limits}")
    logger.info(f"   Total Limit Orders: {total_limits}")
    
    # Final verdict
    logger.info(f"\n🎯 FINAL VERDICT:")
    if all_conservative and all_have_limit_arrays and CANCEL_LIMITS_ON_TP1:
        logger.info(f"   ✅ READY - All positions will cancel limit orders when TP1 hits!")
        logger.info(f"   📝 {positions_with_limits} positions have {total_limits} limit orders to cancel")
    else:
        logger.error(f"   ❌ NOT READY - Issues found:")
        if not all_conservative:
            logger.error(f"      - Some positions not set to Conservative")
        if not all_have_limit_arrays:
            logger.error(f"      - Some positions missing limit_orders field")
        if not CANCEL_LIMITS_ON_TP1:
            logger.error(f"      - CANCEL_LIMITS_ON_TP1 is disabled")

def main():
    """Main execution"""
    verify_limit_order_setup()

if __name__ == "__main__":
    main()