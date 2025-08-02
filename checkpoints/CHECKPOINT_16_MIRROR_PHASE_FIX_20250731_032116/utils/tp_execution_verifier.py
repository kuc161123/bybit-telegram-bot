#!/usr/bin/env python3
"""
TP Execution Verifier - Ensures TP orders actually close the expected position percentage
"""
import logging
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple
import asyncio
import time

from config.constants import *
from clients.bybit_helpers import get_position_info, place_order_with_retry
from utils.helpers import safe_decimal_conversion, value_adjusted_to_step
from utils.order_execution_guard import order_execution_guard

logger = logging.getLogger(__name__)

class TPExecutionVerifier:
    """Verifies that TP orders execute correctly and close the expected position amount"""

    def __init__(self):
        self.verification_history = {}  # Track verification attempts
        self.max_retries = 3
        self.retry_delay = 2.0

    async def verify_tp_execution(
        self,
        symbol: str,
        tp_number: int,
        expected_percentage: float,
        position_before: Dict[str, Any],
        position_after: Dict[str, Any],
        chat_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Verify that a TP execution actually closed the expected percentage of position

        Args:
            symbol: Trading symbol
            tp_number: Which TP (1, 2, 3, or 4)
            expected_percentage: Expected percentage to close (e.g., 0.85 for 85%)
            position_before: Position data before TP hit
            position_after: Position data after TP hit
            chat_data: Chat data containing position info

        Returns:
            Dict with verification results and any corrective actions taken
        """
        try:
            # Get position sizes
            size_before = safe_decimal_conversion(position_before.get("size", "0"))
            size_after = safe_decimal_conversion(position_after.get("size", "0"))

            if size_before == 0:
                logger.error(f"❌ Cannot verify TP{tp_number} execution - no position before")
                return {
                    "verified": False,
                    "error": "No position before TP",
                    "size_before": 0,
                    "size_after": float(size_after)
                }

            # Calculate actual reduction
            size_reduced = size_before - size_after
            actual_percentage = float(size_reduced / size_before) if size_before > 0 else 0
            expected_reduction = size_before * Decimal(str(expected_percentage))

            # Allow 5% tolerance for rounding/fees
            tolerance = 0.05
            percentage_diff = abs(actual_percentage - expected_percentage)

            result = {
                "verified": percentage_diff <= tolerance,
                "tp_number": tp_number,
                "expected_percentage": expected_percentage,
                "actual_percentage": actual_percentage,
                "size_before": float(size_before),
                "size_after": float(size_after),
                "size_reduced": float(size_reduced),
                "expected_reduction": float(expected_reduction),
                "percentage_diff": percentage_diff
            }

            if result["verified"]:
                logger.info(
                    f"✅ TP{tp_number} execution verified: "
                    f"Expected {expected_percentage*100:.0f}%, "
                    f"Actual {actual_percentage*100:.1f}% "
                    f"(within {tolerance*100}% tolerance)"
                )
            else:
                logger.error(
                    f"❌ TP{tp_number} execution MISMATCH: "
                    f"Expected {expected_percentage*100:.0f}%, "
                    f"Actual {actual_percentage*100:.1f}% "
                    f"(diff: {percentage_diff*100:.1f}%)"
                )

                # If significant mismatch, attempt corrective action
                if size_after > 0 and actual_percentage < expected_percentage * 0.5:
                    # TP closed less than half of expected amount
                    result["corrective_action"] = await self._attempt_corrective_closure(
                        symbol, tp_number, size_before, size_after,
                        expected_percentage, actual_percentage, chat_data
                    )

            # Store verification history
            verification_key = f"{symbol}_{tp_number}_{int(time.time())}"
            self.verification_history[verification_key] = result

            return result

        except Exception as e:
            logger.error(f"Error verifying TP{tp_number} execution: {e}")
            return {
                "verified": False,
                "error": str(e),
                "tp_number": tp_number
            }

    async def _attempt_corrective_closure(
        self,
        symbol: str,
        tp_number: int,
        size_before: Decimal,
        size_after: Decimal,
        expected_percentage: float,
        actual_percentage: float,
        chat_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Attempt to close additional position if TP didn't close enough
        """
        try:
            # First check if position still exists to prevent "zero position" errors
            if not await order_execution_guard.prevent_zero_position_errors(symbol):
                return {
                    "action": "aborted",
                    "reason": "No active position - preventing zero position error"
                }
            # Calculate how much more needs to be closed
            expected_final_size = size_before * Decimal(str(1 - expected_percentage))
            additional_close_needed = size_after - expected_final_size

            if additional_close_needed <= 0:
                return {"action": "none", "reason": "No additional closure needed"}

            # Get current market price
            positions = await get_position_info(symbol)
            if not positions:
                return {"action": "failed", "reason": "Could not get current position"}

            position = next((p for p in positions if float(p.get("size", 0)) > 0), None)
            if not position:
                return {"action": "failed", "reason": "Position no longer exists"}

            current_price = safe_decimal_conversion(position.get("markPrice", "0"))
            side = position.get("side")

            # Place market order to close the remaining amount
            close_side = "Sell" if side == "Buy" else "Buy"
            qty_step = safe_decimal_conversion(chat_data.get(INSTRUMENT_QTY_STEP, "0.001"))
            close_qty = value_adjusted_to_step(additional_close_needed, qty_step)

            logger.warning(
                f"⚠️ Attempting corrective closure for TP{tp_number}: "
                f"Closing additional {close_qty} at market"
            )

            # Create order link ID for tracking
            order_link_id = f"BOT_TP{tp_number}_CORRECTIVE_{int(time.time())}"

            result = await place_order_with_retry(
                symbol=symbol,
                side=close_side,
                order_type="Market",
                qty=str(close_qty),
                reduce_only=True,
                order_link_id=order_link_id
            )

            if result:
                return {
                    "action": "corrective_order_placed",
                    "order_id": result.get("orderId"),
                    "qty": float(close_qty),
                    "side": close_side,
                    "reason": f"TP{tp_number} only closed {actual_percentage*100:.1f}% instead of {expected_percentage*100:.0f}%"
                }
            else:
                return {
                    "action": "failed",
                    "reason": "Could not place corrective order"
                }

        except Exception as e:
            logger.error(f"Error attempting corrective closure: {e}")
            return {
                "action": "error",
                "reason": str(e)
            }

    async def check_position_sync(
        self,
        symbol: str,
        expected_size: Decimal,
        chat_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[Decimal]]:
        """
        Check if actual position size matches expected size

        Returns:
            Tuple of (is_synced, actual_size)
        """
        try:
            positions = await get_position_info(symbol)
            if not positions:
                return False, Decimal("0")

            position = next((p for p in positions if float(p.get("size", 0)) > 0), None)
            if not position:
                return expected_size == 0, Decimal("0")

            actual_size = safe_decimal_conversion(position.get("size", "0"))
            qty_step = safe_decimal_conversion(chat_data.get(INSTRUMENT_QTY_STEP, "0.001"))

            # Allow for one qty_step difference due to rounding
            size_diff = abs(actual_size - expected_size)
            is_synced = size_diff <= qty_step

            if not is_synced:
                logger.warning(
                    f"⚠️ Position size mismatch for {symbol}: "
                    f"Expected {expected_size}, Actual {actual_size}, "
                    f"Diff {size_diff}"
                )

            return is_synced, actual_size

        except Exception as e:
            logger.error(f"Error checking position sync: {e}")
            return False, None

    def get_verification_summary(self, symbol: str = None) -> Dict[str, Any]:
        """Get summary of verification history"""
        if symbol:
            symbol_verifications = [
                v for k, v in self.verification_history.items()
                if k.startswith(f"{symbol}_")
            ]
        else:
            symbol_verifications = list(self.verification_history.values())

        if not symbol_verifications:
            return {
                "total_verifications": 0,
                "successful": 0,
                "failed": 0,
                "corrective_actions": 0
            }

        return {
            "total_verifications": len(symbol_verifications),
            "successful": sum(1 for v in symbol_verifications if v.get("verified")),
            "failed": sum(1 for v in symbol_verifications if not v.get("verified")),
            "corrective_actions": sum(
                1 for v in symbol_verifications
                if v.get("corrective_action", {}).get("action") == "corrective_order_placed"
            ),
            "recent_failures": [
                v for v in symbol_verifications[-5:]
                if not v.get("verified")
            ]
        }

# Global instance
tp_execution_verifier = TPExecutionVerifier()

__all__ = ['tp_execution_verifier', 'TPExecutionVerifier']