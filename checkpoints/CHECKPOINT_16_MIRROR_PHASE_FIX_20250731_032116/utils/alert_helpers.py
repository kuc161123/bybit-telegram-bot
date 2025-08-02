#!/usr/bin/env python3
"""
Trade execution alert helpers for sending notifications
"""
import logging
import inspect
import asyncio
from typing import Optional, Dict, Any, List
from decimal import Decimal
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from config.constants import *
from config.settings import ENHANCED_TP_SL_ALERTS_ONLY, ALERT_SETTINGS
from utils.formatters import format_price, format_decimal_or_na, get_emoji

logger = logging.getLogger(__name__)

# Global reference to application (set by main.py)
_application = None

def set_application(app):
    """Set the global application reference for alert system"""
    global _application
    _application = app

# Simple alert function for enhanced TP/SL system
async def send_simple_alert(chat_id: int, message: str, alert_type: str = None) -> bool:
    """
    Simple alert sender for enhanced TP/SL system
    This function is allowed to send alerts regardless of settings
    """
    try:
        global _application
        if not _application:
            logger.error("❌ Application not set for alert system")
            # Try to get application from main module as fallback
            try:
                import main
                if hasattr(main, '_global_app') and main._global_app:
                    _application = main._global_app
                    logger.info("✅ Retrieved application reference from main module")
                else:
                    logger.error("❌ Could not retrieve application reference from main module")
                    return False
            except Exception as e:
                logger.error(f"❌ Failed to import application from main: {e}")
                return False

        # Enhanced retry logic for timeout errors
        max_retries = 5  # Increased from 3
        retry_delay = 3  # Increased from 2 seconds
        timeout_settings = {
            'read_timeout': 20,  # Increased from 10
            'write_timeout': 20,  # Increased from 10
            'connect_timeout': 20,  # Increased from 10
            'pool_timeout': 20  # Increased from 10
        }

        for attempt in range(max_retries):
            try:
                # Log alert details before sending
                logger.info(f"📤 Sending {alert_type or 'general'} alert to chat_id: {chat_id}")
                logger.debug(f"Alert preview: {message[:100]}..." if len(message) > 100 else f"Alert: {message}")
                
                await asyncio.wait_for(
                    _application.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode=ParseMode.HTML,
                        **timeout_settings
                    ),
                    timeout=30  # Overall timeout wrapper
                )

                logger.info(f"✅ Enhanced TP/SL alert sent: {alert_type or 'general'} to chat_id: {chat_id}")
                return True

            except (TelegramError, asyncio.TimeoutError) as e:
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    backoff_time = retry_delay * (2 ** attempt) + (0.1 * attempt)
                    logger.warning(f"⏱️ Telegram timeout on attempt {attempt + 1}/{max_retries}, retrying in {backoff_time:.1f}s...")
                    await asyncio.sleep(backoff_time)
                    continue
                else:
                    logger.error(f"Telegram error sending enhanced TP/SL alert after {max_retries} attempts: {e}")
                    return False

        return False

    except Exception as e:
        logger.error(f"Error sending enhanced TP/SL alert: {e}")
        return False

