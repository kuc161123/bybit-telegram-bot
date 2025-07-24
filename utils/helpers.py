#!/usr/bin/env python3
"""
General helper functions and utilities with FIXED decimal handling.
REFINED: Enhanced P&L calculation helpers and trade validation
PRESERVES: All existing decimal handling and helper functions
"""
import logging
import uuid
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Dict, Any, Union, Optional
from html import escape
import hashlib
import json
import time
from config.constants import *
from utils.formatters import get_emoji

logger = logging.getLogger(__name__)

# =============================================
# EXISTING FUNCTIONS - PRESERVED
# =============================================

def get_field_emoji_and_name(field_key: str) -> str:
    """Get emoji and display name for a field"""
    if not isinstance(field_key, str):
        logger.error(f"CRITICAL: get_field_emoji_and_name called with non-string key: {field_key} of type {type(field_key)}.")
        return f"InvalidFieldKey({field_key})"

    mapping = {
        SYMBOL: f"{get_emoji('diamond')} Symbol",
        SIDE: f"{get_emoji('chart')} Side",
        MARGIN_AMOUNT: f"{get_emoji('money')} Margin (USDT)",
        LEVERAGE: f"{get_emoji('rocket')} Leverage",
        ORDER_STRATEGY: f"{get_emoji('chart')} Strategy",
        PRIMARY_ENTRY_PRICE: f"{get_emoji('target')} Primary Entry",
        LIMIT_ENTRY_1_PRICE: f"📥 L1 Entry ({ENTRY_PORTION_ALLOCATION[1]*100:.0f}%)",
        LIMIT_ENTRY_2_PRICE: f"📥 L2 Entry ({ENTRY_PORTION_ALLOCATION[2]*100:.0f}%)",
        TP1_PRICE: f"{get_emoji('target')} TP1 ({TP_PERCENTAGES[0]*100:.0f}%)",
        TP2_PRICE: f"{get_emoji('target')} TP2 ({TP_PERCENTAGES[1]*100:.0f}%)",
        TP3_PRICE: f"{get_emoji('target')} TP3 ({TP_PERCENTAGES[2]*100:.0f}%)",
        TP4_PRICE: f"{get_emoji('target')} TP4 ({TP_PERCENTAGES[3]*100:.0f}%)",
        SL_PRICE: f"{get_emoji('shield')} Stop Loss",
        MAX_LEVERAGE_FOR_SYMBOL: f"{get_emoji('chart')} Max Leverage",
        MARGIN_INPUT_TYPE: f"{get_emoji('money')} Margin Type",
        MARGIN_PERCENTAGE_VALUE: "％ Margin (%)"
    }
    return mapping.get(field_key, field_key.replace("_", " ").capitalize())

