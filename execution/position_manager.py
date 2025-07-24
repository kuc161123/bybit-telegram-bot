#!/usr/bin/env python3
"""
Position Management Module - Handles individual position operations
Provides functionality to close specific positions and their related orders
on both main and mirror accounts.
"""
import asyncio
import logging
from typing import Dict, List, Tuple, Optional, Any
from decimal import Decimal

from clients.bybit_client import bybit_client
from clients.bybit_helpers import (
    get_position_info, get_all_positions, get_all_open_orders,
    cancel_order_with_retry, api_call_with_retry,
    close_position as close_position_helper
)
from utils.formatters import format_mobile_currency

logger = logging.getLogger(__name__)

# Import mirror trading if available
try:
    from execution.mirror_trader import (
        bybit_client_2, is_mirror_trading_enabled,
        ENABLE_MIRROR_TRADING
    )
    MIRROR_AVAILABLE = True
except ImportError:
    MIRROR_AVAILABLE = False
    ENABLE_MIRROR_TRADING = False
    bybit_client_2 = None


class PositionManager:
    """Manages individual position operations"""
    
    async def get_all_positions_with_details(self) -> List[Dict[str, Any]]:
        """
        Get all active positions from both main and mirror accounts with details
        
        Returns:
            List of position dictionaries with account info
        """
        all_positions = []
        
        try:
            # Get main account positions
            main_positions = await get_all_positions()  # Get all positions
            if main_positions:
                for pos in main_positions:
                    if float(pos.get('size', 0)) > 0:
                        pos_data = {
                            'account': 'main',
                            'symbol': pos.get('symbol'),
                            'side': pos.get('side'),
                            'size': pos.get('size'),
                            'avgPrice': pos.get('avgPrice'),
                            'markPrice': pos.get('markPrice'),
                            'unrealisedPnl': pos.get('unrealisedPnl'),
                            'positionIdx': pos.get('positionIdx', 0),
                            'leverage': pos.get('leverage', '1')
                        }
                        all_positions.append(pos_data)
            
            # Get mirror account positions if available
            if MIRROR_AVAILABLE and bybit_client_2 and ENABLE_MIRROR_TRADING:
                try:
                    # Use the get_all_positions function with mirror client
                    mirror_positions = await get_all_positions(client=bybit_client_2)
                    if mirror_positions:
                        for pos in mirror_positions:
                            if float(pos.get('size', 0)) > 0:
                                pos_data = {
                                    'account': 'mirror',
                                    'symbol': pos.get('symbol'),
                                    'side': pos.get('side'),
                                    'size': pos.get('size'),
                                    'avgPrice': pos.get('avgPrice'),
                                    'markPrice': pos.get('markPrice'),
                                    'unrealisedPnl': pos.get('unrealisedPnl'),
                                    'positionIdx': pos.get('positionIdx', 0),
                                    'leverage': pos.get('leverage', '1')
                                }
                                all_positions.append(pos_data)
                except Exception as e:
                    logger.warning(f"Could not get mirror positions: {e}")
            
            logger.info(f"Found {len(all_positions)} total positions across all accounts")
            return all_positions
            
        except Exception as e:
            logger.error(f"Error getting all positions: {e}")
            return []

    async def close_position_with_orders(self, symbol: str, side: str, account: str = "main") -> Dict[str, Any]:
        """
        Close a specific position and cancel all its related orders

        Args:
            symbol: The trading symbol (e.g., 'BTCUSDT')
            side: Position side ('Buy' or 'Sell')
            account: 'main' or 'mirror'

        Returns:
            Summary of actions taken
        """
        summary = {
            "symbol": symbol,
            "side": side,
            "account": account,
            "position_closed": False,
            "orders_cancelled": [],
            "errors": [],
            "position_details": None,
            "total_orders_cancelled": 0
        }

        try:
            # Determine which client to use
            if account == "mirror" and MIRROR_AVAILABLE and bybit_client_2:
                client = bybit_client_2
            else:
                client = bybit_client
                account = "main"  # Force main if mirror not available

            # Get position details
            position_details = await self.get_position_details(symbol, side, account)
            if not position_details or position_details.get("size", 0) == 0:
                summary["errors"].append(f"No active position found for {symbol}")
                return summary

            summary["position_details"] = position_details

            logger.info(f"📋 Closing position for {symbol} on {account} account")

            # Phase 1: Cancel all orders for this symbol
            logger.info(f"🔄 Phase 1: Cancelling orders for {symbol}")
            cancelled_orders = await self.cancel_all_orders_for_symbol(symbol, account)
            summary["orders_cancelled"] = cancelled_orders
            summary["total_orders_cancelled"] = len(cancelled_orders)

            # Small delay to ensure order cancellations are processed
            await asyncio.sleep(0.5)

            # Phase 2: Close the position
            logger.info(f"💰 Phase 2: Closing position for {symbol}")
            if account == "main":
                # Use the helper function for main account
                close_result = await close_position_helper(symbol)
            else:
                # Use direct API for mirror account
                close_result = await self._close_mirror_position(client, position_details)

            if close_result.get("success"):
                summary["position_closed"] = True
                logger.info(f"✅ Position closed successfully for {symbol}")
            else:
                error_msg = close_result.get("error", "Unknown error")
                summary["errors"].append(f"Failed to close position: {error_msg}")
                logger.error(f"❌ Failed to close position: {error_msg}")

            return summary

        except Exception as e:
            logger.error(f"Error in close_position_with_orders: {e}")
            summary["errors"].append(f"Unexpected error: {str(e)}")
            return summary

    async def get_position_details(self, symbol: str, account: str = "main") -> Optional[Dict]:
        """
        Get detailed information about a specific position

        Args:
            symbol: The trading symbol
            account: 'main' or 'mirror'

        Returns:
            Position details or None if not found
        """
        try:
            if account == "mirror" and MIRROR_AVAILABLE and bybit_client_2:
                # Get mirror position
                response = await api_call_with_retry(
                    lambda: bybit_client_2.get_positions(
                        category="linear",
                        symbol=symbol
                    ),
                    timeout=30
                )

                if response and response.get("retCode") == 0:
                    positions = response.get("result", {}).get("list", [])
                    for pos in positions:
                        if float(pos.get("size", 0)) > 0:
                            return pos
            else:
                # Get main account position
                positions = await get_position_info(symbol)
                if positions:
                    for pos in positions:
                        if float(pos.get("size", 0)) > 0:
                            return pos

            return None

        except Exception as e:
            logger.error(f"Error getting position details for {symbol}: {e}")
            return None

    async def cancel_all_orders_for_symbol(self, symbol: str, account: str = "main") -> List[Dict]:
        """
        Cancel all orders for a specific symbol

        Args:
            symbol: The trading symbol
            account: 'main' or 'mirror'

        Returns:
            List of cancelled orders
        """
        cancelled_orders = []

        try:
            # Get all open orders
            if account == "mirror" and MIRROR_AVAILABLE and bybit_client_2:
                response = await api_call_with_retry(
                    lambda: bybit_client_2.get_open_orders(
                        category="linear",
                        symbol=symbol
                    ),
                    timeout=30
                )
                orders = response.get("result", {}).get("list", []) if response else []
            else:
                # Get orders from main account
                all_orders = await get_all_open_orders()
                orders = [o for o in all_orders if o.get("symbol") == symbol]

            logger.info(f"Found {len(orders)} orders to cancel for {symbol}")

            # Cancel each order
            for order in orders:
                order_id = order.get("orderId", "")
                if not order_id:
                    continue

                try:
                    if account == "main":
                        success = await cancel_order_with_retry(symbol, order_id)
                    else:
                        success = await self._cancel_mirror_order(bybit_client_2, symbol, order_id)

                    if success:
                        cancelled_orders.append({
                            "orderId": order_id,
                            "orderType": order.get("orderType"),
                            "side": order.get("side"),
                            "qty": order.get("qty"),
                            "price": order.get("price", order.get("triggerPrice"))
                        })
                        logger.info(f"✅ Cancelled order {order_id[:8]}...")
                    else:
                        logger.warning(f"Failed to cancel order {order_id[:8]}...")

                except Exception as e:
                    logger.error(f"Error cancelling order {order_id}: {e}")

            return cancelled_orders

        except Exception as e:
            logger.error(f"Error cancelling orders for {symbol}: {e}")
            return cancelled_orders

    async def _close_mirror_position(self, client, position: Dict) -> Dict:
        """Close a position on mirror account"""
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

    async def get_position_details(self, symbol: str, side: str, account: str = "main") -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific position
        
        Args:
            symbol: Trading symbol
            side: Position side (Buy/Sell)
            account: 'main' or 'mirror'
            
        Returns:
            Position details or None if not found
        """
        try:
            # Determine which client to use
            if account == "mirror" and MIRROR_AVAILABLE and bybit_client_2:
                client = bybit_client_2
            else:
                client = bybit_client
                account = "main"
            
            # Get position info
            if account == "main":
                positions = await get_position_info(symbol)
            else:
                # Direct API call for mirror with required parameters
                response = client.get_positions(category="linear", symbol=symbol, settleCoin="USDT")
                if response['retCode'] == 0:
                    positions = response['result']['list']
                else:
                    positions = []
            
            # Find the specific position
            for pos in positions:
                if (pos.get('symbol') == symbol and 
                    pos.get('side') == side and
                    float(pos.get('size', 0)) > 0):
                    
                    # Get open orders for this position
                    orders = await self.get_position_orders(symbol, account)
                    
                    return {
                        'symbol': symbol,
                        'side': side,
                        'size': pos.get('size'),
                        'avgPrice': pos.get('avgPrice'),
                        'markPrice': pos.get('markPrice'),
                        'unrealisedPnl': pos.get('unrealisedPnl'),
                        'leverage': pos.get('leverage', '1'),
                        'orders': orders,
                        'account': account,
                        'positionValue': pos.get('positionValue', 0)
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting position details: {e}")
            return None
    
    async def get_position_orders(self, symbol: str, account: str = "main") -> List[Dict[str, Any]]:
        """
        Get all open orders for a specific symbol
        
        Args:
            symbol: Trading symbol
            account: 'main' or 'mirror'
            
        Returns:
            List of orders
        """
        try:
            if account == "main":
                all_orders = await get_all_open_orders()
                return [o for o in all_orders if o.get('symbol') == symbol]
            else:
                # For mirror account
                if MIRROR_AVAILABLE and bybit_client_2:
                    response = bybit_client_2.get_open_orders(category="linear", symbol=symbol)
                    if response['retCode'] == 0:
                        return response['result']['list']
            return []
            
        except Exception as e:
            logger.error(f"Error getting position orders: {e}")
            return []
    
    def format_position_summary(self, position: Dict) -> str:
        """Format position details for display"""
        if not position:
            return "No position data"

        symbol = position.get("symbol", "Unknown")
        side = position.get("side", "")
        size = float(position.get("size", 0))
        avg_price = float(position.get("avgPrice", 0))
        mark_price = float(position.get("markPrice", 0))
        unrealized_pnl = float(position.get("unrealisedPnl", 0))
        position_value = float(position.get("positionValue", 0))
        leverage = int(position.get("leverage", 1))

        # Calculate percentage
        if avg_price > 0:
            if side == "Buy":
                pnl_pct = ((mark_price - avg_price) / avg_price) * 100
            else:
                pnl_pct = ((avg_price - mark_price) / avg_price) * 100
        else:
            pnl_pct = 0

        # P&L emoji
        pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"

        return f"""<b>{symbol}</b> {side}
