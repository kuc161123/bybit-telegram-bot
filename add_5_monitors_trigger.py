#!/usr/bin/env python3
"""
Create a trigger file to add the 5 missing monitors with correct chat_id.
This approach creates a trigger file that the bot can check and process.
"""

import json
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# The 5 monitors to create
MONITORS_TO_CREATE = {
    'LFLUSDT_Sell_main': {
        'symbol': 'LFLUSDT',
        'side': 'Sell',
        'account': 'main',
        'chat_id': 1559190851,
        'approach': 'conservative'
    },
    'XAIUSDT_Buy_main': {
        'symbol': 'XAIUSDT',
        'side': 'Buy',
        'account': 'main',
        'chat_id': 1559190851,
        'approach': 'conservative'
    },
    'XAIUSDT_Buy_mirror': {
        'symbol': 'XAIUSDT',
        'side': 'Buy',
        'account': 'mirror',
        'chat_id': 1559190851,
        'approach': 'conservative'
    },
    'AIUSDT_Buy_main': {
        'symbol': 'AIUSDT',
        'side': 'Buy',
        'account': 'main',
        'chat_id': 1559190851,
        'approach': 'conservative'
    },
    'AIUSDT_Buy_mirror': {
        'symbol': 'AIUSDT',
        'side': 'Buy',
        'account': 'mirror',
        'chat_id': 1559190851,
        'approach': 'conservative'
    }
}

