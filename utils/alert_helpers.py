#!/usr/bin/env python3
"""
Trade execution alert helpers for sending notifications
"""
import logging
from typing import Optional, Dict, Any, List
from decimal import Decimal
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from config.constants import *
from utils.formatters import format_price, format_decimal_or_na, get_emoji

logger = logging.getLogger(__name__)

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
        else:
            logger.warning(f"Unknown alert type: {alert_type}")
            return False
        
        # Send alert
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=ParseMode.HTML
        )
        
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
    """Format take profit hit alert message"""
    side_emoji = "📈" if side == "Buy" else "📉"
    approach_emoji = "⚡" if approach == "fast" else "🎯"
    
    # Determine which TP was hit for conservative
    tp_number = additional_info.get("tp_number", 1) if approach == "conservative" else ""
    tp_text = f"TP{tp_number}" if tp_number else "TP"
    
    message = f"""
🎯 <b>{tp_text} HIT - PROFIT TAKEN!</b>
━━━━━━━━━━━━━━━━━━━━━━
{approach_emoji} {approach.capitalize()} Approach
📊 {symbol} {side_emoji} {side}

💰 <b>Profit: ${pnl:,.2f} ({pnl_percent:+.2f}%)</b>
📍 Entry: ${format_price(entry_price)}
🎯 Exit: ${format_price(exit_price)}
📦 Size: {format_decimal_or_na(position_size)}
"""
    
    if cancelled_orders:
        message += f"\n❌ <b>Cancelled Orders:</b>\n"
        for order in cancelled_orders[:5]:  # Limit to 5 orders
            message += f"   • {order}\n"
        if len(cancelled_orders) > 5:
            message += f"   • ... and {len(cancelled_orders) - 5} more\n"
    
    if approach == "conservative" and additional_info:
        remaining_tps = additional_info.get("remaining_tps", [])
        if remaining_tps:
            message += f"\n✅ <b>Active TPs:</b> {', '.join(remaining_tps)}"
    
    return message.strip()

def format_sl_hit_alert(symbol: str, side: str, approach: str,
                       pnl: Decimal, pnl_percent: Decimal,
                       entry_price: Decimal, exit_price: Decimal,
                       position_size: Decimal, cancelled_orders: List[str],
                       additional_info: Dict[str, Any]) -> str:
    """Format stop loss hit alert message"""
    side_emoji = "📈" if side == "Buy" else "📉"
    approach_emoji = "⚡" if approach == "fast" else "🎯"
    
    message = f"""
🛡️ <b>STOP LOSS HIT - POSITION CLOSED</b>
━━━━━━━━━━━━━━━━━━━━━━
{approach_emoji} {approach.capitalize()} Approach
📊 {symbol} {side_emoji} {side}

🔴 <b>Loss: ${pnl:,.2f} ({pnl_percent:.2f}%)</b>
📍 Entry: ${format_price(entry_price)}
🛡️ Exit: ${format_price(exit_price)}
📦 Size: {format_decimal_or_na(position_size)}
"""
    
    if cancelled_orders:
        message += f"\n❌ <b>Cancelled Orders:</b>\n"
        for order in cancelled_orders[:5]:
            message += f"   • {order}\n"
        if len(cancelled_orders) > 5:
            message += f"   • ... and {len(cancelled_orders) - 5} more\n"
    
    return message.strip()

def format_limit_filled_alert(symbol: str, side: str, approach: str,
                            additional_info: Dict[str, Any]) -> str:
    """Format limit order filled alert message"""
    side_emoji = "📈" if side == "Buy" else "📉"
    fill_price = additional_info.get("fill_price", Decimal("0"))
    fill_size = additional_info.get("fill_size", Decimal("0"))
    limit_number = additional_info.get("limit_number", 1)
    total_limits = additional_info.get("total_limits", 3)
    
    message = f"""
📦 <b>LIMIT ORDER FILLED</b>
━━━━━━━━━━━━━━━━━━━━━━
🎯 Conservative Approach
📊 {symbol} {side_emoji} {side}

✅ Limit {limit_number}/{total_limits} Filled
💵 Price: ${format_price(fill_price)}
📦 Size: {format_decimal_or_na(fill_size)}
"""
    
    filled_count = additional_info.get("filled_count", 1)
    if filled_count > 1:
        message += f"\n📊 Total Filled: {filled_count}/{total_limits}"
    
    return message.strip()

