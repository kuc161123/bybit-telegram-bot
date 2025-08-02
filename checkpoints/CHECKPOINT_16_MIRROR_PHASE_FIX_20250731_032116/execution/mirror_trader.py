#!/usr/bin/env python3
"""
Mirror Trading Module - Replicates trades on a second Bybit account
This module operates as a sidecar to the main trading system.
It does NOT modify existing trade logic, only adds mirror functionality.
"""
import os
import asyncio
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List
from decimal import Decimal
from pybit.unified_trading import HTTP
from utils.quantity_formatter import format_quantity_for_exchange, validate_quantity_for_order

logger = logging.getLogger(__name__)

# Initialize second Bybit client ONLY if mirror trading is enabled
ENABLE_MIRROR_TRADING = os.getenv("ENABLE_MIRROR_TRADING", "false").lower() == "true"
BYBIT_API_KEY_2 = os.getenv("BYBIT_API_KEY_2", "")
BYBIT_API_SECRET_2 = os.getenv("BYBIT_API_SECRET_2", "")
USE_TESTNET = os.getenv("USE_TESTNET", "false").lower() == "true"

# Only initialize if credentials are provided
bybit_client_2 = None
if ENABLE_MIRROR_TRADING and BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
    try:
        # Initialize mirror client with standard configuration
        # Note: HTTP session optimization will be handled during async operations
        bybit_client_2 = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2
        )
        logger.info("✅ Mirror trading client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize mirror trading client: {e}")
        ENABLE_MIRROR_TRADING = False

# Position mode cache no longer needed - mirror account uses One-Way Mode
# POSITION_MODE_CACHE = {}  # Removed - unified One-Way Mode
# POSITION_MODE_CACHE_TTL = 300  # Removed - no longer needed

async def detect_position_mode_for_symbol_mirror(symbol: str) -> Tuple[bool, int]:
    """
    Detect position mode for a specific symbol on the mirror account.

    NOTE: As of the fresh start process, mirror account has been switched to One-Way Mode.
    This function now always returns One-Way Mode for consistency.

    Returns:
        Tuple[bool, int]: (is_hedge_mode, default_position_idx)
        - is_hedge_mode: Always False (One-Way Mode)
        - default_position_idx: Always 0 (One-Way Mode)
    """
    if not ENABLE_MIRROR_TRADING or not bybit_client_2:
        return False, 0  # Default to one-way mode if mirror trading disabled

    # Mirror account is now permanently in One-Way Mode
    # This eliminates the complexity of mode detection and caching
    logger.debug(f"🔄 MIRROR: Using One-Way Mode for {symbol} (mirror account configured)")
    return False, 0

def get_position_idx_for_side(side: str, is_hedge_mode: bool) -> int:
    """
    Get the correct positionIdx for the given side and mode.

    NOTE: Mirror account is now permanently in One-Way Mode, so this always returns 0.
    """
    # Mirror account is always in One-Way Mode now
    return 0

async def set_mirror_leverage(symbol: str, leverage: int) -> bool:
    """
    Set leverage for a symbol on the mirror account.

    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')
        leverage: Leverage value (e.g., 10 for 10x)

    Returns:
        bool: True if successful, False otherwise
    """
    if not ENABLE_MIRROR_TRADING or not bybit_client_2:
        return False

    try:
        logger.info(f"🔄 MIRROR: Setting leverage for {symbol} to {leverage}x...")

        response = bybit_client_2.set_leverage(
            category="linear",
            symbol=symbol,
            buyLeverage=str(leverage),
            sellLeverage=str(leverage)
        )

        if response and response.get('retCode') == 0:
            logger.info(f"✅ MIRROR: Successfully set {symbol} leverage to {leverage}x")
            return True
        elif response and response.get('retCode') == 110043:
            # Leverage already set - this is fine
            logger.debug(f"✅ MIRROR: {symbol} leverage already at {leverage}x")
            return True
        else:
            logger.error(f"❌ MIRROR: Failed to set leverage for {symbol}: {response}")
            return False

    except Exception as e:
        # Handle leverage not modified error (110043) silently
        error_msg = str(e)
        if "110043" in error_msg and "leverage not modified" in error_msg:
            logger.debug(f"✅ MIRROR: {symbol} leverage already at {leverage}x (no change needed)")
            return True
        logger.error(f"❌ MIRROR: Error setting leverage for {symbol}: {e}")
        return False

