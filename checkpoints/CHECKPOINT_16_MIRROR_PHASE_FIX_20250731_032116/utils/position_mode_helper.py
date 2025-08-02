#!/usr/bin/env python3
"""
Integration helper for position mode protection.
Import this in any module that places orders.
"""

from utils.position_mode_handler import ensure_position_mode_compatibility, position_mode_handler
from utils.position_mode_monitor import handle_order_error
import logging

logger = logging.getLogger(__name__)


async def safe_place_order(client, **kwargs):
    """Safely place an order with position mode handling."""

    symbol = kwargs.get('symbol', 'Unknown')

    # Ensure position mode compatibility
    kwargs = ensure_position_mode_compatibility(client, symbol, kwargs)

    try:
        # Place the order
        response = await client.place_order(**kwargs)

        # Check for position mode errors
        if response.get('retCode') != 0:
            error_info = handle_order_error(response.get('retMsg', ''), symbol)

            if error_info['is_position_mode_error']:
                logger.warning(f"Position mode error for {symbol}, retrying...")

                # Clear cache and retry
                position_mode_handler.clear_cache(symbol)
                kwargs = ensure_position_mode_compatibility(client, symbol, kwargs)
                response = await client.place_order(**kwargs)

        return response

    except Exception as e:
        logger.error(f"Error placing order for {symbol}: {e}")
        raise


async def safe_cancel_order(client, **kwargs):
    """Safely cancel an order with position mode handling."""

    symbol = kwargs.get('symbol', 'Unknown')

    try:
        # First attempt
        response = await client.cancel_order(**kwargs)

        # Check for position mode errors
        if response.get('retCode') == 10001 and 'position idx' in response.get('retMsg', '').lower():
            # Detect position mode and retry
            position_idx = position_mode_handler.detect_position_mode(client, symbol)
            if position_idx is not None:
                kwargs['positionIdx'] = position_idx
                response = await client.cancel_order(**kwargs)

        return response

    except Exception as e:
        logger.error(f"Error cancelling order for {symbol}: {e}")
        raise


# Monkey patch for immediate protection
def inject_safe_methods():
    """Inject safe methods into existing modules."""
    try:
        # Patch into trader module if available
        import execution.trader as trader
        if hasattr(trader, 'place_order'):
            trader._original_place_order = trader.place_order
            trader.place_order = safe_place_order
            logger.info("✅ Injected safe_place_order into trader module")

    except Exception as e:
        logger.debug(f"Could not patch trader module: {e}")


# Auto-inject when imported
inject_safe_methods()