async def send_trade_alert(bot: Bot, chat_id: int, alert_type: str,
                          symbol: str, side: str, approach: str,
                          pnl: Decimal, entry_price: Decimal,
                          current_price: Decimal, position_size: Decimal,
                          cancelled_orders: List[str] = None,
                          additional_info: Dict[str, Any] = None) -> bool:
    """
    Send trade execution alert to user

    Args:
        bot: Telegram bot instance
        chat_id: Chat ID to send alert to
        alert_type: Type of alert (tp_hit, sl_hit, limit_filled, etc.)
        symbol: Trading symbol
        side: Buy or Sell
        approach: fast or conservative
        pnl: Profit/Loss amount
        entry_price: Entry price
        current_price: Current/exit price
        position_size: Position size
        cancelled_orders: List of cancelled order descriptions
        additional_info: Additional information for the alert

    Returns:
        bool: True if alert sent successfully
    """
    try:
        # Check if alerts are enabled
        if ENHANCED_TP_SL_ALERTS_ONLY:
            # Only allow alerts from enhanced TP/SL system
            caller_module = inspect.getmodule(inspect.stack()[1][0])
            if caller_module:
                module_name = caller_module.__name__
                # Only allow alerts from enhanced_tp_sl_manager or mirror_enhanced_tp_sl
                if 'enhanced_tp_sl' not in module_name:
                    logger.debug(f"Alert from {module_name} blocked - only enhanced TP/SL alerts enabled")
                    return False
        else:
            # Check individual alert settings
            component = _get_component_from_caller()
            if not ALERT_SETTINGS.get(component, False):
                logger.debug(f"Alert from {component} blocked by settings")
                return False
        # Calculate P&L percentage
        if entry_price > 0:
            if side == "Buy":
                pnl_percent = ((current_price - entry_price) / entry_price) * 100
            else:  # Sell
                pnl_percent = ((entry_price - current_price) / entry_price) * 100
        else:
            pnl_percent = Decimal("0")

        # Format message based on alert type
        if alert_type == "tp_hit":
            message = format_tp_hit_alert(
                symbol, side, approach, pnl, pnl_percent,
                entry_price, current_price, position_size,
                cancelled_orders, additional_info
            )
        elif alert_type == "sl_hit":
            message = format_sl_hit_alert(
                symbol, side, approach, pnl, pnl_percent,
                entry_price, current_price, position_size,
                cancelled_orders, additional_info
            )
        elif alert_type == "limit_filled":
            message = format_limit_filled_alert(
                symbol, side, approach, additional_info
            )
        elif alert_type == "tp1_early_hit":
            message = format_tp1_early_hit_alert(
                symbol, side, approach, cancelled_orders, additional_info
            )
        elif alert_type == "tp1_with_fills":
            message = format_tp1_with_fills_alert(
                symbol, side, approach, cancelled_orders, additional_info
            )
        elif alert_type == "conservative_rebalance":
            message = format_conservative_rebalance_alert(
                symbol, side, position_size, additional_info
            )
        else:
            logger.warning(f"Unknown alert type: {alert_type}")
            return False

        # Send alert with retry logic
        max_retries = 5
        for attempt in range(max_retries):
            try:
                await asyncio.wait_for(
                    bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode=ParseMode.HTML,
                        read_timeout=20,
                        write_timeout=20,
                        connect_timeout=20,
                        pool_timeout=20
                    ),
                    timeout=30
                )
                break
            except (TelegramError, asyncio.TimeoutError) as e:
                if attempt < max_retries - 1:
                    backoff_time = 3 * (2 ** attempt) + (0.1 * attempt)
                    logger.warning(f"Telegram timeout sending {alert_type} alert, retry {attempt + 1}/{max_retries} in {backoff_time:.1f}s")
                    await asyncio.sleep(backoff_time)
                else:
                    logger.error(f"Failed to send {alert_type} alert after {max_retries} attempts: {e}")
                    return False

        logger.info(f"✅ Trade alert sent: {alert_type} for {symbol}")
        return True

    except TelegramError as e:
        logger.error(f"Telegram error sending trade alert: {e}")
        return False
    except Exception as e:
        logger.error(f"Error sending trade alert: {e}")
        return False

def format_tp_hit_alert(symbol: str, side: str, approach: str,
                       pnl: Decimal, pnl_percent: Decimal,
                       entry_price: Decimal, exit_price: Decimal,
                       position_size: Decimal, cancelled_orders: List[str],
                       additional_info: Dict[str, Any]) -> str:
    """Format take profit hit alert message with enhanced information and 2025 best practices"""
    
    # Determine which TP was hit for conservative/ggshot
    tp_number = additional_info.get("tp_number", 1) if approach in ["conservative", "ggshot"] else ""
    tp_text = f"TP{tp_number}" if tp_number else "TP"
    
    # Get additional context
    account_type = additional_info.get("account_type", "main").upper()
    filled_qty = additional_info.get("filled_qty", position_size)
    remaining_size = additional_info.get("remaining_size", Decimal("0"))
    detection_method = additional_info.get("detection_method", "position_size")
    fill_confidence = additional_info.get("fill_confidence", "High")
    
    # Enhanced 2025 emojis and formatting
    account_emoji = "🏦" if account_type == "MAIN" else "🪞"
    side_emoji = "📈" if side == "Buy" else "📉"
    approach_emoji = {"conservative": "🛡️", "ggshot": "📸", "fast": "⚡"}.get(approach.lower(), "🎯")
    profit_emoji = "💰" if pnl >= 0 else "📉"
    
    message = f"""{profit_emoji} <b>{tp_text} HIT - PROFIT TAKEN!</b>
━━━━━━━━━━━━━━━━━━━━━━
<b>📊 Trade Details:</b>
• Symbol: {symbol} {side_emoji} {side}
• Approach: {approach_emoji} {approach.capitalize()}
• Account: {account_emoji} {account_type}

<b>{profit_emoji} Profit: ${pnl:,.2f} ({pnl_percent:+.2f}%)</b>
• Entry: ${format_price(entry_price)}
• Exit: ${format_price(exit_price)}
• Filled: {format_decimal_or_na(filled_qty)}
• Remaining: {format_decimal_or_na(remaining_size)}

<b>🔍 Detection Details:</b>
• Method: {detection_method.replace('_', ' ').title()}
• Confidence: {fill_confidence} ✅
• Check Interval: 2s (Enhanced) ⚡"""

    if cancelled_orders:
        message += f"\n\n<b>❌ Cancelled Orders:</b>\n"
        for order in cancelled_orders[:5]:  # Limit to 5 orders
            message += f"   • {order}\n"
        if len(cancelled_orders) > 5:
            message += f"   • ... and {len(cancelled_orders) - 5} more\n"

    if approach in ["conservative", "ggshot"] and additional_info:
        remaining_tps = additional_info.get("remaining_tps", [])
        if remaining_tps:
            message += f"\n\n<b>🎯 Active TPs:</b> {', '.join(remaining_tps)}"

        # Enhanced breakeven information for TP1
        if tp_number == 1:
            sl_moved = additional_info.get("sl_moved_to_be", False)
            breakeven_price = additional_info.get("breakeven_price")
            
            if sl_moved and breakeven_price:
                message += f"\n\n<b>🛡️ STOP LOSS MOVED TO BREAKEVEN</b>"
                message += f"\n• Breakeven Price: ${format_price(breakeven_price)} 🎯"
                message += f"\n• Protection: 100% of remaining position 🔒"
                message += f"\n• Includes: 0.06% fees + 0.02% safety margin 📊"
                message += f"\n• Status: Position now risk-free! ✅"
                
                # Add limit order cancellation info if applicable
                limits_cancelled = additional_info.get("limits_cancelled", False)
                if limits_cancelled:
                    message += f"\n• Limit Orders: Cancelled (TP1 hit) ❌"
            else:
                # Enhanced pending breakeven info
                message += f"\n\n<b>⏳ PENDING ACTIONS:</b>"
                message += f"\n• SL will move to breakeven 🛡️"
                message += f"\n• Target: Entry + 0.08% (fees + margin) 🎯"
                message += f"\n• Coverage: Will protect remaining position 🔒"
                if approach == "conservative":
                    message += f"\n• Limit orders will be cancelled ❌"

    # Add system status
    message += f"\n\n<b>⚙️ System Status:</b>"
    message += f"\n• Enhanced TP/SL: Active ✅"
    message += f"\n• Direct Order Checks: Enabled 🔍"
    message += f"\n• SL Auto-Adjustment: Active 🔄"
    
    # Add mirror sync status if applicable
    if account_type == "MIRROR" or additional_info.get("has_mirror"):
        mirror_synced = additional_info.get("mirror_synced", True)
        message += f"\n• Mirror Sync: {'Completed ✅' if mirror_synced else 'Pending ⏳'}"

    return message.strip()

