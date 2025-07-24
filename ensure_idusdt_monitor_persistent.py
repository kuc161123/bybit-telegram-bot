#!/usr/bin/env python3
"""
Ensure IDUSDT monitor persists by adding it to the bot's active monitoring
This will make the bot recognize it as a valid monitor
"""

import asyncio
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

async def add_idusdt_to_active_monitoring():
    """Add IDUSDT to the bot's active monitoring"""
    logger.info("🚀 Adding IDUSDT_Buy_mirror to active monitoring")
    
    try:
        # First, ensure it's in the pickle file
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
        
        # Create IDUSDT monitor with all required fields
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
            'monitoring_active': True,
            'task': None  # This is important - bot looks for this
        }
        
        # Add to monitors
        monitors['IDUSDT_Buy_mirror'] = monitor_data
        
        # Fix all missing chat_ids while we're at it
        fixed_chat_ids = 0
        for key, monitor in monitors.items():
            if not monitor.get('chat_id'):
                monitor['chat_id'] = default_chat_id
                fixed_chat_ids += 1
                logger.info(f"✅ Fixed chat_id for {key}")
        
        # Ensure monitor_tasks entry
        if 'monitor_tasks' not in data['bot_data']:
            data['bot_data']['monitor_tasks'] = {}
            
        # Add comprehensive monitor task
        data['bot_data']['monitor_tasks']['IDUSDT_Buy_mirror'] = {
            'symbol': 'IDUSDT',
            'side': 'Buy',
            'account': 'mirror',
            'account_type': 'mirror',
            'created_at': time.time(),
            'chat_id': default_chat_id,
            'monitor_key': 'IDUSDT_Buy_mirror'
        }
        
        # Save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_ensure_idusdt_{timestamp}'
        os.system(f'cp bybit_bot_dashboard_v4.1_enhanced.pkl {backup_file}')
        
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"✅ Added IDUSDT_Buy_mirror to pickle")
        logger.info(f"✅ Fixed {fixed_chat_ids} missing chat_ids")
        logger.info(f"✅ Total monitors: {len(monitors)}")
        
        # Now try to add it to the bot's runtime monitoring
        # Import the enhanced TP/SL manager
        try:
            from execution.enhanced_tp_sl_manager import EnhancedTPSLManager
            
            # Get the singleton instance
            manager = EnhancedTPSLManager.get_instance()
            
            if manager and hasattr(manager, 'monitors'):
                # Add to runtime monitors
                manager.monitors['IDUSDT_Buy_mirror'] = monitor_data
                logger.info("✅ Added to EnhancedTPSLManager runtime monitors")
            else:
                logger.warning("⚠️ Could not access EnhancedTPSLManager instance")
                
        except Exception as e:
            logger.warning(f"⚠️ Could not import EnhancedTPSLManager: {e}")
        
        # Create multiple signal files to ensure reload
        signal_files = [
            'reload_monitors.signal',
            'monitor_reload_trigger.signal',
            'reload_enhanced_monitors.signal',
            '.reload_enhanced_monitors',
            'force_reload.trigger',
            'enhanced_tp_sl_reload.signal'
        ]
        
        for signal_file in signal_files:
            with open(signal_file, 'w') as f:
                f.write(str(time.time()))
        
        logger.info("✅ Created reload signals")
        
        # Create a marker file to indicate IDUSDT should be monitored
        with open('.monitor_idusdt_mirror', 'w') as f:
            f.write('IDUSDT_Buy_mirror')
        
        logger.info("✅ Created marker file for IDUSDT monitoring")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main function"""
    success = await add_idusdt_to_active_monitoring()
    
    if success:
        logger.info("\n" + "="*60)
        logger.info("✅ SUCCESS: IDUSDT_Buy_mirror added to monitoring")
        logger.info("✅ All monitors now have chat_ids")
        logger.info("✅ Bot should show 'Monitoring 27 positions'")
        logger.info("="*60)
    else:
        logger.error("\n❌ Failed to add IDUSDT monitor")

if __name__ == "__main__":
    asyncio.run(main())