#!/usr/bin/env python3
"""
Stats backup system to prevent data loss
"""
import json
import os
import time
import logging
import asyncio
from decimal import Decimal
from typing import Dict, Any
import pickle

logger = logging.getLogger(__name__)

STATS_BACKUP_FILE = "stats_backup.json"
STATS_KEYS = [
    'stats_total_trades_initiated',
    'stats_tp1_hits',
    'stats_sl_hits',
    'stats_other_closures',
    'stats_last_reset_timestamp',
    'stats_total_pnl',
    'stats_win_streak',
    'stats_loss_streak',
    'stats_best_trade',
    'stats_worst_trade',
    'stats_total_wins',
    'stats_total_losses',
    'stats_conservative_trades',
    'stats_fast_trades',
    'stats_conservative_tp1_cancellations',
    'stats_total_wins_pnl',
    'stats_total_losses_pnl',
    'stats_max_drawdown',
    'stats_peak_equity',
    'stats_current_drawdown',
    'recent_trade_pnls',
    'bot_start_time'
]

def decimal_to_str(obj):
    """Convert Decimal objects to strings for JSON serialization"""
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

async def backup_stats(bot_data: Dict[str, Any]) -> bool:
    """Backup stats to a separate file"""
    try:
        stats_to_backup = {}

        # Extract stats from bot_data
        for key in STATS_KEYS:
            if key in bot_data:
                stats_to_backup[key] = bot_data[key]

        # Add backup metadata
        stats_to_backup['backup_timestamp'] = time.time()
        stats_to_backup['backup_date'] = time.strftime('%Y-%m-%d %H:%M:%S')

        # Save to JSON file
        with open(STATS_BACKUP_FILE, 'w') as f:
            json.dump(stats_to_backup, f, indent=2, default=decimal_to_str)

        logger.info(f"✅ Stats backed up successfully to {STATS_BACKUP_FILE}")
        return True

    except Exception as e:
        logger.error(f"❌ Error backing up stats: {e}")
        return False

async def restore_stats(bot_data: Dict[str, Any]) -> bool:
    """Restore stats from backup if main stats are missing"""
    try:
        if not os.path.exists(STATS_BACKUP_FILE):
            logger.info("No stats backup file found")
            return False

        # Check if we need to restore (stats are missing or all zeros)
        needs_restore = True
        total_trades = bot_data.get('stats_total_trades_initiated', 0)
        total_pnl = bot_data.get('stats_total_pnl', Decimal("0"))

        if total_trades > 0 or (isinstance(total_pnl, Decimal) and total_pnl != Decimal("0")):
            logger.info("Stats already exist, no restore needed")
            needs_restore = False

        if not needs_restore:
            return False

        # Load backup
        with open(STATS_BACKUP_FILE, 'r') as f:
            backup_data = json.load(f)

        # Restore stats
        restored_count = 0
        for key in STATS_KEYS:
            if key in backup_data:
                value = backup_data[key]

                # Convert string back to Decimal for certain fields
                if key in ['stats_total_pnl', 'stats_best_trade', 'stats_worst_trade',
                          'stats_total_wins_pnl', 'stats_total_losses_pnl',
                          'stats_max_drawdown', 'stats_peak_equity', 'stats_current_drawdown']:
                    try:
                        value = Decimal(str(value))
                    except:
                        pass

                bot_data[key] = value
                restored_count += 1

        backup_time = backup_data.get('backup_date', 'Unknown')
        logger.info(f"✅ Restored {restored_count} stats from backup dated {backup_time}")

        # Save restored stats to persistence immediately
        return True

    except Exception as e:
        logger.error(f"❌ Error restoring stats from backup: {e}")
        return False

async def auto_backup_stats(application):
    """Periodically backup stats (call this from a background task)"""
    while True:
        try:
            await asyncio.sleep(3600)  # Backup every hour

            if hasattr(application, 'bot_data'):
                await backup_stats(application.bot_data)

        except asyncio.CancelledError:
            logger.info("Stats backup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in auto backup task: {e}")
            await asyncio.sleep(60)  # Wait a minute before retrying