async def mirror_market_order(
    symbol: str,
    side: str,
    qty: str,
    position_idx: int,
    order_link_id: Optional[str] = None
) -> Optional[Dict]:
    """
    Mirror a market order on the second account.
    Returns None on failure to ensure it doesn't affect primary trading.
    """
    if not ENABLE_MIRROR_TRADING or not bybit_client_2:
        return None

    try:
        # Validate and format quantity to prevent scientific notation
        if not validate_quantity_for_order(qty, symbol):
            logger.error(f"❌ MIRROR: Invalid quantity format for {symbol}: {qty}")
            return None

        # Format quantity properly (this prevents scientific notation)
        formatted_qty = format_quantity_for_exchange(qty, "0.001")  # Default step

        # Detect position mode for mirror account and get correct positionIdx
        is_hedge_mode, _ = await detect_position_mode_for_symbol_mirror(symbol)
        mirror_position_idx = get_position_idx_for_side(side, is_hedge_mode)

        logger.info(f"🔄 MIRROR: Position mode for {symbol}: {'HEDGE' if is_hedge_mode else 'ONE-WAY'}, using positionIdx={mirror_position_idx}")
        logger.debug(f"🔄 MIRROR: Formatted quantity: {qty} -> {formatted_qty}")

        # Use order link ID as-is if it already contains _MIRROR, otherwise add _MIRROR suffix
        if order_link_id and "_MIRROR" in order_link_id:
            mirror_link_id = order_link_id
        else:
            mirror_link_id = f"{order_link_id}_MIRROR" if order_link_id else None

        # Execute mirror order in thread executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client_2.place_order(
                category="linear",
                symbol=symbol,
                side=side,
                orderType="Market",
                qty=formatted_qty,  # Use formatted quantity
                positionIdx=mirror_position_idx,  # Use detected position index
                orderLinkId=mirror_link_id
            )
        )

        if response and response.get("retCode") == 0:
            result = response.get("result", {})
            order_id = result.get("orderId", "")
            logger.info(f"✅ MIRROR: Market order placed successfully: {order_id[:8]}...")
            return result
        else:
            logger.error(f"❌ MIRROR: Market order failed: {response}")
            return None

    except Exception as e:
        logger.error(f"❌ MIRROR: Exception placing market order: {e}")
        return None

async def mirror_limit_order(
    symbol: str,
    side: str,
    qty: str,
    price: str,
    position_idx: int,
    order_link_id: Optional[str] = None
) -> Optional[Dict]:
    """
    Mirror a limit order on the second account.
    Returns None on failure to ensure it doesn't affect primary trading.
    """
    if not ENABLE_MIRROR_TRADING or not bybit_client_2:
        return None

    try:
        # Validate and format quantity to prevent scientific notation
        if not validate_quantity_for_order(qty, symbol):
            logger.error(f"❌ MIRROR: Invalid quantity format for {symbol}: {qty}")
            return None

        # Format quantity properly (this prevents scientific notation)
        formatted_qty = format_quantity_for_exchange(qty, "0.001")  # Default step

        # Detect position mode for mirror account and get correct positionIdx
        is_hedge_mode, _ = await detect_position_mode_for_symbol_mirror(symbol)
        mirror_position_idx = get_position_idx_for_side(side, is_hedge_mode)

        logger.info(f"🔄 MIRROR: Position mode for {symbol}: {'HEDGE' if is_hedge_mode else 'ONE-WAY'}, using positionIdx={mirror_position_idx}")
        logger.debug(f"🔄 MIRROR: Formatted quantity: {qty} -> {formatted_qty}")

        # Use order link ID as-is if it already contains _MIRROR, otherwise add _MIRROR suffix
        if order_link_id and "_MIRROR" in order_link_id:
            mirror_link_id = order_link_id
        else:
            mirror_link_id = f"{order_link_id}_MIRROR" if order_link_id else None

        # Execute mirror order in thread executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client_2.place_order(
                category="linear",
                symbol=symbol,
                side=side,
                orderType="Limit",
                qty=formatted_qty,  # Use formatted quantity
                price=price,
                positionIdx=mirror_position_idx,  # Use detected position index
                orderLinkId=mirror_link_id
            )
        )

        if response and response.get("retCode") == 0:
            result = response.get("result", {})
            order_id = result.get("orderId", "")
            logger.info(f"✅ MIRROR: Limit order placed successfully: {order_id[:8]}...")
            return result
        else:
            logger.error(f"❌ MIRROR: Limit order failed: {response}")
            return None

    except Exception as e:
        logger.error(f"❌ MIRROR: Exception placing limit order: {e}")
        return None

