#!/usr/bin/env python3
"""
Emergency Trading Module - Emergency shutdown of all positions and orders
Provides a safety mechanism to immediately close all positions and cancel all orders
on both main and mirror trading accounts.

CRITICAL: This module performs irreversible actions. Use with extreme caution.
"""
import asyncio
import logging
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
from decimal import Decimal

from clients.bybit_client import bybit_client
from clients.bybit_helpers import (
    get_all_positions, get_all_open_orders,
    cancel_order_with_retry, close_position,
    api_call_with_retry
)
from utils.formatters import format_mobile_currency

logger = logging.getLogger(__name__)

# Import mirror trading if available
try:
    from execution.mirror_trader import (
        bybit_client_2, ENABLE_MIRROR_TRADING,
        is_mirror_trading_enabled
    )
    MIRROR_AVAILABLE = True
except ImportError:
    MIRROR_AVAILABLE = False
    ENABLE_MIRROR_TRADING = False
    bybit_client_2 = None


class EmergencyShutdown:
    """Handles emergency closing of all positions and orders"""

    def __init__(self):
        self.start_time = None
        self.summary = {
            "positions_closed": {"main": [], "mirror": []},
            "orders_cancelled": {"main": [], "mirror": []},
            "errors": {"main": [], "mirror": []},
            "total_value_closed": {"main": Decimal("0"), "mirror": Decimal("0")},
            "execution_time": 0
        }

    async def emergency_shutdown(self, include_mirror: bool = True) -> Dict[str, Any]:
        """
        Execute emergency shutdown - close all positions and cancel all orders

        Args:
            include_mirror: Whether to include mirror account in shutdown

        Returns:
            Summary of all actions taken
        """
        self.start_time = datetime.now()
        logger.critical("🚨 EMERGENCY SHUTDOWN INITIATED 🚨")

        try:
            # Get current status before shutdown
            initial_status = await self.get_emergency_status(include_mirror)
            logger.info(f"📊 Initial status: {initial_status}")

            # Phase 1: Cancel all orders (do this first to prevent fills during position closing)
            logger.info("📝 Phase 1: Cancelling all orders...")
            await self._cancel_all_orders_parallel(include_mirror)

            # Small delay to ensure order cancellations are processed
            await asyncio.sleep(1)

            # Phase 2: Close all positions
            logger.info("💰 Phase 2: Closing all positions...")
            await self._close_all_positions_parallel(include_mirror)

            # Phase 3: Verify completion
            logger.info("✅ Phase 3: Verifying shutdown completion...")
            final_status = await self.get_emergency_status(include_mirror)

            # Calculate execution time
            self.summary["execution_time"] = (datetime.now() - self.start_time).total_seconds()
            self.summary["initial_status"] = initial_status
            self.summary["final_status"] = final_status

            logger.critical(f"🏁 EMERGENCY SHUTDOWN COMPLETED in {self.summary['execution_time']:.1f} seconds")
            return self.summary

        except Exception as e:
            logger.error(f"❌ Critical error during emergency shutdown: {e}")
            self.summary["errors"]["main"].append(f"Critical error: {str(e)}")
            return self.summary

    async def get_emergency_status(self, include_mirror: bool = True) -> Dict[str, Any]:
        """Get current positions and orders status for emergency display"""
        status = {
            "main": {"positions": [], "orders": [], "total_exposure": Decimal("0")},
            "mirror": {"positions": [], "orders": [], "total_exposure": Decimal("0")}
        }

        try:
            # Get main account status
            main_positions = await get_all_positions()
            active_main_positions = [p for p in main_positions if float(p.get('size', 0)) > 0]
            status["main"]["positions"] = active_main_positions

            main_orders = await get_all_open_orders()
            status["main"]["orders"] = main_orders

            # Calculate total exposure
            for pos in active_main_positions:
                value = Decimal(str(pos.get('positionValue', '0')))
                status["main"]["total_exposure"] += abs(value)

            # Get mirror account status if enabled
            if include_mirror and MIRROR_AVAILABLE and bybit_client_2:
                try:
                    # Get mirror positions
                    response = await api_call_with_retry(
                        lambda: bybit_client_2.get_positions(
                            category="linear",
                            settleCoin="USDT"
                        ),
                        timeout=30
                    )
                    if response and response.get("retCode") == 0:
                        mirror_positions = response.get("result", {}).get("list", [])
                        active_mirror_positions = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
                        status["mirror"]["positions"] = active_mirror_positions

                        for pos in active_mirror_positions:
                            value = Decimal(str(pos.get('positionValue', '0')))
                            status["mirror"]["total_exposure"] += abs(value)

                    # Get mirror orders
                    response = await api_call_with_retry(
                        lambda: bybit_client_2.get_open_orders(
                            category="linear",
                            settleCoin="USDT"
                        ),
                        timeout=30
                    )
                    if response and response.get("retCode") == 0:
                        status["mirror"]["orders"] = response.get("result", {}).get("list", [])

                except Exception as e:
                    logger.error(f"Error getting mirror account status: {e}")
                    status["mirror"]["error"] = str(e)

        except Exception as e:
            logger.error(f"Error getting emergency status: {e}")

        return status

    async def _cancel_all_orders_parallel(self, include_mirror: bool):
        """Cancel all orders on main and optionally mirror account"""
        tasks = []

        # Cancel main account orders
        tasks.append(self._cancel_account_orders("main", bybit_client))

        # Cancel mirror account orders if enabled
        if include_mirror and MIRROR_AVAILABLE and bybit_client_2:
            tasks.append(self._cancel_account_orders("mirror", bybit_client_2))

        # Execute in parallel
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _cancel_account_orders(self, account_type: str, client):
        """Cancel all orders for a specific account"""
        try:
            # Get all open orders
            if account_type == "main":
                orders = await get_all_open_orders()
            else:
                # For mirror account, use direct API call
                response = await api_call_with_retry(
                    lambda: client.get_open_orders(
                        category="linear",
                        settleCoin="USDT"
                    ),
                    timeout=30
                )
                orders = response.get("result", {}).get("list", []) if response else []

            logger.info(f"🔄 {account_type.upper()}: Found {len(orders)} orders to cancel")

            # Group orders by symbol for efficient cancellation
            orders_by_symbol = {}
            for order in orders:
                symbol = order.get("symbol", "")
                if symbol not in orders_by_symbol:
                    orders_by_symbol[symbol] = []
                orders_by_symbol[symbol].append(order)

            # Cancel orders for each symbol
            cancel_tasks = []
            for symbol, symbol_orders in orders_by_symbol.items():
                for order in symbol_orders:
                    order_id = order.get("orderId", "")
                    if order_id:
                        if account_type == "main":
                            task = cancel_order_with_retry(symbol, order_id)
                        else:
                            # For mirror account, use direct API call
                            task = self._cancel_mirror_order(client, symbol, order_id)
                        cancel_tasks.append(task)

            # Execute cancellations with concurrency limit
            if cancel_tasks:
                # Process in batches to avoid overwhelming the API
                batch_size = 10
                for i in range(0, len(cancel_tasks), batch_size):
                    batch = cancel_tasks[i:i + batch_size]
                    results = await asyncio.gather(*batch, return_exceptions=True)

                    # Track results
                    for j, result in enumerate(results):
                        order = orders[i + j]
                        if isinstance(result, Exception):
                            error_msg = f"Failed to cancel {order.get('symbol')} order {order.get('orderId', '')[:8]}: {result}"
                            logger.error(error_msg)
                            self.summary["errors"][account_type].append(error_msg)
                        elif result:
                            self.summary["orders_cancelled"][account_type].append({
                                "symbol": order.get("symbol"),
                                "orderId": order.get("orderId"),
                                "orderType": order.get("orderType"),
                                "side": order.get("side"),
                                "qty": order.get("qty"),
                                "price": order.get("price", order.get("triggerPrice"))
                            })

                    # Small delay between batches
                    if i + batch_size < len(cancel_tasks):
                        await asyncio.sleep(0.5)

            logger.info(f"✅ {account_type.upper()}: Cancelled {len(self.summary['orders_cancelled'][account_type])} orders")

        except Exception as e:
            error_msg = f"Error cancelling {account_type} orders: {str(e)}"
            logger.error(error_msg)
            self.summary["errors"][account_type].append(error_msg)

    async def _cancel_mirror_order(self, client, symbol: str, order_id: str) -> bool:
        """Cancel a single order on mirror account"""
        try:
            response = await api_call_with_retry(
                lambda: client.cancel_order(
                    category="linear",
                    symbol=symbol,
                    orderId=order_id
                ),
                timeout=20
            )

            if response and response.get("retCode") == 0:
                return True
            elif response and response.get("retCode") in [110001, 110004, 110005]:
                # Order already gone (filled/cancelled)
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"Error cancelling mirror order {order_id}: {e}")
            return False

    async def _close_all_positions_parallel(self, include_mirror: bool):
        """Close all positions on main and optionally mirror account"""
        tasks = []

        # Close main account positions
        tasks.append(self._close_account_positions("main", bybit_client))

        # Close mirror account positions if enabled
        if include_mirror and MIRROR_AVAILABLE and bybit_client_2:
            tasks.append(self._close_account_positions("mirror", bybit_client_2))

        # Execute in parallel
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _close_account_positions(self, account_type: str, client):
        """Close all positions for a specific account"""
        try:
            # Get all positions
            if account_type == "main":
                positions = await get_all_positions()
            else:
                # For mirror account, use direct API call
                response = await api_call_with_retry(
                    lambda: client.get_positions(
                        category="linear",
                        settleCoin="USDT"
                    ),
                    timeout=30
                )
                positions = response.get("result", {}).get("list", []) if response else []

            # Filter active positions
            active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
            logger.info(f"💰 {account_type.upper()}: Found {len(active_positions)} positions to close")

            # Close each position
            close_tasks = []
            for position in active_positions:
                symbol = position.get("symbol", "")
                if account_type == "main":
                    task = close_position(symbol)
                else:
                    # For mirror account, create market order to close
                    task = self._close_mirror_position(client, position)
                close_tasks.append((position, task))

            # Execute closures
            for position, task in close_tasks:
                try:
                    result = await task

                    if isinstance(result, dict) and result.get("success"):
                        position_value = Decimal(str(position.get('positionValue', '0')))
                        self.summary["total_value_closed"][account_type] += abs(position_value)
                        self.summary["positions_closed"][account_type].append({
                            "symbol": position.get("symbol"),
                            "side": position.get("side"),
                            "size": position.get("size"),
                            "value": str(position_value),
                            "pnl": position.get("unrealisedPnl"),
                            "orderId": result.get("orderId")
                        })
                    else:
                        error_msg = f"Failed to close {position.get('symbol')} position: {result}"
                        logger.error(error_msg)
                        self.summary["errors"][account_type].append(error_msg)

                except Exception as e:
                    error_msg = f"Error closing {position.get('symbol')} position: {str(e)}"
                    logger.error(error_msg)
                    self.summary["errors"][account_type].append(error_msg)

                # Small delay between position closures to avoid overwhelming
                await asyncio.sleep(0.2)

            logger.info(f"✅ {account_type.upper()}: Closed {len(self.summary['positions_closed'][account_type])} positions")

        except Exception as e:
            error_msg = f"Error closing {account_type} positions: {str(e)}"
            logger.error(error_msg)
            self.summary["errors"][account_type].append(error_msg)

    async def _close_mirror_position(self, client, position: Dict) -> Dict:
        """Close a single position on mirror account"""
        try:
            symbol = position.get("symbol", "")
            side = position.get("side", "")
            size = position.get("size", "0")

            # Determine opposite side for closing
            close_side = "Sell" if side == "Buy" else "Buy"

            # Place market order to close
            response = await api_call_with_retry(
                lambda: client.place_order(
                    category="linear",
                    symbol=symbol,
                    side=close_side,
                    orderType="Market",
                    qty=size,
                    reduceOnly=True,
                    positionIdx=position.get("positionIdx", 0)
                ),
                timeout=20
            )

            if response and response.get("retCode") == 0:
                return {
                    "success": True,
                    "orderId": response.get("result", {}).get("orderId"),
                    "message": f"Position closed: {side} {size} {symbol}"
                }
            else:
                return {
                    "success": False,
                    "error": response.get("retMsg", "Unknown error")
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def format_summary_message(self) -> str:
        """Format the emergency shutdown summary for display"""
        lines = ["🚨 <b>EMERGENCY SHUTDOWN SUMMARY</b> 🚨\n"]

        # Execution time
        lines.append(f"⏱ <b>Execution Time:</b> {self.summary['execution_time']:.1f} seconds\n")

        # Main account summary
        lines.append("<b>📊 MAIN ACCOUNT:</b>")
        lines.append(f"• Positions Closed: {len(self.summary['positions_closed']['main'])}")
        lines.append(f"• Orders Cancelled: {len(self.summary['orders_cancelled']['main'])}")
        lines.append(f"• Total Value: {format_mobile_currency(self.summary['total_value_closed']['main'])}")
        if self.summary['errors']['main']:
            lines.append(f"• ⚠️ Errors: {len(self.summary['errors']['main'])}")
        lines.append("")

        # Mirror account summary if applicable
        if MIRROR_AVAILABLE and self.summary['positions_closed']['mirror']:
            lines.append("<b>🔄 MIRROR ACCOUNT:</b>")
            lines.append(f"• Positions Closed: {len(self.summary['positions_closed']['mirror'])}")
            lines.append(f"• Orders Cancelled: {len(self.summary['orders_cancelled']['mirror'])}")
            lines.append(f"• Total Value: {format_mobile_currency(self.summary['total_value_closed']['mirror'])}")
            if self.summary['errors']['mirror']:
                lines.append(f"• ⚠️ Errors: {len(self.summary['errors']['mirror'])}")
            lines.append("")

        # Final status
        final_status = self.summary.get('final_status', {})
        remaining_positions = (
            len(final_status.get('main', {}).get('positions', [])) +
            len(final_status.get('mirror', {}).get('positions', []))
        )
        remaining_orders = (
            len(final_status.get('main', {}).get('orders', [])) +
            len(final_status.get('mirror', {}).get('orders', []))
        )

        if remaining_positions == 0 and remaining_orders == 0:
            lines.append("✅ <b>SHUTDOWN COMPLETE</b>")
            lines.append("All positions closed and orders cancelled.")
        else:
            lines.append("⚠️ <b>PARTIAL SHUTDOWN</b>")
            if remaining_positions > 0:
                lines.append(f"• {remaining_positions} positions still open")
            if remaining_orders > 0:
                lines.append(f"• {remaining_orders} orders still active")

        # Errors summary
        total_errors = len(self.summary['errors']['main']) + len(self.summary['errors']['mirror'])
        if total_errors > 0:
            lines.append(f"\n❌ <b>Errors Encountered:</b> {total_errors}")
            lines.append("Check logs for details.")

        return "\n".join(lines)


# Global instance for easy access
emergency_shutdown = EmergencyShutdown()


async def execute_emergency_shutdown(include_mirror: bool = True) -> Tuple[bool, str]:
    """
    Convenience function to execute emergency shutdown

    Returns:
        Tuple of (success, summary_message)
    """
    try:
        summary = await emergency_shutdown.emergency_shutdown(include_mirror)
        message = emergency_shutdown.format_summary_message()

        # Determine success based on final status
        final_status = summary.get('final_status', {})
        remaining = (
            len(final_status.get('main', {}).get('positions', [])) +
            len(final_status.get('main', {}).get('orders', [])) +
            len(final_status.get('mirror', {}).get('positions', [])) +
            len(final_status.get('mirror', {}).get('orders', []))
        )

        success = remaining == 0
        return success, message

    except Exception as e:
        logger.error(f"Emergency shutdown failed: {e}")
        return False, f"❌ Emergency shutdown failed: {str(e)}"