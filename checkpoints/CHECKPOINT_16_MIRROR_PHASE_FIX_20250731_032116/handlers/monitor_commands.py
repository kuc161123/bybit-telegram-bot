#!/usr/bin/env python3
"""
Monitor management commands for manual cleanup and inspection
"""
import logging
import time
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config.constants import *

logger = logging.getLogger(__name__)

async def cleanup_monitors_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clean up stale monitors manually"""
    chat_id = update.effective_chat.id

    try:
        bot_data = context.application.bot_data
        monitor_tasks = bot_data.get('monitor_tasks', {})
        current_time = time.time()
        stale_count = 0

        # Check each monitor and remove if stale
        monitors_to_remove = []

        for monitor_key, task_info in monitor_tasks.items():
            if isinstance(task_info, dict):
                started_at = task_info.get('started_at', 0)
                is_active = task_info.get('active', False)

                # Remove if older than 24 hours or marked inactive
                if (started_at > 0 and (current_time - started_at) > 86400) or not is_active:
                    age_hours = (current_time - started_at) / 3600 if started_at > 0 else 0
                    monitors_to_remove.append((monitor_key, age_hours, is_active))
                    stale_count += 1

        # Remove stale monitors
        for monitor_key, _, _ in monitors_to_remove:
            del monitor_tasks[monitor_key]

        # Build response message
        if stale_count > 0:
            msg = f"🧹 <b>Monitor Cleanup Complete</b>\n\n"
            msg += f"✅ Removed {stale_count} stale monitors:\n\n"

            for monitor_key, age_hours, is_active in monitors_to_remove[:10]:  # Show max 10
                parts = monitor_key.split('_')
                symbol = parts[1] if len(parts) > 1 else "Unknown"
                approach = parts[2] if len(parts) > 2 else "unknown"
                msg += f"• {symbol} ({approach}) - {age_hours:.1f}h old, active: {is_active}\n"

            if len(monitors_to_remove) > 10:
                msg += f"\n... and {len(monitors_to_remove) - 10} more"

            await context.application.update_persistence()
        else:
            msg = "✅ <b>No stale monitors found</b>\n\nAll monitors are active and recent."

        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error in cleanup_monitors command: {e}")
        await update.message.reply_text(
            f"❌ Error cleaning up monitors: {str(e)}",
            parse_mode=ParseMode.HTML
        )

async def list_monitors_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all monitors with their status"""
    chat_id = update.effective_chat.id

    try:
        bot_data = context.application.bot_data
        monitor_tasks = bot_data.get('monitor_tasks', {})
        current_time = time.time()

        if not monitor_tasks:
            await update.message.reply_text(
                "📊 <b>No monitors found</b>\n\nNo active position monitors.",
                parse_mode=ParseMode.HTML
            )
            return

        msg = f"📊 <b>Monitor Status</b>\n"
        msg += f"Total monitors: {len(monitor_tasks)}\n\n"

        # Categorize monitors
        active_monitors = []
        stale_monitors = []

        for monitor_key, task_info in monitor_tasks.items():
            if isinstance(task_info, dict):
                started_at = task_info.get('started_at', 0)
                is_active = task_info.get('active', False)
                age_hours = (current_time - started_at) / 3600 if started_at > 0 else 0

                monitor_data = {
                    'key': monitor_key,
                    'age_hours': age_hours,
                    'active': is_active,
                    'info': task_info
                }

                if age_hours > 24 or not is_active:
                    stale_monitors.append(monitor_data)
                else:
                    active_monitors.append(monitor_data)

        # Show active monitors
        if active_monitors:
            msg += f"✅ <b>Active Monitors ({len(active_monitors)})</b>\n"
            for mon in active_monitors[:10]:
                parts = mon['key'].split('_')
                symbol = parts[1] if len(parts) > 1 else "Unknown"
                approach = parts[2] if len(parts) > 2 else "unknown"
                msg += f"• {symbol} ({approach}) - {mon['age_hours']:.1f}h old\n"
            if len(active_monitors) > 10:
                msg += f"... and {len(active_monitors) - 10} more\n"
            msg += "\n"

        # Show stale monitors
        if stale_monitors:
            msg += f"⚠️ <b>Stale Monitors ({len(stale_monitors)})</b>\n"
            for mon in stale_monitors[:5]:
                parts = mon['key'].split('_')
                symbol = parts[1] if len(parts) > 1 else "Unknown"
                approach = parts[2] if len(parts) > 2 else "unknown"
                status = "active" if mon['active'] else "inactive"
                msg += f"• {symbol} ({approach}) - {mon['age_hours']:.1f}h old, {status}\n"
            if len(stale_monitors) > 5:
                msg += f"... and {len(stale_monitors) - 5} more\n"

            msg += f"\n💡 Use /cleanup_monitors to remove stale monitors"

        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error in list_monitors command: {e}")
        await update.message.reply_text(
            f"❌ Error listing monitors: {str(e)}",
            parse_mode=ParseMode.HTML
        )

async def force_cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Force cleanup of ALL monitors (admin command)"""
    chat_id = update.effective_chat.id

    # Add admin check if needed
    # if chat_id not in ADMIN_CHAT_IDS:
    #     await update.message.reply_text("❌ Unauthorized")
    #     return

    try:
        bot_data = context.application.bot_data
        monitor_tasks = bot_data.get('monitor_tasks', {})

        count = len(monitor_tasks)
        monitor_tasks.clear()

        await context.application.update_persistence()

        msg = f"🗑️ <b>Force Cleanup Complete</b>\n\n"
        msg += f"Removed ALL {count} monitors from registry.\n\n"
        msg += f"⚠️ Note: This doesn't stop running monitors, just clears the registry."

        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error in force_cleanup_monitors command: {e}")
        await update.message.reply_text(
            f"❌ Error force cleaning monitors: {str(e)}",
            parse_mode=ParseMode.HTML
        )