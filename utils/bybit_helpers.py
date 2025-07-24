#!/usr/bin/env python3
"""
Helper functions for Bybit API operations.
This file provides async wrappers for pybit operations.
ENHANCED: Updated to be consistent with the enhanced clients/bybit_helpers.py
FIXED: Improved error handling and reliability
"""
import asyncio
import logging
from typing import Optional, Dict, List
from decimal import Decimal

from clients.bybit_client import bybit_client

logger = logging.getLogger(__name__)

# REMOVED: get_position_info - Use the one from clients.bybit_helpers instead
# This avoids duplication and confusion about return types

async def get_all_positions() -> List[Dict]:
    """Get all open positions with enhanced error handling."""
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client.get_positions(
                category="linear",
                settleCoin="USDT"
            )
        )

        if response and response.get("retCode") == 0:
            return response.get("result", {}).get("list", [])
        return []
    except Exception as e:
        logger.error(f"Error fetching all positions: {e}")
        return []

async def get_order_info(symbol: str, order_id: str) -> Optional[Dict]:
    """Get information about a specific order."""
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client.get_open_orders(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )
        )

        if response and response.get("retCode") == 0:
            orders = response.get("result", {}).get("list", [])
            return orders[0] if orders else None
        return None
    except Exception as e:
        logger.error(f"Error fetching order info for {order_id}: {e}")
        return None

async def place_order_with_retry(symbol: str, side: str, order_type: str,
                                qty: str, price: Optional[str] = None,
                                trigger_price: Optional[str] = None,
                                position_idx: int = 0,
                                reduce_only: bool = False,
                                time_in_force: Optional[str] = None,
                                max_retries: int = 3) -> Optional[Dict]:
    """
    Place an order with retry logic and enhanced error handling.

    This is a simplified version - for full functionality use clients.bybit_helpers.place_order_with_retry
    """
    for attempt in range(max_retries):
        try:
            # Build order parameters
            params = {
                "category": "linear",
                "symbol": symbol,
                "side": side,
                "orderType": order_type,
                "qty": qty,
                "positionIdx": position_idx
            }

            if price:
                params["price"] = price

            if trigger_price:
                params["triggerPrice"] = trigger_price
                # Simplified trigger direction logic
                params["triggerDirection"] = 1 if side == "Buy" else 2
                if order_type != "Market":
                    params["orderType"] = "Market"  # Conditional orders are typically market orders
                params["triggerBy"] = "LastPrice"

            if reduce_only:
                params["reduceOnly"] = True

            if time_in_force:
                params["timeInForce"] = time_in_force

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: bybit_client.place_order(**params)
            )

            if response and response.get("retCode") == 0:
                result = response.get("result", {})
                logger.info(f"✅ Order placed successfully: {result.get('orderId')}")
                return result

            ret_code = response.get("retCode", 0)
            ret_msg = response.get("retMsg", "")

            if ret_code != 0:
                logger.warning(f"Order placement failed (attempt {attempt + 1}): {ret_msg}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                    continue

            return None

        except Exception as e:
            logger.error(f"Error placing order (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
            return None

    return None

async def cancel_order_with_retry(symbol: str, order_id: str,
                                 max_retries: int = 3) -> bool:
    """
    Cancel an order with retry logic and enhanced error handling.

    This is a simplified version - for full functionality use clients.bybit_helpers.cancel_order_with_retry
    """
    if not order_id:
        logger.warning("❌ Cannot cancel order: No order ID provided")
        return False

    logger.info(f"🔄 Attempting to cancel order {order_id[:8]}... for {symbol}")

    for attempt in range(max_retries):
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: bybit_client.cancel_order(
                    category="linear",
                    symbol=symbol,
                    orderId=order_id
                )
            )

            if response and response.get("retCode") == 0:
                logger.info(f"✅ Order {order_id[:8]}... cancelled successfully")
                return True

            # Handle specific error codes
            ret_code = response.get("retCode", 0)
            ret_msg = response.get("retMsg", "Unknown error")

            if ret_code == 110001:  # Order not found
                logger.info(f"ℹ️ Order {order_id[:8]}... not found (already filled/cancelled)")
                return True  # Consider this success since order is gone
            elif ret_code == 110004:  # Order already cancelled
                logger.info(f"ℹ️ Order {order_id[:8]}... already cancelled")
                return True
            elif ret_code == 110005:  # Order already filled
                logger.info(f"ℹ️ Order {order_id[:8]}... already filled")
                return True  # Order executed, no need to cancel

            logger.warning(f"❌ Cancel order failed (attempt {attempt + 1}): {ret_msg}")

        except Exception as e:
            logger.error(f"❌ Error canceling order (attempt {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(2)

    logger.error(f"❌ Failed to cancel order {order_id[:8]}... after {max_retries} attempts")
    return False

async def amend_order_with_retry(symbol: str, order_id: str,
                                trigger_price: Optional[str] = None,
                                qty: Optional[str] = None,
                                price: Optional[str] = None,
                                max_retries: int = 3) -> Optional[Dict]:
    """
    Amend an order with retry logic and enhanced error handling.

    This is a simplified version - for full functionality use clients.bybit_helpers.amend_order_with_retry
    """
    for attempt in range(max_retries):
        try:
            params = {
                "category": "linear",
                "symbol": symbol,
                "orderId": order_id
            }

            if trigger_price:
                params["triggerPrice"] = trigger_price
            if qty:
                params["qty"] = qty
            if price:
                params["price"] = price

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: bybit_client.amend_order(**params)
            )

            if response and response.get("retCode") == 0:
                logger.info(f"✅ Order {order_id[:8]}... amended successfully")
                return response.get("result")

            logger.warning(f"Amend order failed (attempt {attempt + 1}): {response}")

        except Exception as e:
            logger.error(f"Error amending order (attempt {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(2)

    return None

async def get_current_price(symbol: str) -> float:
    """Get current market price for symbol with enhanced error handling."""
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client.get_tickers(
                category="linear",
                symbol=symbol
            )
        )

        if response and response.get("retCode") == 0:
            tickers = response.get("result", {}).get("list", [])
            if tickers:
                return float(tickers[0].get("lastPrice", 0))

        return 0.0

    except Exception as e:
        logger.error(f"Error getting current price for {symbol}: {e}")
        return 0.0

async def get_account_balance() -> float:
    """Get available USDT balance with enhanced error handling."""
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client.get_wallet_balance(
                accountType="UNIFIED",
                coin="USDT"
            )
        )

        if response and response.get("retCode") == 0:
            account_list = response.get("result", {}).get("list", [])
            if account_list:
                coins = account_list[0].get("coin", [])
                for coin in coins:
                    if coin.get("coin") == "USDT":
                        return float(coin.get("availableToWithdraw", 0))

        return 0.0

    except Exception as e:
        logger.error(f"Error getting account balance: {e}")
        return 0.0