def format_tp1_early_hit_alert(symbol: str, side: str, approach: str,
                              cancelled_orders: List[str],
                              additional_info: Dict[str, Any]) -> str:
    """Format TP1 early hit alert (before any limits filled)"""
    side_emoji = "📈" if side == "Buy" else "📉"
    approach_text = "Conservative" if approach == "conservative" else "GGShot"
    
    message = f"""
🚨 <b>TP1 HIT EARLY - ALL ORDERS CANCELLED</b>
━━━━━━━━━━━━━━━━━━━━━━
🎯 {approach_text} Approach
📊 {symbol} {side_emoji} {side}

⚠️ <b>TP1 hit before limit orders filled!</b>
📝 All remaining orders have been cancelled
💡 Consider market conditions for next trade
"""
    
    if cancelled_orders:
        message += f"\n\n❌ <b>Cancelled Orders ({len(cancelled_orders)}):</b>\n"
        for order in cancelled_orders[:5]:
            message += f"   • {order}\n"
        if len(cancelled_orders) > 5:
            message += f"   • ... and {len(cancelled_orders) - 5} more\n"
    
    return message.strip()

def format_tp1_with_fills_alert(symbol: str, side: str, approach: str,
                               cancelled_orders: List[str],
                               additional_info: Dict[str, Any]) -> str:
    """Format TP1 hit with fills alert (after some limits filled)"""
    side_emoji = "📈" if side == "Buy" else "📉"
    approach_text = "Conservative" if approach == "conservative" else "GGShot"
    filled_count = additional_info.get("filled_count", 0)
    total_limits = additional_info.get("total_limits", 3)
    
    message = f"""
🎯 <b>TP1 HIT - REMAINING LIMITS CANCELLED</b>
━━━━━━━━━━━━━━━━━━━━━━
🎯 {approach_text} Approach
📊 {symbol} {side_emoji} {side}

✅ <b>TP1 hit with {filled_count}/{total_limits} limits filled</b>
📝 Unfilled limit orders cancelled
✨ TP2, TP3, TP4 remain active
"""
    
    if cancelled_orders:
        message += f"\n\n❌ <b>Cancelled Limits ({len(cancelled_orders)}):</b>\n"
        for order in cancelled_orders[:3]:
            message += f"   • {order}\n"
        if len(cancelled_orders) > 3:
            message += f"   • ... and {len(cancelled_orders) - 3} more\n"
    
    return message.strip()

async def send_position_closed_summary(bot: Bot, chat_id: int,
                                     symbol: str, side: str, approach: str,
                                     entry_price: Decimal, exit_price: Decimal,
                                     position_size: Decimal, pnl: Decimal,
                                     close_reason: str, duration_minutes: int) -> bool:
    """Send position closed summary alert"""
    try:
        # Calculate P&L percentage
        if entry_price > 0:
            if side == "Buy":
                pnl_percent = ((exit_price - entry_price) / entry_price) * 100
            else:  # Sell
                pnl_percent = ((entry_price - exit_price) / entry_price) * 100
        else:
            pnl_percent = Decimal("0")
        
        # Format duration
        if duration_minutes < 60:
            duration_text = f"{duration_minutes} minutes"
        else:
            hours = duration_minutes // 60
            mins = duration_minutes % 60
            duration_text = f"{hours}h {mins}m"
        
        # Determine emoji and color
        pnl_emoji = "💰" if pnl >= 0 else "🔴"
        result_text = "PROFIT" if pnl >= 0 else "LOSS"
        
        message = f"""
📊 <b>POSITION CLOSED - {result_text}</b>
━━━━━━━━━━━━━━━━━━━━━━
📈 {symbol} {side}
⚡ {approach.capitalize()} Approach

{pnl_emoji} <b>P&L: ${pnl:,.2f} ({pnl_percent:+.2f}%)</b>
📍 Entry: ${format_price(entry_price)}
🎯 Exit: ${format_price(exit_price)}
📦 Size: {format_decimal_or_na(position_size)}
⏱️ Duration: {duration_text}
📝 Reason: {close_reason.replace('_', ' ').title()}
"""
        
        await bot.send_message(
            chat_id=chat_id,
            text=message.strip(),
            parse_mode=ParseMode.HTML
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending position closed summary: {e}")
        return False