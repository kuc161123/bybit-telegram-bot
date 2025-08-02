#!/usr/bin/env python3
"""
Professional Trading Terminal Formatting Utilities - CLEAN & CONSISTENT DESIGN
PROFESSIONAL: Institutional-grade number and text formatting
MINIMALISTIC: Clean visual hierarchy with essential information only
CONSISTENT: Unified formatting standards across all interfaces
READABLE: Optimized for financial data display and analysis
"""
import time
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Union, List, Optional, Dict
from html import escape
from config.constants import EMOJI_MAP
from config.settings import TELEGRAM_MAX_MESSAGE_LENGTH, TELEGRAM_MESSAGE_BUFFER

def get_emoji(key: str) -> str:
    """Get emoji from map with fallback"""
    return EMOJI_MAP.get(key, '•')

def format_number(value: Union[Decimal, float, int], decimals: int = 2) -> str:
    """Format number with thousand separators - iPhone 16 Pro Max optimized"""
    try:
        if isinstance(value, (int, float)):
            value = Decimal(str(value))
        formatted = f"{value:,.{decimals}f}"
        return formatted.rstrip('0').rstrip('.') if '.' in formatted else formatted
    except:
        return str(value)

def format_mobile_number(value: Union[Decimal, float, int], decimals: int = 2, max_length: int = 12) -> str:
    """Format number optimized for iPhone 16 Pro Max display with enhanced readability"""
    try:
        if isinstance(value, (int, float)):
            value = Decimal(str(value))

        # Format with specified decimals
        formatted = f"{value:,.{decimals}f}"
        formatted = formatted.rstrip('0').rstrip('.') if '.' in formatted else formatted

        # Enhanced mobile formatting for iPhone 16 Pro Max
        if len(formatted) > max_length:
            # Try with fewer decimals first
            if decimals > 0:
                return format_mobile_number(value, decimals - 1, max_length)

            # Use enhanced notation for iPhone screen
            abs_value = abs(float(value))
            if abs_value >= 1_000_000_000:
                billions = abs_value / 1_000_000_000
                sign = "-" if value < 0 else ""
                return f"{sign}{billions:.1f}B"
            elif abs_value >= 1_000_000:
                millions = abs_value / 1_000_000
                sign = "-" if value < 0 else ""
                return f"{sign}{millions:.1f}M"
            elif abs_value >= 1_000:
                thousands = abs_value / 1_000
                sign = "-" if value < 0 else ""
                return f"{sign}{thousands:.1f}K"

        return formatted
    except:
        return str(value)[:max_length]

def create_card_border(width: int = 32, style: str = "solid") -> str:
    """Create iPhone 16 Pro Max optimized card borders"""
    if style == "solid":
        return f"┌{'─' * width}┐"
    elif style == "double":
        return f"╔{'═' * width}╗"
    elif style == "rounded":
        return f"╭{'─' * width}╮"
    else:
        return f"┌{'─' * width}┐"

def create_card_bottom(width: int = 32, style: str = "solid") -> str:
    """Create iPhone 16 Pro Max optimized card bottom borders"""
    if style == "solid":
        return f"└{'─' * width}┘"
    elif style == "double":
        return f"╚{'═' * width}╝"
    elif style == "rounded":
        return f"╰{'─' * width}╯"
    else:
        return f"└{'─' * width}┘"

def create_section_divider(width: int = 32, char: str = "━") -> str:
    """Create iPhone 16 Pro Max optimized section dividers"""
    return char * width

