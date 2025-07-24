#!/usr/bin/env python3
"""
Order Quantity Safeguard - Ensures orders have correct quantities before execution
"""
import logging
from decimal import Decimal
from typing import Dict, Any, Optional, List
import asyncio
import time

from config.constants import *
from clients.bybit_helpers import (
    get_order_info, get_position_info, amend_order_with_retry,
    cancel_order_with_retry, place_order_with_retry
)
from utils.helpers import safe_decimal_conversion, value_adjusted_to_step

logger = logging.getLogger(__name__)

class OrderQuantitySafeguard:
    """Monitors and corrects order quantities to ensure proper execution"""

    def __init__(self):
        self.monitored_orders = {}  # order_id -> order details
        self.correction_history = []
        self.max_correction_attempts = 3

    async def validate_tp_order_quantities(
        self,
        symbol: str,
        tp_order_ids: List[str],
        position_size: Decimal,
        approach: str,
        qty_step: Decimal
    ) -> Dict[str, Any]:
        """
        Validate that TP orders have correct quantities based on current position

        Returns:
            Dict with validation results and any corrections made
        """
        try:
            # Define expected percentages
            if approach == "conservative":
                tp_percentages = [0.85, 0.05, 0.05, 0.05]
            else:  # fast
                tp_percentages = [1.0]

            validation_results = {
                "valid": True,
                "corrections_made": [],
                "errors": [],
                "tp_orders": {}
            }

            # Check each TP order
            for i, (order_id, expected_pct) in enumerate(zip(tp_order_ids, tp_percentages), 1):
                if not order_id:
                    continue

                # Get order info
                order_info = await get_order_info(symbol, order_id)
                if not order_info:
                    validation_results["errors"].append(f"Could not get info for TP{i}")
                    validation_results["valid"] = False
                    continue

                # Check order status
                order_status = order_info.get("orderStatus", "")
                if order_status not in ["New", "Untriggered", "Active"]:
                    # Order already triggered or filled
                    continue

                # Get current order quantity
                current_qty = safe_decimal_conversion(order_info.get("qty", "0"))
                expected_qty = value_adjusted_to_step(
                    position_size * Decimal(str(expected_pct)),
                    qty_step
                )

                # Check if quantity matches (within 1 qty_step tolerance)
                qty_diff = abs(current_qty - expected_qty)
                is_correct = qty_diff <= qty_step

                validation_results["tp_orders"][f"tp{i}"] = {
                    "order_id": order_id,
                    "current_qty": float(current_qty),
                    "expected_qty": float(expected_qty),
                    "percentage": expected_pct,
                    "is_correct": is_correct,
                    "qty_diff": float(qty_diff)
                }

                if not is_correct:
                    logger.warning(
                        f"⚠️ TP{i} quantity mismatch for {symbol}: "
                        f"Current {current_qty}, Expected {expected_qty}"
                    )

                    # Attempt to correct the quantity
                    correction_result = await self._correct_tp_quantity(
                        symbol, order_id, i, current_qty, expected_qty,
                        order_info, qty_step
                    )

                    if correction_result["success"]:
                        validation_results["corrections_made"].append(
                            f"TP{i}: {current_qty} → {expected_qty}"
                        )
                    else:
                        validation_results["errors"].append(
                            f"Failed to correct TP{i}: {correction_result['error']}"
                        )
                        validation_results["valid"] = False

            return validation_results

        except Exception as e:
            logger.error(f"Error validating TP quantities: {e}")
            return {
                "valid": False,
                "error": str(e),
                "corrections_made": [],
                "errors": [str(e)]
            }

    async def _correct_tp_quantity(
        self,
        symbol: str,
        order_id: str,
        tp_number: int,
        current_qty: Decimal,
        expected_qty: Decimal,
        order_info: Dict[str, Any],
        qty_step: Decimal
    ) -> Dict[str, Any]:
        """Correct a TP order quantity by amending or replacing the order"""
        try:
            # Try to amend the order first
            logger.info(f"🔧 Attempting to correct TP{tp_number} quantity: {current_qty} → {expected_qty}")

            # Amend order with new quantity
            amend_result = await amend_order_with_retry(
                symbol=symbol,
                order_id=order_id,
                qty=str(expected_qty)
            )

            if amend_result:
                logger.info(f"✅ Successfully corrected TP{tp_number} quantity")

                # Record correction
                self.correction_history.append({
                    "timestamp": time.time(),
                    "symbol": symbol,
                    "tp_number": tp_number,
                    "order_id": order_id,
                    "old_qty": float(current_qty),
                    "new_qty": float(expected_qty),
                    "method": "amend"
                })

                return {"success": True, "method": "amend"}
            else:
                # If amend fails, try cancel and replace
                logger.warning(f"⚠️ Amend failed for TP{tp_number}, trying cancel and replace")

                # Cancel old order
                cancel_result = await cancel_order_with_retry(symbol, order_id)
                if not cancel_result:
                    return {"success": False, "error": "Could not cancel incorrect order"}

                # Place new order with correct quantity
                side = order_info.get("side")
                trigger_price = order_info.get("triggerPrice")
                order_link_id = order_info.get("orderLinkId", "") + "_CORRECTED"

                new_order_result = await place_order_with_retry(
                    symbol=symbol,
                    side=side,
                    order_type="Market",
                    qty=str(expected_qty),
                    trigger_price=str(trigger_price),
                    reduce_only=True,
                    stop_order_type="TakeProfit",
                    order_link_id=order_link_id
                )

                if new_order_result:
                    logger.info(f"✅ Successfully replaced TP{tp_number} with correct quantity")

                    # Record correction
                    self.correction_history.append({
                        "timestamp": time.time(),
                        "symbol": symbol,
                        "tp_number": tp_number,
                        "old_order_id": order_id,
                        "new_order_id": new_order_result.get("orderId"),
                        "old_qty": float(current_qty),
                        "new_qty": float(expected_qty),
                        "method": "replace"
                    })

                    return {
                        "success": True,
                        "method": "replace",
                        "new_order_id": new_order_result.get("orderId")
                    }
                else:
                    return {"success": False, "error": "Could not place replacement order"}

        except Exception as e:
            logger.error(f"Error correcting TP quantity: {e}")
            return {"success": False, "error": str(e)}

    async def monitor_position_size_changes(
        self,
        symbol: str,
        chat_data: Dict[str, Any],
        interval: int = 5
    ):
        """
        Monitor position size changes and adjust TP orders accordingly
        Useful for positions that might be manually adjusted
        """
        try:
            approach = chat_data.get(TRADING_APPROACH, "fast")
            qty_step = safe_decimal_conversion(chat_data.get(INSTRUMENT_QTY_STEP, "0.001"))

            last_position_size = None
            consecutive_checks = 0
            max_consecutive_checks = 60  # 5 minutes at 5 second intervals

            while consecutive_checks < max_consecutive_checks:
                # Get current position
                positions = await get_position_info(symbol)
                current_position = next((p for p in positions if float(p.get("size", 0)) > 0), None)

                if not current_position:
                    logger.info(f"📊 Position closed for {symbol}, stopping quantity monitoring")
                    break

                current_size = safe_decimal_conversion(current_position.get("size", "0"))

                # Check if position size changed
                if last_position_size and abs(current_size - last_position_size) > qty_step:
                    logger.info(
                        f"📊 Position size changed for {symbol}: "
                        f"{last_position_size} → {current_size}"
                    )

                    # Get TP order IDs
                    tp_order_ids = []
                    if approach == "conservative":
                        tp_order_ids = chat_data.get(CONSERVATIVE_TP_ORDER_IDS, [])
                    else:
                        tp_order_id = chat_data.get("tp_order_id")
                        if tp_order_id:
                            tp_order_ids = [tp_order_id]

                    if tp_order_ids:
                        # Validate and correct TP quantities
                        validation_result = await self.validate_tp_order_quantities(
                            symbol=symbol,
                            tp_order_ids=tp_order_ids,
                            position_size=current_size,
                            approach=approach,
                            qty_step=qty_step
                        )

                        if validation_result["corrections_made"]:
                            logger.info(
                                f"✅ Corrected TP quantities after position change: "
                                f"{', '.join(validation_result['corrections_made'])}"
                            )

                last_position_size = current_size
                consecutive_checks += 1

                # Wait before next check
                await asyncio.sleep(interval)

        except Exception as e:
            logger.error(f"Error monitoring position size changes: {e}")

    def get_correction_summary(self) -> Dict[str, Any]:
        """Get summary of quantity corrections made"""
        if not self.correction_history:
            return {
                "total_corrections": 0,
                "by_method": {},
                "by_symbol": {}
            }

        by_method = {}
        by_symbol = {}

        for correction in self.correction_history:
            method = correction["method"]
            symbol = correction["symbol"]

            by_method[method] = by_method.get(method, 0) + 1
            by_symbol[symbol] = by_symbol.get(symbol, 0) + 1

        return {
            "total_corrections": len(self.correction_history),
            "by_method": by_method,
            "by_symbol": by_symbol,
            "recent_corrections": self.correction_history[-10:]  # Last 10
        }

# Global instance
order_quantity_safeguard = OrderQuantitySafeguard()

__all__ = ['order_quantity_safeguard', 'OrderQuantitySafeguard']