def format_sl_hit_alert(symbol: str, side: str, approach: str,
                       pnl: Decimal, pnl_percent: Decimal,
                       entry_price: Decimal, exit_price: Decimal,
                       position_size: Decimal, cancelled_orders: List[str],
                       additional_info: Dict[str, Any]) -> str:
    """Format stop loss hit alert message with enhanced information and 2025 best practices"""
    
    # Enhanced 2025 emojis and formatting
    account_type = additional_info.get("account_type", "main").upper()
    account_emoji = "🏦" if account_type == "MAIN" else "🪞"
    side_emoji = "📈" if side == "Buy" else "📉"
    approach_emoji = {"conservative": "🛡️", "ggshot": "📸", "fast": "⚡"}.get(approach.lower(), "🎯")
    
    detection_method = additional_info.get("detection_method", "position_size")
    fill_confidence = additional_info.get("fill_confidence", "High")
    position_duration = additional_info.get("position_duration_minutes")
    realized_pnl = additional_info.get("realized_pnl", pnl)
    
    message = f"""🛡️ <b>STOP LOSS HIT - POSITION CLOSED</b>
━━━━━━━━━━━━━━━━━━━━━━
<b>📊 Trade Details:</b>
• Symbol: {symbol} {side_emoji} {side}
• Approach: {approach_emoji} {approach.capitalize()}
• Account: {account_emoji} {account_type}

<b>📉 Loss: ${pnl:,.2f} ({pnl_percent:.2f}%)</b>
• Entry: ${format_price(entry_price)}
• Exit: ${format_price(exit_price)}
• Size: {format_decimal_or_na(position_size)}"""

    if position_duration:
        if position_duration < 60:
            duration_text = f"{position_duration} minutes ⏱️"
        else:
            hours = position_duration // 60
            mins = position_duration % 60
            duration_text = f"{hours}h {mins}m ⏱️"
        message += f"\n• Duration: {duration_text}"

    message += f"""

<b>🔍 Detection Details:</b>
• Method: {detection_method.replace('_', ' ').title()}
• Confidence: {fill_confidence} ✅
• Check Interval: 2s (Enhanced) ⚡"""

    if cancelled_orders:
        message += f"\n\n<b>❌ Cancelled Orders:</b>\n"
        for order in cancelled_orders[:5]:
            message += f"   • {order}\n"
        if len(cancelled_orders) > 5:
            message += f"   • ... and {len(cancelled_orders) - 5} more"

    # Add risk management insights
    message += f"""

<b>🛡️ Risk Management:</b>
• Position Risk: {abs(pnl_percent):.2f}% of position 📊
• Account Impact: {abs(float(pnl) / 10000 * 100):.2f}% (est.) 💼
• Risk Control: ✅ Working as designed 🎯"""

    # Add system status
    message += f"""

<b>⚙️ System Status:</b>
• Enhanced TP/SL: Active ✅
• Direct Order Checks: Enabled 🔍
• Risk Monitoring: Functional 📈

<b>📋 Next Steps:</b>
• Review market conditions 📊
• Check trading approach settings ⚙️
• Consider position sizing 📏"""

    # Add mirror sync status if applicable
    if account_type == "MIRROR" or additional_info.get("has_mirror"):
        mirror_synced = additional_info.get("mirror_synced", True)
        message += f"\n• Mirror Sync: {'Completed ✅' if mirror_synced else 'Pending ⏳'}"

    return message.strip()

