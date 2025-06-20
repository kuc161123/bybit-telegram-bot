#!/usr/bin/env python3
"""
Enhanced mobile-specific command and callback handlers for optimal UX.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from decimal import Decimal
from utils.formatters import get_emoji, format_decimal_or_na
from dashboard.mobile_layouts import (
    build_mobile_optimized_quick_trade_keyboard, 
    build_mobile_help_keyboard,
    build_mobile_dashboard_primary_keyboard,
    build_mobile_voice_keyboard,
    build_mobile_position_management_keyboard,
    build_mobile_ai_insights_keyboard,
    build_mobile_trade_confirmation_keyboard
)
from shared import send_long_message

logger = logging.getLogger(__name__)

async def fetch_mobile_optimized_trades_status() -> str:
    """Mobile-optimized trade status with compact display"""
    from utils.cache import executor
    from clients.bybit_client import bybit_client
    
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        positions_response = await loop.run_in_executor(
            executor, 
            lambda: bybit_client.get_positions(category="linear", settleCoin="USDT", limit=10)
        )
        
        if positions_response.get("retCode") == 0:
            all_positions = positions_response.get("result", {}).get("list", [])
            active_positions = [p for p in all_positions if Decimal(str(p.get("size", "0"))) > 0]
            
            if not active_positions:
                return "📱 <b>Portfolio</b>\n\n🟡 No active positions\n💰 Ready to trade!"
            
            # Mobile-optimized header
            status_lines = [f"📱 <b>Portfolio ({len(active_positions)} active)</b>\n"]
            
            total_pnl = Decimal("0")
            
            # Show max 3 positions for mobile, with compact format
            for i, pos in enumerate(active_positions[:3]):
                symbol = pos.get("symbol", "Unknown")
                side = pos.get("side", "Unknown")
                unrealized = Decimal(str(pos.get("unrealisedPnl", "0")))
                size = Decimal(str(pos.get("size", "0")))
                entry_price = Decimal(str(pos.get("avgPrice", "0")))
                mark_price = Decimal(str(pos.get("markPrice", "0")))
                total_pnl += unrealized
                
                # Calculate percentage change
                if entry_price > 0:
                    if side == "Buy":
                        pct_change = ((mark_price - entry_price) / entry_price) * 100
                    else:
                        pct_change = ((entry_price - mark_price) / entry_price) * 100
                else:
                    pct_change = 0
                
                side_emoji = "📈" if side == "Buy" else "📉"
                pnl_emoji = "🟢" if unrealized > 0 else "🔴" if unrealized < 0 else "🟡"
                
                # Ultra-compact mobile format
                status_lines.append(
                    f"{side_emoji} <b>{symbol}</b> • {pnl_emoji} {unrealized:.2f} USDT ({pct_change:+.1f}%)"
                )
            
            # Show summary if more positions exist
            if len(active_positions) > 3:
                status_lines.append(f"... +{len(active_positions) - 3} more positions")
            
            # Mobile-optimized total
            total_emoji = "📈" if total_pnl > 0 else "📉" if total_pnl < 0 else "➡️"
            status_lines.append(f"\n{total_emoji} <b>Total P&L: {total_pnl:.2f} USDT</b>")
            
            return "\n".join(status_lines)
        else:
            return "📱 <b>Portfolio Status</b>\n\n❌ Could not fetch positions"
    except Exception as e:
        return f"📱 <b>Portfolio Status</b>\n\n❌ Error: {str(e)[:40]}..."

async def mobile_dashboard_command(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Mobile-optimized dashboard command"""
    
    # Import dashboard function
    from handlers.commands import _send_or_edit_dashboard_message
    await _send_or_edit_dashboard_message(upd, ctx, new_msg=True)

