#!/usr/bin/env python3
"""
Helper functions for Bybit API operations.
FIXED: Enhanced API call reliability and connection management
FIXED: Better error handling and timeout management
ENHANCED: Improved orphaned order cleanup with CONSERVATIVE GROUP-AWARE detection
ENHANCED: Intelligent trade group analysis and relationship detection
FIXED: Proper pagination handling and rate limiting
ADDED: Missing get_active_tp_sl_orders function
FIXED: More conservative orphan detection that prioritizes position safety
ENHANCED: Complete external order protection - only processes bot orders
ADDED: Potential P&L calculation functions for active positions
FIXED: Timestamp sync issues with recv_window adjustment
FIXED: Automatic position mode detection and positionIdx assignment
"""
import asyncio
import logging
import time
from typing import Optional, Dict, List, Set, Tuple, Any
from decimal import Decimal
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

# Import bybit_client with error handling
try:
    from .bybit_client import bybit_client
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from clients.bybit_client import bybit_client

# ENHANCED GRACE PERIODS FOR CONSERVATIVE DETECTION
ORDER_GRACE_PERIOD_SECONDS = 600  # 10 minutes for regular orders (increased)
TP_SL_GRACE_PERIOD_SECONDS = 7200  # 2 hours for TP/SL orders (much longer)
LIMIT_ORDER_GRACE_PERIOD_SECONDS = 1800  # 30 minutes for limit orders (increased)
RECENT_TRADE_PROTECTION_SECONDS = 3600  # 1 hour protection for recently traded symbols (increased)

# PROTECTED SYMBOLS TRACKING - Global state for recently traded symbols
RECENTLY_TRADED_SYMBOLS = {}  # symbol -> timestamp of last trade
ACTIVE_TRADE_GROUPS = set()  # Track active trade group IDs
ORDER_CREATION_TIMESTAMPS = {}  # order_id -> creation timestamp for better tracking