def format_limit_filled_alert(symbol: str, side: str, approach: str,
                            additional_info: Dict[str, Any]) -> str:
    """Format limit order filled alert message with enhanced information and 2025 best practices"""
    
    # Enhanced 2025 emojis and formatting
    account_type = additional_info.get("account_type", "main").upper()
    account_emoji = "🏦" if account_type == "MAIN" else "🪞"
    side_emoji = "📈" if side == "Buy" else "📉"
    fill_price = additional_info.get("fill_price", Decimal("0"))
    fill_size = additional_info.get("fill_size", Decimal("0"))
    limit_number = additional_info.get("limit_number", 1)
    total_limits = additional_info.get("total_limits", 3)
    detection_method = additional_info.get("detection_method", "position_size")
    fill_confidence = additional_info.get("fill_confidence", "High")
    fill_timestamp = additional_info.get("fill_timestamp")
    position_size = additional_info.get("position_size", Decimal("0"))
    avg_entry = additional_info.get("avg_entry", fill_price)

    # Format approach text and emoji
    approach_emoji = {"conservative": "🛡️", "ggshot": "📸", "fast": "⚡"}.get(approach.lower(), "🎯")
    approach_text = approach.capitalize()

    message = f"""📦 <b>LIMIT ORDER FILLED</b>
━━━━━━━━━━━━━━━━━━━━━━
<b>📊 Trade Details:</b>
• Symbol: {symbol} {side_emoji} {side}
• Approach: {approach_emoji} {approach_text}
• Account: {account_emoji} {account_type}

<b>✅ Fill Information:</b>
• Limit {limit_number}/{total_limits} Filled 📦
• Price: ${format_price(fill_price)} 💰
• Size: {format_decimal_or_na(fill_size)} 📊"""

    if fill_timestamp:
        from datetime import datetime
        fill_time = datetime.fromtimestamp(fill_timestamp / 1000)
        message += f"\n• Time: {fill_time.strftime('%H:%M:%S')} ⏱️"

    filled_count = additional_info.get("filled_count", 1)
    if filled_count > 1:
        message += f"\n• Total Filled: {filled_count}/{total_limits} 📈"
        message += f"\n• Avg Entry: ${format_price(avg_entry)} 📊"

    message += f"""

<b>📊 Position Status:</b>
• Current Size: {format_decimal_or_na(position_size)} 📦
• Remaining Limits: {total_limits - filled_count} ⏳"""

    # Add detection details
    message += f"""

<b>🔍 Detection Details:</b>
• Method: {detection_method.replace('_', ' ').title()}
• Confidence: {fill_confidence} ✅
• Check Interval: 2s (Enhanced) ⚡"""

    # Add rebalancing note for conservative approach
    if approach == "conservative":
        message += """

<b>🔄 Next Actions:</b>
• Position will be automatically rebalanced 🎯
• TP/SL quantities adjusted to maintain 85/5/5/5 📊
• SL will cover full position size 🛡️"""

    # Add system status
    message += f"""

<b>⚙️ System Status:</b>
• Enhanced TP/SL: Active ✅
• Direct Order Checks: Enabled 🔍
• Auto-Rebalancing: {'Active ✅' if approach == 'conservative' else 'N/A ❌'}"""

    # Add mirror sync status if applicable
    if account_type == "MIRROR" or additional_info.get("has_mirror"):
        mirror_synced = additional_info.get("mirror_synced", True)
        message += f"\n• Mirror Sync: {'Completed ✅' if mirror_synced else 'Pending ⏳'}"

    return message.strip()

