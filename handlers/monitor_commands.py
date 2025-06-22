#!/usr/bin/env python3
"""
Monitor management commands for debugging and administration
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import time

from config.constants import *

logger = logging.getLogger(__name__)

async def cleanup_monitors_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command to manually clean up stale monitors"""
    try:
        message = await update.message.reply_text(
            "🧹 Cleaning up stale monitors...",
            parse_mode=ParseMode.HTML
        )
        
        if 'monitor_tasks' not in context.bot_data:
            await message.edit_text("No monitor_tasks found in bot_data")
            return
        
        monitor_tasks = context.bot_data['monitor_tasks']
        current_time = time.time()
        stale_monitors = []
        
        # Check each monitor entry
        for monitor_key, task_info in list(monitor_tasks.items()):
            if not isinstance(task_info, dict):
                stale_monitors.append(monitor_key)
                continue
            
            # Check if monitor is stale (older than 24 hours)
            started_at = task_info.get('started_at', 0)
            if started_at > 0 and (current_time - started_at) > 86400:  # 24 hours
                stale_monitors.append(monitor_key)
                continue
            
            # Check if monitor is marked as active but has no running task
            if task_info.get('active', False):
                chat_id = task_info.get('chat_id')
                symbol = task_info.get('symbol')
                approach = task_info.get('approach', 'fast')
                
                if chat_id and symbol:
                    from execution.monitor import get_monitor_task_status
                    status = await get_monitor_task_status(chat_id, symbol, approach)
                    
                    if not status.get("running", False):
                        stale_monitors.append(monitor_key)
        
        # Remove stale monitors
        for monitor_key in stale_monitors:
            del monitor_tasks[monitor_key]
        
        if stale_monitors:
            await context.application.update_persistence()
            await message.edit_text(
                f"✅ Cleaned up {len(stale_monitors)} stale monitors:\n"
                f"{chr(10).join(stale_monitors[:10])}{'...' if len(stale_monitors) > 10 else ''}",
                parse_mode=ParseMode.HTML
            )
        else:
            await message.edit_text("✅ No stale monitors found")
            
    except Exception as e:
        logger.error(f"Error in cleanup_monitors_command: {e}")
        await update.message.reply_text(
            f"❌ Error cleaning up monitors: {str(e)}",
            parse_mode=ParseMode.HTML
        )

async def list_monitors_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command to list all active monitors"""
    try:
        monitor_tasks = context.bot_data.get('monitor_tasks', {})
        
        if not monitor_tasks:
            await update.message.reply_text(
                "📊 No monitors found in bot_data",
                parse_mode=ParseMode.HTML
            )
            return
        
        current_time = time.time()
        active_monitors = []
        stale_monitors = []
        
        for monitor_key, task_info in monitor_tasks.items():
            if isinstance(task_info, dict):
                started_at = task_info.get('started_at', 0)
                hours_ago = (current_time - started_at) / 3600 if started_at > 0 else 0
                
                info = {
                    'key': monitor_key,
                    'symbol': task_info.get('symbol', 'Unknown'),
                    'approach': task_info.get('approach', 'Unknown'),
                    'chat_id': task_info.get('chat_id', 'Unknown'),
                    'hours_ago': hours_ago,
                    'active': task_info.get('active', False)
                }
                
                if hours_ago > 24:
                    stale_monitors.append(info)
                else:
                    active_monitors.append(info)
        
        # Build response message
        message_parts = [f"📊 <b>Monitor Status Report</b>"]
        message_parts.append(f"\nTotal monitors in bot_data: {len(monitor_tasks)}")
        
        if active_monitors:
            message_parts.append(f"\n\n<b>Active Monitors ({len(active_monitors)}):</b>")
            for monitor in active_monitors[:10]:  # Show first 10
                message_parts.append(
                    f"• {monitor['symbol']} ({monitor['approach']}) - "
                    f"Chat {monitor['chat_id']} - {monitor['hours_ago']:.1f}h ago"
                )
            if len(active_monitors) > 10:
                message_parts.append(f"... and {len(active_monitors) - 10} more")
        
        if stale_monitors:
            message_parts.append(f"\n\n<b>Stale Monitors ({len(stale_monitors)}):</b>")
            for monitor in stale_monitors[:5]:  # Show first 5
                message_parts.append(
                    f"• {monitor['symbol']} ({monitor['approach']}) - "
                    f"Chat {monitor['chat_id']} - {monitor['hours_ago']:.1f}h ago"
                )
            if len(stale_monitors) > 5:
                message_parts.append(f"... and {len(stale_monitors) - 5} more")
            
            message_parts.append(f"\n💡 Use /cleanup_monitors to remove stale entries")
        
        # Check actual running tasks
        from execution.monitor import get_monitor_registry_stats
        registry_stats = get_monitor_registry_stats()
        message_parts.append(f"\n\n<b>Registry Stats:</b>")
        message_parts.append(f"• Registered tasks: {registry_stats.get('total_registered', 0)}")
        message_parts.append(f"• Running tasks: {registry_stats.get('running_tasks', 0)}")
        
        await update.message.reply_text(
            "\n".join(message_parts),
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Error in list_monitors_command: {e}")
        await update.message.reply_text(
            f"❌ Error listing monitors: {str(e)}",
            parse_mode=ParseMode.HTML
        )

async def force_cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command to force cleanup all monitors (admin only)"""
    try:
        # Add admin check here if needed
        # if update.effective_user.id not in ADMIN_USER_IDS:
        #     await update.message.reply_text("❌ Unauthorized")
        #     return
        
        monitor_tasks = context.bot_data.get('monitor_tasks', {})
        count = len(monitor_tasks)
        
        if count == 0:
            await update.message.reply_text("No monitors to clean up")
            return
        
        # Clear all monitors
        context.bot_data['monitor_tasks'] = {}
        await context.application.update_persistence()
        
        await update.message.reply_text(
            f"✅ Force cleaned {count} monitors from bot_data\n"
            f"⚠️ Active monitors may need to be restarted",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Error in force_cleanup_command: {e}")
        await update.message.reply_text(
            f"❌ Error: {str(e)}",
            parse_mode=ParseMode.HTML
        )