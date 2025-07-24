#!/usr/bin/env python3
"""
Input validation utilities for the trading bot
Ensures data integrity and prevents errors from invalid inputs
"""
import re
from decimal import Decimal, InvalidOperation
from typing import Optional, Union, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)

class ValidationError(ValueError):
    """Custom exception for validation errors"""
    pass

def validate_symbol(symbol: str) -> str:
    """
    Validate and normalize trading symbol

    Args:
        symbol: Trading symbol (e.g., BTCUSDT, BTC, btc-usdt)

    Returns:
        str: Normalized symbol (e.g., BTCUSDT)

    Raises:
        ValidationError: If symbol is invalid
    """
    if not symbol:
        raise ValidationError("Symbol cannot be empty")

    # Remove common separators and convert to uppercase
    normalized = symbol.upper().replace("-", "").replace("/", "").replace("_", "")

    # Ensure it ends with USDT if not already
    if not normalized.endswith("USDT"):
        normalized += "USDT"

    # Validate format (should be SYMBOLUSDT where SYMBOL is 2-10 chars)
    if not re.match(r'^[A-Z]{2,10}USDT$', normalized):
        raise ValidationError(f"Invalid symbol format: {symbol}")

    return normalized

def validate_decimal(
    value: Union[str, float, Decimal],
    min_value: Optional[Decimal] = None,
    max_value: Optional[Decimal] = None,
    decimal_places: Optional[int] = None
) -> Decimal:
    """
    Validate and convert to Decimal

    Args:
        value: Value to validate
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        decimal_places: Required decimal places

    Returns:
        Decimal: Validated decimal value

    Raises:
        ValidationError: If validation fails
    """
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as e:
        raise ValidationError(f"Invalid decimal value: {value}")

    if decimal_value.is_nan() or decimal_value.is_infinite():
        raise ValidationError(f"Invalid numeric value: {value}")

    if min_value is not None and decimal_value < min_value:
        raise ValidationError(f"Value {decimal_value} is below minimum {min_value}")

    if max_value is not None and decimal_value > max_value:
        raise ValidationError(f"Value {decimal_value} exceeds maximum {max_value}")

    if decimal_places is not None:
        # Check decimal places
        sign, digits, exponent = decimal_value.as_tuple()
        actual_places = -exponent if exponent < 0 else 0
        if actual_places > decimal_places:
            raise ValidationError(f"Too many decimal places: {actual_places} > {decimal_places}")

    return decimal_value

def validate_leverage(leverage: Union[int, str], max_leverage: int = 100) -> int:
    """
    Validate leverage value

    Args:
        leverage: Leverage value
        max_leverage: Maximum allowed leverage

    Returns:
        int: Validated leverage

    Raises:
        ValidationError: If leverage is invalid
    """
    try:
        leverage_int = int(leverage)
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid leverage value: {leverage}")

    if leverage_int < 1:
        raise ValidationError("Leverage must be at least 1")

    if leverage_int > max_leverage:
        raise ValidationError(f"Leverage {leverage_int} exceeds maximum {max_leverage}")

    return leverage_int

def validate_side(side: str) -> str:
    """
    Validate trade side

    Args:
        side: Trade side (buy/sell)

    Returns:
        str: Normalized side (Buy/Sell)

    Raises:
        ValidationError: If side is invalid
    """
    normalized = side.strip().capitalize()

    if normalized not in ["Buy", "Sell"]:
        # Try to match common variations
        if normalized.lower() in ["long", "buy", "b"]:
            return "Buy"
        elif normalized.lower() in ["short", "sell", "s"]:
            return "Sell"
        else:
            raise ValidationError(f"Invalid trade side: {side}")

    return normalized

def validate_percentage(
    value: Union[str, float, Decimal],
    allow_zero: bool = False
) -> Decimal:
    """
    Validate percentage value (0-100)

    Args:
        value: Percentage value
        allow_zero: Whether to allow 0%

    Returns:
        Decimal: Validated percentage

    Raises:
        ValidationError: If percentage is invalid
    """
    decimal_value = validate_decimal(value,
                                   min_value=Decimal("0") if allow_zero else Decimal("0.01"),
                                   max_value=Decimal("100"))
    return decimal_value

def validate_price(
    price: Union[str, float, Decimal],
    symbol: str,
    price_type: str = "limit"
) -> Decimal:
    """
    Validate price for a specific symbol

    Args:
        price: Price value
        symbol: Trading symbol
        price_type: Type of price (limit/stop)

    Returns:
        Decimal: Validated price

    Raises:
        ValidationError: If price is invalid
    """
    # Symbol-specific validation rules
    tick_sizes = {
        "BTC": Decimal("0.1"),
        "ETH": Decimal("0.01"),
        # Add more as needed
    }

    base_symbol = symbol.replace("USDT", "")
    tick_size = tick_sizes.get(base_symbol, Decimal("0.01"))

    decimal_price = validate_decimal(price, min_value=Decimal("0.00001"))

    # Ensure price is aligned to tick size
    remainder = decimal_price % tick_size
    if remainder != 0:
        # Round to nearest tick
        decimal_price = decimal_price - remainder
        if remainder >= tick_size / 2:
            decimal_price += tick_size

    return decimal_price

def validate_order_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate complete order parameters

    Args:
        params: Order parameters dictionary

    Returns:
        dict: Validated parameters

    Raises:
        ValidationError: If any parameter is invalid
    """
    validated = {}

    # Required fields
    required_fields = ["symbol", "side", "size"]
    for field in required_fields:
        if field not in params:
            raise ValidationError(f"Missing required field: {field}")

    # Validate each field
    validated["symbol"] = validate_symbol(params["symbol"])
    validated["side"] = validate_side(params["side"])
    validated["size"] = validate_decimal(params["size"], min_value=Decimal("0.001"))

    # Optional fields
    if "leverage" in params:
        validated["leverage"] = validate_leverage(params["leverage"])

    if "limit_price" in params:
        validated["limit_price"] = validate_price(
            params["limit_price"],
            validated["symbol"],
            "limit"
        )

    if "stop_price" in params:
        validated["stop_price"] = validate_price(
            params["stop_price"],
            validated["symbol"],
            "stop"
        )

    return validated

def sanitize_user_input(text: str, max_length: int = 100) -> str:
    """
    Sanitize user input for safety

    Args:
        text: User input text
        max_length: Maximum allowed length

    Returns:
        str: Sanitized text
    """
    if not text:
        return ""

    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>&"\']', '', text)

    # Limit length
    sanitized = sanitized[:max_length]

    # Remove excessive whitespace
    sanitized = ' '.join(sanitized.split())

    return sanitized.strip()