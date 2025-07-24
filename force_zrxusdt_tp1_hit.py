#!/usr/bin/env python3
"""
Force TP1 hit for ZRXUSDT position
This script directly modifies the running bot's monitor state
"""
import pickle
import logging
from datetime import datetime
from decimal import Decimal
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pickle file path
PICKLE_FILE = 'bybit_bot_dashboard_v4.1_enhanced.pkl'

def force_tp1_hit():
    """Force TP1 hit status for ZRXUSDT"""
    try:
        # Create backup
        backup_file = f"{PICKLE_FILE}.backup_force_tp1_{int(datetime.now().timestamp())}"
        logger.info(f"Creating backup: {backup_file}")
        
        # Load pickle data
        with open(PICKLE_FILE, 'rb') as f:
            data = pickle.load(f)
        
        # Backup
        with open(backup_file, 'wb') as f:
            pickle.dump(data, f)
        
        # Get enhanced monitors
        if 'bot_data' not in data:
            data['bot_data'] = {}
        
        enhanced_monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
        
        logger.info(f"Found {len(enhanced_monitors)} enhanced monitors")
        logger.info(f"Monitor keys: {list(enhanced_monitors.keys())}")
        
        # Find ZRXUSDT monitors
        updated_count = 0
        
        for key, monitor in enhanced_monitors.items():
            if 'ZRXUSDT' in key and monitor.get('side') == 'Buy':
                logger.info(f"\n{'='*50}")
                logger.info(f"Processing monitor: {key}")
                logger.info(f"Current state: tp1_hit={monitor.get('tp1_hit', False)}, sl_moved_to_be={monitor.get('sl_moved_to_be', False)}")
                
                # Force TP1 hit
                monitor['tp1_hit'] = True
                monitor['phase'] = 'PROFIT_TAKING'
                monitor['limit_orders_cancelled'] = True
                
                # If there's no entry price, set a reasonable one
                if 'entry_price' not in monitor or 'avg_price' not in monitor:
                    monitor['entry_price'] = Decimal('0.4500')  # Example price
                    monitor['avg_price'] = Decimal('0.4500')
                
                # Mark first TP as filled if exists
                tp_orders = monitor.get('tp_orders', {})
                if isinstance(tp_orders, dict):
                    for order_id, tp_order in tp_orders.items():
                        if tp_order.get('tp_number') == 1:
                            tp_order['status'] = 'FILLED'
                            tp_order['fill_time'] = datetime.now().timestamp()
                            logger.info(f"Marked TP1 order as FILLED: {order_id[:8]}...")
                            break
                
                logger.info(f"Updated state: tp1_hit={monitor.get('tp1_hit')}, phase={monitor.get('phase')}")
                updated_count += 1
        
        if updated_count == 0:
            logger.warning("No ZRXUSDT Buy monitors found!")
            
            # Create a basic monitor for ZRXUSDT
            logger.info("\nCreating new monitor for ZRXUSDT Buy...")
            new_monitor = {
                'symbol': 'ZRXUSDT',
                'side': 'Buy',
                'position_size': Decimal('843'),
                'remaining_size': Decimal('605'),  # After TP1
                'entry_price': Decimal('0.4500'),
                'avg_price': Decimal('0.4500'),
                'approach': 'CONSERVATIVE',
                'tp1_hit': True,
                'sl_moved_to_be': True,
                'phase': 'PROFIT_TAKING',
                'limit_orders_cancelled': True,
                'tp_orders': {},
                'sl_order': None,
                'limit_orders': [],
                'account_type': 'main',
                'created_at': datetime.now().timestamp()
            }
            
            enhanced_monitors['ZRXUSDT_Buy'] = new_monitor
            logger.info("✅ Created new monitor with TP1 hit status")
            updated_count = 1
        
        # Save back to pickle
        data['bot_data']['enhanced_tp_sl_monitors'] = enhanced_monitors
        
        with open(PICKLE_FILE, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"\n{'='*50}")
        logger.info(f"✅ Updated {updated_count} monitors")
        logger.info("✅ Changes saved to pickle file")
        
        # Create reload signal
        reload_signal = 'reload_monitors.signal'
        with open(reload_signal, 'w') as f:
            f.write(str(datetime.now().timestamp()))
        logger.info("✅ Monitor reload signal created")
        
        # Also create a force reload trigger
        force_trigger = 'force_reload.trigger'
        with open(force_trigger, 'w') as f:
            f.write(str(datetime.now().timestamp()))
        logger.info("✅ Force reload trigger created")
        
        logger.info("\n⚠️  IMPORTANT: The bot needs to reload monitors to see these changes.")
        logger.info("    The reload signal has been created.")
        logger.info("    Changes will take effect on the next monitoring cycle.")
        
    except Exception as e:
        logger.error(f"Error forcing TP1 hit: {e}")
        import traceback
        traceback.print_exc()

def verify_changes():
    """Verify the changes in pickle file"""
    try:
        with open(PICKLE_FILE, 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        logger.info(f"\n{'='*50}")
        logger.info("VERIFICATION")
        logger.info(f"{'='*50}")
        
        for key, monitor in enhanced_monitors.items():
            if 'ZRXUSDT' in key and monitor.get('side') == 'Buy':
                logger.info(f"\nMonitor: {key}")
                logger.info(f"  TP1 Hit: {monitor.get('tp1_hit', False)}")
                logger.info(f"  Phase: {monitor.get('phase', 'UNKNOWN')}")
                logger.info(f"  SL at Breakeven: {monitor.get('sl_moved_to_be', False)}")
                logger.info(f"  Limit Orders Cancelled: {monitor.get('limit_orders_cancelled', False)}")
                
    except Exception as e:
        logger.error(f"Error verifying changes: {e}")

if __name__ == "__main__":
    logger.info("ZRXUSDT Force TP1 Hit")
    logger.info("=" * 50)
    
    # Check if pickle file exists
    if not os.path.exists(PICKLE_FILE):
        logger.error(f"Pickle file not found: {PICKLE_FILE}")
        exit(1)
    
    # Force the TP1 hit
    force_tp1_hit()
    
    # Verify
    verify_changes()
    
    logger.info("\n" + "=" * 50)
    logger.info("Process completed!")