def _adjust_value(value: Decimal, step: Decimal, round_mode=ROUND_DOWN) -> str:
    """
    FIXED: Adjust value to step with proper rounding and validation
    """
    try:
        # Ensure inputs are Decimal
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        if not isinstance(step, Decimal):
            step = Decimal(str(step))

        # Handle zero or invalid step
        if step <= Decimal("0"):
            adjusted_val_decimal = value.quantize(Decimal('1e-8'), rounding=ROUND_DOWN)
            return str(adjusted_val_decimal)

        # Calculate decimal places from step
        step_str_normalized = step.normalize().to_eng_string()
        if '.' in step_str_normalized:
            dp = len(step_str_normalized.split('.')[-1])
        else:
            dp = 0

        # Round to step
        if round_mode == ROUND_DOWN:
            adjusted_val_decimal = (value // step) * step
        elif round_mode == "ROUND_UP":
            if value % step != 0:
                adjusted_val_decimal = ((value + step - Decimal('1e-10')) // step) * step
            else:
                adjusted_val_decimal = (value // step) * step
        elif round_mode == "ROUND_NEAREST":
            adjusted_val_decimal = Decimal(round(value / step)) * step
        else:
            adjusted_val_decimal = (value // step) * step

        # Quantize to proper decimal places
        if dp > 0:
            quantizer_str = '1e-' + str(dp)
            final_quantized_val = adjusted_val_decimal.quantize(Decimal(quantizer_str), rounding=ROUND_DOWN)
        else:
            final_quantized_val = adjusted_val_decimal.quantize(Decimal('1'), rounding=ROUND_DOWN)

        # Format result
        if dp == 0:
            formatted_val_str = str(int(final_quantized_val))
        else:
            formatted_val_str = f"{final_quantized_val:.{dp}f}"

        # Clean up trailing zeros
        if '.' in formatted_val_str:
            formatted_val_str = formatted_val_str.rstrip('0').rstrip('.')

        return formatted_val_str

    except Exception as e:
        logger.error(f"Error in _adjust_value: {e}, value={value}, step={step}")
        # Return safe fallback
        try:
            return f"{float(value):.8f}".rstrip('0').rstrip('.')
        except:
            return "0"

def adjust_price(price: Decimal, tick_size: Decimal) -> str:
    """Adjust price to tick size"""
    return _adjust_value(price, tick_size)

def adjust_qty(qty: Decimal, qty_step: Decimal) -> str:
    """Adjust quantity to step size"""
    return _adjust_value(qty, qty_step, ROUND_DOWN)

def value_adjusted_to_step(value: Decimal, step: Decimal) -> Decimal:
    """
    FIXED: Adjust a value to the nearest step size (round down).
    This is the function that execution/trader.py uses.

    Args:
        value: The value to adjust
        step: The step size (e.g., 0.001 for quantity step)

    Returns:
        Adjusted value that is a multiple of step
    """
    try:
        # Ensure inputs are Decimal
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        if not isinstance(step, Decimal):
            step = Decimal(str(step))

        # Handle zero or very small step
        if step <= Decimal("0") or step < Decimal("1e-8"):
            # If step is zero or very small, just round to 8 decimal places
            return value.quantize(Decimal('1e-8'), rounding=ROUND_DOWN)

        # Calculate the number of steps
        steps = (value / step).quantize(Decimal('1'), rounding=ROUND_DOWN)

        # Calculate adjusted value
        adjusted_value = steps * step

        # Determine precision from step size
        step_str = str(step).rstrip('0').rstrip('.')
        if '.' in step_str:
            decimal_places = len(step_str.split('.')[1])
        else:
            decimal_places = 0

        # Quantize to appropriate precision
        if decimal_places > 0:
            quantizer = Decimal('1e-' + str(decimal_places))
            adjusted_value = adjusted_value.quantize(quantizer, rounding=ROUND_DOWN)
        else:
            adjusted_value = adjusted_value.quantize(Decimal('1'), rounding=ROUND_DOWN)

        logger.debug(f"value_adjusted_to_step: {value} -> {adjusted_value} (step: {step})")

        return adjusted_value

    except Exception as e:
        logger.error(f"Error in value_adjusted_to_step: {e}, value={value}, step={step}")
        # Return safe fallback - just round to 8 decimal places
        try:
            if isinstance(value, Decimal):
                return value.quantize(Decimal('1e-8'), rounding=ROUND_DOWN)
            else:
                return Decimal(str(value)).quantize(Decimal('1e-8'), rounding=ROUND_DOWN)
        except:
            return Decimal("0")

def safe_decimal_conversion(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """
    REFINED: Safely convert any value to Decimal with comprehensive validation

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        Decimal value
    """
    try:
        if value is None:
            return default

        if isinstance(value, Decimal):
            return value

        # Handle string values
        if isinstance(value, str):
            value = value.strip()
            if value == '' or value.lower() in ['none', 'null', 'nan']:
                return default
            # Remove any currency symbols or commas
            value = value.replace('$', '').replace(',', '').replace('USDT', '').strip()

        # Handle numeric types
        if isinstance(value, (int, float)):
            # Check for NaN or infinity
            if isinstance(value, float):
                if value != value or value == float('inf') or value == float('-inf'):
                    return default
            return Decimal(str(value))

        # Try conversion
        return Decimal(str(value))

    except (ValueError, InvalidOperation, TypeError) as e:
        logger.warning(f"Could not convert '{value}' (type: {type(value)}) to Decimal: {e}, using default: {default}")
        return default

def validate_decimal_precision(value: Decimal, max_precision: int = 8) -> Decimal:
    """
    Validate and limit decimal precision
    """
    try:
        if not isinstance(value, Decimal):
            value = safe_decimal_conversion(value)

        # Limit precision to prevent overly long decimal strings
        quantizer = Decimal('1e-' + str(max_precision))
        return value.quantize(quantizer, rounding=ROUND_DOWN)
    except Exception as e:
        logger.error(f"Error validating decimal precision: {e}")
        return Decimal("0")

def initialize_chat_data(chat_data: Dict[str, Any]):
    """Initialize chat data with defaults and FIXED decimal handling"""
    defaults = {
        SYMBOL: "BTCUSDT", SIDE: "Buy", MARGIN_INPUT_TYPE: None, MARGIN_PERCENTAGE_VALUE: None,
        MARGIN_AMOUNT: None, LEVERAGE: None, MAX_LEVERAGE_FOR_SYMBOL: None, ORDER_STRATEGY: None,
        PRIMARY_ENTRY_PRICE: None, LIMIT_ENTRY_1_PRICE: None, LIMIT_ENTRY_2_PRICE: None,
        TP1_PRICE: None, TP2_PRICE: None, TP3_PRICE: None, TP4_PRICE: None, SL_PRICE: None,
        AWAITING_INPUT_FOR: None, LAST_UI_MESSAGE_ID: None, POSITION_IDX: 0,
        PLACED_LIMIT_ENTRY_IDS: [], INITIAL_MARKET_FILL_QTY: Decimal("0"),
        INITIAL_AVG_ENTRY_PRICE: Decimal("0"), ACTIVE_MONITOR_TASK: {},
        INSTRUMENT_TICK_SIZE: None, INSTRUMENT_QTY_STEP: None, MIN_ORDER_QTY: None,
        MIN_ORDER_NOTIONAL_VALUE: None, AI_RECOMMENDATIONS_STORE: None,
        AI_RISK_ASSESSMENT_STORE: None, USER_OVERRIDE_MARGIN_TYPE: None,
        USER_OVERRIDE_MARGIN_VALUE_FIXED: None, USER_OVERRIDE_MARGIN_VALUE_PERCENTAGE: None,
        USER_OVERRIDE_LEVERAGE: None, USER_OVERRIDE_STRATEGY: None, MARKET_ORDER_ID: None,
        TP_ORDER_IDS: {}, SL_ORDER_ID: None, LAST_KNOWN_POSITION_SIZE: None,
        HELP_CONTEXT: None, USER_PREFERENCES: {}
    }

    for k, v_def in defaults.items():
        if k not in chat_data or (chat_data.get(k) is None and v_def is not None):
            chat_data[k] = v_def

        # FIXED: Type conversions for specific fields with better error handling
        val_dec_fields = [
            MARGIN_AMOUNT, MARGIN_PERCENTAGE_VALUE, PRIMARY_ENTRY_PRICE, LIMIT_ENTRY_1_PRICE,
            LIMIT_ENTRY_2_PRICE, TP1_PRICE, TP2_PRICE, TP3_PRICE, TP4_PRICE, SL_PRICE,
            INITIAL_MARKET_FILL_QTY, INITIAL_AVG_ENTRY_PRICE, USER_OVERRIDE_MARGIN_VALUE_FIXED,
            USER_OVERRIDE_MARGIN_VALUE_PERCENTAGE, MAX_LEVERAGE_FOR_SYMBOL, INSTRUMENT_TICK_SIZE,
            INSTRUMENT_QTY_STEP, MIN_ORDER_QTY, MIN_ORDER_NOTIONAL_VALUE, LAST_KNOWN_POSITION_SIZE
        ]

        if k in val_dec_fields and chat_data.get(k) is not None:
            if not isinstance(chat_data.get(k), Decimal):
                try:
                    chat_data[k] = safe_decimal_conversion(chat_data.get(k))
                except Exception as e:
                    logger.error(f"Error converting {k} to Decimal: {e}")
                    chat_data[k] = v_def

        elif k in [LEVERAGE, USER_OVERRIDE_LEVERAGE] and chat_data.get(k) is not None:
            if not isinstance(chat_data.get(k), int):
                try:
                    chat_data[k] = int(float(str(chat_data.get(k))))
                except Exception as e:
                    logger.error(f"Error converting {k} to int: {e}")
                    chat_data[k] = v_def

        elif k == ACTIVE_MONITOR_TASK and not isinstance(chat_data.get(k), dict):
            chat_data[k] = {}

        elif k in [AI_RECOMMENDATIONS_STORE, AI_RISK_ASSESSMENT_STORE] and chat_data.get(k) is not None and not isinstance(chat_data.get(k), dict):
            chat_data[k] = None

        elif k == TP_ORDER_IDS and not isinstance(chat_data.get(k), dict):
            chat_data[k] = {}

        elif k == PLACED_LIMIT_ENTRY_IDS and not isinstance(chat_data.get(k), list):
            chat_data[k] = []

        elif k == USER_PREFERENCES and not isinstance(chat_data.get(k), dict):
            chat_data[k] = {}

        # Validate strategy values
        valid_strats = [STRATEGY_MARKET_ONLY, STRATEGY_MARKET_AND_LIMITS, None]
        if k in [ORDER_STRATEGY, USER_OVERRIDE_STRATEGY] and chat_data.get(k) not in valid_strats:
            chat_data[k] = v_def

        # Validate margin type values
        valid_mgn_types = ["fixed", "percentage", None]
        if k in [MARGIN_INPUT_TYPE, USER_OVERRIDE_MARGIN_TYPE] and chat_data.get(k) not in valid_mgn_types:
            chat_data[k] = v_def

# =============================================
# REFINED: ENHANCED P&L CALCULATION FUNCTIONS
# =============================================

def calculate_position_value(size: Decimal, price: Decimal) -> Decimal:
    """
    Calculate position value in USDT

    Args:
        size: Position size
        price: Current price

    Returns:
        Position value in USDT
    """
    try:
        size = safe_decimal_conversion(size)
        price = safe_decimal_conversion(price)

        return size * price

    except Exception as e:
        logger.error(f"Error calculating position value: {e}")
        return Decimal("0")

def calculate_pnl_from_prices(entry_price: Decimal, exit_price: Decimal,
                             size: Decimal, side: str) -> Decimal:
    """
    REFINED: Calculate P&L from entry and exit prices

    Args:
        entry_price: Entry price
        exit_price: Exit price (or current price)
        size: Position size
        side: Buy or Sell

    Returns:
        P&L amount
    """
    try:
        entry_price = safe_decimal_conversion(entry_price)
        exit_price = safe_decimal_conversion(exit_price)
        size = safe_decimal_conversion(size)

        if entry_price == 0 or exit_price == 0 or size == 0:
            return Decimal("0")

        if side == "Buy":
            # Long position: profit when price goes up
            pnl = (exit_price - entry_price) * size
        else:  # Sell/Short
            # Short position: profit when price goes down
            pnl = (entry_price - exit_price) * size

        return pnl

    except Exception as e:
        logger.error(f"Error calculating P&L from prices: {e}")
        return Decimal("0")

def calculate_percentage_change(initial_value: Decimal, final_value: Decimal) -> Decimal:
    """
    Calculate percentage change between two values

    Args:
        initial_value: Initial value
        final_value: Final value

    Returns:
        Percentage change
    """
    try:
        initial = safe_decimal_conversion(initial_value)
        final = safe_decimal_conversion(final_value)

        if initial == 0:
            return Decimal("0")

        change = ((final - initial) / initial) * 100
        return change

    except Exception as e:
        logger.error(f"Error calculating percentage change: {e}")
        return Decimal("0")

def validate_price_levels(entry: Decimal, tp: Decimal, sl: Decimal, side: str) -> Dict[str, Any]:
    """
    REFINED: Validate price levels for a trade

    Args:
        entry: Entry price
        tp: Take profit price
        sl: Stop loss price
        side: Buy or Sell

    Returns:
        Dict with validation results
    """
    try:
        entry = safe_decimal_conversion(entry)
        tp = safe_decimal_conversion(tp)
        sl = safe_decimal_conversion(sl)

        errors = []
        warnings = []

        # Basic validation
        if entry <= 0:
            errors.append("Entry price must be positive")
        if tp <= 0:
            errors.append("Take profit price must be positive")
        if sl <= 0:
            errors.append("Stop loss price must be positive")

        if errors:
            return {"valid": False, "errors": errors, "warnings": warnings}

        # Directional validation
        if side == "Buy":
            # For long: TP should be above entry, SL below entry
            if tp <= entry:
                errors.append("Take profit must be above entry price for long positions")
            if sl >= entry:
                errors.append("Stop loss must be below entry price for long positions")

            # Warning for very tight stops
            if sl > entry * Decimal("0.98"):
                warnings.append("Stop loss is very close to entry (< 2% buffer)")

        else:  # Sell/Short
            # For short: TP should be below entry, SL above entry
            if tp >= entry:
                errors.append("Take profit must be below entry price for short positions")
            if sl <= entry:
                errors.append("Stop loss must be above entry price for short positions")

            # Warning for very tight stops
            if sl < entry * Decimal("1.02"):
                warnings.append("Stop loss is very close to entry (< 2% buffer)")

        # Risk/Reward validation
        if side == "Buy":
            risk = entry - sl
            reward = tp - entry
        else:
            risk = sl - entry
            reward = entry - tp

        rr_ratio = Decimal("0")
        if risk > 0 and reward > 0:
            rr_ratio = reward / risk
            if rr_ratio < Decimal("0.5"):
                warnings.append(f"Poor risk/reward ratio: 1:{rr_ratio:.2f}")
            elif rr_ratio < 1:
                warnings.append(f"Risk/reward ratio below 1:1 (1:{rr_ratio:.2f})")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "risk_reward_ratio": float(rr_ratio) if risk > 0 else 0
        }

    except Exception as e:
        logger.error(f"Error validating price levels: {e}")
        return {
            "valid": False,
            "errors": [f"Validation error: {str(e)}"],
            "warnings": []
        }

def generate_trade_hash(symbol: str, side: str, entry_price: Decimal,
                       size: Decimal, timestamp: float) -> str:
    """
    Generate a unique hash for a trade to prevent duplicates

    Args:
        symbol: Trading symbol
        side: Buy or Sell
        entry_price: Entry price
        size: Position size
        timestamp: Trade timestamp

    Returns:
        Unique trade hash
    """
    try:
        # Create a unique string from trade parameters
        trade_str = f"{symbol}_{side}_{entry_price}_{size}_{int(timestamp)}"

        # Generate hash
        return hashlib.sha256(trade_str.encode()).hexdigest()[:16]

    except Exception as e:
        logger.error(f"Error generating trade hash: {e}")
        # Fallback to UUID
        return str(uuid.uuid4())[:16]

def calculate_required_margin(position_size: Decimal, leverage: int) -> Decimal:
    """
    Calculate required margin for a position

    Args:
        position_size: Total position size in USDT
        leverage: Leverage multiplier

    Returns:
        Required margin amount
    """
    try:
        position_size = safe_decimal_conversion(position_size)
        leverage = int(leverage) if leverage else 1

        if leverage <= 0:
            leverage = 1

        return position_size / leverage

    except Exception as e:
        logger.error(f"Error calculating required margin: {e}")
        return position_size  # Fallback to full position size

def format_order_summary(orders: list) -> str:
    """
    Format a list of orders into a readable summary

    Args:
        orders: List of order descriptions

    Returns:
        Formatted summary string
    """
    if not orders:
        return "No orders placed"

    if len(orders) == 1:
        return orders[0]

    if len(orders) == 2:
        return f"{orders[0]} and {orders[1]}"

    # More than 2 orders
    return f"{', '.join(orders[:-1])}, and {orders[-1]}"

def estimate_fees(position_size: Decimal, fee_rate: Decimal = Decimal("0.0006")) -> Dict[str, Decimal]:
    """
    Estimate trading fees for a position

    Args:
        position_size: Total position size
        fee_rate: Fee rate (default 0.06% for market orders)

    Returns:
        Dict with fee estimates
    """
    try:
        position_size = safe_decimal_conversion(position_size)

        # Entry fee (market order)
        entry_fee = position_size * fee_rate

        # Exit fee (assume limit order at 0.01%)
        exit_fee = position_size * Decimal("0.0001")

        # Total round trip
        total_fees = entry_fee + exit_fee

        return {
            "entry_fee": entry_fee,
            "exit_fee": exit_fee,
            "total_fees": total_fees,
            "fee_percentage": (total_fees / position_size * 100) if position_size > 0 else Decimal("0")
        }

    except Exception as e:
        logger.error(f"Error estimating fees: {e}")
        return {
            "entry_fee": Decimal("0"),
            "exit_fee": Decimal("0"),
            "total_fees": Decimal("0"),
            "fee_percentage": Decimal("0")
        }

def validate_trade_execution_data(chat_data: dict) -> Dict[str, Any]:
    """
    REFINED: Validate trade execution data for completeness

    Args:
        chat_data: Chat data dict containing trade information

    Returns:
        Validation results
    """
    required_fields = {
        SYMBOL: "Trading symbol",
        SIDE: "Trade direction (Buy/Sell)",
        MARGIN_AMOUNT: "Margin amount",
        LEVERAGE: "Leverage",
        TP1_PRICE: "Take profit price",
        SL_PRICE: "Stop loss price"
    }

    errors = []
    warnings = []

    # Check required fields
    for field, description in required_fields.items():
        value = chat_data.get(field)
        if not value:
            errors.append(f"Missing {description}")

    # Validate numeric values
    margin = safe_decimal_conversion(chat_data.get(MARGIN_AMOUNT, 0))
    if margin <= 0:
        errors.append("Margin amount must be positive")

    leverage = int(chat_data.get(LEVERAGE, 0) or 0)
    if leverage <= 0 or leverage > 100:
        errors.append("Leverage must be between 1 and 100")

    # Validate approach-specific data
    approach = chat_data.get(TRADING_APPROACH, "fast")
    if approach == "conservative":
        # Check for limit prices
        has_limits = any(chat_data.get(f"limit{i}_price") for i in range(1, 5))
        if not has_limits:
            errors.append("Conservative approach requires at least one limit price")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "approach": approach
    }

# =============================================
# NEW: ADDITIONAL HELPER FUNCTIONS
# =============================================

def generate_order_link_id() -> str:
    """Generate a unique order link ID"""
    return str(uuid.uuid4())

def get_current_timestamp() -> float:
    """Get current timestamp"""
    return time.time()

def format_trade_summary(trade_data: Dict[str, Any]) -> str:
    """
    Format trade data into a readable summary

    Args:
        trade_data: Dict containing trade information

    Returns:
        Formatted summary string
    """
    try:
        symbol = trade_data.get("symbol", "Unknown")
        side = trade_data.get("side", "Unknown")
        size = safe_decimal_conversion(trade_data.get("size", 0))
        entry = safe_decimal_conversion(trade_data.get("entry_price", 0))
        pnl = safe_decimal_conversion(trade_data.get("pnl", 0))

        summary = f"{symbol} {side} {size}"
        if entry > 0:
            summary += f" @ {entry}"
        if pnl != 0:
            summary += f" P&L: {pnl:+.2f}"

        return summary

    except Exception as e:
        logger.error(f"Error formatting trade summary: {e}")
        return "Trade summary unavailable"

# Export all functions
__all__ = [
    # Existing functions
    'get_field_emoji_and_name',
    '_adjust_value',
    'adjust_price',
    'adjust_qty',
    'value_adjusted_to_step',
    'safe_decimal_conversion',
    'validate_decimal_precision',
    'initialize_chat_data',
    # New P&L and validation functions
    'calculate_position_value',
    'calculate_pnl_from_prices',
    'calculate_percentage_change',
    'validate_price_levels',
    'generate_trade_hash',
    'calculate_required_margin',
    'format_order_summary',
    'estimate_fees',
    'validate_trade_execution_data',
    'generate_order_link_id',
    'get_current_timestamp',
    'format_trade_summary'
]