def format_tp1_early_hit_alert(symbol: str, side: str, approach: str,
                              cancelled_orders: List[str],
                              additional_info: Dict[str, Any]) -> str:
    """Format TP1 early hit alert (before any limits filled) with 2025 best practices"""
    
    # Enhanced 2025 emojis and formatting
    account_type = additional_info.get("account_type", "main").upper() if additional_info else "MAIN"
    account_emoji = "🏦" if account_type == "MAIN" else "🪞"
    side_emoji = "📈" if side == "Buy" else "📉"
    approach_emoji = {"conservative": "🛡️", "ggshot": "📸", "fast": "⚡"}.get(approach.lower(), "🎯")
    approach_text = approach.capitalize()

    # Removed breakeven functionality
    sl_moved = False
    new_sl_price = additional_info.get("new_sl_price") if additional_info else None

    message = f"""🚨 <b>TP1 HIT EARLY - ALL ORDERS CANCELLED</b>
━━━━━━━━━━━━━━━━━━━━━━
<b>📊 Trade Details:</b>
• Symbol: {symbol} {side_emoji} {side}
• Approach: {approach_emoji} {approach_text}
• Account: {account_emoji} {account_type}

⚠️ <b>TP1 hit before limit orders filled!</b>
📝 All remaining orders have been cancelled ❌
💡 Consider market conditions for next trade 📈
"""

    # Add SL movement info if applicable
    # Removed breakeven functionality

    if cancelled_orders:
        message += f"\n\n❌ <b>Cancelled Orders ({len(cancelled_orders)}):</b>\n"
        for order in cancelled_orders[:5]:
            message += f"   • {order}\n"
        if len(cancelled_orders) > 5:
            message += f"   • ... and {len(cancelled_orders) - 5} more\n"

    # Add SL movement information for conservative/ggshot approaches
    if approach in ["conservative", "ggshot"]:
        message += f"\n\n🔄 <b>STOP LOSS WILL BE MOVED TO BREAKEVEN</b>"
        message += f"\n🛡️ SL will be adjusted to entry + fees 🎯"
        message += f"\n📊 Includes 0.12% fees + safety margin 📈"
        message += f"\n✅ Position will become risk-free! 🔒"

    return message.strip()

def format_tp1_with_fills_alert(symbol: str, side: str, approach: str,
                               cancelled_orders: List[str],
                               additional_info: Dict[str, Any]) -> str:
    """Format TP1 hit with fills alert (after some limits filled) with 2025 best practices"""
    
    # Enhanced 2025 emojis and formatting
    account_type = additional_info.get("account_type", "main").upper() if additional_info else "MAIN"
    account_emoji = "🏦" if account_type == "MAIN" else "🪞"
    side_emoji = "📈" if side == "Buy" else "📉"
    approach_emoji = {"conservative": "🛡️", "ggshot": "📸", "fast": "⚡"}.get(approach.lower(), "🎯")
    approach_text = approach.capitalize()
    filled_count = additional_info.get("filled_count", 0)
    total_limits = additional_info.get("total_limits", 3)
    sl_moved = False  # Removed breakeven functionality
    new_sl_price = additional_info.get("new_sl_price")

    message = f"""🎯 <b>TP1 HIT - REMAINING LIMITS CANCELLED</b>
━━━━━━━━━━━━━━━━━━━━━━
<b>📊 Trade Details:</b>
• Symbol: {symbol} {side_emoji} {side}
• Approach: {approach_emoji} {approach_text}
• Account: {account_emoji} {account_type}

✅ <b>TP1 hit with {filled_count}/{total_limits} limits filled</b>
📝 Unfilled limit orders cancelled ❌
✨ TP2, TP3, TP4 remain active 🎯
"""

    # Add SL movement info if applicable
    # Removed breakeven functionality

    if cancelled_orders:
        message += f"\n\n❌ <b>Cancelled Limits ({len(cancelled_orders)}):</b>\n"
        for order in cancelled_orders[:3]:
            message += f"   • {order}\n"
        if len(cancelled_orders) > 3:
            message += f"   • ... and {len(cancelled_orders) - 3} more\n"

    return message.strip()

