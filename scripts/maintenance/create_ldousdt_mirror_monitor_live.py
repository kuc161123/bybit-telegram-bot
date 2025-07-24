#!/usr/bin/env python3
"""
Create LDOUSDT mirror monitor for the running bot
"""

import asyncio
import logging
from decimal import Decimal
from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def create_monitor():
    """Create LDOUSDT mirror monitor"""
    
    # Import the create_monitor method
    monitor_key = 'LDOUSDT_Sell_mirror'
    
    # Create monitor data based on the position we know exists
    # LDOUSDT mirror: 129.4 @ $0.7226
    monitor_data = {
        'symbol': 'LDOUSDT',
        'side': 'Sell',
        'position_size': Decimal('129.4'),
        'remaining_size': Decimal('129.4'),
        'entry_price': Decimal('0.7226'),
        'avg_price': Decimal('0.7226'),
        'approach': 'conservative',
        'tp_orders': {
            'efccf0a8-de77-4d76-8fc8-e19b3c2f4cf6': {
                'price': Decimal('0.7081'),
                'qty': Decimal('110.0'),
                'percentage': 85
            },
            '8dc6c731-f0f9-4b0f-9e00-c096b0f4fba9': {
                'price': Decimal('0.6937'),
                'qty': Decimal('6.5'),
                'percentage': 5
            },
            'dcc42b1f-d1fc-4683-a86a-cbfa6cf7c0f6': {
                'price': Decimal('0.7009'),
                'qty': Decimal('6.5'),
                'percentage': 5
            },
            '0c1bc5c0-d7c9-4ffd-8f7f-7c36a59f3d45': {
                'price': Decimal('0.6865'),
                'qty': Decimal('6.5'),
                'percentage': 5
            }
        },
        'sl_order': {
            'order_id': 'ce5ed90f-f816-4b81-a02f-8dfbc0c11343',
            'price': Decimal('0.7371'),
            'qty': Decimal('129.4')
        },
        'filled_tps': [],
        'cancelled_limits': False,
        'tp1_hit': False,
        'tp1_info': None,
        'sl_moved_to_be': False,
        'sl_move_attempts': 0,
        'limit_orders': [],
        'limit_orders_cancelled': False,
        'phase': 'MONITORING',
        'chat_id': None,
        'account_type': 'mirror',
        'has_mirror': True
    }
    
    # Save to pickle and start monitoring
    import pickle
    import time
    
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    # Load, update, save
    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)
    
    # Add to enhanced monitors
    monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
    monitors[monitor_key] = monitor_data
    monitors[monitor_key]['created_at'] = time.time()
    monitors[monitor_key]['last_check'] = time.time()
    
    # Save back
    with open(pkl_path, 'wb') as f:
        pickle.dump(data, f)
    
    logger.info(f"✅ Created {monitor_key} in pickle")
    
    # Start monitoring task
    task = asyncio.create_task(
        enhanced_tp_sl_manager._run_monitor_loop(monitor_key, 'mirror')
    )
    
    # Store in position_monitors
    enhanced_tp_sl_manager.position_monitors[monitor_key] = {
        'task': task,
        'started_at': asyncio.get_event_loop().time(),
        'account_type': 'mirror'
    }
    
    logger.info(f"✅ Started monitoring task for {monitor_key}")
    
    # Give it a moment
    await asyncio.sleep(2)
    
    # Check active monitors
    active = len(enhanced_tp_sl_manager.position_monitors)
    logger.info(f"📊 Total active monitors now: {active}")
    
    return active

async def main():
    """Main entry point"""
    count = await create_monitor()
    print(f"\n✅ Monitor created. Active monitors: {count}")
    print("🔄 The bot should now show 15 positions monitored")

if __name__ == "__main__":
    asyncio.run(main())