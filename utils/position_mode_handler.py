#!/usr/bin/env python3
"""
Position Mode Handler - CORRECTED VERSION for Hedge Mode.
Ensures reduce orders use the correct positionIdx in hedge mode.
"""

import logging
from typing import Dict, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class PositionModeHandler:
    """Handles position mode detection and automatic parameter injection."""

    def __init__(self):
        self.position_mode_cache = {}
        self.enabled = True
        self.positions_data = {}  # Cache full position data

    def get_position_info(self, client, symbol: str) -> Optional[Dict]:
        """Get position information including mode and indices."""
        try:
            cache_key = f"{id(client)}_{symbol}"

            # Check cache
            if cache_key in self.positions_data:
                cached_time, data = self.positions_data[cache_key]
                if time.time() - cached_time < 30:  # 30 second cache
                    return data

            # Get fresh position info
            response = client.get_positions(
                category="linear",
                symbol=symbol
            )

            if response['retCode'] == 0:
                positions = response['result']['list']

                # Determine position mode from any position
                position_mode = 0  # Default one-way
                active_positions = {}

                for pos in positions:
                    idx = pos.get('positionIdx', 0)
                    if idx > 0:
                        position_mode = 1  # Hedge mode

                    # Store active positions
                    if float(pos.get('size', 0)) > 0:
                        side = pos['side']
                        active_positions[side] = {
                            'idx': idx,
                            'size': float(pos['size']),
                            'avgPrice': float(pos.get('avgPrice', 0))
                        }

                result = {
                    'mode': position_mode,
                    'positions': active_positions
                }

                # Cache result
                self.positions_data[cache_key] = (time.time(), result)
                return result

            return None

        except Exception as e:
            logger.error(f"Error getting position info for {symbol}: {e}")
            return None

    def get_correct_position_idx(self, client, symbol: str, side: str, is_reduce_only: bool) -> Optional[int]:
        """Get the correct position index for an order."""
        try:
            pos_info = self.get_position_info(client, symbol)
            if not pos_info:
                return None

            position_mode = pos_info['mode']

            # One-way mode
            if position_mode == 0:
                return 0

            # Hedge mode
            if is_reduce_only:
                # For reduce orders (TP/SL), use the index of the position being reduced
                # A Sell reduce order reduces a Buy position (idx=1)
                # A Buy reduce order reduces a Sell position (idx=2)
                position_to_reduce = 'Buy' if side == 'Sell' else 'Sell'

                # Get the position being reduced
                if position_to_reduce in pos_info['positions']:
                    return pos_info['positions'][position_to_reduce]['idx']
                else:
                    # Default based on standard hedge mode
                    return 1 if position_to_reduce == 'Buy' else 2
            else:
                # For opening orders
                return 1 if side == 'Buy' else 2

        except Exception as e:
            logger.error(f"Error getting position idx: {e}")
            return None

    def wrap_place_order(self, original_method):
        """Wrap the place_order method to auto-inject correct positionIdx."""

        @wraps(original_method)
        def wrapper(self_client, **kwargs):
            try:
                # Only process linear orders
                if kwargs.get('category') != 'linear':
                    return original_method(self_client, **kwargs)

                symbol = kwargs.get('symbol')
                side = kwargs.get('side')
                if not symbol or not side:
                    return original_method(self_client, **kwargs)

                # Skip if positionIdx already provided correctly
                if 'positionIdx' in kwargs and kwargs['positionIdx'] is not None:
                    return original_method(self_client, **kwargs)

                # Get correct position index
                handler = globals().get('position_mode_handler')
                if handler and handler.enabled:
                    is_reduce = kwargs.get('reduceOnly', False)
                    position_idx = handler.get_correct_position_idx(self_client, symbol, side, is_reduce)

                    if position_idx is not None:
                        kwargs['positionIdx'] = position_idx
                        logger.debug(f"Set positionIdx={position_idx} for {symbol} {side} reduce={is_reduce}")

                return original_method(self_client, **kwargs)

            except Exception as e:
                logger.error(f"Error in place order wrapper: {e}")
                return original_method(self_client, **kwargs)

        return wrapper

    def clear_cache(self, symbol: Optional[str] = None):
        """Clear position cache."""
        if symbol:
            keys_to_remove = [k for k in self.positions_data.keys() if k.endswith(f"_{symbol}")]
            for key in keys_to_remove:
                del self.positions_data[key]
        else:
            self.positions_data.clear()


# Global instance
position_mode_handler = PositionModeHandler()


def inject_position_mode_handling():
    """Inject position mode handling into existing Bybit clients."""

    try:
        import time

        # Import the clients
        from clients.bybit_client import bybit_client

        # Check if client exists and has the HTTP client
        if hasattr(bybit_client, '_client') and bybit_client._client:
            http_client = bybit_client._client

            # Wrap place_order method
            if hasattr(http_client, 'place_order'):
                # Store original if not already wrapped
                if not hasattr(http_client.place_order, '_is_wrapped'):
                    original_place = http_client.place_order
                    wrapped_method = position_mode_handler.wrap_place_order(original_place)
                    wrapped_method._is_wrapped = True
                    http_client.place_order = wrapped_method
                    logger.info("✅ Updated position mode handling for main account")

        # Also handle mirror account if available
        try:
            from execution.mirror_trader import bybit_client_2

            if bybit_client_2:
                # Wrap place_order method
                if hasattr(bybit_client_2, 'place_order'):
                    if not hasattr(bybit_client_2.place_order, '_is_wrapped'):
                        original_place = bybit_client_2.place_order
                        wrapped_method = position_mode_handler.wrap_place_order(original_place)
                        wrapped_method._is_wrapped = True
                        bybit_client_2.place_order = wrapped_method
                        logger.info("✅ Updated position mode handling for mirror account")

        except ImportError:
            logger.debug("Mirror trader not available")

        return True

    except Exception as e:
        logger.error(f"Failed to inject position mode handling: {e}")
        return False


# Auto-inject when module is imported
logger.info("Position Mode Handler (Corrected) loaded")
inject_position_mode_handling()