async def mirror_tp_sl_order(
    symbol: str,
    side: str,
    qty: str,
    trigger_price: str,
    position_idx: int,
    order_type: str = "Market",
    reduce_only: bool = True,
    order_link_id: Optional[str] = None,
    stop_order_type: Optional[str] = None
) -> Optional[Dict]:
    """
    Mirror a TP/SL order on the second account.
    IMPORTANT: TP orders are placed as LIMIT orders, SL orders as STOP orders
    Returns None on failure to ensure it doesn't affect primary trading.
    """
    if not ENABLE_MIRROR_TRADING or not bybit_client_2:
        return None

    try:
        # Check if this is a TP order - if so, use limit order instead
        is_tp_order = (stop_order_type == "TakeProfit" or 
                      (order_link_id and "TP" in order_link_id.upper()))
        
        if is_tp_order:
            # For TP orders, use limit order
            logger.info(f"🔄 MIRROR: Placing TP as LIMIT order for {symbol}")
            return await mirror_limit_order(
                symbol=symbol,
                side=side,
                qty=qty,
                price=trigger_price,  # Use trigger_price as limit price
                position_idx=position_idx,
                order_link_id=order_link_id
            )
        # Validate and format quantity to prevent scientific notation
        if not validate_quantity_for_order(qty, symbol):
            logger.error(f"❌ MIRROR: Invalid quantity format for {symbol}: {qty}")
            return None

        # Format quantity properly (this prevents scientific notation)
        formatted_qty = format_quantity_for_exchange(qty, "0.001")  # Default step

        # Detect position mode for mirror account and get correct positionIdx
        is_hedge_mode, _ = await detect_position_mode_for_symbol_mirror(symbol)
        mirror_position_idx = get_position_idx_for_side(side, is_hedge_mode)

        logger.debug(f"🔄 MIRROR TP/SL: Position mode for {symbol}: {'HEDGE' if is_hedge_mode else 'ONE-WAY'}, using positionIdx={mirror_position_idx}")
        logger.debug(f"🔄 MIRROR TP/SL: Formatted quantity: {qty} -> {formatted_qty}")

        # Use order link ID as-is if it already contains _MIRROR, otherwise add _MIRROR suffix
        if order_link_id and "_MIRROR" in order_link_id:
            mirror_link_id = order_link_id
        else:
            mirror_link_id = f"{order_link_id}_MIRROR" if order_link_id else None

        # Determine trigger direction
        current_price = await get_mirror_current_price(symbol)
        if current_price:
            trigger_price_float = float(trigger_price)
            if side == "Buy":  # Closing short
                trigger_direction = 2 if trigger_price_float < current_price else 1
            else:  # Closing long
                trigger_direction = 1 if trigger_price_float > current_price else 2
        else:
            trigger_direction = 1 if side == "Buy" else 2

        # Build order parameters
        order_params = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "qty": formatted_qty,  # Use formatted quantity
            "triggerPrice": trigger_price,
            "triggerDirection": trigger_direction,
            "triggerBy": "LastPrice",
            "positionIdx": mirror_position_idx,  # Use detected position index
            "reduceOnly": reduce_only,
            "orderLinkId": mirror_link_id
        }

        # Add stopOrderType if provided
        if stop_order_type:
            order_params["stopOrderType"] = stop_order_type

        # Execute mirror order in thread executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client_2.place_order(**order_params)
        )

        if response and response.get("retCode") == 0:
            result = response.get("result", {})
            order_id = result.get("orderId", "")
            logger.info(f"✅ MIRROR: TP/SL order placed successfully: {order_id[:8]}...")
            return result
        else:
            logger.error(f"❌ MIRROR: TP/SL order failed: {response}")
            return None

    except Exception as e:
        logger.error(f"❌ MIRROR: Exception placing TP/SL order: {e}")
        return None