def create_info_card(title: str, content: List[str], emoji: str = "", width: int = 32) -> str:
    """Create iPhone 16 Pro Max optimized information card"""
    if emoji:
        header_text = f"{emoji} {title}"
    else:
        header_text = title

    # Card structure optimized for iPhone 16 Pro Max
    card = f"┌{'─' * width}┐\n"
    card += f"│ <b>{header_text}</b>{' ' * max(0, width - len(header_text) - 1)}│\n"
    card += f"├{'─' * width}┤\n"

    for item in content:
        # Ensure content fits within card width
        if len(item) > width - 4:
            # Wrap long content
            words = item.split()
            current_line = ""
            for word in words:
                if len(current_line + " " + word) <= width - 4:
                    current_line += (" " + word) if current_line else word
                else:
                    if current_line:
                        card += f"│ {current_line}{' ' * (width - len(current_line) - 1)}│\n"
                    current_line = word
            if current_line:
                card += f"│ {current_line}{' ' * (width - len(current_line) - 1)}│\n"
        else:
            card += f"│ {item}{' ' * (width - len(item) - 1)}│\n"

    card += f"└{'─' * width}┘"
    return card

def create_status_badge(status: str, text: str = "") -> str:
    """Create iPhone 16 Pro Max optimized status badges"""
    status_emojis = {
        'success': '✅',
        'error': '❌',
        'warning': '⚠️',
        'info': 'ℹ️',
        'loading': '⏳',
        'active': '🟢',
        'inactive': '🔴',
        'pending': '🟡',
        'profit': '💚',
        'loss': '💔',
        'neutral': '⚪'
    }

    emoji = status_emojis.get(status.lower(), '•')
    return f"{emoji} {text}" if text else emoji

def mobile_progress_bar(percentage: float, length: int = 10, filled_char: str = '█', empty_char: str = '░') -> str:
    """Create iPhone 16 Pro Max optimized visual progress bar"""
    filled = int(length * percentage / 100)
    bar = filled_char * filled + empty_char * (length - filled)
    return f"{bar} {percentage:.0f}%"

def mobile_status_indicator(status: str) -> str:
    """Get iPhone 16 Pro Max optimized status indicator emoji"""
    indicators = {
        'active': '🟢',
        'pending': '🟡',
        'error': '🔴',
        'success': '✅',
        'warning': '⚠️',
        'loading': '⏳',
        'stopped': '⭕',
        'monitoring': '👁️',
        'paused': '⏸️',
        'profit': '📈',
        'loss': '📉',
        'neutral': '➡️',
        'high_risk': '🔴',
        'medium_risk': '🟡',
        'low_risk': '🟢',
        'excellent': '🟢',
        'good': '🟢',
        'fair': '🟡',
        'poor': '🟠',
        'critical': '🔴'
    }
    return indicators.get(status.lower(), '⚪')

def format_mobile_price_change(current: Decimal, previous: Decimal) -> str:
    """Format price change with iPhone 16 Pro Max optimized color indicators"""
    try:
        if current > previous:
            change_pct = ((current - previous) / previous * 100)
            return f"📈 +{change_pct:.1f}%"
        elif current < previous:
            change_pct = ((current - previous) / previous * 100)
            return f"📉 {change_pct:.1f}%"
        else:
            return f"➡️ 0.0%"
    except:
        return "➡️ --"

def create_mobile_risk_meter(risk_score: float, compact: bool = True) -> str:
    """Create iPhone 16 Pro Max optimized visual risk meter"""
    if risk_score <= 3:
        color = "🟢"
        level = "LOW"
        icon = "🛡️"
    elif risk_score <= 6:
        color = "🟡"
        level = "MED"
        icon = "⚠️"
    elif risk_score <= 8:
        color = "🟠"
        level = "HIGH"
        icon = "🔥"
    else:
        color = "🔴"
        level = "MAX"
        icon = "💀"

    if compact:
        # Enhanced compact version for iPhone 16 Pro Max
        filled = min(int(risk_score), 10)
        meter = "█" * min(filled, 5) + "░" * max(0, 5 - filled)
        return f"{color} {meter} {risk_score:.1f}/10 {icon}"
    else:
        # Enhanced full version for larger displays
        filled = min(int(risk_score), 10)
        meter = "█" * filled + "░" * (10 - filled)
        return f"{icon} Risk: {color} {meter} {risk_score:.1f}/10 ({level})"