━━━━━━━━━━━━━━━━━━━━━━
• Size: {size} @ ${avg_price:.4f}
• Mark Price: ${mark_price:.4f}
• Leverage: {leverage}x
• Position Value: {format_mobile_currency(Decimal(str(position_value)))}
• P&L: {pnl_emoji} ${unrealized_pnl:.2f} ({pnl_pct:+.2f}%)"""

    def format_close_summary(self, summary: Dict) -> str:
        """Format the closing summary for display"""
        lines = []

        symbol = summary.get("symbol", "Unknown")
        account = summary.get("account", "main")
        account_label = "MAIN" if account == "main" else "MIRROR"

        if summary.get("position_closed"):
            lines.append(f"✅ <b>POSITION CLOSED SUCCESSFULLY</b>")
        else:
            lines.append(f"❌ <b>POSITION CLOSE FAILED</b>")

        lines.append(f"")
        lines.append(f"<b>Symbol:</b> {symbol}")
        lines.append(f"<b>Account:</b> {account_label}")

        # Orders cancelled
        orders_cancelled = summary.get("total_orders_cancelled", 0)
        if orders_cancelled > 0:
            lines.append(f"<b>Orders Cancelled:</b> {orders_cancelled}")

        # Position details if available
        if summary.get("position_details"):
            pos = summary["position_details"]
            pnl = float(pos.get("unrealisedPnl", 0))
            if pnl != 0:
                pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                lines.append(f"<b>Final P&L:</b> {pnl_emoji} ${pnl:.2f}")

        # Errors
        errors = summary.get("errors", [])
        if errors:
            lines.append(f"\n⚠️ <b>Errors:</b>")
            for error in errors:
                lines.append(f"• {error}")

        return "\n".join(lines)


# Global instance
position_manager = PositionManager()