async def amend_mirror_sl_order(symbol: str, order_id: str, new_trigger_price: str) -> Optional[Dict[str, Any]]:
    """
    Amend a stop loss order on the mirror account to move it to breakeven + fees

    Args:
        symbol: Trading symbol (e.g., "BTCUSDT")
        order_id: The order ID of the SL order to amend
        new_trigger_price: The new trigger price for the SL order

    Returns:
        Response from Bybit API or None if failed
    """
    if not ENABLE_MIRROR_TRADING or not bybit_client_2:
        return None

    try:
        logger.info(f"🔄 MIRROR: Amending SL order {order_id[:8]}... to trigger at {new_trigger_price}")

        # Execute amend order in thread executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client_2.amend_order(
                category="linear",
                symbol=symbol,
                orderId=order_id,
                triggerPrice=new_trigger_price
            )
        )

        if response and response.get("retCode") == 0:
            logger.info(f"✅ MIRROR: SL order amended successfully to breakeven + fees")
            return response.get("result", {})
        else:
            error_msg = response.get("retMsg", "Unknown error") if response else "No response"
            logger.error(f"❌ MIRROR: Failed to amend SL order: {error_msg}")
            return None

    except Exception as e:
        logger.error(f"❌ MIRROR: Exception amending SL order: {e}")
        return None

async def get_mirror_current_price(symbol: str) -> Optional[float]:
    """Get current price from mirror account."""
    if not bybit_client_2:
        return None

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client_2.get_tickers(
                category="linear",
                symbol=symbol
            )
        )

        if response and response.get("retCode") == 0:
            tickers = response.get("result", {}).get("list", [])
            if tickers:
                return float(tickers[0].get("lastPrice", 0))
        return None

    except Exception as e:
        logger.error(f"❌ MIRROR: Error getting current price: {e}")
        return None

async def place_mirror_tp_sl_order(*args, **kwargs):
    """Alias for mirror_tp_sl_order for backward compatibility"""
    return await mirror_tp_sl_order(*args, **kwargs)

async def cancel_mirror_order(symbol: str, order_id: str) -> bool:
    """Cancel an order on the mirror account."""
    if not ENABLE_MIRROR_TRADING or not bybit_client_2:
        return False

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client_2.cancel_order(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )
        )

        if response and response.get("retCode") == 0:
            logger.info(f"✅ MIRROR: Order {order_id[:8]}... cancelled successfully")
            return True
        elif response and response.get("retCode") == 110001:
            # Order not exists or already cancelled/filled
            logger.info(f"ℹ️ MIRROR: Order {order_id[:8]}... already cancelled or filled")
            return True  # Consider this a success since the order is no longer active
        else:
            logger.error(f"❌ MIRROR: Failed to cancel order: {response}")
            return False

    except Exception as e:
        # Handle specific order cancellation errors more gracefully
        error_str = str(e).lower()
        if "order not exists" in error_str or "too late to cancel" in error_str or "110001" in error_str:
            logger.info(f"ℹ️ MIRROR: Order {order_id[:8]}... already cancelled or filled (exception)")
            return True  # Consider this a success since the order is no longer active
        else:
            logger.error(f"❌ MIRROR: Exception cancelling order: {e}")
            return False


# Status check function
def is_mirror_trading_enabled() -> bool:
    """Check if mirror trading is enabled and properly configured."""
    return ENABLE_MIRROR_TRADING and bybit_client_2 is not None

async def get_mirror_wallet_balance() -> Tuple[Decimal, Decimal]:
    """
    Get USDT wallet balance from mirror account.
    Returns (total_balance, available_balance)
    """
    if not ENABLE_MIRROR_TRADING or not bybit_client_2:
        return (Decimal("0"), Decimal("0"))

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client_2.get_wallet_balance(accountType="UNIFIED")
        )

        if response and response.get("retCode") == 0:
            result = response.get("result", {})
            accounts = result.get("list", [])

            if accounts:
                account = accounts[0]
                # Get balance from account level
                total_balance = Decimal(account.get("totalWalletBalance", "0"))
                available_balance = Decimal(account.get("totalAvailableBalance", "0"))

                logger.debug(f"🪞 MIRROR: Account Balance - Total: {total_balance}, Available: {available_balance}")

                # Also check USDT coin details if needed
                coins = account.get("coin", [])
                for coin in coins:
                    if coin.get("coin") == "USDT":
                        # Use coin wallet balance if account level is zero
                        coin_balance = Decimal(coin.get("walletBalance", "0"))
                        if total_balance == 0 and coin_balance > 0:
                            total_balance = coin_balance
                        break

                return (total_balance, available_balance)

        return (Decimal("0"), Decimal("0"))

    except Exception as e:
        logger.error(f"❌ MIRROR: Error fetching wallet balance: {e}")
        return (Decimal("0"), Decimal("0"))