def main():
    """Create trigger file for adding monitors."""
    logger.info("Creating trigger file for 5 missing monitors...")
    
    trigger_file = 'add_monitors_trigger.json'
    
    # Create trigger data
    trigger_data = {
        'action': 'add_monitors',
        'timestamp': datetime.now().isoformat(),
        'monitors': MONITORS_TO_CREATE
    }
    
    # Write trigger file
    with open(trigger_file, 'w') as f:
        json.dump(trigger_data, f, indent=2)
        
    logger.info(f"Created trigger file: {trigger_file}")
    logger.info("The bot should pick up this file and create the monitors.")
    
    # Also log to bot's signal file
    signal_file = 'reload_monitors.signal'
    with open(signal_file, 'w') as f:
        f.write(f"Add 5 monitors at {datetime.now()}\n")
        f.write(json.dumps(MONITORS_TO_CREATE, indent=2))
        
    logger.info(f"Updated signal file: {signal_file}")
    
    # Create a more direct approach - add to the enhanced_tp_sl_manager initialization
    init_file = 'init_5_monitors.py'
    init_code = '''# Initialize 5 monitors with chat_id
import pickle
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

monitors_to_add = {
    'LFLUSDT_Sell_main': {
        'symbol': 'LFLUSDT',
        'side': 'Sell',
        'account': 'main',
        'chat_id': 1559190851,
        'approach': 'conservative',
        'status': 'MONITORING',
        'created_at': datetime.now().timestamp(),
        'last_check': datetime.now().timestamp(),
        'sl_moved_to_be': False,
        'limit_orders': [],
        'limit_orders_filled': False,
        'phase': 'MONITORING',
        'tp1_hit': False,
        'phase_transition_time': None,
        'total_tp_filled': 0.0,
        'cleanup_completed': False,
        'bot_instance': None,
        'account_type': 'main',
        'sl_hit': False,
        'all_tps_filled': False,
        'tp_orders': {},
        'sl_order': None,
        'filled_tps': [],
        'position_size': 0.0,
        'current_size': 0.0,
        'remaining_size': 0.0
    },
    'XAIUSDT_Buy_main': {
        'symbol': 'XAIUSDT',
        'side': 'Buy',
        'account': 'main',
        'chat_id': 1559190851,
        'approach': 'conservative',
        'status': 'MONITORING',
        'created_at': datetime.now().timestamp(),
        'last_check': datetime.now().timestamp(),
        'sl_moved_to_be': False,
        'limit_orders': [],
        'limit_orders_filled': False,
        'phase': 'MONITORING',
        'tp1_hit': False,
        'phase_transition_time': None,
        'total_tp_filled': 0.0,
        'cleanup_completed': False,
        'bot_instance': None,
        'account_type': 'main',
        'sl_hit': False,
        'all_tps_filled': False,
        'tp_orders': {},
        'sl_order': None,
        'filled_tps': [],
        'position_size': 0.0,
        'current_size': 0.0,
        'remaining_size': 0.0
    },
    'XAIUSDT_Buy_mirror': {
        'symbol': 'XAIUSDT',
        'side': 'Buy',
        'account': 'mirror',
        'chat_id': 1559190851,
        'approach': 'conservative',
        'status': 'MONITORING',
        'created_at': datetime.now().timestamp(),
        'last_check': datetime.now().timestamp(),
        'sl_moved_to_be': False,
        'limit_orders': [],
        'limit_orders_filled': False,
        'phase': 'MONITORING',
        'tp1_hit': False,
        'phase_transition_time': None,
        'total_tp_filled': 0.0,
        'cleanup_completed': False,
        'bot_instance': None,
        'account_type': 'mirror',
        'sl_hit': False,
        'all_tps_filled': False,
        'tp_orders': {},
        'sl_order': None,
        'filled_tps': [],
        'position_size': 0.0,
        'current_size': 0.0,
        'remaining_size': 0.0
    },
    'AIUSDT_Buy_main': {
        'symbol': 'AIUSDT',
        'side': 'Buy',
        'account': 'main',
        'chat_id': 1559190851,
        'approach': 'conservative',
        'status': 'MONITORING',
        'created_at': datetime.now().timestamp(),
        'last_check': datetime.now().timestamp(),
        'sl_moved_to_be': False,
        'limit_orders': [],
        'limit_orders_filled': False,
        'phase': 'MONITORING',
        'tp1_hit': False,
        'phase_transition_time': None,
        'total_tp_filled': 0.0,
        'cleanup_completed': False,
        'bot_instance': None,
        'account_type': 'main',
        'sl_hit': False,
        'all_tps_filled': False,
        'tp_orders': {},
        'sl_order': None,
        'filled_tps': [],
        'position_size': 0.0,
        'current_size': 0.0,
        'remaining_size': 0.0
    },
    'AIUSDT_Buy_mirror': {
        'symbol': 'AIUSDT',
        'side': 'Buy',
        'account': 'mirror',
        'chat_id': 1559190851,
        'approach': 'conservative',
        'status': 'MONITORING',
        'created_at': datetime.now().timestamp(),
        'last_check': datetime.now().timestamp(),
        'sl_moved_to_be': False,
        'limit_orders': [],
        'limit_orders_filled': False,
        'phase': 'MONITORING',
        'tp1_hit': False,
        'phase_transition_time': None,
        'total_tp_filled': 0.0,
        'cleanup_completed': False,
        'bot_instance': None,
        'account_type': 'mirror',
        'sl_hit': False,
        'all_tps_filled': False,
        'tp_orders': {},
        'sl_order': None,
        'filled_tps': [],
        'position_size': 0.0,
        'current_size': 0.0,
        'remaining_size': 0.0
    }
}

def add_monitors_to_pickle():
    """Add monitors directly to pickle file."""
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
            
        if 'bot_data' not in data:
            data['bot_data'] = {}
        if 'enhanced_tp_sl_monitors' not in data['bot_data']:
            data['bot_data']['enhanced_tp_sl_monitors'] = {}
            
        # Add monitors
        for key, monitor in monitors_to_add.items():
            if key not in data['bot_data']['enhanced_tp_sl_monitors']:
                data['bot_data']['enhanced_tp_sl_monitors'][key] = monitor
                logger.info(f"Added monitor: {key}")
                
        # Save
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
            
        logger.info("Successfully added monitors to pickle file")
        return True
    except Exception as e:
        logger.error(f"Error adding monitors: {e}")
        return False

# Run if imported
if __name__ != "__main__":
    add_monitors_to_pickle()
'''
    
    with open(init_file, 'w') as f:
        f.write(init_code)
        
    logger.info(f"Created initialization file: {init_file}")
    logger.info("\nTo apply the monitors, you can:")
    logger.info("1. Wait for the bot to pick up the trigger files")
    logger.info("2. Run: python -c 'import init_5_monitors'")
    logger.info("3. Restart the bot to ensure monitors are loaded")
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)