def format_mobile_time_ago(timestamp: float) -> str:
    """Format timestamp as iPhone 16 Pro Max friendly time ago"""
    try:
        delta = time.time() - timestamp
        if delta < 60:
            return f"{int(delta)}s ago"
        elif delta < 3600:
            return f"{int(delta/60)}m ago"
        elif delta < 86400:
            return f"{int(delta/3600)}h ago"
        elif delta < 604800:  # 1 week
            return f"{int(delta/86400)}d ago"
        else:
            return f"{int(delta/604800)}w ago"
    except:
        return "?"

def format_decimal_or_na(value: Optional[Union[Decimal, float, str]], precision: int = 8, default_val: str = "N/A") -> str:
    """Format decimal value with iPhone 16 Pro Max optimized precision"""
    if value is None or str(value).strip() == '':
        return default_val
    try:
        val_str = str(value)
        dec_val = Decimal(val_str)

        # Enhanced auto-adjust precision for iPhone 16 Pro Max display
        abs_val = abs(dec_val)
        if abs_val >= 10000:
            precision = min(precision, 2)  # Large numbers need less precision
        elif abs_val >= 100:
            precision = min(precision, 3)  # Medium numbers
        elif abs_val >= 1:
            precision = min(precision, 4)  # Regular numbers
        elif abs_val > 0:
            # For small numbers, find first significant digit
            str_val = f"{abs_val:.{precision}f}"
            if '.' in str_val:
                decimal_part = str_val.split('.')[1]
                leading_zeros = len(decimal_part) - len(decimal_part.lstrip('0'))
                precision = min(precision, leading_zeros + 4)

        quantizer_str = '1e-' + str(precision)
        quantizer = Decimal(quantizer_str)
        quantized_val = dec_val.quantize(quantizer, rounding=ROUND_DOWN)

        # Format result with enhanced readability
        result = quantized_val.to_eng_string()
        if '.' in result:
            result = result.rstrip('0').rstrip('.')

        # Apply iPhone 16 Pro Max friendly formatting for very long numbers
        if len(result) > 14:  # Increased threshold for iPhone 16 Pro Max
            return format_mobile_number(dec_val, min(precision, 2))

        return result
    except InvalidOperation:
        return "Invalid"

def format_price(value: Optional[Union[Decimal, float, str]], default_val: str = "N/A") -> str:
    """
    Format price value preserving FULL decimal precision.
    This function does NOT reduce precision based on value size.
    Used for prices where every decimal place matters.
    """
    if value is None or str(value).strip() == '':
        return default_val
    try:
        val_str = str(value)
        dec_val = Decimal(val_str)

        # Convert to string without any rounding or precision loss
        result = str(dec_val)

        # Only remove trailing zeros AFTER the decimal point
        if '.' in result:
            # Split into integer and decimal parts
            integer_part, decimal_part = result.split('.')
            # Remove trailing zeros from decimal part
            decimal_part = decimal_part.rstrip('0')
            # Reconstruct the number
            if decimal_part:
                result = f"{integer_part}.{decimal_part}"
            else:
                result = integer_part

        return result
    except (InvalidOperation, ValueError):
        return default_val

def create_mobile_separator(char: str = "━", length: int = 32) -> str:
    """Create iPhone 16 Pro Max optimized visual separator"""
    return char * length

def format_mobile_currency(amount: Union[Decimal, float], currency: str = "USDT", compact: bool = True) -> str:
    """Format currency amount optimized for iPhone 16 Pro Max display"""
    try:
        formatted_amount = format_mobile_number(amount, 2 if compact else 4)
        if compact:
            return f"{formatted_amount} {currency}"
        else:
            return f"{formatted_amount} {currency}"
    except:
        return f"-- {currency}"

