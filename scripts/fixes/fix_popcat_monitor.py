#!/usr/bin/env python3
"""
Fix POPCAT monitoring issue - ensure it's not monitored as MIRROR
"""
import asyncio
import logging
import pickle
import os
from decimal import Decimal

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def fix_popcat_monitor():
    """Fix POPCAT monitor to ensure it's regular monitor, not mirror"""
    
    # Load persistence
    pickle_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    
    if not os.path.exists(pickle_file):
        logger.error(f"Persistence file not found: {pickle_file}")
        return
    
    try:
        with open(pickle_file, 'rb') as f:
            persistence_data = pickle.load(f)
            logger.info(f"Loaded persistence data")
    except Exception as e:
        logger.error(f"Error loading persistence: {e}")
        return
    
    # Get bot data
    bot_data = persistence_data.get('bot_data', {})
    chat_data_dict = persistence_data.get('chat_data', {})
    
    # Find POPCAT monitors
    monitor_tasks = bot_data.get('monitor_tasks', {})
    logger.info(f"Found {len(monitor_tasks)} monitor tasks")
    
    # Look for POPCAT monitors
    popcat_monitors = []
    for key, monitor in monitor_tasks.items():
        if 'POPCATUSDT' in key:
            popcat_monitors.append((key, monitor))
            logger.info(f"Found POPCAT monitor: {key}")
            logger.info(f"  - Monitoring mode: {monitor.get('monitoring_mode')}")
            logger.info(f"  - Account type: {monitor.get('account_type', 'primary')}")
            logger.info(f"  - Approach: {monitor.get('approach')}")
            logger.info(f"  - Active: {monitor.get('active')}")
    
    # Fix any MIRROR monitors to regular monitors
    fixed_count = 0
    for key, monitor in popcat_monitors:
        if 'MIRROR' in monitor.get('monitoring_mode', '') or monitor.get('account_type') == 'mirror':
            logger.info(f"Fixing monitor {key} from MIRROR to regular")
            
            # Update monitoring mode
            if 'MIRROR' in monitor.get('monitoring_mode', ''):
                monitor['monitoring_mode'] = monitor['monitoring_mode'].replace('MIRROR-', '')
            
            # Update account type
            if monitor.get('account_type') == 'mirror':
                monitor['account_type'] = 'primary'
            
            # Remove mirror suffix from key if present
            new_key = key.replace('_mirror', '')
            if new_key != key:
                monitor_tasks[new_key] = monitor
                del monitor_tasks[key]
                logger.info(f"Renamed monitor key from {key} to {new_key}")
            
            fixed_count += 1
    
    # Check chat data for POPCAT
    chat_id = 5634913742  # Your chat ID from logs
    chat_data = chat_data_dict.get(chat_id, {})
    
    # Look for POPCAT-related chat data
    active_monitors = chat_data.get('ACTIVE_MONITOR_TASK', {})
    logger.info(f"\nActive monitors in chat data: {len(active_monitors)}")
    
    for symbol, monitor_info in active_monitors.items():
        if 'POPCAT' in str(symbol):
            logger.info(f"Found POPCAT in active monitors: {symbol}")
            logger.info(f"  - Info: {monitor_info}")
    
    # Save updated persistence
    if fixed_count > 0:
        try:
            with open(pickle_file, 'wb') as f:
                pickle.dump(persistence_data, f)
            logger.info(f"\n✅ Fixed {fixed_count} POPCAT monitors and saved persistence")
        except Exception as e:
            logger.error(f"Error saving persistence: {e}")
    else:
        logger.info("\n✅ No MIRROR monitors found for POPCAT - all good!")
    
    # Show final status
    logger.info("\nFinal POPCAT monitor status:")
    for key, monitor in monitor_tasks.items():
        if 'POPCATUSDT' in key:
            logger.info(f"  - {key}: {monitor.get('monitoring_mode')} ({monitor.get('account_type', 'primary')})")

if __name__ == "__main__":
    asyncio.run(fix_popcat_monitor())