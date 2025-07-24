#!/usr/bin/env python3
"""
Command handlers for the trading bot - MANUAL ENTRY OPTIMIZED.
REMOVED: All voice functionality
ENHANCED: Dashboard and manual trading workflow
ADDED: Hedge mode and position mode commands
"""
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config.constants import *
from utils.helpers import initialize_chat_data
from dashboard.generator_v2 import build_mobile_dashboard_text as build_dashboard_text_async
from dashboard.keyboards_v2 import DashboardKeyboards
from shared import msg_manager
from clients.bybit_helpers import get_all_positions
from utils.formatters import get_emoji, format_mobile_currency
from utils.position_modes import (
    enable_hedge_mode, enable_one_way_mode, get_current_position_mode,
    format_position_mode_help, get_position_mode_commands
)
from clients.bybit_helpers import get_all_positions
from decimal import Decimal
import asyncio
import time
import hashlib

# Import position manager for close functionality
try:
    from execution.position_manager import position_manager
    POSITION_MANAGER_AVAILABLE = True
except ImportError:
    POSITION_MANAGER_AVAILABLE = False
    logger.warning("Position manager not available")

logger = logging.getLogger(__name__)

# Auto-refresh settings
AUTO_REFRESH_INTERVAL = 45  # seconds (increased for better performance)
AUTO_REFRESH_TASK_KEY = "dashboard_auto_refresh_task"

async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enhanced dashboard command with mobile optimization and auto-refresh"""
    logger.info("📱 Dashboard command called - showing ENHANCED UI with auto-refresh")

    # Clear only volatile cached data to ensure fresh UI (keep stable data)
    from utils.cache import invalidate_volatile_caches
    invalidate_volatile_caches()

    # Delete the command message if it exists to keep chat clean
    if update.message:
        try:
            await update.message.delete()
            logger.debug("Deleted command message")
        except Exception as e:
            logger.debug(f"Could not delete command message: {e}")

    # Force new message to show enhanced UI
    await _send_or_edit_dashboard_message(update, context, new_msg=True)

    # Start auto-refresh if there are active positions
    await start_auto_refresh(update.effective_chat.id, context)

async def stop_auto_refresh(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stop auto-refresh task for a chat"""
    # Cancel existing auto-refresh task if any
    task_key = f"{AUTO_REFRESH_TASK_KEY}_{chat_id}"
    if task_key in context.application.bot_data:
        task = context.application.bot_data[task_key]
        if not task.done():
            task.cancel()
            logger.info(f"Cancelled auto-refresh task for chat {chat_id}")
        del context.application.bot_data[task_key]