def create_mobile_header(title: str, emoji: str = "", width: int = 32, style: str = "card") -> str:
    """Create iPhone 16 Pro Max optimized section header"""
    if emoji:
        header_text = f"{emoji} {title}"
    else:
        header_text = title

    if style == "card":
        # Card-style header for iPhone 16 Pro Max
        return f"┌{'─' * width}┐\n│ <b>{header_text}</b>{' ' * max(0, width - len(header_text) - 1)}│\n└{'─' * width}┘"
    elif style == "separator":
        # Separator style
        padding_total = max(0, width - len(header_text))
        padding_each = padding_total // 2
        return f"{'━' * padding_each} <b>{header_text}</b> {'━' * padding_each}"
    else:
        # Simple style
        return f"<b>{header_text}</b>\n{'━' * width}"

def format_mobile_percentage(value: float, show_sign: bool = True, decimals: int = 1) -> str:
    """Format percentage optimized for iPhone 16 Pro Max display"""
    try:
        if show_sign and value >= 0:
            return f"+{value:.{decimals}f}%"
        else:
            return f"{value:.{decimals}f}%"
    except:
        return "-%"

def create_mobile_info_line(label: str, value: str, emoji: str = "•", max_label_width: int = 18) -> str:
    """Create iPhone 16 Pro Max optimized info line with consistent formatting"""
    if emoji:
        formatted_label = f"{emoji} {label}"
    else:
        formatted_label = label

    # Enhanced truncation for iPhone 16 Pro Max
    if len(formatted_label) > max_label_width:
        formatted_label = formatted_label[:max_label_width-1] + "…"

    return f"  {formatted_label}: {value}"

def create_info_grid(items: List[tuple], columns: int = 2, width: int = 32) -> str:
    """Create iPhone 16 Pro Max optimized information grid"""
    grid = ""
    col_width = width // columns

    for i in range(0, len(items), columns):
        row_items = items[i:i+columns]
        line = ""

        for j, (label, value) in enumerate(row_items):
            if j > 0:
                line += " │ "

            item_text = f"{label}: {value}"
            if len(item_text) > col_width - 3:
                item_text = item_text[:col_width-4] + "…"

            line += item_text.ljust(col_width - 3)

        grid += line + "\n"

    return grid.rstrip()

def split_long_message_mobile(message: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH - TELEGRAM_MESSAGE_BUFFER) -> List[str]:
    """Split long message optimized for iPhone 16 Pro Max reading"""
    # Use stricter limit for safety
    safe_max = min(max_length, 3800)  # Conservative limit to avoid issues

    if len(message) <= safe_max:
        return [message]

    messages = []
    current_message = ""
    lines = message.split('\n')

    for line in lines:
        if len(line) > safe_max:
            # If a single line is too long, break it at word boundaries
            if current_message:
                messages.append(current_message.rstrip('\n'))
                current_message = ""

            words = line.split(' ')
            current_line = ""
            for word in words:
                if len(current_line + " " + word) <= safe_max:
                    current_line += (" " + word) if current_line else word
                else:
                    if current_line:
                        messages.append(current_line)
                    current_line = word

            if current_line:
                current_message = current_line + '\n'
        else:
            # Check if adding this line exceeds safe limit
            if len(current_message + line + '\n') > safe_max:
                if current_message:
                    messages.append(current_message.rstrip('\n'))
                current_message = line + '\n'
            else:
                current_message += line + '\n'

    # Add remaining content
    if current_message:
        messages.append(current_message.rstrip('\n'))

    # Add continuation indicators only if multiple parts
    if len(messages) > 1:
        for i in range(len(messages)):
            if i > 0:
                messages[i] = f"📱 Part {i+1}/{len(messages)}\n" + "─" * 20 + "\n\n" + messages[i]
            if i < len(messages) - 1:
                messages[i] += f"\n\n" + "─" * 20 + f"\n📱 Continued... ({i+1}/{len(messages)})"

    return messages