async def send_position_closed_summary(chat_id: int,
                                     symbol: str, side: str, approach: str,
                                     entry_price: float, exit_price: float,
                                     position_size: float, pnl: float,
                                     close_reason: str = None, duration_minutes: int = None,
                                     bot: Bot = None, additional_info: Dict[str, Any] = None) -> bool:
    """Send position closed summary alert with enhanced information"""
    try:
        # Check if alerts are enabled
        if ENHANCED_TP_SL_ALERTS_ONLY:
            # Only allow alerts from enhanced TP/SL system
            caller_module = inspect.getmodule(inspect.stack()[1][0])
            if caller_module:
                module_name = caller_module.__name__
                # Only allow alerts from enhanced_tp_sl_manager or mirror_enhanced_tp_sl
                if 'enhanced_tp_sl' not in module_name:
                    logger.debug(f"Position closed alert from {module_name} blocked - only enhanced TP/SL alerts enabled")
                    return False
        else:
            # Check if position closed alerts are enabled
            if not ALERT_SETTINGS.get("position_closed", False):
                logger.debug("Position closed alerts disabled by settings")
                return False
        # Use application bot if not provided
        if not bot:
            global _application
            if not _application:
                logger.error("❌ Application not set for alert system")
                return False
            bot = _application.bot

        # Calculate P&L percentage
        if entry_price > 0:
            if side == "Buy":
                pnl_percent = ((exit_price - entry_price) / entry_price) * 100
            else:  # Sell
                pnl_percent = ((entry_price - exit_price) / entry_price) * 100
        else:
            pnl_percent = 0.0

        # Format duration
        if duration_minutes:
            if duration_minutes < 60:
                duration_text = f"{duration_minutes} minutes"
            else:
                hours = duration_minutes // 60
                mins = duration_minutes % 60
                duration_text = f"{hours}h {mins}m"
        else:
            duration_text = "Unknown"

        # Determine emoji and color
        pnl_emoji = "💰" if pnl >= 0 else "🔴"
        result_text = "PROFIT" if pnl >= 0 else "LOSS"
        
        # Extract additional info with enhanced 2025 formatting
        info = additional_info or {}
        account_type = info.get("account_type", "main").upper()
        account_emoji = "🏦" if account_type == "MAIN" else "🪞"
        side_emoji = "📈" if side == "Buy" else "📉"
        approach_emoji = {"conservative": "🛡️", "ggshot": "📸", "fast": "⚡"}.get(approach.lower(), "🎯")
        total_fees = info.get("total_fees", 0)
        tp_hits = info.get("tp_hits", 0)
        limit_fills = info.get("limit_fills", 0)
        realized_pnl = info.get("realized_pnl", pnl)
        gross_pnl = info.get("gross_pnl", pnl + total_fees if total_fees else pnl)

        message = f"""📊 <b>POSITION CLOSED - {result_text}</b>
━━━━━━━━━━━━━━━━━━━━━━
<b>📊 Trade Summary:</b>
• Symbol: {symbol} {side_emoji} {side}
• Approach: {approach_emoji} {approach.capitalize()}
• Account: {account_emoji} {account_type}

<b>{pnl_emoji} Final P&L: ${pnl:,.2f} ({pnl_percent:+.2f}%)</b>
• Entry: ${format_price(Decimal(str(entry_price)))} 📊
• Exit: ${format_price(Decimal(str(exit_price)))} 🎯
• Size: {format_decimal_or_na(Decimal(str(position_size)))} 📦
• Duration: {duration_text} ⏱️"""

        # Add fees breakdown if available
        if total_fees:
            message += f"""

<b>💰 P&L Breakdown:</b>
• Gross P&L: ${gross_pnl:,.2f} 📈
• Total Fees: -${abs(total_fees):,.2f} 💸
• Net P&L: ${pnl:,.2f} 💰"""

        # Add execution stats
        if tp_hits > 0 or limit_fills > 0:
            message += f"""

<b>📊 Execution Stats:</b>"""
            if tp_hits > 0:
                message += f"\n• Take Profits Hit: {tp_hits} 🎯"
            if limit_fills > 0:
                message += f"\n• Limit Orders Filled: {limit_fills} 📦"

        # Add close reason if provided
        if close_reason:
            reason_emoji = {
                "all_tp_hit": "🎯",
                "sl_hit": "🛡️",
                "manual_close": "👤",
                "position_sync": "🔄",
                "emergency_close": "🚨"
            }.get(close_reason, "📊")
            
            reason_text = {
                "all_tp_hit": "All Take Profits Hit",
                "sl_hit": "Stop Loss Triggered",
                "manual_close": "Manual Close",
                "position_sync": "Position Sync",
                "emergency_close": "Emergency Close"
            }.get(close_reason, close_reason.replace("_", " ").title())
            
            message += f"\n• Close Reason: {reason_emoji} {reason_text}"

        # Add detection method used
        detection_method = info.get("detection_method", "enhanced_monitoring")
        message += f"""

<b>System Performance:</b>
• Detection: {detection_method.replace('_', ' ').title()}
• Monitoring: Enhanced (2s intervals)
• Order Checks: Direct API Status"""

        # Add system features used
        features_used = []
        if info.get("breakeven_moved"):
            features_used.append("Breakeven Protection")
        if info.get("auto_rebalanced"):
            features_used.append("Auto-Rebalancing")
        if info.get("limit_cancelled_on_tp1"):
            features_used.append("TP1 Limit Cancel")
        if info.get("sl_auto_adjusted"):
            features_used.append("SL Auto-Adjustment")
        
        if features_used:
            message += f"\n• Features Used: {', '.join(features_used)}"

        # Add performance metrics
        rr_ratio = info.get("risk_reward_ratio")
        win_rate = info.get("approach_win_rate")
        
        if rr_ratio or win_rate:
            message += f"""

<b>Performance Metrics:</b>"""
            if rr_ratio:
                message += f"\n• Risk/Reward: 1:{rr_ratio:.2f}"
            if win_rate:
                message += f"\n• Approach Win Rate: {win_rate:.1f}%"

        # Add mirror sync status if applicable
        if account_type == "MIRROR" or info.get("has_mirror"):
            mirror_synced = info.get("mirror_synced", True)
            mirror_pnl = info.get("mirror_pnl")
            
            message += f"""

<b>Mirror Account:</b>
• Sync Status: {'Completed' if mirror_synced else 'Pending'}"""
            if mirror_pnl is not None:
                message += f"\n• Mirror P&L: ${mirror_pnl:,.2f}"

        # Add insights based on result
        if pnl >= 0:
            message += f"""

💡 <b>Trade Insights:</b>
• Successful trade execution
• Enhanced monitoring worked effectively
• All systems performed as designed"""
        else:
            message += f"""

💡 <b>Trade Insights:</b>
• Risk management activated properly
• Loss contained within parameters
• Consider market conditions for next trade"""

        await bot.send_message(
            chat_id=chat_id,
            text=message.strip(),
            parse_mode=ParseMode.HTML
        )

        return True

    except Exception as e:
        logger.error(f"Error sending position closed summary: {e}")
        return False


