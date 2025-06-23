#!/usr/bin/env python3
"""
Monitor cleanup utilities
"""
import logging
from clients.bybit_helpers import get_all_positions

logger = logging.getLogger(__name__)

async def cleanup_stale_monitors_on_startup(bot_data):
    """
    Clean up stale monitors that don't have active positions.
    This runs on startup to ensure monitor counts are accurate.
    """
    try:
        # Get all active positions
        active_positions = await get_all_positions()
        active_symbols = set()
        
        for pos in active_positions:
            if float(pos.get('size', 0)) > 0:
                symbol = pos.get('symbol')
                if symbol:
                    active_symbols.add(symbol)
        
        logger.info(f"Startup cleanup: Found {len(active_symbols)} active positions: {active_symbols}")
        
        # Check and clean monitors
        monitor_tasks = bot_data.get('monitor_tasks', {})
        monitors_removed = []
        
        for monitor_key in list(monitor_tasks.keys()):
            monitor_data = monitor_tasks.get(monitor_key, {})
            symbol = monitor_data.get('symbol')
            
            if symbol:
                # Remove monitors without active positions
                if symbol not in active_symbols:
                    del monitor_tasks[monitor_key]
                    monitors_removed.append(f"{monitor_key} ({symbol})")
                    logger.info(f"Startup cleanup: Removed monitor {monitor_key} - no active position for {symbol}")
                # Also remove inactive monitors
                elif not monitor_data.get('active', False):
                    del monitor_tasks[monitor_key]
                    monitors_removed.append(f"{monitor_key} ({symbol}) - inactive")
                    logger.info(f"Startup cleanup: Removed inactive monitor {monitor_key}")
        
        if monitors_removed:
            logger.info(f"✅ Startup cleanup complete: Removed {len(monitors_removed)} stale monitors")
            return True
        else:
            logger.info("✅ Startup cleanup complete: No stale monitors found")
            return False
            
    except Exception as e:
        logger.error(f"Error during startup monitor cleanup: {e}")
        return False