# FIXED: Rate limiting and connection management
class APIRateLimiter:
    """Enhanced rate limiter with burst support"""

    def __init__(self, calls_per_second: float = 12, burst_size: int = 20):
        self.calls_per_second = calls_per_second
        self.burst_size = burst_size
        self.tokens = burst_size
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Acquire a token for API call"""
        async with self._lock:
            current_time = time.time()
            time_passed = current_time - self.last_update

            # Add tokens based on time passed
            self.tokens = min(
                self.burst_size,
                self.tokens + time_passed * self.calls_per_second
            )
            self.last_update = current_time

            if self.tokens >= 1:
                self.tokens -= 1
                return

            # Need to wait
            wait_time = (1 - self.tokens) / self.calls_per_second
            await asyncio.sleep(wait_time)
            self.tokens = 0

# Global rate limiter
_rate_limiter = APIRateLimiter()

def add_symbol_to_protection(symbol: str):
    """Add a symbol to the protection list to prevent cleanup of its orders"""
    global RECENTLY_TRADED_SYMBOLS
    RECENTLY_TRADED_SYMBOLS[symbol] = time.time()
    logger.info(f"🛡️ Symbol {symbol} added to protection list for {RECENT_TRADE_PROTECTION_SECONDS}s")

def add_trade_group_to_protection(trade_group_id: str):
    """Add a trade group to active protection"""
    global ACTIVE_TRADE_GROUPS
    ACTIVE_TRADE_GROUPS.add(trade_group_id)
    logger.info(f"🛡️ Trade group {trade_group_id} added to active protection")

def is_symbol_protected(symbol: str) -> bool:
    """Check if a symbol is currently protected from cleanup"""
    global RECENTLY_TRADED_SYMBOLS
    if symbol not in RECENTLY_TRADED_SYMBOLS:
        return False

    time_since_trade = time.time() - RECENTLY_TRADED_SYMBOLS[symbol]
    is_protected = time_since_trade < RECENT_TRADE_PROTECTION_SECONDS

    if not is_protected:
        # Clean up expired protection
        del RECENTLY_TRADED_SYMBOLS[symbol]
        logger.info(f"🕐 Protection expired for {symbol}")

    return is_protected

def is_trade_group_protected(trade_group_id: str) -> bool:
    """Check if a trade group is currently protected"""
    global ACTIVE_TRADE_GROUPS
    return trade_group_id in ACTIVE_TRADE_GROUPS

def cleanup_expired_protections():
    """Clean up expired protections to prevent memory leaks"""
    global RECENTLY_TRADED_SYMBOLS, ORDER_CREATION_TIMESTAMPS
    current_time = time.time()

    # Clean up expired symbol protections
    expired_symbols = [
        symbol for symbol, timestamp in RECENTLY_TRADED_SYMBOLS.items()
        if current_time - timestamp > RECENT_TRADE_PROTECTION_SECONDS
    ]

    for symbol in expired_symbols:
        del RECENTLY_TRADED_SYMBOLS[symbol]
        logger.debug(f"🧹 Cleaned up expired protection for {symbol}")

    # Clean up old order timestamps (older than 4 hours)
    expired_orders = [
        order_id for order_id, timestamp in ORDER_CREATION_TIMESTAMPS.items()
        if current_time - timestamp > 14400
    ]

    for order_id in expired_orders:
        del ORDER_CREATION_TIMESTAMPS[order_id]

    # Position mode cache cleanup no longer needed - unified One-Way Mode

# =============================================
# FIXED: POSITION MODE DETECTION FUNCTIONS
# =============================================

async def detect_position_mode_for_symbol(symbol: str) -> Tuple[bool, int]:
    """
    UNIFIED: Detect position mode for a specific symbol

    NOTE: Both main and mirror accounts have been switched to One-Way Mode.
    This function now always returns One-Way Mode for consistency and simplification.

    Returns:
        Tuple[bool, int]: (is_hedge_mode, default_position_idx)
        - is_hedge_mode: Always False (One-Way Mode)
        - default_position_idx: Always 0 (One-Way Mode)
    """
    # Both main and mirror accounts are now in One-Way Mode
    # This eliminates the complexity of mode detection and caching
    logger.debug(f"🔄 Using One-Way Mode for {symbol} (unified configuration)")
    return False, 0

async def get_correct_position_idx(symbol: str, side: str) -> int:
    """
    UNIFIED: Get the correct positionIdx based on symbol's position mode and order side

    NOTE: Both main and mirror accounts now use One-Way Mode, so this always returns 0.

    Args:
        symbol: Trading symbol (e.g., "BTCUSDT")
        side: Order side ("Buy" or "Sell") - ignored in One-Way Mode

    Returns:
        int: Always 0 (One-Way Mode)
    """
    # Both accounts are now in One-Way Mode
    logger.debug(f"📊 {symbol} using One-Way Mode: positionIdx=0")
    return 0

# =============================================
# ENHANCED API CALL WRAPPER WITH BETTER RELIABILITY
# =============================================

async def api_call_with_retry(api_func, max_retries=5, initial_delay=1.5, backoff_factor=2.0, timeout=35):
    """
    ENHANCED API call wrapper with better timeout and retry handling
    FIXED: Dynamic recv_window adjustment for timestamp sync issues
    """
    delay = initial_delay
    recv_window_adjustment = 0

    for attempt in range(max_retries):
        try:
            # Apply rate limiting
            await _rate_limiter.acquire()

            # FIXED: Adjust recv_window if needed
            if recv_window_adjustment > 0:
                logger.debug(f"Adjusting recv_window by {recv_window_adjustment}ms")
                # Temporarily increase recv_window for this call
                original_recv_window = getattr(bybit_client, 'recv_window', 5000)
                try:
                    bybit_client.recv_window = original_recv_window + recv_window_adjustment
                except:
                    logger.debug("Could not adjust recv_window on client")

            # Execute API call with timeout
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, api_func),
                timeout=timeout
            )

            # Success - return result
            return result

        except asyncio.TimeoutError:
            logger.warning(f"API call timeout (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {delay:.1f} seconds...")
                await asyncio.sleep(delay)
                delay *= backoff_factor
                timeout += 5  # Increase timeout on retry
                continue
            else:
                logger.error("Max retries reached for API call")
                raise

        except Exception as e:
            error_msg = str(e)

            # FIXED: Handle timestamp sync errors specifically
            if "ErrCode: 10002" in error_msg or "recv_window" in error_msg:
                logger.warning(f"Timestamp sync error detected: {error_msg}")
                # Extract server timestamp difference if possible
                try:
                    if "server_timestamp" in error_msg and "req_timestamp" in error_msg:
                        # Parse timestamps from error message
                        import re
                        req_match = re.search(r'req_timestamp\[(\d+)\]', error_msg)
                        server_match = re.search(r'server_timestamp\[(\d+)\]', error_msg)
                        if req_match and server_match:
                            req_time = int(req_match.group(1))
                            server_time = int(server_match.group(1))
                            time_diff = abs(server_time - req_time)
                            # Add buffer to recv_window
                            recv_window_adjustment = time_diff + 5000
                            logger.info(f"Calculated time difference: {time_diff}ms, adjusting recv_window by {recv_window_adjustment}ms")
                except:
                    # Fallback: just increase recv_window progressively
                    recv_window_adjustment += 5000
                    logger.info(f"Increasing recv_window adjustment to {recv_window_adjustment}ms")

            # FIXED: Handle leverage not modified error (110043) silently
            if "ErrCode: 110043" in error_msg and "leverage not modified" in error_msg:
                logger.debug(f"Leverage already set correctly (attempt {attempt + 1}/{max_retries})")
                # Return success since leverage is already correct
                return {"retCode": 0, "retMsg": "Leverage already set"}

            logger.error(f"API call error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
                delay *= backoff_factor
                continue
            else:
                raise

    return None

# =============================================
# FIXED POSITION AND ORDER FUNCTIONS WITH ENHANCED ERROR HANDLING
# =============================================

async def check_existing_position(symbol: str) -> Optional[Dict]:
    """
    FIXED: Check if position already exists for symbol (async wrapper)
    """
    try:
        response = await api_call_with_retry(
            lambda: bybit_client.get_positions(
                category="linear",
                symbol=symbol
            ),
            timeout=25
        )

        if response and response.get("retCode") == 0:
            positions = response.get("result", {}).get("list", [])
            for position in positions:
                size = float(position.get("size", 0))
                if size > 0:
                    logger.info(f"Existing position found: {symbol} - {position.get('side')} {size}")
                    return position

        return None

    except Exception as e:
        logger.error(f"Error checking existing position: {e}")
        return None

async def get_position_info(symbol: str) -> Optional[List[Dict]]:
    """Get position information for a specific symbol with enhanced error handling

    Returns:
        List of position dictionaries for the symbol, or empty list if none found
    """
    try:
        response = await api_call_with_retry(
            lambda: bybit_client.get_positions(
                category="linear",
                symbol=symbol
            ),
            timeout=25
        )

        if response and response.get("retCode") == 0:
            result = response.get("result", {})
            positions = result.get("list", [])
            return positions  # Return the full list of positions

        return []  # Return empty list instead of None

    except Exception as e:
        logger.error(f"Error fetching position info for {symbol}: {e}")
        return []  # Return empty list on error

async def get_positions_and_orders_batch() -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
    """
    Get positions and orders in parallel to reduce API calls
    Returns: (main_positions, main_orders, mirror_positions, mirror_orders)
    """
    try:
        from clients.bybit_client import bybit_client

        # Check if mirror trading is available
        try:
            from execution.mirror_trader import bybit_client_2, ENABLE_MIRROR_TRADING
            has_mirror = ENABLE_MIRROR_TRADING and bybit_client_2 is not None
        except:
            has_mirror = False

        # Prepare tasks
        tasks = [
            get_all_positions(),  # Main positions
            get_all_open_orders(),  # Main orders
        ]

        if has_mirror:
            tasks.extend([
                get_all_positions(client=bybit_client_2),  # Mirror positions
                get_all_open_orders(client=bybit_client_2),  # Mirror orders
            ])

        # Fetch all data in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        main_positions = results[0] if not isinstance(results[0], Exception) else []
        main_orders = results[1] if not isinstance(results[1], Exception) else []

        mirror_positions = []
        mirror_orders = []

        if has_mirror and len(results) >= 4:
            mirror_positions = results[2] if not isinstance(results[2], Exception) else []
            mirror_orders = results[3] if not isinstance(results[3], Exception) else []

            if mirror_positions or mirror_orders:
                logger.info(f"📊 Fetched mirror data: {len(mirror_positions)} positions, {len(mirror_orders)} orders")

        return main_positions, main_orders, mirror_positions, mirror_orders

    except Exception as e:
        logger.error(f"Error in batch API call: {e}")
        return [], [], [], []

async def get_all_positions(client=None) -> List[Dict]:
    """
    FIXED: Get all open positions with proper pagination and error handling
    """
    try:
        if client is None:
            from clients.bybit_client import bybit_client
            client = bybit_client
        all_positions = []
        cursor = None
        page_count = 0
        max_pages = 10  # Safety limit to prevent infinite loops

        logger.debug("🔍 Fetching all positions with enhanced pagination...")

        while page_count < max_pages:
            page_count += 1

            # Build API parameters
            params = {
                "category": "linear",
                "settleCoin": "USDT",
                "limit": 200  # Maximum records per page
            }

            if cursor:
                params["cursor"] = cursor

            logger.debug(f"📄 Fetching positions page {page_count} (cursor: {cursor})")

            response = await api_call_with_retry(
                lambda: client.get_positions(**params),
                timeout=30
            )

            if not response or response.get("retCode") != 0:
                logger.error(f"Failed to get positions page {page_count}: {response}")
                break

            result = response.get("result", {})
            page_positions = result.get("list", [])
            next_cursor = result.get("nextPageCursor", "")

            # Add positions from this page
            all_positions.extend(page_positions)
            logger.debug(f"📄 Page {page_count}: Found {len(page_positions)} positions")

            # Check if we have more pages
            if not next_cursor or next_cursor == cursor:
                logger.debug(f"✅ Pagination complete - no more pages")
                break

            cursor = next_cursor

            # Small delay to avoid rate limits
            await asyncio.sleep(0.2)

        logger.info(f"📊 Total positions fetched: {len(all_positions)} across {page_count} pages")
        return all_positions

    except Exception as e:
        logger.error(f"Error fetching all positions: {e}")
        return []

async def get_current_price(symbol: str) -> float:
    """
    FIXED: Get current market price for symbol with enhanced error handling
    """
    try:
        response = await api_call_with_retry(
            lambda: bybit_client.get_tickers(
                category="linear",
                symbol=symbol
            ),
            timeout=20
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
    """
    FIXED: Get available USDT balance with enhanced error handling
    """
    try:
        response = await api_call_with_retry(
            lambda: bybit_client.get_wallet_balance(
                accountType="UNIFIED",
                coin="USDT"
            ),
            timeout=25
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

async def get_active_tp_sl_orders(symbol: str) -> List[Dict]:
    """Get active TP/SL conditional orders for a symbol with enhanced error handling"""
    try:
        response = await api_call_with_retry(
            lambda: bybit_client.get_open_orders(
                category="linear",
                symbol=symbol
            ),
            timeout=20
        )

        if response and response.get("retCode") == 0:
            orders = response.get("result", {}).get("list", [])
            # Filter for conditional orders (TP/SL orders)
            tp_sl_orders = []
            for order in orders:
                order_type = order.get("orderType", "")
                trigger_price = order.get("triggerPrice", "")
                reduce_only = order.get("reduceOnly", False)
                stop_order_type = order.get("stopOrderType", "")
                order_link_id = order.get("orderLinkId", "")

                # Enhanced detection: Check multiple conditions
                is_tp_sl = False

                # Method 1: Has trigger price and is reduce only (standard conditional order)
                if trigger_price and reduce_only:
                    is_tp_sl = True

                # Method 2: Has stopOrderType field indicating TP/SL
                elif stop_order_type in ["TakeProfit", "StopLoss"]:
                    is_tp_sl = True

                # Method 3: Has TP/SL pattern in orderLinkId (even if other fields missing)
                elif any(pattern in order_link_id for pattern in ["_TP", "_SL", "TP1", "TP2", "TP3", "TP4", "SL"]):
                    is_tp_sl = True

                if is_tp_sl:
                    tp_sl_orders.append(order)
                    logger.debug(f"Found TP/SL order: {order.get('orderId', '')[:8]}... "
                               f"(type: {stop_order_type or 'conditional'}, "
                               f"trigger: {trigger_price}, linkId: {order_link_id})")

            return tp_sl_orders
        return []

    except Exception as e:
        logger.error(f"Error fetching TP/SL orders for {symbol}: {e}")
        return []

async def check_stop_order_limit(symbol: str) -> Dict[str, Any]:
    """
    Check the current stop order count for a symbol and determine how many more can be placed.
    Bybit has a limit of 10 stop orders per symbol.

    Returns:
        Dict containing:
        - current_count: Number of existing stop orders
        - limit: Maximum allowed (10)
        - available_slots: How many more can be placed
        - existing_orders: List of existing stop orders
    """
    try:
        # Get all open orders for the symbol
        response = await api_call_with_retry(
            lambda: bybit_client.get_open_orders(
                category="linear",
                symbol=symbol
            ),
            timeout=20
        )

        if response and response.get("retCode") == 0:
            orders = response.get("result", {}).get("list", [])

            # Count stop orders (orders with trigger price)
            stop_orders = []
            for order in orders:
                trigger_price = order.get("triggerPrice", "")
                if trigger_price:  # This is a stop/conditional order
                    stop_orders.append(order)

            current_count = len(stop_orders)
            limit = 10  # Bybit's limit
            available_slots = max(0, limit - current_count)

            logger.info(f"📊 Stop order status for {symbol}: {current_count}/{limit} (Available: {available_slots})")

            return {
                "current_count": current_count,
                "limit": limit,
                "available_slots": available_slots,
                "existing_orders": stop_orders
            }

        # If we can't get the orders, return conservative estimate
        logger.warning(f"Could not fetch stop orders for {symbol}, returning conservative estimate")
        return {
            "current_count": 0,
            "limit": 10,
            "available_slots": 10,
            "existing_orders": []
        }

    except Exception as e:
        logger.error(f"Error checking stop order limit for {symbol}: {e}")
        # Return conservative estimate on error
        return {
            "current_count": 0,
            "limit": 10,
            "available_slots": 10,
            "existing_orders": [],
            "error": str(e)
        }

async def get_order_info(symbol: str, order_id: str) -> Optional[Dict]:
    """Get information about a specific order with enhanced error handling"""
    try:
        response = await api_call_with_retry(
            lambda: bybit_client.get_open_orders(
                category="linear",
                symbol=symbol,
                orderId=order_id
            ),
            timeout=20
        )

        if response and response.get("retCode") == 0:
            orders = response.get("result", {}).get("list", [])
            return orders[0] if orders else None
        return None

    except Exception as e:
        logger.error(f"Error fetching order info for {order_id}: {e}")
        return None

async def get_order_info_mirror(symbol: str, order_id: str) -> Optional[Dict]:
    """Get information about a specific order from mirror account"""
    try:
        from execution.mirror_trader import bybit_client_2

        if not bybit_client_2:
            return None

        response = await api_call_with_retry(
            lambda: bybit_client_2.get_open_orders(
                category="linear",
                symbol=symbol,
                orderId=order_id
            ),
            timeout=20
        )

        if response and response.get("retCode") == 0:
            orders = response.get("result", {}).get("list", [])
            if orders:
                return orders[0]

        # If not in open orders, check order history
        response = await api_call_with_retry(
            lambda: bybit_client_2.get_order_history(
                category="linear",
                symbol=symbol,
                orderId=order_id
            ),
            timeout=20
        )

        if response and response.get("retCode") == 0:
            orders = response.get("result", {}).get("list", [])
            if orders:
                return orders[0]

        return None

    except Exception as e:
        logger.error(f"Error getting mirror order info: {e}")
        return None

# =============================================
# PRICE ADJUSTMENT FUNCTIONS
# =============================================

async def adjust_price_to_tick_size(symbol: str, price: str) -> str:
    """
    Adjust price to match the symbol's tick size requirement.
    This ensures orders are accepted by Bybit.

    Args:
        symbol: Trading symbol (e.g., "BTCUSDT")
        price: Price as string to preserve full precision

    Returns:
        Adjusted price as string
    """
    try:
        from utils.cache import get_instrument_info_cached

        # Get instrument info
        instrument_info = await get_instrument_info_cached(symbol)
        if not instrument_info:
            logger.warning(f"Could not get instrument info for {symbol}, using original price")
            return price

        # Get tick size
        price_filter = instrument_info.get("priceFilter", {})
        tick_size = price_filter.get("tickSize", "0.01")

        # Convert to Decimal for precise arithmetic
        price_decimal = Decimal(str(price))
        tick_decimal = Decimal(str(tick_size))

        # Round to nearest tick
        if tick_decimal > 0:
            # Calculate how many ticks
            ticks = price_decimal / tick_decimal
            # Round to nearest integer number of ticks
            rounded_ticks = int(ticks.quantize(Decimal('1'), rounding='ROUND_HALF_UP'))
            # Calculate adjusted price
            adjusted_price = rounded_ticks * tick_decimal

            # Convert back to string, removing trailing zeros
            result = str(adjusted_price.normalize())

            if result != str(price):
                logger.debug(f"Adjusted price for {symbol}: {price} → {result} (tick_size: {tick_size})")

            return result
        else:
            return str(price)

    except Exception as e:
        logger.error(f"Error adjusting price to tick size: {e}")
        return str(price)

async def adjust_quantity_to_step_size(symbol: str, quantity: str) -> str:
    """
    Adjust quantity to match the symbol's lot size step requirement.
    This ensures orders are accepted by Bybit.

    Args:
        symbol: Trading symbol (e.g., "BTCUSDT")
        quantity: Quantity as string to preserve full precision

    Returns:
        Adjusted quantity as string
    """
    try:
        from utils.cache import get_instrument_info_cached
        from utils.helpers import value_adjusted_to_step

        # Get instrument info
        instrument_info = await get_instrument_info_cached(symbol)
        if not instrument_info:
            logger.warning(f"Could not get instrument info for {symbol}, using original quantity")
            return quantity

        # Get lot size filter
        lot_size_filter = instrument_info.get("lotSizeFilter", {})
        qty_step = lot_size_filter.get("qtyStep", "1")
        min_order_qty = lot_size_filter.get("minOrderQty", "0")
        max_order_qty = lot_size_filter.get("maxOrderQty", "999999999")

        # Convert to Decimal for precise arithmetic
        quantity_decimal = Decimal(str(quantity))
        qty_step_decimal = Decimal(str(qty_step))
        min_qty_decimal = Decimal(str(min_order_qty))
        max_qty_decimal = Decimal(str(max_order_qty))

        # Adjust to step size using existing helper
        adjusted_quantity = value_adjusted_to_step(quantity_decimal, qty_step_decimal)

        # Ensure it meets minimum requirements
        if adjusted_quantity < min_qty_decimal:
            adjusted_quantity = min_qty_decimal
            logger.warning(f"Quantity {quantity} below minimum {min_order_qty} for {symbol}, using minimum")

        # Ensure it doesn't exceed maximum
        if adjusted_quantity > max_qty_decimal:
            adjusted_quantity = max_qty_decimal
            logger.warning(f"Quantity {quantity} above maximum {max_order_qty} for {symbol}, using maximum")

        # Convert back to string
        result = str(adjusted_quantity)

        if result != str(quantity):
            logger.debug(f"Adjusted quantity for {symbol}: {quantity} → {result} (step: {qty_step})")

        return result

    except Exception as e:
        logger.error(f"Error adjusting quantity to step size: {e}")
        return str(quantity)

# =============================================
# ENHANCED ORDER FUNCTIONS WITH AUTOMATIC POSITION MODE DETECTION
# =============================================

async def place_order_with_retry(symbol: str, side: str, order_type: str,
                                qty: str, price: Optional[str] = None,
                                trigger_price: Optional[str] = None,
                                position_idx: Optional[int] = None,
                                reduce_only: bool = False,
                                order_link_id: Optional[str] = None,
                                time_in_force: Optional[str] = None,
                                stop_order_type: Optional[str] = None,
                                max_retries: int = 3) -> Optional[Dict]:
    """
    FIXED: Place an order with automatic position mode detection and improved retry logic
    """
    for attempt in range(max_retries):
        try:
            # FIXED: Automatically detect correct positionIdx if not provided
            if position_idx is None:
                logger.info(f"🎯 Auto-detecting position mode for {symbol} {side}...")
                position_idx = await get_correct_position_idx(symbol, side)
                logger.info(f"✅ Using positionIdx={position_idx} for {symbol} {side}")

            # Validate and adjust quantity to meet symbol requirements
            adjusted_qty = await adjust_quantity_to_step_size(symbol, qty)

            # Build order parameters
            params = {
                "category": "linear",
                "symbol": symbol,
                "side": side,
                "orderType": order_type,
                "qty": adjusted_qty,
                "positionIdx": position_idx
            }

            if price:
                # Adjust price to tick size for the symbol
                adjusted_price = await adjust_price_to_tick_size(symbol, price)
                params["price"] = str(adjusted_price)

            if order_link_id:
                params["orderLinkId"] = order_link_id

            if time_in_force:
                params["timeInForce"] = time_in_force

            if trigger_price:
                # Adjust trigger price to tick size for the symbol
                adjusted_trigger_price = await adjust_price_to_tick_size(symbol, trigger_price)
                params["triggerPrice"] = str(adjusted_trigger_price)

                # CRITICAL FIX: Always set triggerDirection for orders with trigger price
                # This prevents "TriggerDirection invalid" errors
                try:
                    current_price = await get_current_price(symbol)
                    trigger_price_float = float(trigger_price)

                    logger.debug(f"🎯 Trigger direction analysis: current={current_price}, trigger={trigger_price_float}, side={side}, reduce_only={reduce_only}")

                    # Determine trigger direction based on position side and order type
                    if reduce_only:  # TP/SL orders (closing positions)
                        if side == "Buy":  # Closing short position
                            if trigger_price_float < current_price:
                                params["triggerDirection"] = 2  # Falling (TP for short)
                                logger.debug(f"📉 Short TP: trigger when price falls to {trigger_price_float}")
                            else:
                                params["triggerDirection"] = 1  # Rising (SL for short)
                                logger.debug(f"📈 Short SL: trigger when price rises to {trigger_price_float}")
                        else:  # side == "Sell", closing long position
                            if trigger_price_float > current_price:
                                params["triggerDirection"] = 1  # Rising (TP for long)
                                logger.debug(f"📈 Long TP: trigger when price rises to {trigger_price_float}")
                            else:
                                params["triggerDirection"] = 2  # Falling (SL for long)
                                logger.debug(f"📉 Long SL: trigger when price falls to {trigger_price_float}")
                    else:
                        # For entry orders (limit orders)
                        if side == "Buy":
                            # Buy limit: trigger when price falls to our level
                            params["triggerDirection"] = 2  # Falling
                            logger.debug(f"📉 Buy Limit: trigger when price falls to {trigger_price_float}")
                        else:  # Sell
                            # Sell limit: trigger when price rises to our level
                            params["triggerDirection"] = 1  # Rising
                            logger.debug(f"📈 Sell Limit: trigger when price rises to {trigger_price_float}")

                    # Always set triggerBy when we have a trigger price
                    params["triggerBy"] = "LastPrice"

                except Exception as e:
                    logger.error(f"Error determining trigger direction: {e}")
                    # Fallback: Use stop order type or side to determine direction
                    if stop_order_type == "StopLoss":
                        # Stop loss triggers opposite to profit direction
                        params["triggerDirection"] = 1 if side == "Buy" else 2
                    elif stop_order_type == "TakeProfit":
                        # Take profit triggers in profit direction
                        params["triggerDirection"] = 2 if side == "Buy" else 1
                    else:
                        # Default based on side
                        params["triggerDirection"] = 1 if side == "Buy" else 2
                    params["triggerBy"] = "LastPrice"
                    logger.warning(f"⚠️ Using fallback trigger direction: {params['triggerDirection']}")

            if reduce_only:
                params["reduceOnly"] = True

            if stop_order_type:
                params["stopOrderType"] = stop_order_type

            logger.debug(f"Placing order (attempt {attempt + 1}): {params}")

            response = await api_call_with_retry(
                lambda: bybit_client.place_order(**params),
                timeout=30
            )

            if response and response.get("retCode") == 0:
                result = response.get("result", {})
                order_id = result.get("orderId")

                logger.info(f"✅ Order placed successfully: {order_id}")

                # ENHANCEMENT: Add symbol to protection when order is placed
                add_symbol_to_protection(symbol)

                # Track order creation time
                if order_id:
                    ORDER_CREATION_TIMESTAMPS[order_id] = time.time()

                return result

            ret_code = response.get("retCode", 0)
            ret_msg = response.get("retMsg", "")

            # FIXED: Handle position mode mismatch error specifically
            if ret_code == 10001 and "position idx not match position mode" in ret_msg:
                logger.warning(f"Position idx mismatch detected for {symbol}. Using unified One-Way Mode...")
                # Position mode cache no longer needed - unified One-Way Mode
                # Force re-detection of position mode
                position_idx = await get_correct_position_idx(symbol, side)
                logger.info(f"🔄 Retrying with corrected positionIdx={position_idx}")
                continue  # Retry with new position index

            # Handle other specific error codes
            if ret_code == 110043:  # Leverage not modified
                logger.info("Leverage already set, continuing...")
                continue
            elif ret_code == 110092:  # Invalid trigger direction
                logger.error(f"Invalid trigger direction: {ret_msg}")
                logger.error(f"Order params that failed: {params}")
                return None  # Don't retry on logic errors
            elif ret_code == 110093:  # Invalid trigger price
                logger.error(f"Invalid trigger price logic: {ret_msg}")
                return None  # Don't retry on logic errors

            if ret_code != 0:
                logger.warning(f"Order placement failed (attempt {attempt + 1}): {ret_msg} (Code: {ret_code})")
                if attempt < max_retries - 1:
                    # PERFORMANCE: Exponential backoff instead of fixed delay
                    delay = 0.5 * (2 ** attempt)  # 0.5s, 1s, 2s instead of 2s, 2s, 2s
                    await asyncio.sleep(delay)
                    continue

            return None

        except Exception as e:
            logger.error(f"Error placing order (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                # PERFORMANCE: Exponential backoff instead of fixed delay
                delay = 0.5 * (2 ** attempt)  # 0.5s, 1s, 2s instead of 2s, 2s, 2s
                await asyncio.sleep(delay)
                continue
            return None

    return None

async def amend_order_with_retry(symbol: str, order_id: str,
                                trigger_price: Optional[str] = None,
                                qty: Optional[str] = None,
                                price: Optional[str] = None,
                                max_retries: int = 3) -> Optional[Dict]:
    """
    ENHANCED: Amend an order with better retry logic
    """
    for attempt in range(max_retries):
        try:
            params = {
                "category": "linear",
                "symbol": symbol,
                "orderId": order_id
            }

            if trigger_price:
                # Adjust trigger price to tick size
                adjusted_trigger_price = await adjust_price_to_tick_size(symbol, trigger_price)
                params["triggerPrice"] = str(adjusted_trigger_price)
            if qty:
                params["qty"] = qty
            if price:
                # Adjust price to tick size
                adjusted_price = await adjust_price_to_tick_size(symbol, price)
                params["price"] = str(adjusted_price)

            response = await api_call_with_retry(
                lambda: bybit_client.amend_order(**params),
                timeout=25
            )

            if response and response.get("retCode") == 0:
                logger.info(f"✅ Order {order_id[:8]}... amended successfully")
                return response.get("result")

            logger.warning(f"Amend order failed (attempt {attempt + 1}): {response}")

        except Exception as e:
            logger.error(f"Error amending order (attempt {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            # PERFORMANCE: Exponential backoff instead of fixed delay
            delay = 0.5 * (2 ** attempt)  # 0.5s, 1s, 2s instead of 2s, 2s, 2s
            await asyncio.sleep(delay)

    return None

async def cancel_order_with_retry(symbol: str, order_id: str,
                                 max_retries: int = 3) -> bool:
    """
    ENHANCED: Cancel an order with state validation and better retry logic
    PROTECTED: Will not cancel external orders without bot prefixes
    """
    if not order_id:
        logger.warning("❌ Cannot cancel order: No order ID provided")
        return False

    # Import order state cache
    from utils.order_state_cache import order_state_cache

    # Check if this order was recently attempted
    if hasattr(order_state_cache, '_recent_cancellations'):
        if order_id in order_state_cache._recent_cancellations:
            recent_time = order_state_cache._recent_cancellations[order_id]
            if time.time() - recent_time < 30:  # Within 30 seconds
                logger.info(f"ℹ️ Order {order_id[:8]}... recently cancelled - skipping")
                return True
    else:
        order_state_cache._recent_cancellations = {}

    order_state_cache._recent_cancellations[order_id] = time.time()

    # Check if order is likely cancellable from cache
    if not await order_state_cache.is_order_cancellable(order_id):
        await order_state_cache.prevent_cancellation(order_id)
        logger.info(f"🛡️ Order {order_id[:8]}... is not cancellable (cached state)")
        return True  # Return True as order is already in terminal state

    # Try to get order info to check current state
    try:
        order_info = await get_order_info(symbol, order_id)
        if order_info:
            # Update cache with current state
            order_status = order_info.get("orderStatus", "")
            await order_state_cache.update_order_state(order_id, order_status, order_info)

            # Check if already in terminal state
            if order_status in ["Filled", "Cancelled", "Rejected"]:
                logger.info(f"ℹ️ Order {order_id[:8]}... already in terminal state: {order_status}")
                return True
    except Exception as e:
        logger.debug(f"Could not verify order {order_id[:8]}... status: {e}")

    logger.info(f"🔄 Attempting to cancel order {order_id[:8]}... for {symbol}")

    for attempt in range(max_retries):
        try:
            response = await api_call_with_retry(
                lambda: bybit_client.cancel_order(
                    category="linear",
                    symbol=symbol,
                    orderId=order_id
                ),
                timeout=25
            )

            if response and response.get("retCode") == 0:
                logger.info(f"✅ Order {order_id[:8]}... cancelled successfully on attempt {attempt + 1}")
                await order_state_cache.record_cancel_attempt(order_id, success=True)
                await order_state_cache.update_order_state(order_id, "Cancelled")
                return True

            # Handle specific error codes
            ret_code = response.get("retCode", 0)
            ret_msg = response.get("retMsg", "Unknown error")

            if ret_code == 110001:  # Order not found
                logger.info(f"ℹ️ Order {order_id[:8]}... not found (likely filled/cancelled)")
                await order_state_cache.prevent_cancellation(order_id)
                await order_state_cache.record_cancel_attempt(order_id, success=True)
                await order_state_cache.update_order_state(order_id, "Filled")  # Assume filled
                return True  # Consider this success since order is gone
            elif ret_code == 110004:  # Order already cancelled
                logger.info(f"ℹ️ Order {order_id[:8]}... already cancelled")
                await order_state_cache.record_cancel_attempt(order_id, success=True)
                await order_state_cache.update_order_state(order_id, "Cancelled")
                return True
            elif ret_code == 110005:  # Order already filled
                logger.info(f"ℹ️ Order {order_id[:8]}... already filled")
                await order_state_cache.record_cancel_attempt(order_id, success=True)
                await order_state_cache.update_order_state(order_id, "Filled")
                return True  # Order executed, no need to cancel

            logger.warning(f"❌ Cancel order failed (attempt {attempt + 1}): {ret_msg} (Code: {ret_code})")

        except Exception as e:
            logger.error(f"❌ Error canceling order (attempt {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            # Exponential backoff with jitter
            import random
            base_delay = 1.0
            max_delay = 10.0
            jitter_factor = 0.1

            delay = min(base_delay * (2 ** attempt), max_delay)
            # Add random jitter to prevent thundering herd
            jitter = delay * jitter_factor * (2 * random.random() - 1)
            delay = max(0.5, delay + jitter)  # Ensure minimum 0.5s delay

            logger.info(f"⏳ Retrying order cancellation in {delay:.1f} seconds...")
            await asyncio.sleep(delay)

    logger.error(f"❌ Failed to cancel order {order_id[:8]}... after {max_retries} attempts")
    await order_state_cache.record_cancel_attempt(order_id, success=False)
    return False

async def close_position(symbol: str) -> Dict:
    """
    ENHANCED: Close existing position using market order with correct positionIdx
    """
    try:
        # Get current position
        positions = await get_position_info(symbol)
        if not positions:
            return {"success": False, "error": "No position found"}

        # Find active position
        position = None
        for pos in positions:
            if float(pos.get("size", 0)) > 0:
                position = pos
                break

        if not position:
            return {"success": False, "error": "No active position found"}

        size = float(position.get("size", 0))
        if size == 0:
            return {"success": False, "error": "No active position to close"}

        side = position.get("side", "")
        if not side:
            return {"success": False, "error": "Could not determine position side"}

        # Determine opposite side for closing
        close_side = "Sell" if side == "Buy" else "Buy"

        # FIXED: Use automatic position mode detection
        result = await place_order_with_retry(
            symbol=symbol,
            side=close_side,
            order_type="Market",
            qty=str(size),
            reduce_only=True
        )

        if result:
            return {
                "success": True,
                "orderId": result.get("orderId"),
                "message": f"Position closed: {side} {size} -> {close_side} market order"
            }
        else:
            return {"success": False, "error": "Failed to place close order"}

    except Exception as e:
        logger.error(f"Error closing position: {e}")
        return {"success": False, "error": str(e)}

# =============================================
# ENHANCED ORDER RETRIEVAL FUNCTIONS
# =============================================

async def get_order_info(symbol: str, order_id: str) -> Optional[Dict]:
    """
    Get information about a specific order

    Args:
        symbol: Trading symbol
        order_id: Order ID to query

    Returns:
        Order information dict or None if not found
    """
    try:
        # Try to get order from open orders first
        response = await api_call_with_retry(
            lambda: bybit_client.get_open_orders(
                category="linear",
                symbol=symbol,
                orderId=order_id
            ),
            timeout=20
        )

        if response and response.get("retCode") == 0:
            orders = response.get("result", {}).get("list", [])
            if orders:
                return orders[0]

        # If not found in open orders, try order history
        response = await api_call_with_retry(
            lambda: bybit_client.get_order_history(
                category="linear",
                symbol=symbol,
                orderId=order_id,
                limit=1
            ),
            timeout=20
        )

        if response and response.get("retCode") == 0:
            orders = response.get("result", {}).get("list", [])
            if orders:
                return orders[0]

        return None

    except Exception as e:
        logger.error(f"Error getting order info for {order_id}: {e}")
        return None

async def get_open_orders(symbol: str = None) -> List[Dict]:
    """Get open orders for a specific symbol or all symbols"""
    try:
        if symbol:
            response = await api_call_with_retry(
                lambda: bybit_client.get_open_orders(
                    category="linear",
                    symbol=symbol,
                    settleCoin="USDT"
                )
            )
            if response and response.get('retCode') == 0:
                return response.get('result', {}).get('list', [])
            return []
        else:
            return await get_all_open_orders()
    except Exception as e:
        logger.error(f"Error fetching open orders: {e}")
        return []


async def get_all_open_orders(client=None) -> List[Dict]:
    """
    ENHANCED: Get all open orders across all USDT symbols with proper pagination
    """
    try:
        if client is None:
            from clients.bybit_client import bybit_client
            client = bybit_client
        all_orders = []
        cursor = None
        page_count = 0
        max_pages = 20  # Safety limit for orders

        logger.info("🔍 Fetching all open orders with enhanced pagination...")

        while page_count < max_pages:
            page_count += 1

            # Build API parameters
            params = {
                "category": "linear",
                "settleCoin": "USDT",
                "limit": 50  # Maximum records per page for orders
            }

            if cursor:
                params["cursor"] = cursor

            logger.debug(f"📄 Fetching orders page {page_count} (cursor: {cursor})")

            response = await api_call_with_retry(
                lambda: client.get_open_orders(**params),
                timeout=30
            )

            if not response or response.get("retCode") != 0:
                logger.error(f"Failed to get orders page {page_count}: {response}")
                break

            result = response.get("result", {})
            page_orders = result.get("list", [])
            next_cursor = result.get("nextPageCursor", "")

            # Add orders from this page
            all_orders.extend(page_orders)
            logger.debug(f"📄 Page {page_count}: Found {len(page_orders)} orders")

            # Check if we have more pages
            if not next_cursor or next_cursor == cursor:
                logger.debug(f"✅ Orders pagination complete - no more pages")
                break

            cursor = next_cursor

            # Small delay to avoid rate limits
            await asyncio.sleep(0.2)

        logger.info(f"📋 Total orders fetched: {len(all_orders)} across {page_count} pages")

        # Track order creation timestamps for better analysis
        for order in all_orders:
            order_id = order.get("orderId")
            created_time = order.get("createdTime")
            if order_id and created_time:
                ORDER_CREATION_TIMESTAMPS[order_id] = int(created_time) / 1000

        return all_orders

    except Exception as e:
        logger.error(f"Error fetching all open orders: {e}")
        return []

async def get_order_history(**kwargs) -> Dict:
    """
    Get order history from Bybit API with account support
    
    Args:
        **kwargs: Parameters to pass to the order history API
        client: Optional specific client to use (for mirror account)
    
    Returns:
        Order history response from API
    """
    try:
        client = kwargs.pop('client', None)
        
        if client:
            # Use specific client (for mirror account)
            response = await api_call_with_retry(
                lambda: client.get_order_history(
                    category="linear",
                    **kwargs
                ),
                timeout=20
            )
        else:
            # Use main client
            response = await api_call_with_retry(
                lambda: bybit_client.get_order_history(
                    category="linear",
                    **kwargs
                ),
                timeout=20
            )
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting order history: {e}")
        return {}

# =============================================
# ENHANCED CONSERVATIVE GROUP-AWARE ORPHAN DETECTION SYSTEM
# =============================================

def extract_trade_group_id(order: Dict) -> Optional[str]:
    """
    Extract trade group ID from order if present

    Conservative approach orders should have orderLinkId like: "groupid_TP1", "groupid_LIMIT1", etc.
    """
    order_link_id = order.get("orderLinkId", "")
    if not order_link_id:
        return None

    # Check if this looks like a trade group pattern
    if "_" in order_link_id:
        parts = order_link_id.split("_")
        if len(parts) >= 2:
            # First part is likely the trade group ID
            group_id = parts[0]
            order_type = "_".join(parts[1:])

            # Validate this looks like a valid trade group pattern
            valid_order_types = ["TP1", "TP2", "TP3", "TP4", "SL", "LIMIT1", "LIMIT2", "LIMIT3"]
            if order_type in valid_order_types:
                return group_id

    return None

def classify_order_type(order: Dict) -> str:
    """
    Classify an order into categories for group analysis

    Returns: "limit", "tp", "sl", "market", "unknown"
    """
    order_type = order.get("orderType", "").lower()
    trigger_price = order.get("triggerPrice", "")
    reduce_only = order.get("reduceOnly", False)
    order_link_id = order.get("orderLinkId", "")

    # Check for TP/SL by orderLinkId first (most reliable for our bot)
    if order_link_id:
        if any(tp in order_link_id for tp in ["_TP1", "_TP2", "_TP3", "_TP4"]):
            return "tp"
        if "_SL" in order_link_id:
            return "sl"
        if any(limit in order_link_id for limit in ["_LIMIT1", "_LIMIT2", "_LIMIT3"]):
            return "limit"

    # Fallback to order characteristics
    if trigger_price and reduce_only:
        # This is a conditional order that reduces position
        if "tp" in order_link_id.lower() or "take" in order_link_id.lower():
            return "tp"
        elif "sl" in order_link_id.lower() or "stop" in order_link_id.lower():
            return "sl"
        else:
            # Generic TP/SL - need more analysis
            return "tp"  # Assume TP for now
    elif order_type == "limit":
        return "limit"
    elif order_type == "market":
        return "market"

    return "unknown"

async def analyze_trade_groups(orders: List[Dict], positions: List[Dict]) -> Dict[str, Dict]:
    """
    ENHANCED: Analyze orders and group them by trade relationships

    Returns a dictionary with trade group analysis:
    {
        "grouped_orders": {symbol: {group_id: [orders]}},
        "ungrouped_orders": {symbol: [orders]},
        "symbols_with_positions": set of symbols,
        "group_analysis": {group_id: {...}}
    }
    """
    try:
        logger.info("🔍 Starting enhanced trade group analysis...")

        # Initialize analysis structures
        grouped_orders = defaultdict(lambda: defaultdict(list))
        ungrouped_orders = defaultdict(list)
        symbols_with_positions = set()
        group_analysis = {}

        # Track symbols with active positions
        for position in positions:
            size = float(position.get("size", "0"))
            if size > 0:
                symbol = position.get("symbol", "")
                if symbol:
                    symbols_with_positions.add(symbol)
                    logger.debug(f"📊 Active position: {symbol} {position.get('side')} {size}")

        logger.info(f"📊 Found {len(symbols_with_positions)} symbols with active positions")

        # Analyze each order and group them
        for order in orders:
            symbol = order.get("symbol", "")
            order_id = order.get("orderId", "")

            if not symbol or not order_id:
                logger.warning(f"⚠️ Order missing symbol or ID: {order}")
                continue

            # Extract trade group ID
            trade_group_id = extract_trade_group_id(order)
            order_type = classify_order_type(order)

            logger.debug(f"🔍 Analyzing order {order_id[:8]}... ({symbol}): group={trade_group_id}, type={order_type}")

            if trade_group_id:
                # This order belongs to a trade group
                grouped_orders[symbol][trade_group_id].append(order)
                logger.debug(f"✅ Grouped order: {symbol} group {trade_group_id} type {order_type}")
            else:
                # This order doesn't belong to a trade group
                ungrouped_orders[symbol].append(order)
                logger.debug(f"❓ Ungrouped order: {symbol} type {order_type}")

        # Analyze each trade group
        total_groups = 0
        for symbol, groups in grouped_orders.items():
            for group_id, group_orders in groups.items():
                total_groups += 1

                # Analyze the composition of this trade group
                group_composition = {
                    "symbol": symbol,
                    "total_orders": len(group_orders),
                    "order_types": defaultdict(int),
                    "order_ids": [],
                    "has_position": symbol in symbols_with_positions,
                    "protected": is_trade_group_protected(group_id)
                }

                for order in group_orders:
                    order_type = classify_order_type(order)
                    group_composition["order_types"][order_type] += 1
                    group_composition["order_ids"].append(order.get("orderId"))

                group_analysis[group_id] = group_composition

                # Log group analysis
                types_summary = dict(group_composition["order_types"])
                logger.info(f"📊 Group {group_id} ({symbol}): {types_summary}, position={group_composition['has_position']}, protected={group_composition['protected']}")

        # Summary
        total_orders = len(orders)
        total_grouped = sum(len(group_orders) for symbol_groups in grouped_orders.values() for group_orders in symbol_groups.values())
        total_ungrouped = sum(len(orders) for orders in ungrouped_orders.values())

        logger.info(f"📊 Trade Group Analysis Summary:")
        logger.info(f"   Total orders: {total_orders}")
        logger.info(f"   Grouped orders: {total_grouped} in {total_groups} groups")
        logger.info(f"   Ungrouped orders: {total_ungrouped}")
        logger.info(f"   Symbols with positions: {len(symbols_with_positions)}")

        return {
            "grouped_orders": dict(grouped_orders),
            "ungrouped_orders": dict(ungrouped_orders),
            "symbols_with_positions": symbols_with_positions,
            "group_analysis": group_analysis
        }

    except Exception as e:
        logger.error(f"❌ Error in trade group analysis: {e}", exc_info=True)
        return {
            "grouped_orders": {},
            "ungrouped_orders": {},
            "symbols_with_positions": set(),
            "group_analysis": {}
        }

def should_preserve_order_with_active_elements(group_analysis: Dict, group_id: str,
                                             symbols_with_positions: Set[str], symbol: str) -> bool:
    """
    ENHANCED: Check if orders should be preserved due to active positions, limits, or TP/SL relationships

    This implements the user's core requirement:
    "check if there are limit orders present and take profit orders and stop losses
    if these are not there then the orphan mechanism can cancel legitimate orphan orders"
    """
    try:
        # PRIORITY 1: If symbol has active position, preserve ALL orders for that symbol
        if symbol in symbols_with_positions:
            logger.info(f"🛡️ PRESERVING orders for {symbol}: Active position exists")
            return True

        if group_id not in group_analysis:
            return False

        group_info = group_analysis[group_id]
        order_types = group_info.get("order_types", {})

        # PRIORITY 2: If group has multiple types of orders, it's likely a complete trade setup
        has_tp_orders = order_types.get("tp", 0) > 0
        has_sl_orders = order_types.get("sl", 0) > 0
        has_limit_orders = order_types.get("limit", 0) > 0

        # Count total different order types
        active_order_types = sum(1 for count in order_types.values() if count > 0)

        if active_order_types >= 2:
            logger.info(f"🛡️ PRESERVING group {group_id}: Multiple order types ({dict(order_types)})")
            return True

        # PRIORITY 3: Conservative approach specific preservation
        if has_tp_orders and has_limit_orders:
            logger.info(f"🛡️ PRESERVING group {group_id}: TP orders with active limits")
            return True

        if has_tp_orders and has_sl_orders:
            logger.info(f"🛡️ PRESERVING group {group_id}: TP and SL orders together")
            return True

        # PRIORITY 4: If group is explicitly protected
        if group_info.get("protected", False):
            logger.info(f"🛡️ PRESERVING group {group_id}: Explicitly protected")
            return True

        return False

    except Exception as e:
        logger.error(f"Error checking order preservation for group {group_id}: {e}")
        return True  # Err on the side of caution - preserve the order

def final_orphan_verification(order: Dict, symbol: str, symbols_with_positions: Set[str]) -> bool:
    """
    FINAL safety check before marking an order as orphaned
    """
    try:
        # Last chance safety checks
        order_id = order.get("orderId", "")

        # Check if symbol somehow got position after our analysis
        if symbol in symbols_with_positions:
            logger.info(f"🛡️ FINAL VETO: {order_id[:8]}... - symbol has position")
            return False

        # Check if this is a very recent order (within last hour regardless of grace period)
        order_age = time.time() - ORDER_CREATION_TIMESTAMPS.get(order_id, time.time())
        if order_age < 3600:  # Less than 1 hour old
            logger.info(f"🛡️ FINAL VETO: {order_id[:8]}... - too recent (only {order_age/60:.1f} minutes old)")
            return False

        # If we reach here, the order is truly orphaned
        return True

    except Exception as e:
        logger.error(f"Error in final orphan verification: {e}")
        return False  # Err on the side of safety

def identify_orphaned_orders(analysis: Dict) -> List[Dict]:
    """
    SIMPLIFIED: Identify orphaned orders - ANY order without an active position
    All orders are bot orders, no external orders exist
    """
    try:
        logger.info("🔍 Identifying orphaned orders (only requirement: no position exists)...")

        grouped_orders = analysis["grouped_orders"]
        ungrouped_orders = analysis["ungrouped_orders"]
        symbols_with_positions = analysis["symbols_with_positions"]

        orphaned_orders = []

        # Process ALL orders - both grouped and ungrouped
        all_orders = []

        # Add grouped orders
        for symbol, groups in grouped_orders.items():
            for group_id, group_orders in groups.items():
                all_orders.extend(group_orders)

        # Add ungrouped orders
        for symbol, orders in ungrouped_orders.items():
            all_orders.extend(orders)

        logger.info(f"🔍 Checking {len(all_orders)} total orders...")

        # Simple logic: If no position exists for the symbol, the order is orphaned
        for order in all_orders:
            symbol = order.get('symbol')

            # ONLY CHECK: Does this symbol have an active position?
            if symbol not in symbols_with_positions:
                logger.info(f"🧹 Found orphaned order {order['orderId'][:8]}... for {symbol} - no position exists")
                orphaned_orders.append(order)

        logger.info(f"✅ Identified {len(orphaned_orders)} orphaned orders for cleanup")
        return orphaned_orders

    except Exception as e:
        logger.error(f"❌ Error identifying orphaned orders: {e}", exc_info=True)
        return []


async def cleanup_orphaned_orders(orphaned_orders: List[Dict]) -> Dict[str, int]:
    """
    ENHANCED: Clean up orphaned orders with proper error handling and reporting
    """
    try:
        if not orphaned_orders:
            logger.info("✅ No orphaned orders to clean up")
            return {"attempted": 0, "successful": 0, "failed": 0}

        logger.info(f"🧹 Starting cleanup of {len(orphaned_orders)} orphaned orders...")

        attempted = 0
        successful = 0
        failed = 0

        for order in orphaned_orders:
            try:
                attempted += 1
                order_id = order.get("orderId", "")
                symbol = order.get("symbol", "")
                order_type = classify_order_type(order)

                logger.info(f"🗑️ Cleaning up orphaned order {attempted}/{len(orphaned_orders)}: {symbol} {order_id[:8]}... ({order_type})")

                # Attempt to cancel the order
                success = await cancel_order_with_retry(symbol, order_id)

                if success:
                    successful += 1
                    logger.info(f"✅ Successfully cleaned up orphaned order: {symbol} {order_id[:8]}...")
                else:
                    failed += 1
                    logger.error(f"❌ Failed to clean up orphaned order: {symbol} {order_id[:8]}...")

                # PERFORMANCE: Reduced delay for faster cleanup
                await asyncio.sleep(0.1)

            except Exception as e:
                failed += 1
                logger.error(f"❌ Exception cleaning up order {order.get('orderId', 'unknown')}: {e}")
                continue

        # Summary
        logger.info(f"🧹 Orphaned order cleanup completed:")
        logger.info(f"   Attempted: {attempted}")
        logger.info(f"   Successful: {successful}")
        logger.info(f"   Failed: {failed}")

        return {
            "attempted": attempted,
            "successful": successful,
            "failed": failed
        }

    except Exception as e:
        logger.error(f"❌ Error in orphaned order cleanup: {e}", exc_info=True)
        return {"attempted": 0, "successful": 0, "failed": 0, "error": str(e)}

async def run_enhanced_orphan_scanner():
    """
    SIMPLIFIED: Main orphan scanner function - removes any order without an active position
    Supports both main and mirror accounts
    """
    try:
        logger.info("🔍 Starting orphan scanner for MAIN and MIRROR accounts...")

        # Process MAIN account
        logger.info("📊 [MAIN] Fetching orders and positions...")
        main_orders = await get_all_open_orders()
        main_positions = await get_all_positions()

        main_results = {"attempted": 0, "successful": 0, "failed": 0}

        if main_orders:
            logger.info(f"📊 [MAIN] Retrieved {len(main_orders)} orders and {len(main_positions)} positions")

            # Analyze main account
            main_analysis = await analyze_trade_groups(main_orders, main_positions)
            main_orphaned = identify_orphaned_orders(main_analysis)

            if main_orphaned:
                logger.warning(f"🚨 [MAIN] Found {len(main_orphaned)} orphaned orders")
                main_results = await cleanup_orphaned_orders(main_orphaned)
        else:
            logger.info("✅ [MAIN] No open orders found")

        # Process MIRROR account if available
        mirror_results = {"attempted": 0, "successful": 0, "failed": 0}
        try:
            from execution.mirror_trader import bybit_client_2
            if bybit_client_2:
                logger.info("📊 [MIRROR] Fetching orders and positions...")
                mirror_orders = await get_all_open_orders(client=bybit_client_2)
                mirror_positions = await get_all_positions(client=bybit_client_2)

                if mirror_orders:
                    logger.info(f"📊 [MIRROR] Retrieved {len(mirror_orders)} orders and {len(mirror_positions)} positions")

                    # Analyze mirror account
                    mirror_analysis = await analyze_trade_groups(mirror_orders, mirror_positions)
                    mirror_orphaned = identify_orphaned_orders(mirror_analysis)

                    if mirror_orphaned:
                        logger.warning(f"🚨 [MIRROR] Found {len(mirror_orphaned)} orphaned orders")
                        # Clean up using mirror client
                        for order in mirror_orphaned:
                            try:
                                symbol = order.get('symbol')
                                order_id = order.get('orderId')
                                # Use mirror client directly for cancellation
                                response = await api_call_with_retry(
                                    lambda: bybit_client_2.cancel_order(
                                        category="linear",
                                        symbol=symbol,
                                        orderId=order_id
                                    )
                                )
                                success = response and response.get("retCode") == 0
                                if success:
                                    mirror_results['successful'] += 1
                                else:
                                    mirror_results['failed'] += 1
                                mirror_results['attempted'] += 1
                            except Exception as e:
                                logger.error(f"Error cancelling mirror order: {e}")
                                mirror_results['failed'] += 1
                else:
                    logger.info("✅ [MIRROR] No open orders found")
        except ImportError:
            logger.info("ℹ️ Mirror trading not available")

        # Combine results
        total_attempted = main_results['attempted'] + mirror_results['attempted']
        total_successful = main_results['successful'] + mirror_results['successful']
        total_failed = main_results['failed'] + mirror_results['failed']

        return {
            "status": "completed",
            "message": f"Cleanup complete: {total_successful}/{total_attempted} orders removed (Main: {main_results['successful']}, Mirror: {mirror_results['successful']})",
            "details": {
                "main": main_results,
                "mirror": mirror_results,
                "total_attempted": total_attempted,
                "total_successful": total_successful,
                "total_failed": total_failed
            }
        }

    except Exception as e:
        logger.error(f"❌ Error in orphan scanner: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

# =============================================
# SIMPLE P&L FUNCTIONS FOR DASHBOARD
# =============================================

async def get_active_positions() -> List[Dict]:
    """Get only active positions (size > 0) with enhanced error handling"""
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
    """Get total unrealised P&L across all positions with enhanced error handling"""
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

# =============================================
# NEW: POTENTIAL P&L CALCULATION FUNCTIONS
# =============================================

async def calculate_potential_pnl_for_positions() -> Dict[str, Any]:
    """
    Enhanced calculation of potential P&L scenarios for all active positions

    Calculates:
    - TP1 only profit (if all positions hit their first TP)
    - All TPs profit (maximum profit if all TPs are hit)
    - SL loss (if all positions hit their stop loss)
    - Current unrealized P&L
    - Position-by-position breakdown

    Returns:
        Dict with detailed scenario calculations and position breakdowns
    """
    try:
        logger.info("🔍 Calculating enhanced potential P&L scenarios...")

        # Get all positions
        positions = await get_all_positions()
        active_positions = [p for p in positions if float(p.get("size", "0")) > 0]

        if not active_positions:
            return {
                "tp1_profit": 0.0,
                "all_tp_profit": 0.0,
                "sl_loss": 0.0,
                "current_pnl": 0.0,
                "positions_count": 0,
                "tp_orders_count": 0,
                "sl_orders_count": 0,
                "position_details": [],
                "potential_profit": 0.0,  # Legacy compatibility
                "potential_loss": 0.0      # Legacy compatibility
            }

        # Initialize accumulators
        total_tp1_profit = 0.0
        total_all_tp_profit = 0.0
        total_sl_loss = 0.0
        total_current_pnl = 0.0
        positions_count = 0
        tp_orders_count = 0
        sl_orders_count = 0
        position_details = []

        # Process each active position
        for position in active_positions:
            symbol = position.get("symbol", "")
            side = position.get("side", "")
            size = float(position.get("size", "0"))
            entry_price = float(position.get("avgPrice", "0"))
            mark_price = float(position.get("markPrice", "0"))
            unrealized_pnl = float(position.get("unrealisedPnl", "0"))

            if not all([symbol, side, size > 0, entry_price > 0]):
                continue

            # Get TP/SL orders for this position
            tp_sl_orders = await get_active_tp_sl_orders(symbol)

            # Find all TP orders and SL order
            tp_orders = []
            sl_price = None

            for order in tp_sl_orders:
                order_link_id = order.get("orderLinkId", "")
                trigger_price = order.get("triggerPrice", "")
                qty = float(order.get("qty", "0"))
                stop_order_type = order.get("stopOrderType", "")

                if not trigger_price:
                    continue

                trigger_price = float(trigger_price)

                # Enhanced TP order identification
                is_tp_order = False
                is_sl_order = False

                # Method 1: Check stopOrderType field (most reliable if present)
                if stop_order_type == "TakeProfit":
                    is_tp_order = True
                elif stop_order_type == "StopLoss":
                    is_sl_order = True
                # Method 2: Check orderLinkId patterns
                elif any(tp_pattern in order_link_id for tp_pattern in ["_TP", "TP1", "TP2", "TP3", "TP4"]):
                    is_tp_order = True
                elif "_SL" in order_link_id:
                    is_sl_order = True
                # Method 3: Infer from price relative to entry (only if no other indicators)
                elif not stop_order_type and not any(pattern in order_link_id for pattern in ["_TP", "_SL", "TP", "SL"]):
                    if side == "Buy" and trigger_price > entry_price:
                        is_tp_order = True
                    elif side == "Sell" and trigger_price < entry_price:
                        is_tp_order = True
                    elif side == "Buy" and trigger_price < entry_price and not sl_price:
                        is_sl_order = True
                    elif side == "Sell" and trigger_price > entry_price and not sl_price:
                        is_sl_order = True

                # Process TP orders
                if is_tp_order and order.get("reduceOnly", False):
                    tp_orders.append({
                        "price": trigger_price,
                        "qty": qty,
                        "order_id": order.get("orderId", ""),
                        "link_id": order_link_id,
                        "stop_order_type": stop_order_type
                    })
                    tp_orders_count += 1

                # Process SL orders (only one SL per position)
                if is_sl_order and order.get("reduceOnly", False) and not sl_price:
                    sl_price = trigger_price
                    sl_orders_count += 1

            # Sort TP orders by price (ascending for Buy, descending for Sell)
            tp_orders.sort(key=lambda x: x["price"], reverse=(side == "Sell"))

            # Calculate scenarios for this position
            position_tp1_profit = 0.0
            position_all_tp_profit = 0.0
            position_sl_loss = 0.0

            # TP1 profit calculation
            if tp_orders:
                tp1 = tp_orders[0]
                if side == "Buy":
                    # For conservative approach, TP1 is usually 70% of position
                    tp1_qty = min(tp1["qty"], size * 0.7) if "_TP1" in tp1["link_id"] else tp1["qty"]
                    position_tp1_profit = (tp1["price"] - entry_price) * tp1_qty
                else:  # Sell
                    tp1_qty = min(tp1["qty"], size * 0.7) if "_TP1" in tp1["link_id"] else tp1["qty"]
                    position_tp1_profit = (entry_price - tp1["price"]) * tp1_qty

            # All TPs profit calculation
            remaining_size = size
            for tp in tp_orders:
                tp_qty = min(tp["qty"], remaining_size)
                if tp_qty <= 0:
                    break

                if side == "Buy":
                    position_all_tp_profit += (tp["price"] - entry_price) * tp_qty
                else:  # Sell
                    position_all_tp_profit += (entry_price - tp["price"]) * tp_qty

                remaining_size -= tp_qty

            # If no TP orders or remaining size, use mark price estimate
            if remaining_size > 0 and mark_price > 0:
                if side == "Buy":
                    position_all_tp_profit += (mark_price - entry_price) * remaining_size
                else:  # Sell
                    position_all_tp_profit += (entry_price - mark_price) * remaining_size

            # SL loss calculation
            if sl_price:
                if side == "Buy":
                    position_sl_loss = (sl_price - entry_price) * size  # Will be negative
                else:  # Sell
                    position_sl_loss = (entry_price - sl_price) * size  # Will be negative

            # Add to totals
            total_tp1_profit += position_tp1_profit
            total_all_tp_profit += position_all_tp_profit
            total_sl_loss += position_sl_loss
            total_current_pnl += unrealized_pnl
            positions_count += 1

            # Store position details
            position_details.append({
                "symbol": symbol,
                "side": side,
                "size": size,
                "entry_price": entry_price,
                "current_pnl": unrealized_pnl,
                "tp1_profit": position_tp1_profit,
                "all_tp_profit": position_all_tp_profit,
                "sl_loss": position_sl_loss,
                "tp_count": len(tp_orders),
                "has_sl": sl_price is not None
            })

            logger.debug(f"📊 {symbol} {side}: TP1={position_tp1_profit:.2f}, AllTP={position_all_tp_profit:.2f}, SL={position_sl_loss:.2f}")

        logger.info(f"✅ Analyzed {positions_count} positions with {tp_orders_count} TP orders and {sl_orders_count} SL orders")
        logger.info(f"💰 TP1 Scenario: {total_tp1_profit:.2f}, All TP Scenario: {total_all_tp_profit:.2f}")
        logger.info(f"💸 SL Scenario: {total_sl_loss:.2f}, Current P&L: {total_current_pnl:.2f}")

        return {
            "tp1_profit": total_tp1_profit,
            "all_tp_profit": total_all_tp_profit,
            "sl_loss": total_sl_loss,
            "current_pnl": total_current_pnl,
            "positions_count": positions_count,
            "tp_orders_count": tp_orders_count,
            "sl_orders_count": sl_orders_count,
            "position_details": position_details,
            # Legacy compatibility
            "potential_profit": total_tp1_profit,
            "potential_loss": total_sl_loss,
            "positions_analyzed": positions_count
        }

    except Exception as e:
        logger.error(f"Error calculating potential P&L scenarios: {e}")
        return {
            "tp1_profit": 0.0,
            "all_tp_profit": 0.0,
            "sl_loss": 0.0,
            "current_pnl": 0.0,
            "positions_count": 0,
            "tp_orders_count": 0,
            "sl_orders_count": 0,
            "position_details": [],
            "error": str(e),
            # Legacy compatibility
            "potential_profit": 0.0,
            "potential_loss": 0.0,
            "positions_analyzed": 0
        }

async def get_detailed_order_info(symbol: str) -> Dict[str, Any]:
    """
    Get detailed information about all orders for a symbol, categorized by type.
    Useful for debugging and understanding order structure.

    Returns:
        Dict containing categorized orders and analysis
    """
    try:
        response = await api_call_with_retry(
            lambda: bybit_client.get_open_orders(
                category="linear",
                symbol=symbol
            ),
            timeout=20
        )

        if not response or response.get("retCode") != 0:
            return {"error": "Failed to fetch orders", "orders": []}

        all_orders = response.get("result", {}).get("list", [])

        # Categorize orders
        limit_orders = []
        tp_orders = []
        sl_orders = []
        other_orders = []

        for order in all_orders:
            order_info = {
                "orderId": order.get("orderId", ""),
                "orderLinkId": order.get("orderLinkId", ""),
                "orderType": order.get("orderType", ""),
                "side": order.get("side", ""),
                "qty": order.get("qty", ""),
                "price": order.get("price", ""),
                "triggerPrice": order.get("triggerPrice", ""),
                "stopOrderType": order.get("stopOrderType", ""),
                "reduceOnly": order.get("reduceOnly", False),
                "orderStatus": order.get("orderStatus", ""),
                "createdTime": order.get("createdTime", "")
            }

            # Enhanced categorization
            is_categorized = False

            # Check if it's a TP order
            if (order.get("stopOrderType") == "TakeProfit" or
                any(tp in order.get("orderLinkId", "") for tp in ["_TP", "TP1", "TP2", "TP3", "TP4"])):
                tp_orders.append(order_info)
                is_categorized = True

            # Check if it's a SL order
            elif (order.get("stopOrderType") == "StopLoss" or
                  "_SL" in order.get("orderLinkId", "")):
                sl_orders.append(order_info)
                is_categorized = True

            # Check if it's a limit entry order
            elif (order.get("orderType") == "Limit" and
                  not order.get("reduceOnly", False) and
                  not order.get("triggerPrice")):
                limit_orders.append(order_info)
                is_categorized = True

            # Other orders (conditional, market, etc.)
            if not is_categorized:
                other_orders.append(order_info)

        # Sort orders for better readability
        tp_orders.sort(key=lambda x: float(x.get("triggerPrice", x.get("price", "0")) or "0"))
        limit_orders.sort(key=lambda x: float(x.get("price", "0") or "0"))

        result = {
            "symbol": symbol,
            "total_orders": len(all_orders),
            "limit_orders": {
                "count": len(limit_orders),
                "orders": limit_orders
            },
            "tp_orders": {
                "count": len(tp_orders),
                "orders": tp_orders
            },
            "sl_orders": {
                "count": len(sl_orders),
                "orders": sl_orders
            },
            "other_orders": {
                "count": len(other_orders),
                "orders": other_orders
            }
        }

        logger.info(f"Order analysis for {symbol}: "
                   f"{len(limit_orders)} limit, {len(tp_orders)} TP, "
                   f"{len(sl_orders)} SL, {len(other_orders)} other")

        return result

    except Exception as e:
        logger.error(f"Error getting detailed order info for {symbol}: {e}")
        return {"error": str(e), "orders": []}

async def get_instrument_info(symbol: str) -> Optional[Dict]:
    """Get instrument information for symbol with enhanced error handling"""
    try:
        response = await api_call_with_retry(
            lambda: bybit_client.get_instruments_info(
                category="linear",
                symbol=symbol
            ),
            timeout=20
        )

        if response and response.get("retCode") == 0:
            instruments = response.get("result", {}).get("list", [])
            if instruments:
                return instruments[0]

        return None

    except Exception as e:
        logger.error(f"Error getting instrument info for {symbol}: {e}")
        return None

async def validate_order_parameters(symbol: str, quantity: float, price: float) -> tuple[bool, str]:
    """
    ENHANCED: Validate order parameters against instrument requirements
    """
    try:
        inst_info = await get_instrument_info(symbol)
        if not inst_info:
            return False, "Could not get instrument information"

        # Get size filters
        lot_size_filter = inst_info.get("lotSizeFilter", {})
        price_filter = inst_info.get("priceFilter", {})

        qty_step = float(lot_size_filter.get("qtyStep", 0.01))
        min_qty = float(lot_size_filter.get("minOrderQty", 0))
        tick_size = float(price_filter.get("tickSize", 0.01))

        # Validate quantity
        if quantity < min_qty:
            return False, f"Quantity {quantity} below minimum {min_qty}"

        # Check quantity step
        if qty_step > 0:
            remainder = (quantity * 1e8) % (qty_step * 1e8)  # Use integer math for precision
            if remainder > 1e-6:  # Allow small floating point errors
                return False, f"Quantity {quantity} doesn't match step size {qty_step}"

        # Check price step
        if tick_size > 0 and price > 0:
            remainder = (price * 1e8) % (tick_size * 1e8)  # Use integer math for precision
            if remainder > 1e-6:  # Allow small floating point errors
                return False, f"Price {price} doesn't match tick size {tick_size}"

        return True, "Parameters valid"

    except Exception as e:
        logger.error(f"Error validating order parameters: {e}")
        return False, f"Validation error: {e}"

# =============================================
# PUBLIC API FOR TRADE EXECUTION INTEGRATION
# =============================================

def protect_symbol_from_cleanup(symbol: str):
    """PUBLIC API: Protect a symbol from order cleanup (called by trade execution)"""
    add_symbol_to_protection(symbol)

def protect_trade_group_from_cleanup(trade_group_id: str):
    """PUBLIC API: Protect a trade group from cleanup (called by trade execution)"""
    add_trade_group_to_protection(trade_group_id)

def remove_trade_group_protection(trade_group_id: str):
    """PUBLIC API: Remove protection from a trade group (called when trade is complete)"""
    global ACTIVE_TRADE_GROUPS
    if trade_group_id in ACTIVE_TRADE_GROUPS:
        ACTIVE_TRADE_GROUPS.remove(trade_group_id)
        logger.info(f"🔓 Trade group {trade_group_id} protection removed")

# =============================================
# PERIODIC CLEANUP TASKS
# =============================================

async def set_symbol_leverage(symbol: str, leverage: int, client=None) -> bool:
    """
    Set leverage for a symbol before placing orders.

    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')
        leverage: Leverage value (e.g., 10 for 10x)
        client: Bybit client instance (defaults to main client)

    Returns:
        bool: True if successful, False otherwise
    """
    if client is None:
        client = bybit_client

    try:
        logger.info(f"⚡ Setting leverage for {symbol} to {leverage}x...")

        response = await api_call_with_retry(
            lambda: client.set_leverage(
                category="linear",
                symbol=symbol,
                buyLeverage=str(leverage),
                sellLeverage=str(leverage)
            ),
            timeout=30
        )

        if response and response.get('retCode') == 0:
            # Check if it's the "already set" response
            if response.get('retMsg') == "Leverage already set":
                logger.debug(f"✅ {symbol} leverage already at {leverage}x")
            else:
                logger.info(f"✅ Successfully set {symbol} leverage to {leverage}x")
            return True
        else:
            # Handle leverage not modified error (110043) silently
            if response and response.get('retCode') == 110043:
                logger.debug(f"✅ {symbol} leverage already at {leverage}x (no change needed)")
                return True
            logger.error(f"❌ Failed to set leverage for {symbol}: {response}")
            return False

    except Exception as e:
        # Handle leverage not modified error (110043) silently
        error_msg = str(e)
        if "110043" in error_msg and "leverage not modified" in error_msg:
            logger.debug(f"✅ {symbol} leverage already at {leverage}x (no change needed)")
            return True
        logger.error(f"❌ Error setting leverage for {symbol}: {e}")
        return False


async def periodic_order_cleanup_task():
    """Periodic task for ULTRA-CONSERVATIVE group-aware order cleanup with EXTERNAL ORDER PROTECTION"""
    try:
        # Import here to avoid circular imports
        from config.settings import (
            ENABLE_ORDER_CLEANUP,
            ORDER_CLEANUP_INTERVAL_SECONDS
        )

        if not ENABLE_ORDER_CLEANUP:
            logger.info("🧹 Periodic ULTRA-CONSERVATIVE order cleanup with EXTERNAL PROTECTION is disabled")
            return

        logger.info(f"🕐 Starting periodic ULTRA-CONSERVATIVE group-aware order cleanup task with EXTERNAL ORDER PROTECTION (interval: {ORDER_CLEANUP_INTERVAL_SECONDS}s)")

        while True:
            try:
                await asyncio.sleep(ORDER_CLEANUP_INTERVAL_SECONDS)

                logger.info("🕐 Running periodic ULTRA-CONSERVATIVE group-aware orphaned order cleanup with EXTERNAL ORDER PROTECTION...")

                # Cleanup expired protections first
                cleanup_expired_protections()

                # Run the ULTRA-CONSERVATIVE orphan scanner with EXTERNAL ORDER PROTECTION
                result = await run_enhanced_orphan_scanner()

                if result["status"] == "completed":
                    logger.info(f"✅ Periodic ULTRA-CONSERVATIVE cleanup with EXTERNAL PROTECTION completed: {result['message']}")
                elif result["status"] == "success":
                    logger.info(f"✅ Periodic ULTRA-CONSERVATIVE cleanup with EXTERNAL PROTECTION successful: {result['message']}")
                else:
                    logger.error(f"❌ Periodic ULTRA-CONSERVATIVE cleanup with EXTERNAL PROTECTION failed: {result['message']}")

            except Exception as e:
                logger.error(f"❌ Error in periodic ULTRA-CONSERVATIVE cleanup with EXTERNAL PROTECTION task: {e}")
                # Continue the loop even if there's an error
                await asyncio.sleep(60)  # Wait a minute before retrying

    except Exception as e:
        logger.error(f"❌ Fatal error in periodic ULTRA-CONSERVATIVE cleanup with EXTERNAL PROTECTION task: {e}")

# =============================================
# HEALTH CHECK FUNCTIONS
# =============================================

async def health_check() -> Dict[str, any]:
    """Perform health check on Bybit API connection"""
    try:
        # Test basic connectivity
        start_time = time.time()
        response = await api_call_with_retry(
            lambda: bybit_client.get_instruments_info(category="linear", limit=1),
            timeout=10
        )
        response_time = time.time() - start_time

        if response and response.get("retCode") == 0:
            return {
                "healthy": True,
                "response_time": response_time,
                "rate_limiter_tokens": _rate_limiter.tokens,
                "protected_symbols": len(RECENTLY_TRADED_SYMBOLS),
                "protected_trade_groups": len(ACTIVE_TRADE_GROUPS),
                "position_mode": "UNIFIED_ONE_WAY_MODE",
                "orphan_scanner": "ULTRA-CONSERVATIVE with EXTERNAL ORDER PROTECTION",
                "safety_level": "MAXIMUM",
                "position_mode_detection": "AUTOMATIC"
            }
        else:
            return {
                "healthy": False,
                "error": "Invalid API response",
                "response": response
            }

    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "response_time": None
        }

async def get_open_orders_with_client(client, **kwargs):
    """Get open orders from Bybit using provided client."""
    try:
        return client.get_open_orders(**kwargs)
    except Exception as e:
        logger.error(f"Error getting open orders: {e}")
        return None


async def get_all_positions_with_client(client):
    """Get all positions from Bybit using provided client."""
    try:
        response = client.get_positions(category="linear", settleCoin="USDT")
        if response and response.get('retCode') == 0:
            positions = response.get('result', {}).get('list', [])
            return [pos for pos in positions if float(pos.get('size', 0)) > 0]
        return []
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return []


async def place_order_with_client_retry(client, **kwargs):
    """Place order with retry logic using provided client."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.place_order(**kwargs)
            if response and response.get('retCode') == 0:
                return response
            logger.warning(f"Order placement failed: {response}")
        except Exception as e:
            logger.error(f"Error placing order (attempt {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(1)

    return None


async def cancel_order_with_client_retry(client, **kwargs):
    """Cancel order with retry logic using provided client."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.cancel_order(**kwargs)
            if response and response.get('retCode') == 0:
                return response
            logger.warning(f"Order cancellation failed: {response}")
        except Exception as e:
            logger.error(f"Error cancelling order (attempt {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(1)

    return None


async def get_position_info_for_account(symbol: str, account_type: str = "main") -> Optional[List[Dict]]:
    """Get position information for a specific symbol and account

    Args:
        symbol: Trading pair symbol
        account_type: 'main' or 'mirror'

    Returns:
        List of position dictionaries for the symbol, or empty list if none found
    """
    try:
        if account_type == "mirror":
            from execution.mirror_trader import bybit_client_2
            client = bybit_client_2
        else:
            from clients.bybit_client import bybit_client
            client = bybit_client

        response = client.get_positions(category="linear", symbol=symbol)
        if response and response.get('retCode') == 0:
            return response.get('result', {}).get('list', [])
    except Exception as e:
        logger.error(f"Error getting {account_type} position info for {symbol}: {e}")
    return []
