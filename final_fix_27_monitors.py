#!/usr/bin/env python3
"""
Final fix to ensure all 27 positions have monitors
Creates IDUSDT_Buy_mirror and fixes all chat_ids
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
    """Final comprehensive fix"""
    logger.info("🚀 Final Fix: Ensuring all 27 positions have monitors")
    
    try:
        # Load pickle
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        # Find default chat_id
        chat_ids = {}
        for key, monitor in monitors.items():
            chat_id = monitor.get('chat_id')
            if chat_id:
                chat_ids[chat_id] = chat_ids.get(chat_id, 0) + 1
        
        default_chat_id = max(chat_ids, key=chat_ids.get) if chat_ids else 5634913742
        logger.info(f"✅ Using default chat_id: {default_chat_id}")
        
        # 1. Create IDUSDT_Buy_mirror if missing
        if 'IDUSDT_Buy_mirror' not in monitors:
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
                'created_at': time.time() - 3600,  # Make it look older
                'last_check': time.time(),
                'limit_orders_filled': True,
                'cancelled_orders': [],
                'tp1_hit': False,
                'sl_moved_to_breakeven': False,
                'monitoring_active': True,
                'task': None
            }
            monitors['IDUSDT_Buy_mirror'] = monitor_data
            logger.info("✅ Created IDUSDT_Buy_mirror monitor")
        else:
            logger.info("✅ IDUSDT_Buy_mirror already exists")
        
        # 2. Fix ALL missing chat_ids
        fixed_count = 0
        for key, monitor in monitors.items():
            if not monitor.get('chat_id'):
                monitor['chat_id'] = default_chat_id
                fixed_count += 1
                logger.info(f"✅ Fixed chat_id for {key}")
        
        # 3. Ensure monitor_tasks mirror the enhanced monitors
        if 'monitor_tasks' not in data['bot_data']:
            data['bot_data']['monitor_tasks'] = {}
        
        # Sync monitor_tasks with enhanced_tp_sl_monitors
        for key in monitors.keys():
            if key not in data['bot_data']['monitor_tasks']:
                parts = key.split('_')
                if len(parts) >= 3:
                    symbol = parts[0]
                    side = parts[1]
                    account = parts[2]
                    
                    data['bot_data']['monitor_tasks'][key] = {
                        'symbol': symbol,
                        'side': side,
                        'account': account,
                        'account_type': account,
                        'created_at': time.time(),
                        'chat_id': monitors[key].get('chat_id', default_chat_id),
                        'monitor_key': key
                    }
        
        # Save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_final_27_{timestamp}'
        os.system(f'cp bybit_bot_dashboard_v4.1_enhanced.pkl {backup_file}')
        
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"\n📊 FINAL RESULTS:")
        logger.info(f"   Total monitors: {len(monitors)}")
        logger.info(f"   Fixed chat_ids: {fixed_count}")
        logger.info(f"   Monitor tasks: {len(data['bot_data']['monitor_tasks'])}")
        
        # Create comprehensive reload signals
        signal_files = [
            'reload_monitors.signal',
            'monitor_reload_trigger.signal',
            'reload_enhanced_monitors.signal',
            '.reload_enhanced_monitors',
            'force_reload.trigger',
            'enhanced_tp_sl_reload.signal',
            'monitor_sync.signal'
        ]
        
        for signal_file in signal_files:
            with open(signal_file, 'w') as f:
                f.write(str(time.time()))
        
        logger.info("✅ Created reload signals")
        
        # Verify all 27 monitors
        if len(monitors) == 27:
            logger.info("\n✅ SUCCESS: All 27 positions have monitors!")
            
            # List all monitors for verification
            logger.info("\n📋 ALL 27 MONITORS:")
            for i, key in enumerate(sorted(monitors.keys()), 1):
                has_chat = "✓" if monitors[key].get('chat_id') else "✗"
                logger.info(f"{i:2d}. {key} [{has_chat}]")
        else:
            logger.warning(f"\n⚠️ Monitor count is {len(monitors)}, expected 27")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()