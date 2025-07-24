#!/usr/bin/env python3
"""
Quantity Formatter - Ensures proper decimal formatting for trading quantities
Prevents scientific notation and ensures exchange-compatible formatting
"""
import logging
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Union, Optional

logger = logging.getLogger(__name__)

def format_quantity_for_exchange(
    quantity: Union[Decimal, float, str],
    qty_step: Union[Decimal, float, str],
    min_qty: Optional[Union[Decimal, float, str]] = None,
    max_qty: Optional[Union[Decimal, float, str]] = None
) -> str:
    """
    Format quantity for exchange API calls, preventing scientific notation.

    Args:
        quantity: The quantity to format
        qty_step: The minimum step size for the instrument
        min_qty: Minimum allowed quantity (optional)
        max_qty: Maximum allowed quantity (optional)

    Returns:
        String representation of quantity suitable for exchange API
    """
    try:
        # Convert to Decimal for precise arithmetic
        qty_decimal = Decimal(str(quantity))
        step_decimal = Decimal(str(qty_step))

        # Handle zero quantity
        if qty_decimal <= 0:
            logger.warning(f"Zero or negative quantity provided: {quantity}")
            return "0"

        # Adjust to step size
        if step_decimal > 0:
            # Calculate number of steps
            steps = (qty_decimal / step_decimal).quantize(Decimal('1'), rounding=ROUND_DOWN)
            adjusted_qty = steps * step_decimal
        else:
            adjusted_qty = qty_decimal

        # Apply min/max constraints
        if min_qty is not None:
            min_qty_decimal = Decimal(str(min_qty))
            if adjusted_qty < min_qty_decimal:
                logger.warning(f"Quantity {adjusted_qty} below minimum {min_qty_decimal}")
                adjusted_qty = min_qty_decimal

        if max_qty is not None:
            max_qty_decimal = Decimal(str(max_qty))
            if adjusted_qty > max_qty_decimal:
                logger.warning(f"Quantity {adjusted_qty} above maximum {max_qty_decimal}")
                adjusted_qty = max_qty_decimal

        # Determine decimal places from step size
        step_str = str(step_decimal)
        if '.' in step_str:
            decimal_places = len(step_str.split('.')[-1])
        else:
            decimal_places = 0

        # Format with proper decimal places
        if decimal_places > 0:
            # Use fixed-point notation to prevent scientific notation
            format_str = f"{{:.{decimal_places}f}}"
            result = format_str.format(adjusted_qty)
            # Remove trailing zeros but keep at least one decimal place if needed
            if '.' in result:
                result = result.rstrip('0')
                if result.endswith('.'):
                    result = result[:-1]
        else:
            # Integer quantity
            result = str(int(adjusted_qty))

        # Final validation - ensure no scientific notation
        if 'e' in result.lower():
            logger.error(f"Scientific notation detected in formatted quantity: {result}")
            # Force decimal formatting
            if decimal_places > 0:
                result = f"{float(adjusted_qty):.{decimal_places}f}".rstrip('0').rstrip('.')
            else:
                result = str(int(float(adjusted_qty)))

        # Validate the result is a valid number
        try:
            float(result)
        except ValueError:
            logger.error(f"Invalid quantity format: {result}")
            return "0"

        logger.debug(f"Formatted quantity: {quantity} -> {result} (step: {qty_step})")
        return result

    except Exception as e:
        logger.error(f"Error formatting quantity: {e}, quantity={quantity}, step={qty_step}")
        # Return safe fallback
        try:
            # Attempt basic formatting
            return str(float(quantity))
        except:
            return "0"

def validate_quantity_for_order(
    quantity: str,
    symbol: str = "UNKNOWN"
) -> bool:
    """
    Validate that a quantity string is suitable for order placement.

    Args:
        quantity: String representation of quantity
        symbol: Trading symbol for logging

    Returns:
        True if valid, False otherwise
    """
    try:
        # Check for scientific notation
        if 'e' in quantity.lower():
            logger.error(f"Scientific notation in quantity for {symbol}: {quantity}")
            return False

        # Check if it's a valid number
        qty_float = float(quantity)

        # Check for extremely small values that might cause issues
        if qty_float < 1e-8 and qty_float != 0:
            logger.error(f"Quantity too small for {symbol}: {quantity}")
            return False

        # Check for NaN or infinity
        if not (qty_float == qty_float) or qty_float == float('inf'):
            logger.error(f"Invalid quantity (NaN/Inf) for {symbol}: {quantity}")
            return False

        return True

    except Exception as e:
        logger.error(f"Invalid quantity format for {symbol}: {quantity}, error: {e}")
        return False

# Export convenience function
def safe_qty_string(
    qty: Union[Decimal, float, str],
    qty_step: Union[Decimal, float, str] = "0.001"
) -> str:
    """
    Convert any quantity to a safe string representation for API calls.

    Args:
        qty: Quantity in any numeric format
        qty_step: Step size (default 0.001)

    Returns:
        Safe string representation
    """
    return format_quantity_for_exchange(qty, qty_step)