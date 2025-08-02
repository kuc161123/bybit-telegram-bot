#!/usr/bin/env python3
"""
TP Order Tracker - Tracks and verifies TP order executions
"""
import logging
from decimal import Decimal
from typing import Dict, Any, Optional, List
import time

from config.constants import *
from clients.bybit_helpers import get_order_info, get_position_info
from utils.helpers import safe_decimal_conversion

logger = logging.getLogger(__name__)

class TPOrderTracker:
    """Tracks TP orders and their expected vs actual execution"""

    def __init__(self):
        self.tp_orders = {}  # symbol -> {tp1: {...}, tp2: {...}, ...}
        self.execution_history = {}  # Track all executions

    def register_tp_orders(
        self,
        symbol: str,
        approach: str,
        tp_order_ids: List[str],
        position_size: Decimal,
        side: str
    ):
        """
        Register TP orders with their expected execution sizes

        Args:
            symbol: Trading symbol
            approach: Trading approach (conservative only)
            tp_order_ids: List of TP order IDs
            position_size: Total position size
            side: Position side (Buy/Sell)
        """
        try:
            if symbol not in self.tp_orders:
                self.tp_orders[symbol] = {}

            # Conservative approach only: 85%, 5%, 5%, 5%
            tp_percentages = [0.85, 0.05, 0.05, 0.05]

            # Register each TP order
            for i, (order_id, percentage) in enumerate(zip(tp_order_ids, tp_percentages), 1):
                if order_id:
                    expected_size = position_size * Decimal(str(percentage))
                    self.tp_orders[symbol][f"tp{i}"] = {
                        "order_id": order_id,
                        "tp_number": i,
                        "expected_percentage": percentage,
                        "expected_size": expected_size,
                        "position_size_at_registration": position_size,
                        "side": side,
                        "status": "pending",
                        "registered_at": time.time()
                    }
                    logger.info(
                        f"📝 Registered TP{i} for {symbol}: "
                        f"Order {order_id[:8]}..., "
                        f"Expected {percentage*100:.0f}% ({expected_size:.4f})"
                    )

        except Exception as e:
            logger.error(f"Error registering TP orders: {e}")

    async def check_tp_execution(
        self,
        symbol: str,
        tp_number: int,
        current_position_size: Decimal
    ) -> Dict[str, Any]:
        """
        Check if a specific TP has been executed and verify the execution

        Returns:
            Dict with execution status and verification results
        """
        try:
            if symbol not in self.tp_orders:
                return {"executed": False, "error": "No TP orders registered for symbol"}

            tp_key = f"tp{tp_number}"
            if tp_key not in self.tp_orders[symbol]:
                return {"executed": False, "error": f"TP{tp_number} not registered"}

            tp_data = self.tp_orders[symbol][tp_key]
            order_id = tp_data["order_id"]

            # Check order status
            order_info = await get_order_info(symbol, order_id)
            if not order_info:
                return {"executed": False, "error": "Could not get order info"}

            order_status = order_info.get("orderStatus", "")

            # Check if order is filled
            if order_status not in ["Filled", "PartiallyFilled"]:
                return {
                    "executed": False,
                    "order_status": order_status,
                    "tp_number": tp_number
                }

            # Order is filled - verify execution
            filled_qty = safe_decimal_conversion(order_info.get("cumExecQty", "0"))
            avg_price = safe_decimal_conversion(order_info.get("avgPrice", "0"))

            # Calculate actual position reduction
            original_size = tp_data["position_size_at_registration"]
            size_reduction = original_size - current_position_size
            actual_percentage = float(size_reduction / original_size) if original_size > 0 else 0
            expected_percentage = tp_data["expected_percentage"]

            # Check if execution matches expectations
            percentage_diff = abs(actual_percentage - expected_percentage)
            tolerance = 0.05  # 5% tolerance
            verified = percentage_diff <= tolerance

            result = {
                "executed": True,
                "verified": verified,
                "tp_number": tp_number,
                "order_id": order_id,
                "order_status": order_status,
                "filled_qty": float(filled_qty),
                "avg_price": float(avg_price),
                "expected_percentage": expected_percentage,
                "actual_percentage": actual_percentage,
                "percentage_diff": percentage_diff,
                "original_position_size": float(original_size),
                "current_position_size": float(current_position_size),
                "size_reduction": float(size_reduction)
            }

            # Update status
            tp_data["status"] = "executed"
            tp_data["execution_result"] = result
            tp_data["executed_at"] = time.time()

            # Store in history
            history_key = f"{symbol}_{tp_number}_{int(time.time())}"
            self.execution_history[history_key] = result

            if verified:
                logger.info(
                    f"✅ TP{tp_number} execution verified for {symbol}: "
                    f"Expected {expected_percentage*100:.0f}%, "
                    f"Actual {actual_percentage*100:.1f}%"
                )
            else:
                logger.error(
                    f"❌ TP{tp_number} execution MISMATCH for {symbol}: "
                    f"Expected {expected_percentage*100:.0f}%, "
                    f"Actual {actual_percentage*100:.1f}% "
                    f"(diff: {percentage_diff*100:.1f}%)"
                )

            return result

        except Exception as e:
            logger.error(f"Error checking TP execution: {e}")
            return {"executed": False, "error": str(e)}

    async def check_all_tp_executions(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Check all TP orders for a symbol and return their status
        """
        try:
            if symbol not in self.tp_orders:
                return {"error": "No TP orders registered for symbol"}

            # Get current position
            positions = await get_position_info(symbol)
            current_position = next((p for p in positions if float(p.get("size", 0)) > 0), None)
            current_size = safe_decimal_conversion(
                current_position.get("size", "0") if current_position else "0"
            )

            results = {}
            for tp_key, tp_data in self.tp_orders[symbol].items():
                tp_number = tp_data["tp_number"]

                # Skip if already executed
                if tp_data["status"] == "executed":
                    results[tp_key] = tp_data.get("execution_result", {"executed": True})
                else:
                    # Check execution
                    result = await self.check_tp_execution(symbol, tp_number, current_size)
                    results[tp_key] = result

            return results

        except Exception as e:
            logger.error(f"Error checking all TP executions: {e}")
            return {"error": str(e)}

    def get_tp_summary(self, symbol: str = None) -> Dict[str, Any]:
        """Get summary of TP order tracking"""
        if symbol:
            if symbol not in self.tp_orders:
                return {"error": "No data for symbol"}

            symbol_data = self.tp_orders[symbol]
            return {
                "symbol": symbol,
                "total_tps": len(symbol_data),
                "pending": sum(1 for tp in symbol_data.values() if tp["status"] == "pending"),
                "executed": sum(1 for tp in symbol_data.values() if tp["status"] == "executed"),
                "verified": sum(
                    1 for tp in symbol_data.values()
                    if tp.get("execution_result", {}).get("verified", False)
                ),
                "tps": {
                    k: {
                        "status": v["status"],
                        "expected_percentage": v["expected_percentage"],
                        "verified": v.get("execution_result", {}).get("verified", None)
                    }
                    for k, v in symbol_data.items()
                }
            }
        else:
            # Summary for all symbols
            return {
                "total_symbols": len(self.tp_orders),
                "total_executions": len(self.execution_history),
                "symbols": list(self.tp_orders.keys())
            }

    def clear_symbol_data(self, symbol: str):
        """Clear tracking data for a symbol (e.g., when position closes)"""
        if symbol in self.tp_orders:
            del self.tp_orders[symbol]
            logger.info(f"🧹 Cleared TP tracking data for {symbol}")

# Global instance
tp_order_tracker = TPOrderTracker()

__all__ = ['tp_order_tracker', 'TPOrderTracker']