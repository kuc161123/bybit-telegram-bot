#!/usr/bin/env python3
"""
Create the 5 missing Enhanced TP/SL monitors with correct chat_id.
"""

import pickle
import logging
from datetime import datetime
import os

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
        'chat_id': 1559190851
    },
    'XAIUSDT_Buy_main': {
        'symbol': 'XAIUSDT',
        'side': 'Buy',
        'account': 'main',
        'chat_id': 1559190851
    },
    'XAIUSDT_Buy_mirror': {
        'symbol': 'XAIUSDT',
        'side': 'Buy',
        'account': 'mirror',
        'chat_id': 1559190851
    },
    'AIUSDT_Buy_main': {
        'symbol': 'AIUSDT',
        'side': 'Buy',
        'account': 'main',
        'chat_id': 1559190851
    },
    'AIUSDT_Buy_mirror': {
        'symbol': 'AIUSDT',
        'side': 'Buy',
        'account': 'mirror',
        'chat_id': 1559190851
    }
}

def create_monitor_data(symbol, side, account, chat_id):
    """Create monitor data structure."""
    return {
        'symbol': symbol,
        'side': side,
        'account': account,
        'chat_id': chat_id,
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
        'account_type': account,
        'sl_hit': False,
        'all_tps_filled': False,
        'tp_orders': {},
        'sl_order': None,
        'filled_tps': [],
        'position_size': 0.0,
        'current_size': 0.0,
        'remaining_size': 0.0
    }

def main():
    """Main function to create missing monitors."""
    logger.info("Starting creation of 5 missing monitors...")
    
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    try:
        # Create backup
        backup_file = f"{pickle_file}.backup_create_5_monitors_{int(datetime.now().timestamp())}"
        
        # Load current data
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
            
        # Ensure structure exists
        if 'bot_data' not in data:
            data['bot_data'] = {}
        if 'enhanced_tp_sl_monitors' not in data['bot_data']:
            data['bot_data']['enhanced_tp_sl_monitors'] = {}
            
        monitors = data['bot_data']['enhanced_tp_sl_monitors']
        
        # Check and create monitors
        created_count = 0
        for monitor_key, config in MONITORS_TO_CREATE.items():
            if monitor_key not in monitors:
                logger.info(f"Creating monitor: {monitor_key}")
                monitor_data = create_monitor_data(
                    config['symbol'],
                    config['side'],
                    config['account'],
                    config['chat_id']
                )
                monitors[monitor_key] = monitor_data
                created_count += 1
            else:
                # Update chat_id if needed
                if monitors[monitor_key].get('chat_id') != config['chat_id']:
                    logger.info(f"Updating chat_id for existing monitor: {monitor_key}")
                    monitors[monitor_key]['chat_id'] = config['chat_id']
                    created_count += 1
                else:
                    logger.info(f"Monitor {monitor_key} already exists with correct chat_id")
                    
        if created_count > 0:
            # Save backup
            os.rename(pickle_file, backup_file)
            logger.info(f"Created backup: {backup_file}")
            
            # Save updated data
            with open(pickle_file, 'wb') as f:
                pickle.dump(data, f)
                
            logger.info(f"Successfully created/updated {created_count} monitors")
        else:
            logger.info("No monitors needed to be created or updated")
            
        # Verify
        logger.info("\n=== Verification ===")
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
            
        if 'bot_data' in data and 'enhanced_tp_sl_monitors' in data['bot_data']:
            monitors = data['bot_data']['enhanced_tp_sl_monitors']
            
            for monitor_key in MONITORS_TO_CREATE.keys():
                if monitor_key in monitors:
                    chat_id = monitors[monitor_key].get('chat_id')
                    logger.info(f"✅ {monitor_key}: chat_id = {chat_id}")
                else:
                    logger.error(f"❌ {monitor_key}: NOT FOUND")
                    
        logger.info("\n✅ Monitors created successfully!")
        logger.info("The bot will start monitoring these positions on the next check cycle.")
        
        # Create a signal file to trigger monitor reload
        signal_file = 'reload_monitors.signal'
        with open(signal_file, 'w') as f:
            f.write(f"Reload monitors at {datetime.now()}")
        logger.info(f"Created {signal_file} to trigger monitor reload")
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating monitors: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)