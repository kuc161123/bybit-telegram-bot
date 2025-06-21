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
from dashboard.generator_analytics_compact import build_mobile_dashboard_text as build_dashboard_text_async
from dashboard.keyboards_analytics import build_enhanced_dashboard_keyboard
from shared import msg_manager
from utils.formatters import get_emoji
from utils.position_modes import (
    enable_hedge_mode, enable_one_way_mode, get_current_position_mode,
    format_position_mode_help, get_position_mode_commands
)
from clients.bybit_helpers import get_all_positions

logger = logging.getLogger(__name__)

async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enhanced dashboard command with mobile optimization"""
    logger.info("📱 Dashboard command called - showing ENHANCED UI")
    
    # Clear any cached data to ensure fresh UI
    from utils.cache import invalidate_all_caches
    invalidate_all_caches()
    
    # Delete the command message if it exists to keep chat clean
    if update.message:
        try:
            await update.message.delete()
            logger.debug("Deleted command message")
        except Exception as e:
            logger.debug(f"Could not delete command message: {e}")
    
    # Force new message to show enhanced UI
    await _send_or_edit_dashboard_message(update, context, new_msg=True)

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
        
        # Get active positions count for keyboard
        positions = await get_all_positions()
        active_positions = len([p for p in positions if float(p.get('size', 0)) > 0])
        has_monitors = ctx.chat_data.get('ACTIVE_MONITOR_TASK', {}) != {}
        
        keyboard = build_enhanced_dashboard_keyboard(c_id, ctx, active_positions, has_monitors)
        
        # ALWAYS delete previous dashboard message if it exists
        old_msg_id = ctx.chat_data.get(LAST_UI_MESSAGE_ID)
        if old_msg_id:
            try:
                await ctx.bot.delete_message(chat_id=c_id, message_id=old_msg_id)
                logger.debug(f"Deleted previous dashboard message {old_msg_id}")
            except Exception as e:
                logger.debug(f"Could not delete old dashboard message: {e}")
            # Clear the stored ID since we deleted it
            ctx.chat_data[LAST_UI_MESSAGE_ID] = None
        
        # Force new_msg to True to ensure we always send a fresh message
        new_msg = True
        
        # Always send new message (since we deleted the old one)
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
        except Exception as e:
            logger.error(f"Error sending dashboard message: {e}")
            
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

🎯 <b>POSITION MODES:</b>
• /hedge_mode - Enable hedge mode (both directions)
• /one_way_mode - Enable one-way mode (single direction)
• /check_mode - Check current position mode

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