async def get_mirror_positions() -> List[Dict]:
    """
    Get all open positions from mirror account with pagination.
    """
    if not ENABLE_MIRROR_TRADING or not bybit_client_2:
        return []

    try:
        all_positions = []
        cursor = None
        page_count = 0
        max_pages = 10  # Safety limit

        logger.debug("🪞 MIRROR: Fetching all positions...")

        while page_count < max_pages:
            page_count += 1

            # Build API parameters
            params = {
                "category": "linear",
                "settleCoin": "USDT",
                "limit": 200
            }

            if cursor:
                params["cursor"] = cursor

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: bybit_client_2.get_positions(**params)
            )

            if not response or response.get("retCode") != 0:
                logger.error(f"❌ MIRROR: Failed to get positions page {page_count}: {response}")
                break

            result = response.get("result", {})
            page_positions = result.get("list", [])
            next_cursor = result.get("nextPageCursor", "")

            # Add positions from this page
            all_positions.extend(page_positions)
            logger.debug(f"🪞 MIRROR: Page {page_count}: Found {len(page_positions)} positions")

            # Check if we have more pages
            if not next_cursor or next_cursor == cursor:
                break

            cursor = next_cursor

        # Filter active positions (size > 0)
        active_positions = [p for p in all_positions if float(p.get('size', 0)) > 0]
        logger.info(f"🪞 MIRROR: Total positions: {len(active_positions)}")

        return active_positions

    except Exception as e:
        logger.error(f"❌ MIRROR: Error fetching positions: {e}")
        return []

async def calculate_mirror_pnl() -> Tuple[Decimal, Decimal]:
    """
    Calculate total realized and unrealized P&L for mirror account.
    Returns (total_unrealized_pnl, total_realized_pnl_today)
    """
    if not ENABLE_MIRROR_TRADING or not bybit_client_2:
        return (Decimal("0"), Decimal("0"))

    try:
        # Get all active positions for unrealized P&L
        positions = await get_mirror_positions()
        total_unrealized_pnl = Decimal("0")

        for pos in positions:
            unrealized_pnl = Decimal(str(pos.get('unrealisedPnl', '0')))
            total_unrealized_pnl += unrealized_pnl

        # Get today's realized P&L
        total_realized_pnl = Decimal("0")
        try:
            loop = asyncio.get_event_loop()
            # Get closed P&L for today
            response = await loop.run_in_executor(
                None,
                lambda: bybit_client_2.get_closed_pnl(
                    category="linear",
                    limit=200
                )
            )

            if response and response.get("retCode") == 0:
                pnl_list = response.get("result", {}).get("list", [])

                # Sum up today's realized P&L
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                today_timestamp = int(today_start.timestamp() * 1000)

                for pnl_entry in pnl_list:
                    created_time = int(pnl_entry.get('createdTime', '0'))
                    if created_time >= today_timestamp:
                        closed_pnl = Decimal(str(pnl_entry.get('closedPnl', '0')))
                        total_realized_pnl += closed_pnl
        except Exception as e:
            logger.warning(f"⚠️ MIRROR: Could not fetch realized P&L: {e}")

        logger.info(f"🪞 MIRROR: P&L - Unrealized: {total_unrealized_pnl}, Realized Today: {total_realized_pnl}")
        return (total_unrealized_pnl, total_realized_pnl)

    except Exception as e:
        logger.error(f"❌ MIRROR: Error calculating P&L: {e}")
        return (Decimal("0"), Decimal("0"))

async def get_mirror_position_info(symbol: str) -> Optional[List[Dict]]:
    """
    Get position info from mirror account for a specific symbol.

    Args:
        symbol: Trading symbol (e.g., "BTCUSDT")

    Returns:
        List of position dictionaries or None if failed
    """
    if not ENABLE_MIRROR_TRADING or not bybit_client_2:
        return None

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client_2.get_positions(
                category="linear",
                symbol=symbol
            )
        )

        if response and response.get("retCode") == 0:
            positions = response.get("result", {}).get("list", [])
            return positions
        else:
            logger.error(f"❌ MIRROR: Failed to get position info for {symbol}: {response}")
            return None

    except Exception as e:
        logger.error(f"❌ MIRROR: Exception getting position info: {e}")
        return None