def format_mobile_position_summary(symbol: str, side: str, pnl: Decimal,
                                  pnl_pct: float, size: Decimal) -> str:
    """Format position summary optimized for iPhone 16 Pro Max display"""
    side_emoji = "📈" if side == "Buy" else "📉"
    pnl_emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "🟡"

    # Enhanced ultra-compact format for iPhone 16 Pro Max
    pnl_formatted = format_mobile_currency(pnl, compact=True)
    pct_formatted = format_mobile_percentage(pnl_pct, show_sign=True, decimals=1)
    size_formatted = format_mobile_number(size, decimals=3, max_length=10)

    return f"{side_emoji} <b>{symbol}</b> • {pnl_emoji} {pnl_formatted} ({pct_formatted}) • {size_formatted}"

def create_mobile_progress_indicator(current: int, total: int,
                                   description: str = "Progress") -> str:
    """Create iPhone 16 Pro Max optimized progress indicator"""
    percentage = (current / total * 100) if total > 0 else 0
    bar = mobile_progress_bar(percentage, length=8)  # Optimized length for iPhone
    return f"{description}: {bar} ({current}/{total})"

def create_highlight_box(text: str, style: str = "info", width: int = 32) -> str:
    """Create iPhone 16 Pro Max optimized highlight box"""
    styles = {
        "info": {"emoji": "ℹ️", "border": "─"},
        "warning": {"emoji": "⚠️", "border": "━"},
        "success": {"emoji": "✅", "border": "═"},
        "error": {"emoji": "❌", "border": "▬"}
    }

    style_config = styles.get(style, styles["info"])
    emoji = style_config["emoji"]
    border_char = style_config["border"]

    box = f"┌{border_char * width}┐\n"
    box += f"│ {emoji} {text}{' ' * max(0, width - len(text) - 3)}│\n"
    box += f"└{border_char * width}┘"

    return box

def format_trade_summary_card(symbol: str, side: str, entry: Decimal,
                             current: Decimal, pnl: Decimal, approach: str) -> str:
    """Create iPhone 16 Pro Max optimized trade summary card"""
    side_emoji = "📈" if side == "Buy" else "📉"
    approach_emoji = "⚡" if approach == "fast" else "🛡️"
    pnl_emoji = "💚" if pnl >= 0 else "💔"
    pnl_status = "🟢" if pnl >= 0 else "🔴"

    # Calculate percentage change
    pct_change = 0
    if entry > 0:
        if side == "Buy":
            pct_change = ((current - entry) / entry) * 100
        else:
            pct_change = ((entry - current) / entry) * 100

    card = create_card_border(30) + "\n"
    card += f"│ {approach_emoji} {symbol} {side_emoji} {side.upper()}{' ' * (25 - len(symbol) - len(side))}│\n"
    card += f"├{'─' * 30}┤\n"
    card += f"│ Entry: ${format_decimal_or_na(entry)}{' ' * (22 - len(format_decimal_or_na(entry)))}│\n"
    card += f"│ Current: ${format_decimal_or_na(current)}{' ' * (20 - len(format_decimal_or_na(current)))}│\n"
    card += f"│ P&L: {pnl_status} {format_decimal_or_na(pnl, 2)} USDT {pnl_emoji}{' ' * (10 - len(format_decimal_or_na(pnl, 2)))}│\n"

    if pct_change != 0:
        pct_emoji = "🚀" if pct_change > 5 else "📈" if pct_change > 0 else "📉"
        card += f"│ Change: {pct_emoji} {pct_change:+.2f}%{' ' * (16 - len(f'{pct_change:+.2f}'))}│\n"

    card += create_card_bottom(30)

    return card

# Legacy compatibility functions
progress_bar = mobile_progress_bar
status_indicator = mobile_status_indicator
format_price_change = format_mobile_price_change
create_risk_meter = create_mobile_risk_meter
format_time_ago = format_mobile_time_ago
split_long_message = split_long_message_mobile

