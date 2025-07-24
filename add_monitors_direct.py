#!/usr/bin/env python3
"""
Add Monitors Directly to Pickle File
Direct approach to add missing monitors
"""

import pickle
import logging
import time
from decimal import Decimal
from datetime import datetime
import shutil
import os

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Missing monitors data
MISSING_MONITORS = [
    {
        "monitor_key": "AUCTIONUSDT_Buy_mirror",
        "symbol": "AUCTIONUSDT",
        "side": "Buy",
        "account": "mirror",
        "size": "7.1",
        "avgPrice": "9.816"
    },
    {
        "monitor_key": "CRVUSDT_Buy_mirror",
        "symbol": "CRVUSDT",
        "side": "Buy",
        "account": "mirror",
        "size": "225.5",
        "avgPrice": "0.6408"
    },
    {
        "monitor_key": "SEIUSDT_Buy_mirror",
        "symbol": "SEIUSDT",
        "side": "Buy",
        "account": "mirror",
        "size": "429",
        "avgPrice": "0.3418"
    },
    {
        "monitor_key": "ARBUSDT_Buy_mirror",
        "symbol": "ARBUSDT",
        "side": "Buy",
        "account": "mirror",
        "size": "349.7",
        "avgPrice": "0.41181092"
    },
    {
        "monitor_key": "IDUSDT_Buy_mirror",
        "symbol": "IDUSDT",
        "side": "Buy",
        "account": "mirror",
        "size": "77",
        "avgPrice": "0.172"
    }
]

def main():
    """Add monitors directly to pickle file"""
    logger.info("🔧 Adding Missing Monitors Directly to Pickle")
    logger.info("=" * 80)
    
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    try:
        # Create backup
        backup_file = f"{pickle_file}.backup_add_monitors_{int(time.time())}"
        shutil.copy2(pickle_file, backup_file)
        logger.info(f"✅ Created backup: {backup_file}")
        
        # Load pickle data
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        # Get chat_id
        chat_id = None
        for uid, user_data in data.get('user_data', {}).items():
            if user_data.get('positions'):
                chat_id = uid
                break
        
        logger.info(f"📊 Found chat_id: {chat_id}")
        
        # Ensure bot_data structure exists
        if 'bot_data' not in data:
            data['bot_data'] = {}
        if 'enhanced_tp_sl_monitors' not in data['bot_data']:
            data['bot_data']['enhanced_tp_sl_monitors'] = {}
        if 'monitor_tasks' not in data['bot_data']:
            data['bot_data']['monitor_tasks'] = {}
        
        # Current monitor count
        current_monitors = len(data['bot_data']['enhanced_tp_sl_monitors'])
        logger.info(f"📊 Current monitors: {current_monitors}")
        
        # Add each missing monitor
        added_count = 0
        
        for monitor_info in MISSING_MONITORS:
            monitor_key = monitor_info['monitor_key']
            symbol = monitor_info['symbol']
            side = monitor_info['side']
            account = monitor_info['account']
            size = Decimal(str(monitor_info['size']))
            avg_price = Decimal(str(monitor_info['avgPrice']))
            
            logger.info(f"\n📍 Adding monitor: {monitor_key}")
            
            # Check if already exists
            if monitor_key in data['bot_data']['enhanced_tp_sl_monitors']:
                logger.warning(f"   ⚠️ Monitor already exists, skipping")
                continue
            
            # Create enhanced monitor data
            monitor_data = {
                'symbol': symbol,
                'side': side,
                'size': size,
                'position_size': size,
                'initial_size': size,
                'remaining_size': size,
                'filled_size': Decimal('0'),
                'account': account,
                'account_type': account,
                'avg_entry_price': avg_price,
                'entry_price': avg_price,
                'weighted_avg_entry': avg_price,
                'actual_entry_prices': [(avg_price, size)],
                'tp_orders': {},
                'sl_order': None,
                'approach': 'conservative',
                'status': 'active',
                'created_at': datetime.now().isoformat(),
                'last_check': time.time(),
                'monitoring_active': True,
                'tp1_hit': False,
                'tp2_hit': False,
                'tp3_hit': False,
                'tp4_hit': False,
                'breakeven_moved': False,
                'sl_moved_to_breakeven': False,
                'limit_orders_cancelled': False,
                'chat_id': chat_id,
                'position_idx': 0,
                'dashboard_key': monitor_key,
                'stop_loss': None,
                'take_profits': []
            }
            
            # Add to enhanced monitors
            data['bot_data']['enhanced_tp_sl_monitors'][monitor_key] = monitor_data
            
            # Also add to monitor_tasks for dashboard
            data['bot_data']['monitor_tasks'][monitor_key] = {
                'symbol': symbol,
                'side': side,
                'approach': 'conservative',
                'entry_price': str(avg_price),
                'stop_loss': None,
                'take_profits': [],
                'created_at': datetime.now().isoformat(),
                'status': 'active',
                'account_type': account
            }
            
            added_count += 1
            logger.info(f"   ✅ Added successfully")
            logger.info(f"   Size: {size}")
            logger.info(f"   Entry: {avg_price}")
        
        # Save updated data
        with open(pickle_file, 'wb') as f:
            pickle.dump(data, f)
        
        new_monitor_count = len(data['bot_data']['enhanced_tp_sl_monitors'])
        logger.info(f"\n✅ Added {added_count} monitors")
        logger.info(f"📊 Total monitors now: {new_monitor_count}")
        
        # Create reload signal files
        signal_files = [
            'reload_enhanced_monitors.signal',
            'reload_monitors.signal',
            'monitor_reload_trigger.signal'
        ]
        
        for signal_file in signal_files:
            with open(signal_file, 'w') as f:
                f.write(str(time.time()))
            logger.info(f"🔄 Created signal: {signal_file}")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ SUCCESS!")
        logger.info(f"   Added {added_count} monitors")
        logger.info(f"   Total monitors: {new_monitor_count}")
        logger.info("   Bot will reload monitors within 5 seconds")
        logger.info("   No restart required!")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()