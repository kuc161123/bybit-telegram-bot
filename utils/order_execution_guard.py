#!/usr/bin/env python3
"""
Order Execution Guard - Prevents TP/SL execution failures by validating and adjusting quantities before execution
"""

import logging
from decimal import Decimal
from typing import Dict, Optional, Tuple, List
import asyncio

from clients.bybit_helpers import (
    get_position_info, get_open_orders,
    cancel_order_with_retry, place_order_with_retry
)
from utils.helpers import safe_decimal_conversion, value_adjusted_to_step
from config.constants import BOT_PREFIX

logger = logging.getLogger(__name__)


class OrderExecutionGuard:
    """Guards against TP/SL execution failures by ensuring order quantities match position sizes"""

    def __init__(self):
        self.validation_history = {}
        self.correction_count = 0
        self.max_correction_attempts = 3

    async def validate_before_execution(
        self,
        symbol: str,
        order: Dict,
        expected_percentage: float = None
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Validate an order before it executes

        Returns:
            Tuple of (is_valid, correction_needed)
        """
        try:
            order_id = order.get('orderId', '')
            order_qty = safe_decimal_conversion(order.get('qty', '0'))
            order_side = order.get('side')
            order_link_id = order.get('orderLinkId', '')

            # Get current position
            positions = await get_position_info(symbol)
            if not positions:
                logger.error(f"❌ No position found for {symbol} - order {order_id[:8]}... may fail")
                return False, None

            position = next((p for p in positions if float(p.get('size', 0)) > 0), None)
            if not position:
                logger.error(f"❌ No active position for {symbol} - order {order_id[:8]}... will fail")
                return False, None

            position_size = safe_decimal_conversion(position.get('size', '0'))
            position_side = position.get('side')

            # Validate order is for correct position side
            expected_order_side = "Sell" if position_side == "Buy" else "Buy"
            if order_side != expected_order_side:
                logger.error(f"❌ Order side mismatch: Order is {order_side}, Position is {position_side}")
                return False, None

            # Check if order quantity exceeds position size
            if order_qty > position_size:
                logger.warning(
                    f"⚠️ Order quantity ({order_qty}) exceeds position size ({position_size}) "
                    f"for {symbol} order {order_id[:8]}..."
                )

                # Determine correction needed
                correction = {
                    'order_id': order_id,
                    'current_qty': float(order_qty),
                    'correct_qty': float(position_size),
                    'order_link_id': order_link_id,
                    'trigger_price': order.get('triggerPrice'),
                    'stop_order_type': order.get('stopOrderType'),
                    'side': order_side,
                    'position_idx': position.get('positionIdx', 0)
                }

                # If expected percentage provided, calculate correct quantity
                if expected_percentage and expected_percentage < 1.0:
                    correction['correct_qty'] = float(position_size * Decimal(str(expected_percentage)))

                return False, correction

            # Check if it's a TP1 order (85%) and validate quantity
            if 'TP1' in order_link_id and expected_percentage == 0.85:
                expected_qty = position_size * Decimal('0.85')
                qty_diff = abs(order_qty - expected_qty)

                # Allow 5% tolerance
                if qty_diff > position_size * Decimal('0.05'):
                    logger.warning(
                        f"⚠️ TP1 quantity mismatch: Order has {order_qty}, "
                        f"Expected {expected_qty} (85% of {position_size})"
                    )

                    correction = {
                        'order_id': order_id,
                        'current_qty': float(order_qty),
                        'correct_qty': float(expected_qty),
                        'order_link_id': order_link_id,
                        'trigger_price': order.get('triggerPrice'),
                        'stop_order_type': order.get('stopOrderType', 'TakeProfit'),
                        'side': order_side,
                        'position_idx': position.get('positionIdx', 0)
                    }

                    return False, correction

            # Order appears valid
            logger.info(f"✅ Order {order_id[:8]}... validated: {order_qty} units for position of {position_size}")
            return True, None

        except Exception as e:
            logger.error(f"Error validating order: {e}")
            return False, None

    async def correct_order_quantity(
        self,
        symbol: str,
        correction: Dict,
        qty_step: Decimal
    ) -> bool:
        """
        Correct an order by cancelling and replacing with proper quantity
        """
        try:
            order_id = correction['order_id']
            current_qty = correction['current_qty']
            correct_qty = correction['correct_qty']

            logger.info(f"🔧 Correcting order {order_id[:8]}... quantity: {current_qty} -> {correct_qty}")

            # Cancel the incorrect order
            cancel_result = await cancel_order_with_retry(
                symbol=symbol,
                order_id=order_id
            )

            if not cancel_result:
                logger.error(f"❌ Failed to cancel incorrect order {order_id[:8]}...")
                return False

            # Wait a moment for cancellation to process
            await asyncio.sleep(0.5)

            # Place new order with correct quantity
            adjusted_qty = value_adjusted_to_step(Decimal(str(correct_qty)), qty_step)

            # Generate new order link ID to avoid duplicates
            import time
            new_link_id = f"{correction['order_link_id']}_CORRECTED_{int(time.time())}"
            if len(new_link_id) > 45:  # Bybit limit
                new_link_id = f"{BOT_PREFIX}CORRECTED_{int(time.time())}"

            place_result = await place_order_with_retry(
                symbol=symbol,
                side=correction['side'],
                order_type="Market",
                qty=str(adjusted_qty),
                trigger_price=correction['trigger_price'],
                position_idx=correction['position_idx'],
                reduce_only=True,
                order_link_id=new_link_id,
                stop_order_type=correction['stop_order_type']
            )

            if place_result:
                new_order_id = place_result.get('orderId', '')
                logger.info(f"✅ Placed corrected order {new_order_id[:8]}... with quantity {adjusted_qty}")
                self.correction_count += 1
                return True
            else:
                logger.error(f"❌ Failed to place corrected order")
                return False

        except Exception as e:
            logger.error(f"Error correcting order quantity: {e}")
            return False

    async def validate_all_tp_orders(self, symbol: str) -> Dict:
        """
        Validate all TP orders for a position and return status
        """
        try:
            # Get position
            positions = await get_position_info(symbol)
            if not positions:
                return {'valid': False, 'error': 'No position found'}

            position = next((p for p in positions if float(p.get('size', 0)) > 0), None)
            if not position:
                return {'valid': False, 'error': 'No active position'}

            position_size = safe_decimal_conversion(position.get('size', '0'))
            position_side = position.get('side')

            # Get all orders
            orders = await get_open_orders(symbol)

            # Filter TP orders
            tp_orders = []
            for order in orders:
                if not order.get('reduceOnly'):
                    continue

                link_id = order.get('orderLinkId', '')
                if 'TP' in link_id:
                    tp_orders.append(order)

            if not tp_orders:
                return {'valid': True, 'tp_count': 0, 'total_qty': 0}

            # Calculate total TP quantity
            total_tp_qty = sum(safe_decimal_conversion(o.get('qty', '0')) for o in tp_orders)

            # Validate total matches position
            qty_diff = abs(total_tp_qty - position_size)
            is_valid = qty_diff <= position_size * Decimal('0.01')  # 1% tolerance

            result = {
                'valid': is_valid,
                'tp_count': len(tp_orders),
                'total_qty': float(total_tp_qty),
                'position_size': float(position_size),
                'qty_diff': float(qty_diff),
                'tp_orders': tp_orders
            }

            if not is_valid:
                logger.warning(
                    f"⚠️ TP orders total quantity ({total_tp_qty}) doesn't match "
                    f"position size ({position_size}) for {symbol}"
                )

            return result

        except Exception as e:
            logger.error(f"Error validating TP orders: {e}")
            return {'valid': False, 'error': str(e)}

    async def prevent_zero_position_errors(self, symbol: str) -> bool:
        """
        Check if position exists before attempting any reduce-only operations
        """
        try:
            positions = await get_position_info(symbol)
            if not positions:
                logger.warning(f"⚠️ No position data for {symbol} - stopping operations")
                return False

            has_position = any(float(p.get('size', 0)) > 0 for p in positions)

            if not has_position:
                logger.warning(f"⚠️ No active position for {symbol} - preventing reduce-only operations")
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking position existence: {e}")
            return False


# Global instance
order_execution_guard = OrderExecutionGuard()

__all__ = ['order_execution_guard', 'OrderExecutionGuard']