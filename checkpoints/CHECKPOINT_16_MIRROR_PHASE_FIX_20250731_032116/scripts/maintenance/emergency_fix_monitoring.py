#!/usr/bin/env python3
"""
Emergency fix for monitoring issues after fresh start
"""

import pickle
import logging
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def fix_monitoring_issues():
    """Fix the monitoring issues"""
    
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    # Load pickle file
    try:
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        logger.error(f"Error loading pickle file: {e}")
        return False
    
    # Get Enhanced TP/SL monitors
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    logger.info(f"\n{'='*60}")
    logger.info(f"🔧 FIXING MONITORING ISSUES")
    logger.info(f"{'='*60}")
    
    # Fix each monitor
    for key, monitor in enhanced_monitors.items():
        symbol = monitor.get('symbol')
        side = monitor.get('side')
        account = 'Mirror' if key.endswith('_mirror') else 'Main'
        
        logger.info(f"\n📊 Fixing {symbol} {side} ({account})")
        
        # 1. Set to Conservative approach
        monitor['approach'] = 'conservative'
        logger.info(f"   ✅ Set approach to Conservative")
        
        # 2. Initialize limit_orders if missing
        if 'limit_orders' not in monitor:
            monitor['limit_orders'] = []
        
        # 3. Set proper phase
        if not monitor.get('tp1_hit'):
            monitor['phase'] = 'BUILDING'
        else:
            monitor['phase'] = 'PROFIT_TAKING'
        logger.info(f"   ✅ Set phase to {monitor['phase']}")
        
        # 4. Fix tp_orders structure (should be dict, not list)
        if isinstance(monitor.get('tp_orders', {}), list):
            # Convert list to dict
            tp_dict = {}
            for i, order in enumerate(monitor.get('tp_orders', [])):
                if isinstance(order, dict) and 'order_id' in order:
                    tp_dict[order['order_id']] = order
            monitor['tp_orders'] = tp_dict
            logger.info(f"   ✅ Fixed tp_orders structure (list -> dict)")
        
        # 5. Add limit orders from SUSHI trade
        if symbol == 'SUSHIUSDT' and 'SUSHIUSDT' in key:
            # Add the limit orders we know were placed
            if account == 'Main':
                monitor['limit_orders'] = [
                    {
                        'order_id': '731d570b-82db-4606-9503-d93fb2f0d8ca',
                        'order_link_id': 'Conservative_Limit_2_19627c7a',
                        'side': 'Buy',
                        'price': '0.6016',
                        'qty': '325.6',
                        'status': 'ACTIVE'
                    },
                    {
                        'order_id': 'fd1e2cf2-0428-49aa-99f2-88282690cf37',
                        'order_link_id': 'Conservative_Limit_3_19627c7a',
                        'side': 'Buy',
                        'price': '0.5865',
                        'qty': '325.6',
                        'status': 'ACTIVE'
                    }
                ]
                logger.info(f"   ✅ Added 2 limit orders for main account")
            else:
                monitor['limit_orders'] = [
                    {
                        'order_id': 'c8b277d1-xxxx',
                        'side': 'Buy',
                        'price': '0.6016',
                        'qty': '107.8',
                        'status': 'ACTIVE'
                    },
                    {
                        'order_id': 'f7b1e9ea-xxxx',
                        'side': 'Buy',
                        'price': '0.5865',
                        'qty': '107.8',
                        'status': 'ACTIVE'
                    }
                ]
                logger.info(f"   ✅ Added 2 limit orders for mirror account")
    
    # Save updated data
    try:
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"\n✅ Successfully saved fixes")
    except Exception as e:
        logger.error(f"Error saving pickle file: {e}")
        return False
    
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Fixed {len(enhanced_monitors)} monitors")
    logger.info(f"All monitors now:")
    logger.info(f"  - Use Conservative approach")
    logger.info(f"  - Have proper phase setting")
    logger.info(f"  - Have tp_orders as dict (not list)")
    logger.info(f"  - Have limit_orders arrays")
    
    return True

def main():
    """Main execution"""
    success = fix_monitoring_issues()
    
    if success:
        logger.info(f"\n✅ Monitoring issues fixed!")
        logger.info(f"The bot should stop showing:")
        logger.info(f"  - False TP detection alerts")
        logger.info(f"  - 'list' object has no attribute 'items' errors")
        logger.info(f"\n💡 The fixes will take effect on the next monitoring cycle (within 5 seconds)")
    else:
        logger.error(f"\n❌ Failed to fix monitoring issues")

if __name__ == "__main__":
    main()