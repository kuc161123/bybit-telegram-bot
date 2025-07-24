#!/usr/bin/env python3
"""
Comprehensive Monitor Manager
Shows all active monitors for both main and mirror accounts
Allows starting, stopping, and managing monitors
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config.constants import *
from utils.formatters import format_number
from clients.bybit_helpers import get_all_positions, get_all_open_orders

logger = logging.getLogger(__name__)


class MonitorManager:
    """Manages monitor display and control"""

    @staticmethod
    async def get_all_monitor_data(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
        """Get comprehensive monitor data"""
        data = {
            'main_monitors': [],
            'mirror_monitors': [],
            'monitor_stats': {},
            'error': None
        }

        try:
            # Get monitor tasks from bot data
            monitor_tasks = context.bot_data.get('monitor_tasks', {})

            # Separate main and mirror monitors
            for monitor_key, monitor_data in monitor_tasks.items():
                if not isinstance(monitor_data, dict):
                    continue

                monitor_info = MonitorManager.format_monitor_info(monitor_key, monitor_data)

                if 'mirror' in monitor_key.lower():
                    data['mirror_monitors'].append(monitor_info)
                else:
                    data['main_monitors'].append(monitor_info)

            # Calculate stats
            data['monitor_stats'] = MonitorManager.calculate_monitor_stats(
                data['main_monitors'], data['mirror_monitors']
            )

        except Exception as e:
            data['error'] = str(e)
            logger.error(f"Error getting monitor data: {e}")

        return data

    @staticmethod
    def format_monitor_info(monitor_key: str, monitor_data: Dict) -> Dict[str, Any]:
        """Format monitor information for display"""
        # Parse monitor key (format: symbol_side_approach_chatid or similar)
        parts = monitor_key.split('_')

        # Extract information from monitor data
        symbol = monitor_data.get('symbol', parts[0] if parts else 'UNKNOWN')
        side = monitor_data.get('side', parts[1] if len(parts) > 1 else 'UNKNOWN')
        approach = monitor_data.get('approach', parts[2] if len(parts) > 2 else 'UNKNOWN')
        chat_id = monitor_data.get('chat_id', parts[-1] if parts else 'UNKNOWN')

        # Monitor status
        active = monitor_data.get('active', False)
        last_check = monitor_data.get('last_check', 0)
        start_time = monitor_data.get('start_time', 0)
        error_count = monitor_data.get('error_count', 0)
        last_error = monitor_data.get('last_error', '')

        # Position info
        position_size = monitor_data.get('position_size', 0)
        entry_price = monitor_data.get('entry_price', 0)
        current_pnl = monitor_data.get('current_pnl', 0)

        # Order counts
        tp_orders = monitor_data.get('tp_orders', 0)
        sl_orders = monitor_data.get('sl_orders', 0)

        # Calculate runtime
        runtime_seconds = (datetime.now().timestamp() - start_time) if start_time else 0
        runtime_str = MonitorManager.format_runtime(runtime_seconds)

        # Calculate time since last check
        if last_check:
            last_check_seconds = datetime.now().timestamp() - last_check
            last_check_str = MonitorManager.format_time_ago(last_check_seconds)
        else:
            last_check_str = "Never"

        # Status indicators
        status_emoji = "🟢" if active else "🔴"
        if error_count > 0:
            status_emoji = "🟡"

        side_emoji = "🟢" if side == "Buy" else "🔴"
        approach_emoji = "⚡" if "fast" in approach.lower() else "🛡️" if "conservative" in approach.lower() else "📸"

        return {
            'monitor_key': monitor_key,
            'symbol': symbol,
            'side': side,
            'approach': approach,
            'chat_id': chat_id,
            'active': active,
            'status_emoji': status_emoji,
            'side_emoji': side_emoji,
            'approach_emoji': approach_emoji,
            'runtime': runtime_str,
            'last_check': last_check_str,
            'error_count': error_count,
            'last_error': last_error,
            'position_size': position_size,
            'entry_price': entry_price,
            'current_pnl': current_pnl,
            'tp_orders': tp_orders,
            'sl_orders': sl_orders,
            'is_mirror': 'mirror' in monitor_key.lower()
        }

    @staticmethod
    def format_runtime(seconds: float) -> str:
        """Format runtime in human readable format"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
        else:
            days = int(seconds // 86400)
            hours = int((seconds % 86400) // 3600)
            return f"{days}d {hours}h"

    @staticmethod
    def format_time_ago(seconds: float) -> str:
        """Format time ago in human readable format"""
        if seconds < 60:
            return f"{int(seconds)}s ago"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m ago"
        elif seconds < 86400:
            return f"{int(seconds // 3600)}h ago"
        else:
            return f"{int(seconds // 86400)}d ago"

    @staticmethod
    def calculate_monitor_stats(main_monitors: List[Dict], mirror_monitors: List[Dict]) -> Dict[str, Any]:
        """Calculate overall monitor statistics"""
        all_monitors = main_monitors + mirror_monitors

        total_monitors = len(all_monitors)
        active_monitors = len([m for m in all_monitors if m['active']])

        # Count by approach
        fast_count = len([m for m in all_monitors if 'fast' in m['approach'].lower()])
        conservative_count = len([m for m in all_monitors if 'conservative' in m['approach'].lower()])
        ggshot_count = len([m for m in all_monitors if 'ggshot' in m['approach'].lower()])

        # Count with errors
        error_count = len([m for m in all_monitors if m['error_count'] > 0])

        # Average runtime
        runtimes = [m.get('runtime', '0s') for m in all_monitors if m['active']]

        return {
            'total': total_monitors,
            'active': active_monitors,
            'inactive': total_monitors - active_monitors,
            'main_count': len(main_monitors),
            'mirror_count': len(mirror_monitors),
            'fast_count': fast_count,
            'conservative_count': conservative_count,
            'ggshot_count': ggshot_count,
            'error_count': error_count,
            'health_percentage': ((active_monitors - error_count) / max(total_monitors, 1)) * 100
        }

    @staticmethod
    def format_monitor_display(monitors: List[Dict], account_type: str) -> str:
        """Format monitors for display"""
        if not monitors:
            return f"<b>{account_type.upper()} ACCOUNT</b>\nNo active monitors\n"

        result = f"<b>{account_type.upper()} ACCOUNT</b> ({len(monitors)} monitors)\n\n"

        # Group by status
        active_monitors = [m for m in monitors if m['active']]
        inactive_monitors = [m for m in monitors if not m['active']]
        error_monitors = [m for m in monitors if m['error_count'] > 0]

        # Show active monitors
        if active_monitors:
            result += "<b>🟢 ACTIVE MONITORS</b>\n"
            for monitor in active_monitors[:5]:  # Show max 5
                pnl_str = ""
                if monitor['current_pnl'] != 0:
                    pnl_sign = "+" if monitor['current_pnl'] > 0 else ""
                    pnl_str = f" | P&L: {pnl_sign}${format_number(abs(monitor['current_pnl']))}"

                result += (
                    f"{monitor['status_emoji']} {monitor['approach_emoji']} "
                    f"<b>{monitor['symbol']}</b> {monitor['side_emoji']}\n"
                    f"   Runtime: {monitor['runtime']} | "
                    f"Last: {monitor['last_check']}{pnl_str}\n"
                )

                if monitor['tp_orders'] or monitor['sl_orders']:
                    result += f"   Orders: {monitor['tp_orders']} TP, {monitor['sl_orders']} SL\n"

                result += "\n"

            if len(active_monitors) > 5:
                result += f"   ... and {len(active_monitors) - 5} more active\n\n"

        # Show monitors with errors
        if error_monitors:
            result += "<b>🟡 MONITORS WITH ERRORS</b>\n"
            for monitor in error_monitors[:3]:  # Show max 3
                result += (
                    f"🟡 {monitor['approach_emoji']} <b>{monitor['symbol']}</b> "
                    f"{monitor['side_emoji']}\n"
                    f"   Errors: {monitor['error_count']} | "
                    f"Last: {monitor['last_error'][:50]}...\n\n"
                )

        # Show inactive monitors
        if inactive_monitors:
            result += f"<b>🔴 INACTIVE</b> ({len(inactive_monitors)} monitors)\n"
            for monitor in inactive_monitors[:3]:  # Show max 3
                result += (
                    f"🔴 {monitor['approach_emoji']} <b>{monitor['symbol']}</b> "
                    f"{monitor['side_emoji']} (Stopped)\n"
                )

            if len(inactive_monitors) > 3:
                result += f"   ... and {len(inactive_monitors) - 3} more inactive\n"

        return result

    @staticmethod
    def build_monitor_management_keyboard(stats: Dict[str, Any]) -> InlineKeyboardMarkup:
        """Build keyboard for monitor management"""
        keyboard = []

        # First row - Refresh and overview
        first_row = [
            InlineKeyboardButton("🔄 Refresh", callback_data="show_monitors"),
            InlineKeyboardButton("📊 Overview", callback_data="monitor_overview")
        ]
        keyboard.append(first_row)

        # Second row - Account specific actions
        second_row = [
            InlineKeyboardButton("📍 Main Only", callback_data="show_main_monitors"),
            InlineKeyboardButton("🪞 Mirror Only", callback_data="show_mirror_monitors")
        ]
        keyboard.append(second_row)

        # Third row - Monitor controls
        third_row = [
            InlineKeyboardButton("▶️ Start All", callback_data="start_all_monitors"),
            InlineKeyboardButton("⏹️ Stop All", callback_data="stop_all_monitors")
        ]
        keyboard.append(third_row)

        # Fourth row - Maintenance
        fourth_row = [
            InlineKeyboardButton("🧹 Cleanup", callback_data="cleanup_monitors"),
            InlineKeyboardButton("🔧 Restart Errors", callback_data="restart_error_monitors")
        ]
        keyboard.append(fourth_row)

        # Fifth row - Navigation
        fifth_row = [
            InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard"),
            InlineKeyboardButton("📊 Positions", callback_data="show_all_positions")
        ]
        keyboard.append(fifth_row)

        return InlineKeyboardMarkup(keyboard)


async def show_monitors(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show comprehensive monitor overview"""
    query = update.callback_query
    if query:
        from utils.telegram_helpers import safe_answer_callback
        await safe_answer_callback(query)

    try:
        # Get monitor data
        monitor_data = await MonitorManager.get_all_monitor_data(context)

        if monitor_data['error']:
            await query.edit_message_text(
                f"❌ Error loading monitors: {monitor_data['error']}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Retry", callback_data="show_monitors"),
                    InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
                ]])
            )
            return

        # Build message
        stats = monitor_data['monitor_stats']
        main_monitors = monitor_data['main_monitors']
        mirror_monitors = monitor_data['mirror_monitors']

        message_parts = ["<b>⚡ MONITOR MANAGEMENT CENTER</b>\n"]

        # Overall stats
        health_emoji = "🟢" if stats['health_percentage'] > 80 else "🟡" if stats['health_percentage'] > 50 else "🔴"
        message_parts.append(
            f"<b>📊 OVERVIEW</b>\n"
            f"Total: {stats['total']} | Active: {stats['active']} | "
            f"Errors: {stats['error_count']}\n"
            f"Health: {health_emoji} {stats['health_percentage']:.0f}%\n"
            f"⚡ Fast: {stats['fast_count']} | 🛡️ Conservative: {stats['conservative_count']} | "
            f"📸 GGShot: {stats['ggshot_count']}\n"
        )

        # Main account monitors
        if main_monitors:
            message_parts.append(MonitorManager.format_monitor_display(main_monitors, "main"))
        else:
            message_parts.append("<b>📍 MAIN ACCOUNT</b>\nNo active monitors\n")

        # Mirror account monitors
        if mirror_monitors:
            message_parts.append(MonitorManager.format_monitor_display(mirror_monitors, "mirror"))
        elif stats['mirror_count'] == 0:
            message_parts.append("<b>🪞 MIRROR ACCOUNT</b>\nMirror trading not enabled\n")

        # Build final message
        message = "\n".join(message_parts)

        # Truncate if too long
        if len(message) > 4000:
            message = message[:3800] + "\n\n... (truncated for length)"

        keyboard = MonitorManager.build_monitor_management_keyboard(stats)

        if query:
            await query.edit_message_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )

    except Exception as e:
        logger.error(f"Error in show_monitors: {e}")
        error_message = f"❌ Error: {str(e)}"

        if query:
            await query.edit_message_text(
                error_message,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Retry", callback_data="show_monitors")
                ]])
            )


async def handle_monitor_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle monitor management actions"""
    query = update.callback_query
    if not query:
        return

    from utils.telegram_helpers import safe_answer_callback
    await safe_answer_callback(query)

    try:
        action = query.data

        if action == "monitor_overview":
            await show_monitor_overview(query, context)
        elif action == "show_main_monitors":
            await show_account_monitors(query, context, "main")
        elif action == "show_mirror_monitors":
            await show_account_monitors(query, context, "mirror")
        elif action == "start_all_monitors":
            await start_all_monitors(query, context)
        elif action == "stop_all_monitors":
            await stop_all_monitors(query, context)
        elif action == "cleanup_monitors":
            await cleanup_monitors(query, context)
        elif action == "restart_error_monitors":
            await restart_error_monitors(query, context)

    except Exception as e:
        logger.error(f"Error handling monitor action: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")


async def show_monitor_overview(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed monitor overview"""
    try:
        monitor_data = await MonitorManager.get_all_monitor_data(context)
        stats = monitor_data['monitor_stats']

        message = f"""<b>📊 MONITOR OVERVIEW</b>

<b>📈 STATISTICS</b>
Total Monitors: {stats['total']}
Active: 🟢 {stats['active']}
Inactive: 🔴 {stats['inactive']}
With Errors: 🟡 {stats['error_count']}

<b>📍 BY ACCOUNT</b>
Main Account: {stats['main_count']} monitors
Mirror Account: {stats['mirror_count']} monitors

<b>⚡ BY APPROACH</b>
Fast Market: {stats['fast_count']} monitors
Conservative: {stats['conservative_count']} monitors
GGShot: {stats['ggshot_count']} monitors

<b>🏥 HEALTH STATUS</b>
Overall Health: {stats['health_percentage']:.1f}%
Status: {'🟢 Excellent' if stats['health_percentage'] > 80 else '🟡 Good' if stats['health_percentage'] > 50 else '🔴 Needs Attention'}
"""

        await query.edit_message_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="show_monitors")
            ]])
        )

    except Exception as e:
        logger.error(f"Error showing monitor overview: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")


async def show_account_monitors(query, context: ContextTypes.DEFAULT_TYPE, account: str) -> None:
    """Show monitors for specific account"""
    try:
        monitor_data = await MonitorManager.get_all_monitor_data(context)

        if account == "main":
            monitors = monitor_data['main_monitors']
        else:
            monitors = monitor_data['mirror_monitors']

        message = MonitorManager.format_monitor_display(monitors, account)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"▶️ Start All {account.title()}", callback_data=f"start_{account}_monitors"),
                InlineKeyboardButton(f"⏹️ Stop All {account.title()}", callback_data=f"stop_{account}_monitors")
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="show_monitors")
            ]
        ])

        await query.edit_message_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error showing {account} monitors: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")


async def start_all_monitors(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start all monitors"""
    await query.edit_message_text(
        "⏳ Starting all monitors...\n\nThis feature will restart all inactive monitors.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back", callback_data="show_monitors")
        ]])
    )