async def mobile_quick_actions_command(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Enhanced mobile quick actions with better UX"""
    
    # Get current portfolio status for context
    portfolio_status = await fetch_mobile_optimized_trades_status()
    
    quick_message = f"""
⚡ <b>QUICK TRADING</b> 
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{portfolio_status}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🚀 One-Tap Trading:</b>
• ⚡ Pre-configured 10x leverage
• 📊 Popular crypto pairs
• 🎯 Instant execution

<b>📱 Mobile-Optimized:</b>
• 👆 Large touch targets
• 📐 Thumb-friendly layout
• ⚡ Ultra-fast execution

<i>Tap any option below to trade instantly!</i>
"""
    
    await ctx.bot.send_message(
        chat_id=upd.effective_chat.id,
        text=quick_message,
        reply_markup=build_mobile_optimized_quick_trade_keyboard(),
        parse_mode=ParseMode.HTML
    )

async def mobile_portfolio_command(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Enhanced mobile portfolio with detailed insights"""
    
    # Get detailed mobile-optimized status
    status_text = await fetch_mobile_optimized_trades_status()
    
    portfolio_message = f"""
{status_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📊 Portfolio Actions:</b>
• 📈 Real-time P&L tracking
• 🎯 Position management
• 📊 Performance analytics  
• 🔔 Price alerts & monitoring

<b>⚡ Quick Access:</b>
• 🎤 Voice commands
• ⚡ One-tap trading
• 📱 Mobile-optimized controls

<i>Optimized for iPhone 16 Pro Max experience</i>
"""
    
    await send_long_message(
        ctx.bot, 
        upd.effective_chat.id, 
        portfolio_message, 
        parse_mode=ParseMode.HTML,
        reply_markup=build_mobile_position_management_keyboard()
    )

async def mobile_help_command(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Enhanced mobile help with comprehensive guidance"""
    
    help_message = f"""
📱 <b>MOBILE TRADING GUIDE</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🚀 Quick Commands:</b>
/quick - Lightning-fast trading menu
/portfolio - Position overview & management
/dashboard - Complete control panel
/voice - Natural speech trading

<b>📱 Mobile Features:</b>
• 👆 Large, touch-friendly buttons
• 🤲 One-handed operation support
• ⚡ Swipe-friendly interfaces
• 📊 Instant visual feedback

<b>⚡ Speed Features:</b>
• 🧠 AI-powered trade insights
• 🎤 Voice command trading
• ⚡ One-tap position management
• 📈 Real-time P&L tracking
• 🔔 Smart notifications

<b>🎯 iPhone 16 Pro Max Optimized:</b>
• 📐 Perfect 6.7" screen layout
• 👍 Optimized thumb-reach zones
• 🌙 Portrait mode prioritized
• 🎨 High-contrast visual elements
• ⚡ 120Hz ProMotion compatibility

<b>🎤 Voice Trading Examples:</b>
• <i>"Bitcoin long 65000, TP 67000, stop 62000"</i>
• <i>"ETH short 3500, profit 3400, stop 3600"</i>
• <i>"Close all positions"</i>
• <i>"Check my portfolio"</i>

<b>💡 Pro Tips:</b>
• Use landscape for detailed analysis
• Voice commands work in any language
• Hold dashboard for quick refresh
• Swipe for navigation shortcuts

<i>Select a topic below for detailed help:</i>
"""
    
    await ctx.bot.send_message(
        chat_id=upd.effective_chat.id,
        text=help_message,
        reply_markup=build_mobile_help_keyboard(),
        parse_mode=ParseMode.HTML
    )

async def mobile_voice_help_command(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Mobile-optimized voice trading help"""
    
    voice_help_message = f"""
🎤 <b>VOICE TRADING GUIDE</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🌟 Universal Symbol Support:</b>
• 500+ Bybit symbols supported
• Natural language recognition
• Auto-complete symbol matching

<b>📱 Mobile Voice Features:</b>
• 🎙️ Tap-to-record interface
• 📝 Text input alternative
• ⚡ Instant voice parsing
• 🔄 Real-time feedback

<b>💬 Voice Command Examples:</b>

<b>Complete Setup:</b>
<i>"Bitcoin long entry 65000, limit 1 at 64800, TP1 67000, TP2 68000, stop 62000, 20x leverage"</i>

<b>Quick Setup:</b>
<i>"ETH short 3500, profit 3400, stop 3600"</i>

<b>Minimal Setup:</b>
<i>"SOL long 150, TP 155, stop 145"</i>

<b>Position Management:</b>
<i>"Close Bitcoin position"</i>
<i>"Move stop loss to breakeven"</i>

<b>🎯 Supported Phrases:</b>
• Entry: "entry", "enter at", "buy at"
• Take Profit: "TP", "profit", "target"
• Stop Loss: "SL", "stop", "stop loss"
• Leverage: "10x", "leverage 20", "times"
• Direction: "long", "short", "buy", "sell"

<b>💡 Pro Tips:</b>
• Speak clearly and naturally
• Include all key levels in one command
• Use common crypto names
• Add leverage and margin preferences

<i>Ready to try voice trading? Tap below!</i>
"""
    
    await ctx.bot.send_message(
        chat_id=upd.effective_chat.id,
        text=voice_help_message,
        reply_markup=build_mobile_voice_keyboard(),
        parse_mode=ParseMode.HTML
    )

async def mobile_ai_insights_command(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Mobile-optimized AI insights display"""
    
    ai_insights_message = f"""
🧠 <b>AI TRADING INSIGHTS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📊 Real-Time Analysis:</b>
• 🎯 Market regime detection
• 📈 Sentiment analysis
• 💡 Portfolio health scoring
• 🎲 Risk assessment

<b>🤖 AI-Powered Features:</b>
• 📊 Smart position sizing
• 🎯 Entry/exit recommendations
• 🛡️ Risk management alerts
• 📈 Performance optimization

<b>📱 Mobile AI Tools:</b>
• 🔄 Instant analysis refresh
• 📊 Visual risk meters
• 🎯 One-tap recommendations
• 📈 Real-time market updates

<b>💡 Current Market Insights:</b>
• Loading real-time analysis...
• Processing market data...
• Calculating optimal strategies...

<b>🎯 Available Actions:</b>
• Get trade recommendations
• Analyze current positions
• Check market sentiment
• Optimize portfolio health

<i>AI analysis updates every 30 seconds</i>
"""
    
    await ctx.bot.send_message(
        chat_id=upd.effective_chat.id,
        text=ai_insights_message,
        reply_markup=build_mobile_ai_insights_keyboard(),
        parse_mode=ParseMode.HTML
    )

async def handle_mobile_quick_trade_callback(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Enhanced mobile quick trade callback with better UX"""
    query = upd.callback_query
    await query.answer("⚡ Setting up quick trade...")
    
    try:
        # Parse callback data: quick_trade:side:symbol:leverage
        parts = query.data.split(":")
        if len(parts) >= 4:
            _, action, side, symbol, leverage = parts[:5]
            
            if action == "trade":
                side_emoji = "📈" if side == "long" else "📉"
                side_text = "LONG" if side == "long" else "SHORT"
                
                # Mobile-optimized quick setup message
                quick_setup_message = f"""
⚡ <b>QUICK TRADE SETUP</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{side_emoji} <b>{side_text} {symbol}</b>
🚀 <b>Leverage:</b> {leverage}x (Pre-configured)
💰 <b>Margin:</b> Will be set in next step

<b>⚡ Quick Setup Benefits:</b>
• 🎯 Instant position opening
• 📊 Smart default settings
• 🛡️ Auto risk management
• 📱 Mobile-optimized flow

<b>📝 Next Steps:</b>
1️⃣ Set your margin amount
2️⃣ Configure entry & targets
3️⃣ Execute instantly

<b>💡 Alternative Options:</b>
• Use voice for complete setup
• Switch to manual for full control
• Return to dashboard for overview

<i>Choose your next action below:</i>
"""
                
                # Mobile-optimized next steps keyboard
                next_steps_keyboard = build_mobile_trade_confirmation_keyboard()
                
                await query.edit_message_text(
                    text=quick_setup_message,
                    parse_mode=ParseMode.HTML,
                    reply_markup=next_steps_keyboard
                )
        
    except Exception as e:
        logger.error(f"Error in mobile quick trade callback: {e}")
        await query.edit_message_text(
            text=f"{get_emoji('error')} Error setting up quick trade.\n\n"
                 f"<b>Alternative Options:</b>\n"
                 f"• 🎤 Try voice trading\n"
                 f"• 📝 Use manual setup\n"
                 f"• 🏠 Return to dashboard\n\n"
                 f"<i>Tap an option below to continue</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=build_mobile_dashboard_primary_keyboard()
        )

async def handle_mobile_dashboard_refresh(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Enhanced mobile dashboard refresh with loading states"""
    query = upd.callback_query
    await query.answer("🔄 Refreshing dashboard...")
    
    try:
        # Show loading state first for better UX
        loading_message = f"""
⏳ <b>REFRESHING DASHBOARD</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Loading portfolio data...
🎯 Fetching position updates...  
🧠 Refreshing AI insights...
💰 Updating balance info...

<i>This will take just a moment...</i>
"""
        
        await query.edit_message_text(
            text=loading_message,
            parse_mode=ParseMode.HTML
        )
        
        # Import and call enhanced dashboard function
        from handlers.commands import _send_or_edit_dashboard_message
        await _send_or_edit_dashboard_message(query.message.chat.id, ctx, new_msg=True)
        
        # Delete the loading message
        try:
            await query.message.delete()
        except:
            pass
            
    except Exception as e:
        logger.error(f"Error in mobile dashboard refresh: {e}")
        await query.edit_message_text(
            text=f"{get_emoji('error')} Error refreshing dashboard.\n\n"
                 f"<b>What you can do:</b>\n"
                 f"• 🔄 Try refresh again\n"
                 f"• 🎤 Use voice commands\n"
                 f"• 📝 Start manual trade\n\n"
                 f"<i>Tap an option below</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=build_mobile_error_recovery_keyboard()
        )

async def handle_mobile_position_management(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Enhanced mobile position management interface"""
    query = upd.callback_query
    await query.answer("📊 Loading positions...")
    
    try:
        # Get current positions
        position_status = await fetch_mobile_optimized_trades_status()
        
        position_management_message = f"""
📊 <b>POSITION MANAGEMENT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{position_status}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>⚡ Quick Actions:</b>
• 🎯 Modify TP/SL levels
• 📏 Adjust position sizes
• ❌ Close positions partially/fully
• ➕ Add to existing positions

<b>📱 Mobile Features:</b>
• 👆 One-tap modifications
• 📊 Real-time P&L updates
• 🔔 Instant notifications
• 🛡️ Risk management tools

<b>🧠 AI Assistance:</b>
• Smart position analysis
• Optimal exit recommendations
• Risk assessment scoring
• Market timing insights

<i>Select an action below to manage your positions</i>
"""
        
        await query.edit_message_text(
            text=position_management_message,
            parse_mode=ParseMode.HTML,
            reply_markup=build_mobile_position_management_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error in mobile position management: {e}")
        await query.edit_message_text(
            text=f"{get_emoji('error')} Error loading positions.\n\n"
                 f"<b>Try these alternatives:</b>\n"
                 f"• 🔄 Refresh and try again\n"
                 f"• 📊 Check dashboard\n"
                 f"• 🎤 Use voice commands\n\n"
                 f"<i>Tap an option below</i>",
            parse_mode=ParseMode.HTML
        )

async def handle_back_to_dashboard(upd: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Enhanced back to dashboard with smooth transition"""
    query = upd.callback_query
    await query.answer("🏠 Returning to dashboard...")
    
    try:
        # Import and call dashboard function with smooth transition
        from handlers.commands import _send_or_edit_dashboard_message
        await _send_or_edit_dashboard_message(query.message.chat.id, ctx, new_msg=True)
        
        # Delete the current message for clean transition
        try:
            await query.message.delete()
        except:
            pass
            
    except Exception as e:
        logger.error(f"Error returning to dashboard: {e}")
        # Fallback - just show error message with dashboard option
        await query.edit_message_text(
            text=f"{get_emoji('error')} Unable to load dashboard.\n\n"
                 f"Please try using /dashboard command directly.",
            parse_mode=ParseMode.HTML
        )

def build_mobile_error_recovery_keyboard():
    """Mobile-optimized error recovery keyboard"""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Try Again", callback_data="retry_last_action")],
        [
            InlineKeyboardButton("🎤 Voice Trade", callback_data="voice_command"),
            InlineKeyboardButton("📝 Manual Trade", callback_data="start_conversation")
        ],
        [
            InlineKeyboardButton("📊 Check Positions", callback_data="view_positions"),
            InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
        ]
    ])

# Export mobile-optimized functions
__all__ = [
    'fetch_mobile_optimized_trades_status',
    'mobile_dashboard_command',
    'mobile_quick_actions_command', 
    'mobile_portfolio_command',
    'mobile_help_command',
    'mobile_voice_help_command',
    'mobile_ai_insights_command',
    'handle_mobile_quick_trade_callback',
    'handle_mobile_dashboard_refresh',
    'handle_mobile_position_management',
    'handle_back_to_dashboard'
]