async def send_rebalancing_alert(bot: Bot, chat_id: int, symbol: str, side: str,
                                approach: str, trigger_reason: str,
                                rebalance_details: Dict[str, Any]) -> bool:
    """
    Send rebalancing notification alert (main account only)

    Args:
        bot: Telegram bot instance
        chat_id: Chat ID to send alert to
        symbol: Trading symbol
        side: Buy or Sell
        approach: fast or conservative
        trigger_reason: What triggered the rebalancing
        rebalance_details: Details about what was rebalanced

    Returns:
        bool: True if alert sent successfully
    """
    try:
        # Check if alerts are enabled
        if ENHANCED_TP_SL_ALERTS_ONLY:
            logger.debug("Rebalancing alert blocked - only enhanced TP/SL alerts enabled")
            return False

        # Check if conservative rebalancer alerts are enabled
        if not ALERT_SETTINGS.get("conservative_rebalancer", False):
            logger.debug("Conservative rebalancer alerts disabled by settings")
            return False
        # Format approach
        approach_emoji = "🛡️" if approach == "conservative" else "🎯"
        approach_text = approach.capitalize()

        # Format trigger reason
        trigger_emoji = {
            "new_position": "🆕",
            "merge": "🔄",
            "orders_filled": "✅",
            "size_change": "📊"
        }.get(trigger_reason, "⚙️")

        trigger_text = {
            "new_position": "New Position Opened",
            "merge": "Position Merged",
            "orders_filled": "Limit Orders Filled",
            "size_change": "Position Size Changed"
        }.get(trigger_reason, "Manual Trigger")

        message = f"""
⚖️ <b>POSITION REBALANCED</b>
━━━━━━━━━━━━━━━━━━━━━━
{approach_emoji} {approach_text} Approach
📊 {symbol} {"📈" if side == "Buy" else "📉"} {side}

{trigger_emoji} Trigger: {trigger_text}
"""

        # Add rebalance details
        if rebalance_details:
            if "orders_cancelled" in rebalance_details:
                message += f"\n🗑️ Orders Cancelled: {rebalance_details['orders_cancelled']}"

            if "orders_created" in rebalance_details:
                message += f"\n✅ Orders Created: {rebalance_details['orders_created']}"

            if "tp_distribution" in rebalance_details:
                message += f"\n📊 TP Distribution: {rebalance_details['tp_distribution']}"

            if "position_size" in rebalance_details:
                message += f"\n📦 Position Size: {rebalance_details['position_size']}"

        message += "\n\n✨ Orders have been automatically adjusted to match the trading approach."

        await bot.send_message(
            chat_id=chat_id,
            text=message.strip(),
            parse_mode=ParseMode.HTML
        )

        return True

    except Exception as e:
        logger.error(f"Error sending rebalancing alert: {e}")
        return False