async def stop_all_monitors(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stop all monitors with confirmation"""
    confirmation_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm Stop All", callback_data="confirm_stop_all_monitors"),
            InlineKeyboardButton("❌ Cancel", callback_data="show_monitors")
        ]
    ])

    await query.edit_message_text(
        "⚠️ Are you sure you want to stop ALL monitors?\n\nThis will disable automatic TP/SL management for all positions.",
        reply_markup=confirmation_keyboard
    )


async def cleanup_monitors(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clean up stale monitors"""
    try:
        # This would call the existing monitor cleanup functionality
        from utils.monitor_cleanup import cleanup_stale_monitors_on_startup

        await query.edit_message_text("🧹 Cleaning up monitors...")

        cleanup_performed = await cleanup_stale_monitors_on_startup(context.bot_data)

        if cleanup_performed:
            await query.edit_message_text(
                "✅ Monitor cleanup completed!\n\nStale monitors have been removed.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Refresh", callback_data="show_monitors")
                ]])
            )
        else:
            await query.edit_message_text(
                "✅ No cleanup needed!\n\nAll monitors are healthy.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="show_monitors")
                ]])
            )

    except Exception as e:
        logger.error(f"Error cleaning up monitors: {e}")
        await query.edit_message_text(f"❌ Cleanup failed: {str(e)}")


async def restart_error_monitors(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Restart monitors with errors"""
    await query.edit_message_text(
        "🔧 Restarting monitors with errors...\n\nThis feature will attempt to restart failed monitors.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back", callback_data="show_monitors")
        ]])
    )