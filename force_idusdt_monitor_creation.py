#!/usr/bin/env python3
"""
Force IDUSDT_Buy_mirror monitor creation
Ensures the monitor persists through bot updates
"""

import pickle
import time
import os
import logging
from datetime import datetime
from decimal import Decimal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Force create IDUSDT_Buy_mirror monitor"""
    logger.info("🚀 Forcing IDUSDT_Buy_mirror monitor creation")
    
    # Multiple attempts to ensure persistence
    for attempt in range(3):
        try:
            # Load pickle
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
                data = pickle.load(f)
            
            # Get monitors
            monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
            
            # Check if already exists
            if 'IDUSDT_Buy_mirror' in monitors and monitors['IDUSDT_Buy_mirror'].get('chat_id'):
                logger.info(f"✅ Monitor already exists with chat_id")
                return
            
            # Find default chat_id
            chat_ids = {}
            for key, monitor in monitors.items():
                chat_id = monitor.get('chat_id')
                if chat_id:
                    chat_ids[chat_id] = chat_ids.get(chat_id, 0) + 1
            
            default_chat_id = max(chat_ids, key=chat_ids.get) if chat_ids else 5634913742
            
            # Create comprehensive monitor
            monitor_data = {
                'symbol': 'IDUSDT',
                'side': 'Buy',
                'chat_id': default_chat_id,
                'account': 'mirror',
                'account_type': 'mirror',
                'position_size': Decimal('77'),
                'initial_size': Decimal('77'),
                'remaining_size': Decimal('77'),
                'filled_size': Decimal('0'),
                'size': Decimal('77'),
                'entry_price': Decimal('0.17166'),
                'avg_entry_price': Decimal('0.17166'),
                'tp_orders': {},
                'sl_order': {
                    'order_id': 'c9bed50b-1c62-40cd-8626-f485eea06b1a',
                    'price': 0.1624,
                    'qty': 77.0,
                    'order_link_id': 'BOT_SL_IDUSDT_mirror_1752309550'
                },
                'status': 'active',
                'approach': 'CONSERVATIVE',
                'created_at': time.time(),
                'last_check': time.time(),
                'limit_orders_filled': True,
                'cancelled_orders': [],
                'tp1_hit': False,
                'sl_moved_to_breakeven': False,
                'monitoring_active': True
            }
            
            # Add to monitors
            monitors['IDUSDT_Buy_mirror'] = monitor_data
            
            # Also ensure monitor_tasks entry
            if 'monitor_tasks' not in data['bot_data']:
                data['bot_data']['monitor_tasks'] = {}
                
            data['bot_data']['monitor_tasks']['IDUSDT_Buy_mirror'] = {
                'symbol': 'IDUSDT',
                'side': 'Buy',
                'account': 'mirror',
                'created_at': time.time(),
                'chat_id': default_chat_id
            }
            
            # Backup and save
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_force_idusdt_{timestamp}'
            os.system(f'cp bybit_bot_dashboard_v4.1_enhanced.pkl {backup_file}')
            
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
                pickle.dump(data, f)
                
            logger.info(f"✅ Attempt {attempt+1}: Created IDUSDT_Buy_mirror monitor")
            
            # Create reload signals
            signal_files = [
                'reload_monitors.signal',
                'monitor_reload_trigger.signal',
                'reload_enhanced_monitors.signal',
                '.reload_enhanced_monitors',
                'force_reload.trigger'
            ]
            
            for signal_file in signal_files:
                with open(signal_file, 'w') as f:
                    f.write(str(time.time()))
                    
            logger.info("✅ Created reload signals")
            
            # Wait a bit between attempts
            if attempt < 2:
                time.sleep(2)
                
        except Exception as e:
            logger.error(f"❌ Attempt {attempt+1} failed: {e}")
            
    # Final verification
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        if 'IDUSDT_Buy_mirror' in monitors:
            logger.info("✅ SUCCESS: IDUSDT_Buy_mirror monitor created and persisted")
            logger.info("✅ Bot should now show 'Monitoring 27 positions'")
        else:
            logger.error("❌ Failed to create persistent monitor")
            
    except Exception as e:
        logger.error(f"❌ Final verification failed: {e}")

if __name__ == "__main__":
    main()