# NEW: Enhanced formatting functions for clean UI
def create_section_header(title: str, emoji: str = "") -> str:
    """Create clean section header with separator"""
    header = f"{emoji} {title}" if emoji else title
    return f"{header}\n{'═' * len(title)}\n"

def create_beautiful_header(title: str, icon: str = "", subtitle: str = "") -> str:
    """Create visually stunning section header with elegant styling"""
    if icon:
        header_line = f"{icon} <b>{title}</b>"
    else:
        header_line = f"<b>{title}</b>"

    # Beautiful header with decorative elements
    result = f"╭─── {header_line} ───╮\n"
    if subtitle:
        result += f"│ <i>{subtitle}</i>\n"
    result += "╰" + "─" * (len(title) + 8) + "╯\n\n"
    return result

def create_elegant_divider() -> str:
    """Create elegant section divider"""
    return "═" * 35

def create_info_line(label: str, value: str, icon: str = "•") -> str:
    """Create beautifully formatted information line"""
    return f"  {icon} <b>{label}:</b> <code>{value}</code>"

def create_status_line(label: str, value: str, status: str = "neutral") -> str:
    """Create status line with beautiful visual indicators"""
    status_styles = {
        "positive": "💚",
        "negative": "❤️",
        "neutral": "💙",
        "warning": "💛",
        "success": "💚",
        "excellent": "✨"
    }
    icon = status_styles.get(status, "💙")
    return f"  {icon} <b>{label}:</b> <code>{value}</code>"

def create_info_box(title: str, content: Dict[str, str]) -> str:
    """Create bordered information box"""
    lines = [f"╭─ {title} ─{'─' * (30 - len(title))}╮"]
    for key, value in content.items():
        # Ensure value fits in box
        value_str = str(value)[:25]
        lines.append(f"│ {key}: {value_str:<25}│")
    lines.append("╰" + "─" * 35 + "╯")
    return "\n".join(lines)