def format_conservative_rebalance_alert(symbol: str, side: str, position_size: Decimal,
                                      additional_info: Dict[str, Any] = None) -> str:
    """
    Format Conservative approach rebalancing alert

    Args:
        symbol: Trading symbol
        side: Buy or Sell
        position_size: Current position size
        additional_info: Additional info containing trigger, quantities, etc.

    Returns:
        str: Formatted alert message
    """
    try:
        # Extract info
        info = additional_info or {}
        trigger = info.get("trigger", "unknown")
        filled_limits = info.get("filled_limits", 0)
        total_limits = info.get("total_limits", 3)
        tp1_qty = info.get("tp1_qty", 0)
        tp2_qty = info.get("tp2_qty", 0)
        tp3_qty = info.get("tp3_qty", 0)
        tp4_qty = info.get("tp4_qty", 0)
        sl_qty = info.get("sl_qty", 0)
        cancelled_orders = info.get("cancelled_orders", [])
        new_orders = info.get("new_orders", [])

        # Format trigger text
        if trigger == "limit_fill":
            trigger_text = f"Limit Order Fill ({filled_limits}/{total_limits})"
            trigger_emoji = "✅"
        elif trigger == "position_merge":
            trigger_text = "Position Merge"
            trigger_emoji = "🔄"
        elif trigger.startswith("TP") and trigger.endswith("_hit"):
            tp_num = trigger[2]  # Extract TP number
            remaining_tps = info.get("remaining_tps", 0)
            trigger_text = f"TP{tp_num} Hit - {remaining_tps} TPs Remaining"
            trigger_emoji = "🎯"
        else:
            trigger_text = "Manual Trigger"
            trigger_emoji = "⚙️"

        # Determine distribution text based on trigger
        if trigger.startswith("TP") and trigger.endswith("_hit"):
            tp_hit_num = int(trigger[2])
            remaining_tps = info.get("remaining_tps", 0)
            if remaining_tps > 0:
                dist_pct = f"{100/remaining_tps:.1f}"
                distribution_text = f"EQUAL DISTRIBUTION ({dist_pct}% each)"
            else:
                distribution_text = "NO TPs REMAINING"
        else:
            distribution_text = "STANDARD DISTRIBUTION (85/5/5/5)"

        # Build message
        message = f"""🛡️ <b>CONSERVATIVE REBALANCE</b>
━━━━━━━━━━━━━━━━━━━━━━
📊 {symbol} {"📈" if side == "Buy" else "📉"} {side}

{trigger_emoji} <b>Trigger:</b> {trigger_text}
📦 <b>Position Size:</b> {format_decimal_or_na(position_size, 4)}
💰 <b>Entry Price:</b> {format_decimal_or_na(info.get('entry_price', 0), 6)}
📍 <b>Current Price:</b> {format_decimal_or_na(info.get('current_price', 0), 6)}

<b>🎯 NEW TP {distribution_text}</b>
├─ TP1: {format_decimal_or_na(tp1_qty, 4)}{' (hit)' if tp1_qty == 0 and trigger.startswith('TP') else ' (85%)' if not trigger.startswith('TP') else ''}
├─ TP2: {format_decimal_or_na(tp2_qty, 4)}{' (hit)' if tp2_qty == 0 and trigger.startswith('TP') else ' (5%)' if not trigger.startswith('TP') else ''}
├─ TP3: {format_decimal_or_na(tp3_qty, 4)}{' (hit)' if tp3_qty == 0 and trigger.startswith('TP') else ' (5%)' if not trigger.startswith('TP') else ''}
└─ TP4: {format_decimal_or_na(tp4_qty, 4)}{' (hit)' if tp4_qty == 0 and trigger.startswith('TP') else ' (5%)' if not trigger.startswith('TP') else ''}

<b>🛡️ STOP LOSS</b>
└─ SL: {format_decimal_or_na(sl_qty, 4)} (100%)
"""

        # Add cancelled orders info
        if cancelled_orders:
            message += f"\n<b>🗑️ CANCELLED ORDERS</b>\n"
            for order in cancelled_orders[:5]:  # Limit to 5
                message += f"• {order}\n"

        # Add new orders info
        if new_orders:
            message += f"\n<b>✅ NEW ORDERS PLACED</b>\n"
            for order in new_orders[:5]:  # Limit to 5
                message += f"• {order}\n"

        # Add explanation
        if trigger == "limit_fill":
            message += f"\n📌 <b>Why Rebalanced?</b>\nLimit order filled, adjusting TP/SL quantities to maintain 85/5/5/5 distribution for the updated position size."
        elif trigger == "position_merge":
            message += f"\n📌 <b>Why Rebalanced?</b>\nPositions merged, adjusting TP/SL quantities to maintain 85/5/5/5 distribution for the combined position."

        message += "\n\n✨ Conservative approach maintained with updated quantities."

        return message.strip()

    except Exception as e:
        logger.error(f"Error formatting conservative rebalance alert: {e}")
        return f"🛡️ Conservative Rebalance Alert\n{symbol} - Check logs for details."

def _get_component_from_caller() -> str:
    """Determine which component is calling the alert function"""
    try:
        # Get the calling module
        caller_module = inspect.getmodule(inspect.stack()[2][0])
        if not caller_module:
            return "unknown"

        module_name = caller_module.__name__

        # Map module names to component names
        if 'enhanced_tp_sl' in module_name:
            return "enhanced_tp_sl"
        elif 'monitor' in module_name:
            return "monitor"
        elif 'conservative_rebalancer' in module_name:
            return "conservative_rebalancer"
        elif 'mirror' in module_name:
            return "mirror_trading"
        elif 'trader' in module_name or 'execution' in module_name:
            return "trade_execution"
        else:
            return "unknown"
    except Exception as e:
        logger.debug(f"Could not determine caller component: {e}")
        return "unknown"