async def start_auto_refresh(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start or restart auto-refresh task for dashboard"""
    # Cancel existing task if any
    await stop_auto_refresh(chat_id, context)

    # CRITICAL FIX: Use monitoring cache for positions
    try:
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        positions = await enhanced_tp_sl_manager._get_cached_position_info("ALL", "main")
    except Exception as e:
        # Fallback to direct API call if cache unavailable
        from clients.bybit_client import bybit_client
        positions = await get_all_positions()
    active_positions = [p for p in positions if float(p.get('size', 0)) > 0]

    if active_positions:
        # Start new auto-refresh task
        task_key = f"{AUTO_REFRESH_TASK_KEY}_{chat_id}"
        task = asyncio.create_task(auto_refresh_dashboard(chat_id, context))
        context.application.bot_data[task_key] = task
        logger.info(f"Started auto-refresh task for chat {chat_id} with {len(active_positions)} active positions")
    else:
        logger.info(f"No active positions, auto-refresh not started for chat {chat_id}")

async def auto_refresh_dashboard(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Auto-refresh dashboard while positions are active"""
    logger.info(f"Auto-refresh started for chat {chat_id}")
    consecutive_errors = 0

    try:
        while True:
            await asyncio.sleep(AUTO_REFRESH_INTERVAL)

            # CRITICAL FIX: Use monitoring cache for positions
            try:
                from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
                positions = await enhanced_tp_sl_manager._get_cached_position_info("ALL", "main")
            except Exception as e:
                positions = await get_all_positions()
            active_positions = [p for p in positions if float(p.get('size', 0)) > 0]

            if not active_positions:
                logger.info(f"No active positions, stopping auto-refresh for chat {chat_id}")
                break

            # Check if dashboard is still being viewed (last refresh within 5 minutes)
            last_refresh = context.chat_data.get('last_dashboard_refresh', 0)
            if time.time() - last_refresh > 300:  # 5 minutes
                logger.info(f"Dashboard not viewed recently, stopping auto-refresh for chat {chat_id}")
                break

            try:
                # Clear only volatile cache and refresh dashboard (preserve market analysis cache for token savings)
                from utils.cache import invalidate_volatile_caches
                invalidate_volatile_caches()

                # Update dashboard
                await _send_or_edit_dashboard_message(chat_id, context, new_msg=False)
                logger.debug(f"Auto-refreshed dashboard for chat {chat_id}")
                consecutive_errors = 0

            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error auto-refreshing dashboard: {e}")
                if consecutive_errors >= 3:
                    logger.error(f"Too many errors, stopping auto-refresh for chat {chat_id}")
                    break

    except asyncio.CancelledError:
        logger.info(f"Auto-refresh cancelled for chat {chat_id}")
    except Exception as e:
        logger.error(f"Auto-refresh error for chat {chat_id}: {e}")
    finally:
        # Clean up task reference
        task_key = f"{AUTO_REFRESH_TASK_KEY}_{chat_id}"
        if task_key in context.application.bot_data:
            del context.application.bot_data[task_key]

async def _send_or_edit_dashboard_message(upd_or_cid, ctx: ContextTypes.DEFAULT_TYPE, new_msg: bool = False):
    """Send or edit dashboard message with enhanced mobile optimization"""
    # Determine chat ID
    if isinstance(upd_or_cid, (int, str)):
        c_id = upd_or_cid
    elif hasattr(upd_or_cid, 'effective_chat') and upd_or_cid.effective_chat:
        c_id = upd_or_cid.effective_chat.id
    elif hasattr(upd_or_cid, 'message') and upd_or_cid.message:
        c_id = upd_or_cid.message.chat.id
    else:
        logger.error("Could not determine chat ID from input")
        return

    # Initialize chat data if needed
    if ctx.chat_data is None:
        ctx.chat_data = {}
    initialize_chat_data(ctx.chat_data)

    # Build dashboard
    try:
        dashboard_text = await build_dashboard_text_async(c_id, ctx)

        # CRITICAL FIX: Use monitoring cache for positions
        try:
            from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
            positions = await enhanced_tp_sl_manager._get_cached_position_info("ALL", "main")
        except Exception as e:
            from clients.bybit_client import bybit_client
            positions = await get_all_positions()
        active_positions = len([p for p in positions if float(p.get('size', 0)) > 0])
        has_monitors = ctx.chat_data.get('ACTIVE_MONITOR_TASK', {}) != {}

        # Check if mirror trading is enabled
        has_mirror = False
        try:
            from execution.mirror_trader import is_mirror_trading_enabled
            has_mirror = is_mirror_trading_enabled()
        except:
            pass

        keyboard = DashboardKeyboards.main_dashboard(active_positions > 0, has_mirror)

        # Calculate content hash for comparison (only for auto-refresh)
        if not new_msg:
            content_hash = hashlib.md5(dashboard_text.encode()).hexdigest()
            last_content_hash = ctx.chat_data.get('last_dashboard_content_hash')

            if content_hash == last_content_hash:
                # Content hasn't changed, skip update
                logger.debug("Dashboard content unchanged, skipping auto-refresh")
                ctx.chat_data['last_dashboard_refresh'] = time.time()
                return

            # Store new content hash
            ctx.chat_data['last_dashboard_content_hash'] = content_hash

        # Get the previous message ID
        old_msg_id = ctx.chat_data.get(LAST_UI_MESSAGE_ID)

        # If auto-refresh (new_msg=False) and we have an existing message, edit it
        if not new_msg and old_msg_id:
            try:
                await ctx.bot.edit_message_text(
                    chat_id=c_id,
                    message_id=old_msg_id,
                    text=dashboard_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )
                logger.debug(f"Edited existing dashboard message {old_msg_id} (auto-refresh)")
                # Store last refresh time
                ctx.chat_data['last_dashboard_refresh'] = time.time()
                return  # Successfully edited, no need to send new message
            except Exception as e:
                # For auto-refresh, check the type of error
                error_str = str(e).lower()
                if "message is not modified" in error_str or "message to edit not found" not in error_str:
                    # Message content is identical or minor error - just update refresh time
                    logger.debug(f"Dashboard unchanged or minor error: {e}")
                    ctx.chat_data['last_dashboard_refresh'] = time.time()
                    return  # Don't send a new message for unchanged content
                else:
                    # Message was deleted - need to send new one but without notification
                    logger.debug(f"Message deleted, will send new one silently: {e}")
                    # Don't set new_msg=True here, handle it differently below

        # For manual refresh or if edit failed, handle accordingly
        if new_msg:
            # Manual refresh - delete old and send new with notification
            if old_msg_id:
                try:
                    await ctx.bot.delete_message(chat_id=c_id, message_id=old_msg_id)
                    logger.debug(f"Deleted previous dashboard message {old_msg_id}")
                except Exception as e:
                    logger.debug(f"Could not delete old dashboard message: {e}")
                # Clear the stored ID since we deleted it
                ctx.chat_data[LAST_UI_MESSAGE_ID] = None

            # Send new message with notification (manual refresh)
            try:
                sent = await ctx.bot.send_message(
                    c_id,
                    dashboard_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )
                if sent:
                    ctx.chat_data[LAST_UI_MESSAGE_ID] = sent.message_id
                    logger.debug(f"Sent new dashboard message {sent.message_id}")
                    # Store last refresh time and content hash
                    ctx.chat_data['last_dashboard_refresh'] = time.time()
                    ctx.chat_data['last_dashboard_content_hash'] = hashlib.md5(dashboard_text.encode()).hexdigest()
            except Exception as e:
                logger.error(f"Error sending dashboard message: {e}")
        else:
            # Auto-refresh where message was deleted - send new without notification
            if old_msg_id:
                # Clear the stored ID since the message doesn't exist
                ctx.chat_data[LAST_UI_MESSAGE_ID] = None

            try:
                sent = await ctx.bot.send_message(
                    c_id,
                    dashboard_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                    disable_notification=True  # Silent update for auto-refresh
                )
                if sent:
                    ctx.chat_data[LAST_UI_MESSAGE_ID] = sent.message_id
                    logger.debug(f"Sent new dashboard message {sent.message_id} (silent auto-refresh)")
                    # Store last refresh time and content hash
                    ctx.chat_data['last_dashboard_refresh'] = time.time()
                    ctx.chat_data['last_dashboard_content_hash'] = hashlib.md5(dashboard_text.encode()).hexdigest()
            except Exception as e:
                logger.error(f"Error sending silent dashboard message: {e}")

    except Exception as e:
        logger.error(f"Error in dashboard generation: {e}", exc_info=True)
        await ctx.bot.send_message(
            c_id,
            f"{get_emoji('error')} Error loading dashboard. Please try /start",
            parse_mode=ParseMode.HTML
        )

async def hedge_mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enable hedge mode for trading both directions simultaneously"""
    chat_id = update.effective_chat.id

    # Check if a specific symbol was provided
    symbol = None
    if context.args:
        symbol = context.args[0].upper()
        if not symbol.endswith('USDT'):
            symbol = symbol + 'USDT'

    # Send processing message
    processing_msg = await update.message.reply_text(
        f"{get_emoji('loading')} Enabling hedge mode...",
        parse_mode=ParseMode.HTML
    )

    try:
        # Enable hedge mode
        if symbol:
            success, message = enable_hedge_mode(symbol=symbol)
        else:
            success, message = enable_hedge_mode()

        # Create response with current mode info
        if success:
            # Get current mode info
            mode_success, mode_info, mode_details = get_current_position_mode(symbol)

            response_text = f"""
{get_emoji('success')} <b>HEDGE MODE ENABLED</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{message}

{get_emoji('info')} <b>Current Status:</b>
{mode_info if mode_success else 'Could not verify current mode'}

{get_emoji('target')} <b>What This Means:</b>
• Can hold BOTH long AND short positions
• Same symbol can have BUY + SELL simultaneously
• Advanced position management enabled
• Useful for hedging strategies

{get_emoji('warning')} <b>Important Notes:</b>
• More complex than one-way mode
• Requires careful position management
• Both directions can be profitable/unprofitable

{get_emoji('gear')} <b>Commands:</b>
• /one_way_mode - Switch back to one-way mode
• /check_mode - Check current position mode
• /dashboard - Return to main dashboard
"""
        else:
            response_text = f"""
{get_emoji('error')} <b>HEDGE MODE FAILED</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{message}

{get_emoji('info')} <b>Common Issues:</b>
• Open orders exist (close them first)
• Already in hedge mode
• API connectivity issues

{get_emoji('gear')} <b>What to Try:</b>
• Close all open orders
• Check /check_mode for current status
• Try again in a few seconds
"""

        # Create keyboard
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{get_emoji('chart')} Check Mode", callback_data="check_position_mode"),
                InlineKeyboardButton(f"{get_emoji('shield')} One-Way Mode", callback_data="enable_one_way_mode")
            ],
            [InlineKeyboardButton(f"{get_emoji('refresh')} Dashboard", callback_data="refresh_dashboard")]
        ])

        # Edit the processing message
        await processing_msg.edit_text(
            response_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error in hedge mode command: {e}")
        await processing_msg.edit_text(
            f"{get_emoji('error')} Error enabling hedge mode: {str(e)}",
            parse_mode=ParseMode.HTML
        )

async def one_way_mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enable one-way mode for single position per symbol"""
    chat_id = update.effective_chat.id

    # Check if a specific symbol was provided
    symbol = None
    if context.args:
        symbol = context.args[0].upper()
        if not symbol.endswith('USDT'):
            symbol = symbol + 'USDT'

    # Send processing message
    processing_msg = await update.message.reply_text(
        f"{get_emoji('loading')} Enabling one-way mode...",
        parse_mode=ParseMode.HTML
    )

    try:
        # Enable one-way mode
        if symbol:
            success, message = enable_one_way_mode(symbol=symbol)
        else:
            success, message = enable_one_way_mode()

        # Create response with current mode info
        if success:
            # Get current mode info
            mode_success, mode_info, mode_details = get_current_position_mode(symbol)

            response_text = f"""
{get_emoji('success')} <b>ONE-WAY MODE ENABLED</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{message}

{get_emoji('info')} <b>Current Status:</b>
{mode_info if mode_success else 'Could not verify current mode'}

{get_emoji('target')} <b>What This Means:</b>
• Only ONE position per symbol
• BUY or SELL, but not both
• Same direction trades ADD to position
• Opposite direction trades are BLOCKED

{get_emoji('shield')} <b>Benefits:</b>
• Simpler position management
• Prevents conflicting positions
• Easier to track performance

{get_emoji('gear')} <b>Commands:</b>
• /hedge_mode - Switch to hedge mode
• /check_mode - Check current position mode
• /dashboard - Return to main dashboard
"""
        else:
            response_text = f"""
{get_emoji('error')} <b>ONE-WAY MODE FAILED</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{message}

{get_emoji('info')} <b>Common Issues:</b>
• Open orders exist (close them first)
• Already in one-way mode
• API connectivity issues

{get_emoji('gear')} <b>What to Try:</b>
• Close all open orders
• Check /check_mode for current status
• Try again in a few seconds
"""

        # Create keyboard
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{get_emoji('chart')} Check Mode", callback_data="check_position_mode"),
                InlineKeyboardButton(f"{get_emoji('target')} Hedge Mode", callback_data="enable_hedge_mode")
            ],
            [InlineKeyboardButton(f"{get_emoji('refresh')} Dashboard", callback_data="refresh_dashboard")]
        ])

        # Edit the processing message
        await processing_msg.edit_text(
            response_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error in one-way mode command: {e}")
        await processing_msg.edit_text(
            f"{get_emoji('error')} Error enabling one-way mode: {str(e)}",
            parse_mode=ParseMode.HTML
        )

async def check_mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check current position mode"""
    chat_id = update.effective_chat.id

    # Check if a specific symbol was provided
    symbol = None
    if context.args:
        symbol = context.args[0].upper()
        if not symbol.endswith('USDT'):
            symbol = symbol + 'USDT'

    # Send processing message
    processing_msg = await update.message.reply_text(
        f"{get_emoji('loading')} Checking position mode...",
        parse_mode=ParseMode.HTML
    )

    try:
        # Get current position mode
        success, mode_info, mode_details = get_current_position_mode(symbol)

        if success:
            is_hedge_mode = mode_details.get("hedge_mode", False)
            positions_found = mode_details.get("positions_found", 0)

            response_text = f"""
{get_emoji('chart')} <b>POSITION MODE STATUS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{get_emoji('info')} <b>Current Mode:</b>
{mode_info}

{get_emoji('target')} <b>Target:</b> {'All USDT contracts' if not symbol else symbol}

{get_emoji('shield')} <b>Mode Details:</b>
• Hedge Mode: {'Yes' if is_hedge_mode else 'No'}
• Positions Found: {positions_found}

{get_emoji('bulb')} <b>What This Means:</b>
"""

            if is_hedge_mode:
                response_text += """
• Can trade BOTH long and short simultaneously
• More complex position management
• Useful for hedging strategies
• Both BUY and SELL orders allowed
"""
            else:
                response_text += """
• Only ONE position per symbol
• Same direction adds to position
• Opposite direction is blocked
• Simpler position management
"""

            response_text += f"""
{format_position_mode_help()}

{get_position_mode_commands()}
"""
        else:
            response_text = f"""
{get_emoji('error')} <b>POSITION MODE CHECK FAILED</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{mode_info}

{get_emoji('gear')} <b>What to Try:</b>
• Check your API connection
• Verify your API keys
• Try again in a few seconds
• Contact support if issue persists

{get_emoji('info')} <b>Commands:</b>
• /hedge_mode - Enable hedge mode
• /one_way_mode - Enable one-way mode
• /dashboard - Return to dashboard
"""

        # Create keyboard
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{get_emoji('target')} Hedge Mode", callback_data="enable_hedge_mode"),
                InlineKeyboardButton(f"{get_emoji('shield')} One-Way Mode", callback_data="enable_one_way_mode")
            ],
            [InlineKeyboardButton(f"{get_emoji('refresh')} Dashboard", callback_data="refresh_dashboard")]
        ])

        # Edit the processing message
        await processing_msg.edit_text(
            response_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error in check mode command: {e}")
        await processing_msg.edit_text(
            f"{get_emoji('error')} Error checking position mode: {str(e)}",
            parse_mode=ParseMode.HTML
        )

async def cleanup_monitors_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clean up stuck monitors for closed positions"""
    chat_id = update.effective_chat.id

    # Send processing message
    processing_msg = await update.message.reply_text(
        f"{get_emoji('loading')} Cleaning up stuck monitors...",
        parse_mode=ParseMode.HTML
    )

    try:
        # Get bot data
        bot_data = context.bot_data

        # CRITICAL FIX: Use monitoring cache for positions
        try:
            from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
            active_positions = await enhanced_tp_sl_manager._get_cached_position_info("ALL", "main")
        except Exception as e:
            active_positions = await get_all_positions()
        active_symbols = set()

        for pos in active_positions:
            if float(pos.get('size', 0)) > 0:
                symbol = pos.get('symbol')
                if symbol:
                    active_symbols.add(symbol)

        # Check monitors
        monitor_tasks = bot_data.get('monitor_tasks', {})
        monitors_removed = []

        # First pass: check all monitors regardless of 'active' status
        for monitor_key in list(monitor_tasks.keys()):
            monitor_data = monitor_tasks[monitor_key]
            symbol = monitor_data.get('symbol')
            if symbol:
                if symbol not in active_symbols:
                    # Remove stuck monitor completely
                    del monitor_tasks[monitor_key]
                    monitors_removed.append(f"{symbol} ({monitor_data.get('approach', 'unknown')})")
                    logger.info(f"Removed monitor {monitor_key} - no active position")
                elif not monitor_data.get('active', False):
                    # Also remove inactive monitors
                    del monitor_tasks[monitor_key]
                    monitors_removed.append(f"{symbol} ({monitor_data.get('approach', 'unknown')}) - inactive")
                    logger.info(f"Removed inactive monitor {monitor_key}")

        # Build response
        if monitors_removed:
            response = f"""
{get_emoji('check')} <b>MONITOR CLEANUP COMPLETED</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{get_emoji('trash')} <b>Removed {len(monitors_removed)} stuck monitors:</b>
"""
            for monitor in monitors_removed:
                response += f"• {monitor}\n"
        else:
            response = f"""
{get_emoji('check')} <b>NO STUCK MONITORS FOUND</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

All monitors are tracking active positions.
"""

        # Show active monitors
        active_monitors = [f"{v['symbol']} ({v['approach']})" for k, v in monitor_tasks.items() if v.get('active', False)]
        if active_monitors:
            response += f"\n{get_emoji('chart')} <b>Active Monitors ({len(active_monitors)}):</b>\n"
            for monitor in active_monitors:
                response += f"• {monitor}\n"

        # Force persistence update after cleanup
        try:
            await context.update_persistence()
            logger.info("Persistence updated after monitor cleanup")
        except Exception as e:
            logger.warning(f"Could not update persistence: {e}")

        await processing_msg.edit_text(response, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error cleaning up monitors: {e}")
        await processing_msg.edit_text(
            f"{get_emoji('error')} Error cleaning up monitors: {str(e)}",
            parse_mode=ParseMode.HTML
        )

async def closeposition_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command to display and close individual positions"""
    logger.info("Close position command called")
    
    if not POSITION_MANAGER_AVAILABLE:
        await update.message.reply_text(
            f"{get_emoji('error')} Position manager not available. Please check system configuration.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Delete the command message if it exists
    if update.message:
        try:
            await update.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete command message: {e}")
    
    # Send processing message
    processing_msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"{get_emoji('loading')} Loading positions...",
        parse_mode=ParseMode.HTML
    )
    
    try:
        # Get all positions from both accounts
        positions = await position_manager.get_all_positions_with_details()
        
        if not positions:
            await processing_msg.edit_text(
                f"{get_emoji('info')} No active positions found on either account.",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Format position list with compact format to avoid message too long
        text = f"<b>📊 ACTIVE POSITIONS</b>\n"
        text += f"{'━' * 30}\n"
        
        # Group by account
        main_positions = [p for p in positions if p['account'] == 'main']
        mirror_positions = [p for p in positions if p['account'] == 'mirror']
        
        keyboard_buttons = []
        
        # Count total positions
        total_main = len(main_positions)
        total_mirror = len(mirror_positions)
        total_positions = total_main + total_mirror
        
        # If too many positions, use ultra-compact format
        if total_positions > 20:
            # Ultra-compact format - just symbol and P&L
            if main_positions:
                text += f"\n<b>💼 MAIN ({total_main})</b>\n"
                for pos in main_positions:
                    symbol = pos['symbol']
                    side = pos['side']
                    pnl = float(pos.get('unrealisedPnl', 0))
                    pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                    pnl_str = format_mobile_currency(Decimal(str(pnl)))
                    
                    text += f"{pnl_emoji} {symbol}: ${pnl_str}\n"
                    
                    # Add button for this position
                    keyboard_buttons.append([
                        InlineKeyboardButton(
                            f"❌ {symbol} (M)",
                            callback_data=f"close_position:{symbol}:{side}:main"
                        )
                    ])
            
            if mirror_positions:
                text += f"\n<b>🔄 MIRROR ({total_mirror})</b>\n"
                for pos in mirror_positions:
                    symbol = pos['symbol']
                    side = pos['side']
                    pnl = float(pos.get('unrealisedPnl', 0))
                    pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                    pnl_str = format_mobile_currency(Decimal(str(pnl)))
                    
                    text += f"{pnl_emoji} {symbol}: ${pnl_str}\n"
                    
                    # Add button for this position
                    keyboard_buttons.append([
                        InlineKeyboardButton(
                            f"❌ {symbol} (🔄)",
                            callback_data=f"close_position:{symbol}:{side}:mirror"
                        )
                    ])
        else:
            # Standard format for fewer positions
            if main_positions:
                text += f"\n<b>💼 MAIN ACCOUNT ({total_main} positions)</b>\n"
                for pos in main_positions:
                    symbol = pos['symbol']
                    side = pos['side']
                    size = pos['size']
                    pnl = pos.get('unrealisedPnl', 0)
                    pnl_emoji = "🟢" if float(pnl) >= 0 else "🔴"
                    
                    text += f"\n{pnl_emoji} <b>{symbol}</b> {side}\n"
                    text += f"   Size: {size}, PnL: ${format_mobile_currency(Decimal(str(pnl)))}\n"
                    
                    # Add button for this position
                    keyboard_buttons.append([
                        InlineKeyboardButton(
                            f"❌ Close {symbol} (Main)",
                            callback_data=f"close_position:{symbol}:{side}:main"
                        )
                    ])
            
            # Mirror account positions
            if mirror_positions:
                text += f"\n<b>🔄 MIRROR ACCOUNT ({total_mirror} positions)</b>\n"
                for pos in mirror_positions:
                    symbol = pos['symbol']
                    side = pos['side']
                    size = pos['size']
                    pnl = pos.get('unrealisedPnl', 0)
                    pnl_emoji = "🟢" if float(pnl) >= 0 else "🔴"
                    
                    text += f"\n{pnl_emoji} <b>{symbol}</b> {side}\n"
                    text += f"   Size: {size}, PnL: ${format_mobile_currency(Decimal(str(pnl)))}\n"
                    
                    # Add button for this position
                    keyboard_buttons.append([
                        InlineKeyboardButton(
                            f"❌ Close {symbol} (Mirror)",
                            callback_data=f"close_position:{symbol}:{side}:mirror"
                        )
                    ])
        
        # Add back to dashboard button
        keyboard_buttons.append([
            InlineKeyboardButton("🔙 Back to Dashboard", callback_data="refresh_dashboard")
        ])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        text += f"\n\n⚠️ <b>Warning:</b> Closing a position will:\n"
        text += f"• Cancel ALL orders for that symbol\n"
        text += f"• Close at market price\n"
        text += f"• This cannot be undone"
        
        await processing_msg.edit_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in closeposition command: {e}")
        await processing_msg.edit_text(
            f"{get_emoji('error')} Error loading positions: {str(e)}",
            parse_mode=ParseMode.HTML
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enhanced help command"""
    help_text = f"""
🚀 <b>ENHANCED TRADING BOT HELP</b>
{'═' * 35}

📱 <b>MOBILE OPTIMIZED FEATURES:</b>
• Enhanced manual trading workflow
• Quick selection buttons
• Mobile-first dashboard design
• Streamlined UX for touch devices
• Responsive layout for all screen sizes

📝 <b>MANUAL TRADING:</b>
• /start - Access main dashboard
• /trade - Start manual trade setup
• /dashboard - View trading dashboard
• /closeposition - Close individual positions

🎯 <b>POSITION MODES:</b>
• /hedge_mode - Enable hedge mode (both directions)
• /one_way_mode - Enable one-way mode (single direction)
• /check_mode - Check current position mode

🚨 <b>EMERGENCY CONTROLS:</b>
• /emergency - EMERGENCY SHUTDOWN (close all positions/orders)
  ⚠️ Requires two-step confirmation
  ⚠️ Closes positions on main AND mirror accounts
  ⚠️ 5-minute cooldown between uses

🔔 <b>SMART ALERTS:</b>
• /alerts - Manage price & position alerts
• /testreport - Generate sample daily report
• Price crossing & percentage change alerts
• Position P&L thresholds
• Risk warnings & market volatility
• Daily trading summary reports

⚙️ <b>QUICK ACTIONS:</b>
• Use buttons for faster navigation
• All inputs have quick selection options
• Mobile-optimized layouts

📊 <b>SETTINGS & STATS:</b>
• Customize default leverage
• Set preferred margin amounts
• View performance statistics
• Export trading data

🔧 <b>FEATURES:</b>
• AI-powered insights
• Real-time position monitoring
• Performance tracking
• Risk management tools
• Mobile-optimized interface
• Hedge mode support

💡 <b>TIPS:</b>
• Use the dashboard for quick overview
• All functions accessible via buttons
• Settings save automatically
• Statistics tracked in real-time

🔧 <b>SUPPORT:</b>
Need help? Use /start to access the main dashboard
or contact support for technical issues.
"""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Dashboard", callback_data="refresh_dashboard")],
        [InlineKeyboardButton("📝 Start Trading", callback_data="start_conversation")],
        [
            InlineKeyboardButton("🎯 Hedge Mode", callback_data="enable_hedge_mode"),
            InlineKeyboardButton("🛡️ One-Way Mode", callback_data="enable_one_way_mode")
        ]
    ])

    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enhanced error handler with better user experience"""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

    # Try to notify user with helpful message
    if update and hasattr(update, 'effective_chat') and update.effective_chat:
        try:
            error_msg = f"""
{get_emoji('error')} <b>Oops! Something went wrong</b>

🔧 <b>What you can do:</b>
• Try the action again
• Use /start to return to dashboard
• Check your internet connection

💡 The error has been logged for review.
"""

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")],
                [InlineKeyboardButton("📝 Start Trading", callback_data="start_conversation")]
            ])

            await context.bot.send_message(
                update.effective_chat.id,
                error_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        except:
            pass