def create_progress_indicator(current: float, target: float, width: int = 10) -> str:
    """Create visual progress bar indicator"""
    if target == 0:
        return "░" * width + " 0.0%"

    percentage = min(100, (current / target) * 100)
    filled = int((percentage / 100) * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"{bar} {percentage:.1f}%"

def format_pnl_with_color(pnl: Union[float, Decimal]) -> str:
    """Format P&L value with color indicator"""
    pnl_float = float(pnl)
    if pnl_float > 0:
        return f"+${abs(pnl_float):.2f} 🟢"
    elif pnl_float < 0:
        return f"-${abs(pnl_float):.2f} 🔴"
    else:
        return f"${pnl_float:.2f} ⚪"

def create_enhanced_risk_meter(score: float, max_score: float = 10) -> str:
    """Create enhanced visual risk meter with emoji indicators"""
    normalized = (score / max_score) * 5

    if normalized <= 1:
        return "🟢🟢⚪⚪⚪ Low Risk"
    elif normalized <= 2:
        return "🟢🟢🟢⚪⚪ Low-Med Risk"
    elif normalized <= 3:
        return "🟡🟡🟡⚪⚪ Medium Risk"
    elif normalized <= 4:
        return "🟠🟠🟠🟠⚪ High Risk"
    else:
        return "🔴🔴🔴🔴🔴 Very High Risk"

def create_enhanced_status_badge(status: str) -> str:
    """Create enhanced colored status badge"""
    badges = {
        "active": "🟢 ACTIVE",
        "pending": "🟡 PENDING",
        "filled": "✅ FILLED",
        "cancelled": "❌ CANCELLED",
        "closed": "⚪ CLOSED",
        "error": "🔴 ERROR",
        "monitoring": "👁️ MONITORING",
        "tp_hit": "🎯 TP HIT",
        "sl_hit": "🛡️ SL HIT",
        "partial": "⚡ PARTIAL",
        "breakeven": "🔒 BREAKEVEN"
    }
    return badges.get(status.lower(), f"⚪ {status.upper()}")

def create_pnl_scenario_card(tp1: float, all_tp: float, sl: float, current: float) -> str:
    """Create clean P&L scenario card for dashboard"""
    lines = []
    lines.append("┌─── 💰 P&L Scenarios ─────────┐")

    if current != 0:
        current_str = f"+${abs(current):.2f}" if current > 0 else f"-${abs(current):.2f}"
        color = "🟢" if current > 0 else "🔴" if current < 0 else "⚪"
        lines.append(f"│ Current: {current_str} {color}        │")

    if tp1 > 0:
        lines.append(f"│ TP1 Hit: +${tp1:.2f} 🎯       │")

    if all_tp > 0:
        lines.append(f"│ All TPs: +${all_tp:.2f} 🏆     │")

    if sl < 0:
        lines.append(f"│ All SLs: -${abs(sl):.2f} 🛡️      │")

    lines.append("└──────────────────────────────┘")

    return "\n".join(lines)

def format_position_summary(symbol: str, side: str, pnl: float, size: float = None) -> str:
    """Format a compact position summary line"""
    side_emoji = "📈" if side == "Buy" else "📉"
    pnl_str = format_pnl_with_color(pnl)

    summary = f"{side_emoji} {symbol}: {pnl_str}"
    if size:
        summary += f" ({size:.4f})"

    return summary

def create_position_heatmap_indicator(pnl: float, scale: float = 100) -> str:
    """Create visual heatmap indicator for position P&L"""
    if pnl > 0:
        intensity = min(3, int(pnl / scale) + 1)
        return "🟢" * intensity + "⚪" * (3 - intensity)
    elif pnl < 0:
        intensity = min(3, int(abs(pnl) / scale) + 1)
        return "🔴" * intensity + "⚪" * (3 - intensity)
    else:
        return "⚪⚪⚪"

def format_potential_outcome(label: str, value: float, detail: str = "") -> str:
    """Format potential P&L outcome with visual styling"""
    value_str = format_pnl_with_color(value)
    if detail:
        return f"{label}: {value_str}\n   {detail}"
    else:
        return f"{label}: {value_str}"

# iPhone 16 Pro Max specific exports for enhanced UX
__all__ = [
    # Core formatting functions
    'get_emoji',
    'format_number',
    'format_decimal_or_na',
    'format_price',  # New function for full precision prices
    'split_long_message',

    # iPhone 16 Pro Max optimized functions
    'format_mobile_number',
    'mobile_progress_bar',
    'mobile_status_indicator',
    'format_mobile_price_change',
    'create_mobile_risk_meter',
    'format_mobile_time_ago',
    'create_mobile_separator',
    'format_mobile_currency',
    'create_mobile_header',
    'format_mobile_percentage',
    'create_mobile_info_line',
    'split_long_message_mobile',
    'format_mobile_position_summary',
    'create_mobile_progress_indicator',

    # Card-based formatting (iPhone 16 Pro Max specific)
    'create_card_border',
    'create_card_bottom',
    'create_section_divider',
    'create_info_card',
    'create_status_badge',
    'create_info_grid',
    'create_highlight_box',
    'format_trade_summary_card',

    # Enhanced formatting functions
    'create_section_header',
    'create_beautiful_header',
    'create_elegant_divider',
    'create_info_line',
    'create_status_line',
    'create_info_box',
    'create_progress_indicator',
    'format_pnl_with_color',
    'create_enhanced_risk_meter',
    'create_enhanced_status_badge',
    'format_position_summary',
    'create_position_heatmap_indicator',
    'format_potential_outcome',
    'create_pnl_scenario_card',

    # Legacy compatibility
    'progress_bar',
    'status_indicator',
    'format_price_change',
    'create_risk_meter',
    'format_time_ago'
]