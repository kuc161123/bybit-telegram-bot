#!/usr/bin/env python3
"""
Monitor cleanup utilities
"""
import logging
from clients.bybit_helpers import get_all_positions
from clients.bybit_client import bybit_client

logger = logging.getLogger(__name__)

async def cleanup_stale_monitors_on_startup(bot_data):
    """
    Clean up stale monitors that don't have active positions.
    This runs on startup to ensure monitor counts are accurate.
    Enhanced to handle hedge mode with side information.
    """
    try:
        # Get all active positions with side information
        active_positions = await get_all_positions()
        active_position_keys = set()

        for pos in active_positions:
            if float(pos.get('size', 0)) > 0:
                symbol = pos.get('symbol')
                side = pos.get('side')
                if symbol:
                    # Store symbol-side combination for hedge mode
                    active_position_keys.add(f"{symbol}_{side}")
                    # Also store just symbol for backward compatibility
                    active_position_keys.add(symbol)

        logger.info(f"Startup cleanup: Found {len(active_positions)} active positions")

        # Check and clean monitors
        monitor_tasks = bot_data.get('monitor_tasks', {})
        monitors_removed = []

        for monitor_key in list(monitor_tasks.keys()):
            monitor_data = monitor_tasks.get(monitor_key, {})
            symbol = monitor_data.get('symbol')
            side = monitor_data.get('side')

            if symbol:
                # Create position key with side if available
                position_key = f"{symbol}_{side}" if side else symbol

                # Remove monitors without active positions
                # Check both symbol-side combination and just symbol
                if position_key not in active_position_keys and symbol not in active_position_keys:
                    del monitor_tasks[monitor_key]
                    monitors_removed.append(f"{monitor_key} ({symbol} {side or ''})")
                    logger.info(f"Startup cleanup: Removed monitor {monitor_key} - no active position for {symbol} {side or ''}")
                # Also remove inactive monitors
                elif not monitor_data.get('active', False):
                    del monitor_tasks[monitor_key]
                    monitors_removed.append(f"{monitor_key} ({symbol} {side or ''}) - inactive")
                    logger.info(f"Startup cleanup: Removed inactive monitor {monitor_key}")

        # Also check for duplicate monitors for same symbol/side/approach
        # Group monitors by symbol-side-approach
        monitor_groups = {}
        for monitor_key, monitor_data in monitor_tasks.items():
            symbol = monitor_data.get('symbol')
            side = monitor_data.get('side', 'unknown')
            approach = monitor_data.get('approach', 'unknown')
            account = monitor_data.get('account_type', 'main')

            if symbol:
                group_key = f"{symbol}_{side}_{approach}_{account}"
                if group_key not in monitor_groups:
                    monitor_groups[group_key] = []
                monitor_groups[group_key].append(monitor_key)

        # Remove duplicates (keep only the most recent one)
        for group_key, monitor_keys in monitor_groups.items():
            if len(monitor_keys) > 1:
                logger.warning(f"Found {len(monitor_keys)} duplicate monitors for {group_key}")
                # Sort by monitor key (assuming newer ones have higher IDs)
                monitor_keys.sort()
                # Keep the last one (most recent)
                for monitor_key in monitor_keys[:-1]:
                    del monitor_tasks[monitor_key]
                    monitors_removed.append(f"{monitor_key} (duplicate)")
                    logger.info(f"Startup cleanup: Removed duplicate monitor {monitor_key}")

        if monitors_removed:
            logger.info(f"✅ Startup cleanup complete: Removed {len(monitors_removed)} stale/duplicate monitors")
            return True
        else:
            logger.info("✅ Startup cleanup complete: No stale monitors found")
            return False

    except Exception as e:
        logger.error(f"Error during startup monitor cleanup: {e}")
        return False