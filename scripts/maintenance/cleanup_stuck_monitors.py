#!/usr/bin/env python3
"""
Utility script to clean up stuck monitors that continue running after positions are closed.
This can be run manually to stop all monitors for positions that no longer exist.
"""

import asyncio
import logging
from decimal import Decimal
from config.settings import PERSISTENCE_FILE
import pickle
from clients.bybit_client import get_all_positions

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def cleanup_stuck_monitors():
    """Clean up monitors for positions that no longer exist"""
    try:
        # Load persistence data
        with open(PERSISTENCE_FILE, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        chat_data_all = data.get('chat_data', {})
        
        # Get all active positions
        active_positions = await get_all_positions()
        active_symbols = set()
        
        for pos in active_positions:
            if float(pos.get('size', 0)) > 0:
                symbol = pos.get('symbol')
                if symbol:
                    active_symbols.add(symbol)
        
        logger.info(f"Found {len(active_symbols)} active positions: {active_symbols}")
        
        # Check monitors
        monitor_tasks = bot_data.get('monitor_tasks', {})
        monitors_to_remove = []
        
        for monitor_key, monitor_data in monitor_tasks.items():
            if monitor_data.get('active', False):
                symbol = monitor_data.get('symbol')
                if symbol and symbol not in active_symbols:
                    monitors_to_remove.append(monitor_key)
                    logger.info(f"Found stuck monitor for {symbol} - marking for removal")
        
        # Remove stuck monitors
        for monitor_key in monitors_to_remove:
            monitor_data = monitor_tasks[monitor_key]
            monitor_data['active'] = False
            del monitor_tasks[monitor_key]
            logger.info(f"Removed stuck monitor: {monitor_key}")
        
        # Also clean up chat data
        for chat_id, chat_data in chat_data_all.items():
            active_monitor = chat_data.get('active_monitor_task_data_v2', {})
            if active_monitor.get('active', False):
                symbol = active_monitor.get('symbol')
                if symbol and symbol not in active_symbols:
                    active_monitor['active'] = False
                    logger.info(f"Deactivated monitor in chat {chat_id} for {symbol}")
        
        # Save updated data
        if monitors_to_remove:
            with open(PERSISTENCE_FILE, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"✅ Cleaned up {len(monitors_to_remove)} stuck monitors")
        else:
            logger.info("✅ No stuck monitors found")
        
        # Show current monitor status
        active_monitors = [k for k, v in monitor_tasks.items() if v.get('active', False)]
        logger.info(f"Active monitors remaining: {len(active_monitors)}")
        for monitor in active_monitors:
            logger.info(f"  - {monitor}")
        
    except Exception as e:
        logger.error(f"Error cleaning up monitors: {e}")

async def main():
    """Main function"""
    logger.info("Starting monitor cleanup...")
    await cleanup_stuck_monitors()
    logger.info("Monitor cleanup completed")

if __name__ == "__main__":
    asyncio.run(main())