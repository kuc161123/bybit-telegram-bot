#!/usr/bin/env python3
"""
Position Size Tracker - Tracks position size changes and triggers order updates when needed
"""

import logging
from decimal import Decimal
from typing import Dict, Optional, List, Tuple
import time
import asyncio

from clients.bybit_helpers import get_position_info, get_open_orders
from utils.helpers import safe_decimal_conversion
from config.constants import BOT_PREFIX

logger = logging.getLogger(__name__)


class PositionSizeTracker:
    """Tracks position size changes and ensures orders stay synchronized"""

    def __init__(self):
        self.position_history = {}  # symbol -> list of (timestamp, size)
        self.last_known_sizes = {}  # symbol -> size
        self.size_change_callbacks = {}  # symbol -> list of callbacks
        self.max_history_per_symbol = 100

    def track_position_change(self, symbol: str, new_size: Decimal) -> Optional[Decimal]:
        """
        Track a position size change and return the size difference

        Returns:
            Size difference (positive for increase, negative for decrease)
        """
        old_size = self.last_known_sizes.get(symbol, Decimal('0'))
        size_diff = new_size - old_size

        if size_diff != 0:
            # Record the change
            self.last_known_sizes[symbol] = new_size

            # Add to history
            if symbol not in self.position_history:
                self.position_history[symbol] = []

            history = self.position_history[symbol]
            history.append((time.time(), float(new_size)))

            # Limit history size
            if len(history) > self.max_history_per_symbol:
                history.pop(0)

            logger.info(
                f"📊 Position size change detected for {symbol}: "
                f"{old_size} -> {new_size} (diff: {size_diff:+.4f})"
            )

            # Trigger callbacks
            if symbol in self.size_change_callbacks:
                for callback in self.size_change_callbacks[symbol]:
                    try:
                        asyncio.create_task(callback(symbol, old_size, new_size, size_diff))
                    except Exception as e:
                        logger.error(f"Error in position size change callback: {e}")

            return size_diff

        return None

    def register_size_change_callback(self, symbol: str, callback):
        """Register a callback for position size changes"""
        if symbol not in self.size_change_callbacks:
            self.size_change_callbacks[symbol] = []
        self.size_change_callbacks[symbol].append(callback)

    def get_position_history(self, symbol: str, lookback_seconds: int = 300) -> List[Tuple[float, float]]:
        """Get position size history for a symbol"""
        if symbol not in self.position_history:
            return []

        cutoff_time = time.time() - lookback_seconds
        history = self.position_history[symbol]

        return [(ts, size) for ts, size in history if ts >= cutoff_time]

    async def detect_position_merge(self, symbol: str) -> bool:
        """
        Detect if a position merge happened by analyzing size changes

        A merge is likely if:
        - Position size increased significantly (>10%)
        - Multiple orders were placed recently
        """
        history = self.get_position_history(symbol, lookback_seconds=60)

        if len(history) < 2:
            return False

        # Check for significant size increase
        prev_size = history[-2][1]
        curr_size = history[-1][1]

        if prev_size == 0:
            return False

        size_increase_pct = (curr_size - prev_size) / prev_size

        if size_increase_pct > 0.1:  # >10% increase
            logger.info(f"🔄 Possible position merge detected for {symbol}: {size_increase_pct*100:.1f}% increase")
            return True

        return False

    async def validate_order_quantities(self, symbol: str) -> Dict:
        """
        Validate that all TP/SL order quantities match current position size

        Returns:
            Dict with validation results and any mismatches found
        """
        try:
            # Get current position
            positions = await get_position_info(symbol)
            if not positions:
                return {'valid': False, 'error': 'No position found'}

            position = next((p for p in positions if float(p.get('size', 0)) > 0), None)
            if not position:
                return {'valid': False, 'error': 'No active position'}

            position_size = safe_decimal_conversion(position.get('size', '0'))

            # Get all orders
            orders = await get_open_orders(symbol)

            # Separate order types
            tp_orders = []
            sl_orders = []

            for order in orders:
                if not order.get('reduceOnly'):
                    continue

                link_id = order.get('orderLinkId', '')
                if 'TP' in link_id:
                    tp_orders.append(order)
                elif 'SL' in link_id:
                    sl_orders.append(order)

            # Validate TP orders
            tp_total = sum(safe_decimal_conversion(o.get('qty', '0')) for o in tp_orders)
            tp_valid = abs(tp_total - position_size) <= position_size * Decimal('0.01')  # 1% tolerance

            # Validate SL orders
            sl_total = sum(safe_decimal_conversion(o.get('qty', '0')) for o in sl_orders)
            sl_valid = abs(sl_total - position_size) <= position_size * Decimal('0.01')  # 1% tolerance

            # Prepare results
            result = {
                'valid': tp_valid and sl_valid,
                'position_size': float(position_size),
                'tp_orders': {
                    'count': len(tp_orders),
                    'total_qty': float(tp_total),
                    'valid': tp_valid,
                    'diff': float(tp_total - position_size)
                },
                'sl_orders': {
                    'count': len(sl_orders),
                    'total_qty': float(sl_total),
                    'valid': sl_valid,
                    'diff': float(sl_total - position_size)
                }
            }

            if not result['valid']:
                mismatches = []
                if not tp_valid:
                    mismatches.append(f"TP orders: {tp_total} vs position: {position_size}")
                if not sl_valid:
                    mismatches.append(f"SL orders: {sl_total} vs position: {position_size}")
                result['mismatches'] = mismatches

                logger.warning(f"⚠️ Order quantity mismatches found for {symbol}: {', '.join(mismatches)}")

            return result

        except Exception as e:
            logger.error(f"Error validating order quantities: {e}")
            return {'valid': False, 'error': str(e)}

    def clear_history(self, symbol: str = None):
        """Clear position history for a symbol or all symbols"""
        if symbol:
            if symbol in self.position_history:
                del self.position_history[symbol]
            if symbol in self.last_known_sizes:
                del self.last_known_sizes[symbol]
        else:
            self.position_history.clear()
            self.last_known_sizes.clear()


# Global instance
position_size_tracker = PositionSizeTracker()

__all__ = ['position_size_tracker', 'PositionSizeTracker']