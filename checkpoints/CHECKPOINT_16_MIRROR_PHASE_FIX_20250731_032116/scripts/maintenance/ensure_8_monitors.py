#!/usr/bin/env python3
"""
Ensure All 8 Monitors Are Present
=================================

This script ensures all 8 monitors (4 main + 4 mirror) are in the pickle file
and creates the force load signal to make the bot load them all.
"""

import pickle
import logging
import os
from decimal import Decimal
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def ensure_all_monitors():
    """Ensure all 8 monitors are present in pickle file"""
    try:
        # Load current data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        if 'bot_data' not in data:
            data['bot_data'] = {}
        if 'enhanced_tp_sl_monitors' not in data['bot_data']:
            data['bot_data']['enhanced_tp_sl_monitors'] = {}
        
        monitors = data['bot_data']['enhanced_tp_sl_monitors']
        
        logger.info(f"Current monitors: {len(monitors)}")
        logger.info(f"Monitor keys: {list(monitors.keys())}")
        
        # Expected monitors based on the positions we know exist
        expected_monitors = {
            # Main account
            'CAKEUSDT_Buy_main': {
                'symbol': 'CAKEUSDT',
                'side': 'Buy',
                'position_size': Decimal('83.3'),
                'remaining_size': Decimal('83.3'),
                'entry_price': Decimal('2.29'),
                'avg_price': Decimal('2.29'),
                'approach': 'fast',
                'account_type': 'main'
            },
            'SNXUSDT_Buy_main': {
                'symbol': 'SNXUSDT',
                'side': 'Buy',
                'position_size': Decimal('338.3'),
                'remaining_size': Decimal('338.3'),
                'entry_price': Decimal('0.57079639'),
                'avg_price': Decimal('0.57079639'),
                'approach': 'fast',
                'account_type': 'main'
            },
            '1INCHUSDT_Buy_main': {
                'symbol': '1INCHUSDT',
                'side': 'Buy',
                'position_size': Decimal('992.5'),
                'remaining_size': Decimal('992.5'),
                'entry_price': Decimal('0.2012'),
                'avg_price': Decimal('0.2012'),
                'approach': 'fast',
                'account_type': 'main'
            },
            'SUSHIUSDT_Buy_main': {
                'symbol': 'SUSHIUSDT',
                'side': 'Buy',
                'position_size': Decimal('325.3'),
                'remaining_size': Decimal('325.3'),
                'entry_price': Decimal('0.61664141'),
                'avg_price': Decimal('0.61664141'),
                'approach': 'fast',
                'account_type': 'main'
            },
            # Mirror account
            'CAKEUSDT_Buy_mirror': {
                'symbol': 'CAKEUSDT',
                'side': 'Buy',
                'position_size': Decimal('27.5'),
                'remaining_size': Decimal('27.5'),
                'entry_price': Decimal('2.277333333333333333333333333'),
                'avg_price': Decimal('2.277333333333333333333333333'),
                'approach': 'conservative',
                'account_type': 'mirror',
                'has_mirror': True
            },
            'SNXUSDT_Buy_mirror': {
                'symbol': 'SNXUSDT',
                'side': 'Buy',
                'position_size': Decimal('112'),
                'remaining_size': Decimal('112'),
                'entry_price': Decimal('0.5677'),
                'avg_price': Decimal('0.5677'),
                'approach': 'conservative',
                'account_type': 'mirror'
            },
            '1INCHUSDT_Buy_mirror': {
                'symbol': '1INCHUSDT',
                'side': 'Buy',
                'position_size': Decimal('328.7'),
                'remaining_size': Decimal('328.7'),
                'entry_price': Decimal('0.2002'),
                'avg_price': Decimal('0.2002'),
                'approach': 'conservative',
                'account_type': 'mirror'
            },
            'SUSHIUSDT_Buy_mirror': {
                'symbol': 'SUSHIUSDT',
                'side': 'Buy',
                'position_size': Decimal('107.7'),
                'remaining_size': Decimal('107.7'),
                'entry_price': Decimal('0.6132'),
                'avg_price': Decimal('0.6132'),
                'approach': 'conservative',
                'account_type': 'mirror'
            }
        }
        
        # Add missing monitors
        added = 0
        for key, monitor_template in expected_monitors.items():
            if key not in monitors:
                logger.info(f"Adding missing monitor: {key}")
                # Create full monitor data
                monitor_data = {
                    'symbol': monitor_template['symbol'],
                    'side': monitor_template['side'],
                    'position_size': monitor_template['position_size'],
                    'remaining_size': monitor_template['remaining_size'],
                    'entry_price': monitor_template['entry_price'],
                    'avg_price': monitor_template['avg_price'],
                    'approach': monitor_template['approach'],
                    'tp_orders': {},
                    'sl_order': None,
                    'filled_tps': [],
                    'cancelled_limits': False,
                    'tp1_hit': False,
                    'tp1_info': None,
                    'sl_moved_to_be': False,
                    'sl_move_attempts': 0,
                    'created_at': time.time(),
                    'last_check': time.time(),
                    'limit_orders': [],
                    'limit_orders_cancelled': False,
                    'phase': 'MONITORING',
                    'chat_id': None,
                    'account_type': monitor_template['account_type']
                }
                if 'has_mirror' in monitor_template:
                    monitor_data['has_mirror'] = monitor_template['has_mirror']
                
                monitors[key] = monitor_data
                added += 1
        
        # Save updated data
        data['bot_data']['enhanced_tp_sl_monitors'] = monitors
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"\n✅ Added {added} missing monitors")
        logger.info(f"Total monitors now: {len(monitors)}")
        
        # Create force load signal
        signal_file = '.force_load_all_monitors'
        with open(signal_file, 'w') as f:
            f.write("# Force load all monitors signal\n")
        
        logger.info(f"\n✅ Created {signal_file} signal")
        logger.info("The bot will now load all 8 monitors on next check")
        
        # Display summary
        logger.info("\n📊 Monitor Summary:")
        main_count = sum(1 for k in monitors.keys() if k.endswith('_main'))
        mirror_count = sum(1 for k in monitors.keys() if k.endswith('_mirror'))
        logger.info(f"  Main account: {main_count} monitors")
        logger.info(f"  Mirror account: {mirror_count} monitors")
        logger.info(f"  Total: {len(monitors)} monitors")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    ensure_all_monitors()