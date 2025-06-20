#!/usr/bin/env python3
"""
Position and Statistics button handlers
"""
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from clients.bybit_helpers import get_all_positions
from dashboard.keyboards_analytics import build_stats_keyboard, build_analytics_dashboard_keyboard, build_settings_keyboard, build_help_keyboard
from config.constants import *
from utils.formatters import format_number

logger = logging.getLogger(__name__)

async def list_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle list positions button"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get all positions
        positions = await get_all_positions()
        active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
        
        if not active_positions:
            await query.edit_message_text(
                "📋 <b>No Active Positions</b>\n\n"
                "You don't have any open positions.\n"
                "Use /trade to open a new position.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📊 New Trade", callback_data="start_conversation"),
                    InlineKeyboardButton("🔙 Back", callback_data="refresh_dashboard")
                ]])
            )
            return
        
        # Build position list
        position_text = "📋 <b>Active Positions</b>\n\n"
        
        for i, pos in enumerate(active_positions, 1):
            symbol = pos.get('symbol', '')
            side = pos.get('side', '')
            size = float(pos.get('size', 0))
            avg_price = float(pos.get('avgPrice', 0))
            mark_price = float(pos.get('markPrice', 0))
            unrealized_pnl = float(pos.get('unrealisedPnl', 0))
            leverage = int(pos.get('leverage', 1))
            
            # Calculate percentage
            if avg_price > 0:
                if side == 'Buy':
                    pnl_pct = ((mark_price - avg_price) / avg_price) * 100
                else:
                    pnl_pct = ((avg_price - mark_price) / avg_price) * 100
            else:
                pnl_pct = 0
            
            # Emoji based on P&L
            if unrealized_pnl > 0:
                emoji = "🟢"
            elif unrealized_pnl < 0:
                emoji = "🔴"
            else:
                emoji = "⚪"
            
            position_text += f"{i}. {emoji} <b>{symbol}</b> {side}\n"
            position_text += f"   Size: {size} @ ${avg_price:.4f}\n"
            position_text += f"   Mark: ${mark_price:.4f} | Lev: {leverage}x\n"
            position_text += f"   P&L: ${unrealized_pnl:.2f} ({pnl_pct:+.2f}%)\n\n"
        
        # Add summary
        total_pnl = sum(float(p.get('unrealisedPnl', 0)) for p in active_positions)
        position_text += f"<b>Total Unrealized P&L: ${total_pnl:.2f}</b>"
        
        # Add keyboard
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="list_positions"),
                InlineKeyboardButton("🔙 Back", callback_data="refresh_dashboard")
            ]
        ])
        
        await query.edit_message_text(
            position_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error listing positions: {e}")
        await query.edit_message_text(
            "❌ Error loading positions. Please try again.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="refresh_dashboard")
            ]])
        )

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle show statistics button"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get stats from bot data
        bot_data = context.bot_data if context.bot_data else {}
        
        # Calculate stats
        total_trades = bot_data.get(STATS_TOTAL_TRADES, 0)
        total_wins = bot_data.get(STATS_TOTAL_WINS, 0)
        total_losses = bot_data.get(STATS_TOTAL_LOSSES, 0)
        total_pnl = bot_data.get(STATS_TOTAL_PNL, 0)
        
        win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        avg_trade = total_pnl / total_trades if total_trades > 0 else 0
        
        # Get approach-specific stats
        conservative_trades = bot_data.get('stats_conservative_trades', 0)
        fast_trades = bot_data.get('stats_fast_trades', 0)
        
        # Build statistics text
        stats_text = f"""📊 <b>Trading Statistics</b>

<b>Overall Performance</b>
├ Total Trades: {total_trades}
├ Win Rate: {win_rate:.1f}% ({total_wins}W / {total_losses}L)
├ Total P&L: ${format_number(total_pnl)}
└ Avg per Trade: ${format_number(avg_trade)}

<b>Trading Approaches</b>
├ Fast Market: {fast_trades} trades
└ Conservative: {conservative_trades} trades

<b>Recent Performance</b>
├ Last 24h: ${format_number(bot_data.get('pnl_24h', 0))}
├ Last 7d: ${format_number(bot_data.get('pnl_7d', 0))}
└ Last 30d: ${format_number(bot_data.get('pnl_30d', 0))}

<b>Best/Worst</b>
├ Best Trade: ${format_number(bot_data.get('stats_best_trade', 0))}
├ Worst Trade: ${format_number(bot_data.get('stats_worst_trade', 0))}
├ Win Streak: {bot_data.get('stats_win_streak', 0)}
└ Loss Streak: {bot_data.get('stats_loss_streak', 0)}"""
        
        # Show statistics with menu
        keyboard = build_stats_keyboard()
        
        await query.edit_message_text(
            stats_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error showing statistics: {e}")
        await query.edit_message_text(
            "❌ Error loading statistics. Please try again.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="refresh_dashboard")
            ]])
        )

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle show settings button"""
    query = update.callback_query
    await query.answer()
    
    try:
        settings_text = """⚙️ <b>Bot Settings</b>

<b>Trading Defaults</b>
├ Default Leverage: 10x
├ Default Risk: 2%
├ Auto TP: Enabled ✅
└ Auto SL: Enabled ✅

<b>Display Settings</b>
├ Decimal Places: 2
├ Show Leverage: No
└ Compact Mode: Yes

<b>API Configuration</b>
├ Exchange: Bybit
├ Network: Mainnet
└ Rate Limit: 5 req/sec

Select a category to configure:"""
        
        keyboard = build_settings_keyboard()
        
        await query.edit_message_text(
            settings_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error showing settings: {e}")
        await query.edit_message_text(
            "❌ Error loading settings. Please try again.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="refresh_dashboard")
            ]])
        )

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle show help button"""
    query = update.callback_query
    await query.answer()
    
    try:
        help_text = """❓ <b>Bot Help & Guide</b>

<b>Quick Start</b>
1. Use /trade to open a new position
2. Choose Fast or Conservative approach
3. Set your parameters
4. Confirm and execute

<b>Trading Approaches</b>
• <b>Fast Market</b>: Single entry, quick execution
• <b>Conservative</b>: Multiple entries, gradual scaling

<b>Key Commands</b>
• /start or /dashboard - Main dashboard
• /trade - Start new trade
• /help - This help menu

<b>Features</b>
• Real-time position monitoring
• Automatic TP/SL management
• P&L tracking and statistics
• Risk management tools

Select a topic for more details:"""
        
        keyboard = build_help_keyboard()
        
        await query.edit_message_text(
            help_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error showing help: {e}")
        await query.edit_message_text(
            "❌ Error loading help. Please try again.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="refresh_dashboard")
            ]])
        )