# =============================================
# INTEGRATION WITH ENHANCED CLIENT
# =============================================

def use_enhanced_client():
    """
    Recommendation: For full functionality including ultra-conservative orphan detection,
    advanced order management, and enhanced error handling, use:

    from clients.bybit_helpers import (
        run_enhanced_orphan_scanner,
        protect_symbol_from_cleanup,
        protect_trade_group_from_cleanup,
        api_call_with_retry
    )

    This utils version provides basic functionality for backward compatibility.
    """
    pass

# Legacy compatibility functions
async def check_existing_position(symbol: str) -> Optional[Dict]:
    """Legacy wrapper - use clients.bybit_helpers.get_position_info instead"""
    from clients.bybit_helpers import get_position_info
    positions = await get_position_info(symbol)
    # Return first position for backward compatibility
    if positions and len(positions) > 0:
        return positions[0]
    return None

async def get_active_positions() -> List[Dict]:
    """Get only active positions (size > 0)"""
    try:
        all_positions = await get_all_positions()
        active_positions = []

        for pos in all_positions:
            size = float(pos.get("size", "0"))
            if size > 0:
                active_positions.append(pos)

        return active_positions

    except Exception as e:
        logger.error(f"Error filtering active positions: {e}")
        return []

async def get_total_unrealised_pnl() -> float:
    """Get total unrealised P&L across all positions"""
    try:
        positions = await get_all_positions()
        total_pnl = 0.0

        for pos in positions:
            unrealised_pnl = float(pos.get("unrealisedPnl", "0"))
            total_pnl += unrealised_pnl

        return total_pnl

    except Exception as e:
        logger.error(f"Error calculating total unrealised P&L: {e}")
        return 0.0