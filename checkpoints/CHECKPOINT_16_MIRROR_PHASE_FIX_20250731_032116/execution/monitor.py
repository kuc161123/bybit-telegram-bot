#!/usr/bin/env python3
"""
Position monitoring with ENHANCED PERFORMANCE TRACKING.
REFINED: Accurate P&L calculation, duplicate prevention, trade history
ENHANCED: Separate tracking for bot vs external trades
IMPROVED: Better error handling and validation
FIXED: Force immediate persistence after stats update
ADDED: Trade execution alerts for both approaches
"""
import logging
import asyncio
import time
import gc
from decimal import Decimal
from typing import Optional, Dict, Any, List, Set
import weakref
from collections import defaultdict
import hashlib
import json

from config.constants import *
from config.settings import POSITION_MONITOR_INTERVAL, ENABLE_MIRROR_TRADING
from clients.bybit_helpers import (
    get_position_info, get_order_info, get_open_orders,
    cancel_order_with_retry, amend_order_with_retry, api_call_with_retry
)
from utils.formatters import get_emoji, format_decimal_or_na
from utils.helpers import value_adjusted_to_step, safe_decimal_conversion
from utils.alert_helpers import send_trade_alert, send_position_closed_summary
from utils.persistence_optimizer import optimize_persistence_update
from utils.order_identifier import (
    identify_order_type, generate_order_link_id, group_orders_by_type,
    validate_order_coverage, ORDER_TYPE_TP, ORDER_TYPE_SL, ORDER_TYPE_LIMIT
)
from utils.tp_execution_verifier import tp_execution_verifier
from utils.order_execution_guard import order_execution_guard
from utils.position_size_tracker import position_size_tracker

# Import mirror trading components
try:
    from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
    MIRROR_TRADING_AVAILABLE = True
except ImportError:
    MIRROR_TRADING_AVAILABLE = False
    bybit_client_2 = None

logger = logging.getLogger(__name__)

# Import execution summary module
try:
    from execution.execution_summary import execution_summary
    EXECUTION_SUMMARY_AVAILABLE = True
except ImportError:
    EXECUTION_SUMMARY_AVAILABLE = False
    logger.warning("Execution summary module not available")

# Import get_all_positions for checking active positions
from clients.bybit_helpers import get_all_positions

def safe_decimal_conversion(value, default=Decimal("0")):
    """Safely convert value to Decimal with validation"""
    try:
        if value is None or str(value).strip() == '':
            return default
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except (ValueError, Exception):
        logger.warning(f"Could not convert '{value}' to Decimal, using default: {default}")
        return default

# REFINED: Trade history tracking to prevent duplicates
class TradeHistoryTracker:
    """Track completed trades to prevent duplicate performance updates"""

    def __init__(self, max_history=1000):
        self._completed_trades: Set[str] = set()
        self._trade_details: Dict[str, Dict[str, Any]] = {}
        self._max_history = max_history
        self._lock = asyncio.Lock()

    async def generate_trade_id(self, symbol: str, side: str, entry_price: Decimal,
                                close_time: float, pnl: Decimal) -> str:
        """Generate unique trade ID based on trade parameters"""
        # Create unique hash from trade parameters
        trade_str = f"{symbol}_{side}_{entry_price}_{close_time}_{pnl}"
        return hashlib.md5(trade_str.encode()).hexdigest()[:16]

    async def is_trade_processed(self, trade_id: str) -> bool:
        """Check if trade has already been processed"""
        async with self._lock:
            return trade_id in self._completed_trades

    async def mark_trade_processed(self, trade_id: str, trade_details: Dict[str, Any]):
        """Mark trade as processed and store details"""
        async with self._lock:
            self._completed_trades.add(trade_id)
            self._trade_details[trade_id] = {
                **trade_details,
                'processed_at': time.time()
            }

            # Cleanup old entries if needed
            if len(self._completed_trades) > self._max_history:
                # Remove oldest 20% of trades
                sorted_trades = sorted(
                    self._trade_details.items(),
                    key=lambda x: x[1].get('processed_at', 0)
                )
                trades_to_remove = sorted_trades[:int(self._max_history * 0.2)]

                for trade_id, _ in trades_to_remove:
                    self._completed_trades.discard(trade_id)
                    self._trade_details.pop(trade_id, None)

    def get_trade_details(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """Get details of a processed trade"""
        return self._trade_details.get(trade_id)

# Global trade history tracker
_trade_history = TradeHistoryTracker()

# REFINED: Enhanced task registry with proper cleanup
class TaskRegistry:
    """Enhanced task registry with memory leak prevention"""

    def __init__(self):
        self._tasks: Dict[str, weakref.ref] = {}
        self._task_metadata: Dict[str, Dict[str, Any]] = {}
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()

    def register_task(self, task_key: str, task, metadata: Dict[str, Any] = None):
        """Register a monitoring task with metadata"""
        self._tasks[task_key] = weakref.ref(task, self._task_cleanup_callback(task_key))
        self._task_metadata[task_key] = metadata or {}
        self._task_metadata[task_key]['registered_at'] = time.time()
        logger.debug(f"Task registered: {task_key}")

        # Periodic cleanup
        self._maybe_cleanup()

    def unregister_task(self, task_key: str):
        """Unregister a monitoring task"""
        if task_key in self._tasks:
            del self._tasks[task_key]
        if task_key in self._task_metadata:
            del self._task_metadata[task_key]
        logger.debug(f"Task unregistered: {task_key}")

    def get_task_status(self, task_key: str) -> Dict[str, Any]:
        """Get task status with enhanced information"""
        if task_key not in self._tasks:
            return {"exists": False, "running": False, "task_key": task_key}

        task_ref = self._tasks[task_key]
        task = task_ref()

        if task is None:
            # Task was garbage collected
            self.unregister_task(task_key)
            return {"exists": False, "running": False, "task_key": task_key}

        metadata = self._task_metadata.get(task_key, {})

        status = {
            "exists": True,
            "task_key": task_key,
            "registered_at": metadata.get('registered_at', 0),
            "running_time": time.time() - metadata.get('registered_at', time.time()),
            "metadata": metadata
        }

        if hasattr(task, 'done'):
            status.update({
                "running": not task.done(),
                "done": task.done(),
                "cancelled": task.cancelled() if hasattr(task, 'cancelled') else False
            })
        else:
            status["running"] = True

        return status

    def _task_cleanup_callback(self, task_key: str):
        """Create cleanup callback for weak reference"""
        def cleanup(ref):
            if task_key in self._tasks:
                del self._tasks[task_key]
            if task_key in self._task_metadata:
                del self._task_metadata[task_key]
            logger.debug(f"Task auto-cleaned: {task_key}")
        return cleanup

    def _maybe_cleanup(self):
        """Perform periodic cleanup if needed"""
        current_time = time.time()
        if current_time - self._last_cleanup > self._cleanup_interval:
            self.cleanup_stale_tasks()
            self._last_cleanup = current_time

    def cleanup_stale_tasks(self):
        """Clean up stale tasks and run garbage collection"""
        stale_keys = []
        current_time = time.time()

        for task_key, task_ref in self._tasks.items():
            task = task_ref()
            if task is None:
                stale_keys.append(task_key)
            elif hasattr(task, 'done') and task.done():
                # Check if task has been done for more than 1 hour
                metadata = self._task_metadata.get(task_key, {})
                if current_time - metadata.get('registered_at', current_time) > 3600:
                    stale_keys.append(task_key)

        for key in stale_keys:
            self.unregister_task(key)

        if stale_keys:
            logger.info(f"Cleaned up {len(stale_keys)} stale monitoring tasks")
            # Force garbage collection
            gc.collect()

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        active_tasks = 0
        running_tasks = 0

        for task_key in list(self._tasks.keys()):
            status = self.get_task_status(task_key)
            if status["exists"]:
                active_tasks += 1
                if status.get("running", False):
                    running_tasks += 1

        return {
            "total_registered": len(self._tasks),
            "active_tasks": active_tasks,
            "running_tasks": running_tasks,
            "metadata_entries": len(self._task_metadata)
        }

# Global task registry with proper cleanup
_task_registry = TaskRegistry()

async def register_monitor_task(chat_id: int, symbol: str, task, metadata: Dict[str, Any] = None):
    """Register a monitor task for tracking"""
    approach = metadata.get('approach', 'conservative') if metadata else 'conservative'
    account_type = metadata.get('account_type', ACCOUNT_TYPE_PRIMARY) if metadata else ACCOUNT_TYPE_PRIMARY
    task_key = f"{chat_id}_{symbol}_{approach}_{account_type}"
    enhanced_metadata = {
        "chat_id": chat_id,
        "symbol": symbol,
        "approach": approach,
        "account_type": account_type,
        "type": "position_monitor",
        **(metadata or {})
    }
    _task_registry.register_task(task_key, task, enhanced_metadata)
    logger.info(f"📋 Registered {account_type} monitor task for {symbol} ({approach}) in chat {chat_id}")

    # Also store in bot_data for dashboard access
    try:
        # Get bot_data from the application context if available
        from telegram.ext import Application
        # This will be passed through context when needed
        # For now, we'll rely on the calling function to update bot_data
        pass
    except:
        pass

async def unregister_monitor_task(chat_id: int, symbol: str, approach: str = None, account_type: str = None):
    """Unregister a monitor task"""
    # If approach not specified, try to get it from chat_data or unregister both
    if approach and account_type:
        task_key = f"{chat_id}_{symbol}_{approach}_{account_type}"
        _task_registry.unregister_task(task_key)
        logger.info(f"📋 Unregistered {account_type} monitor task for {symbol} ({approach}) in chat {chat_id}")
    elif approach:
        # Try both account types if account_type not specified
        for acc_type in [ACCOUNT_TYPE_PRIMARY, ACCOUNT_TYPE_MIRROR]:
            task_key = f"{chat_id}_{symbol}_{approach}_{acc_type}"
            if task_key in _task_registry._tasks:
                _task_registry.unregister_task(task_key)
                logger.info(f"📋 Unregistered {acc_type} monitor task for {symbol} ({approach}) in chat {chat_id}")
    else:
        # Try all combinations if neither specified
        for app in ['conservative']:
            for acc_type in [ACCOUNT_TYPE_PRIMARY, ACCOUNT_TYPE_MIRROR]:
                task_key = f"{chat_id}_{symbol}_{app}_{acc_type}"
                if task_key in _task_registry._tasks:
                    _task_registry.unregister_task(task_key)
                    logger.info(f"📋 Unregistered {acc_type} monitor task for {symbol} ({app}) in chat {chat_id}")

async def get_monitor_task_status(chat_id: int, symbol: str, approach: str = None, account_type: str = None) -> Dict:
    """Get the status of a monitor task"""
    if approach and account_type:
        task_key = f"{chat_id}_{symbol}_{approach}_{account_type}"
        return _task_registry.get_task_status(task_key)
    elif approach:
        # Check both account types if account_type not specified
        for acc_type in [ACCOUNT_TYPE_PRIMARY, ACCOUNT_TYPE_MIRROR]:
            task_key = f"{chat_id}_{symbol}_{approach}_{acc_type}"
            status = _task_registry.get_task_status(task_key)
            if status.get('exists') and status.get('running'):
                return status
    else:
        # If no approach specified, check all combinations
        for app in ['conservative']:
            for acc_type in [ACCOUNT_TYPE_PRIMARY, ACCOUNT_TYPE_MIRROR]:
                task_key = f"{chat_id}_{symbol}_{app}_{acc_type}"
                status = _task_registry.get_task_status(task_key)
                if status.get('exists') and status.get('running'):
                    return status

    # Return not found status
    return {"exists": False, "running": False, "task_key": f"{chat_id}_{symbol}_unknown"}

def get_monitoring_mode(chat_data: dict) -> str:
    """Get the monitoring mode description - all trades are bot trades now"""
    approach = chat_data.get(TRADING_APPROACH, "conservative")
    return f"BOT-{approach.upper()}"

# =============================================
# MIRROR ACCOUNT POSITION MONITORING FUNCTIONS
# =============================================

async def get_mirror_position_info(symbol: str) -> Optional[List[Dict]]:
    """Get position information from mirror account"""
    if not MIRROR_TRADING_AVAILABLE or not bybit_client_2:
        return []

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
            result = response.get("result", {})
            positions = result.get("list", [])
            return positions

        return []

    except Exception as e:
        logger.error(f"Error fetching mirror position info for {symbol}: {e}")
        return []

async def get_mirror_order_info(symbol: str, order_id: str) -> Optional[Dict]:
    """Get order information from mirror account"""
    if not MIRROR_TRADING_AVAILABLE or not bybit_client_2:
        return None

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client_2.get_order_history(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )
        )

        if response and response.get("retCode") == 0:
            orders = response.get("result", {}).get("list", [])
            if orders:
                return orders[0]

        return None

    except Exception as e:
        logger.error(f"Error fetching mirror order info: {e}")
        return None

async def cancel_mirror_order_with_retry(symbol: str, order_id: str) -> bool:
    """Cancel order on mirror account with retry logic"""
    if not MIRROR_TRADING_AVAILABLE or not bybit_client_2:
        return False

    try:
        from execution.mirror_trader import cancel_mirror_order
        return await cancel_mirror_order(symbol, order_id)
    except Exception as e:
        logger.error(f"Error cancelling mirror order: {e}")
        return False

# =============================================
# ENHANCED: CONSERVATIVE APPROACH ORDER MANAGEMENT (ONLY FOR FULL MONITORING)
# =============================================

async def check_conservative_tp1_hit(chat_data: dict, symbol: str, current_price: Decimal, side: str) -> bool:
    """
    Check if TP1 has been hit BEFORE any limit orders are filled
    This triggers full cancellation of all orders
    """
    try:
        approach = chat_data.get(TRADING_APPROACH, "conservative")
        if approach not in ["conservative", "ggshot"]:
            return False

        # Check if TP1 cancellation already processed
        if chat_data.get(CONSERVATIVE_TP1_HIT_BEFORE_LIMITS, False):
            return False

        # Get TP order IDs
        tp_order_ids = chat_data.get(CONSERVATIVE_TP_ORDER_IDS, [])
        if not tp_order_ids:
            logger.warning(f"No TP order IDs found for {symbol} conservative - cannot check TP1 hit")
            return False

        # Check actual TP1 order status (first TP order)
        tp1_order_id = tp_order_ids[0]
        tp1_info = await get_order_info(symbol, tp1_order_id)

        if not tp1_info:
            logger.warning(f"Could not get TP1 order info for {symbol}")
            # Fall back to price check
            tp1_price = chat_data.get(TP1_PRICE)
            if tp1_price:
                tp1_price = safe_decimal_conversion(tp1_price)
                if side == "Buy" and current_price >= tp1_price:
                    logger.info(f"TP1 price {tp1_price} crossed by market price {current_price}")
                elif side == "Sell" and current_price <= tp1_price:
                    logger.info(f"TP1 price {tp1_price} crossed by market price {current_price}")
            return False

        tp1_status = tp1_info.get("orderStatus", "")
        logger.debug(f"TP1 order {tp1_order_id[:8]}... status: {tp1_status}")

        if tp1_status in ["Filled", "PartiallyFilled"]:
            # TP1 has been hit - check if NO limit orders have been filled yet
            limits_filled = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])

            if len(limits_filled) == 0:
                logger.info(f"🚨 TP1 HIT (order filled) BEFORE any limits filled for {symbol} - triggering full cancellation")
                return True
            else:
                logger.info(f"TP1 hit but {len(limits_filled)} limits already filled - using partial cancellation logic")

        return False

    except Exception as e:
        logger.error(f"Error checking conservative TP1 hit before limits: {e}")
        return False

async def check_conservative_tp1_hit_with_fills(chat_data: dict, symbol: str, current_price: Decimal, side: str) -> bool:
    """
    Check if TP1 has been hit after some limit orders were filled
    This handles the scenario where we want to cancel remaining limits but keep TP2-TP4 active
    """
    try:
        approach = chat_data.get(TRADING_APPROACH, "conservative")
        if approach not in ["conservative", "ggshot"]:
            return False

        # Check if we already processed TP1 hit with fills
        if chat_data.get("conservative_tp1_hit_with_fills_processed", False):
            return False

        # Get TP order IDs
        tp_order_ids = chat_data.get(CONSERVATIVE_TP_ORDER_IDS, [])
        if not tp_order_ids:
            logger.warning(f"No TP order IDs found for {symbol} conservative - cannot check TP1 hit with fills")
            return False

        # Check actual TP1 order status (first TP order)
        tp1_order_id = tp_order_ids[0]
        tp1_info = await get_order_info(symbol, tp1_order_id)

        if not tp1_info:
            logger.warning(f"Could not get TP1 order info for {symbol} - falling back to price check")
            # Fall back to price check
            tp1_price = chat_data.get(TP1_PRICE)
            if not tp1_price:
                return False

            tp1_price = safe_decimal_conversion(tp1_price)
            tp1_triggered = False

            if side == "Buy":
                tp1_triggered = current_price >= tp1_price
            elif side == "Sell":
                tp1_triggered = current_price <= tp1_price

            if not tp1_triggered:
                return False
        else:
            tp1_status = tp1_info.get("orderStatus", "")
            logger.debug(f"TP1 order {tp1_order_id[:8]}... status: {tp1_status} (checking with fills)")

            if tp1_status not in ["Filled", "PartiallyFilled"]:
                return False

        # TP1 has been hit - check if at least one limit order has been filled
        # FIX: Check monitor data for limit order IDs if not in chat_data
        limit_order_ids = chat_data.get(LIMIT_ORDER_IDS, [])

        # If no limit IDs in chat_data, check monitor data (for existing positions)
        if not limit_order_ids and ctx_app and hasattr(ctx_app, 'bot_data'):
            try:
                bot_data = ctx_app.bot_data
                chat_data_all = bot_data.get('chat_data', {})
                chat_id = chat_data.get('chat_id') or chat_data.get('_chat_id')
                if chat_id:
                    stored_chat_data = chat_data_all.get(chat_id, {})
                    active_monitors = stored_chat_data.get('active_monitor_task_data_v2', {})

                    # Find monitor for this symbol
                    monitor_key = f"{chat_id}_{symbol}_{approach}"
                    monitor_data = active_monitors.get(monitor_key, {})

                    # Get limit order IDs from monitor data
                    monitor_limit_ids = monitor_data.get('conservative_limit_order_ids', [])
                    if monitor_limit_ids:
                        limit_order_ids = monitor_limit_ids
                        logger.info(f"✅ Found {len(limit_order_ids)} limit order IDs in monitor data")
            except Exception as e:
                logger.debug(f"Could not check monitor data for limit IDs: {e}")

        limits_filled = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])

        # If some limits are filled but not all
        if len(limits_filled) > 0 and len(limits_filled) < len(limit_order_ids):
            logger.info(f"🎯 TP1 HIT (order filled) with {len(limits_filled)} limits filled - cancelling remaining {len(limit_order_ids) - len(limits_filled)} limits")
            return True
        elif len(limits_filled) == len(limit_order_ids):
            logger.info(f"TP1 hit but all {len(limit_order_ids)} limits already filled - no cancellation needed")

        return False

    except Exception as e:
        logger.error(f"Error checking conservative TP1 hit with fills: {e}")
        return False

async def cancel_remaining_conservative_limits_only(chat_data: dict, symbol: str, ctx_app=None) -> List[str]:
    """
    Cancel only remaining unfilled limit orders when TP1 hits after some fills
    Keep TP2, TP3, TP4 active for the life of the trade
    ADDED: Send alert for TP1 hit with fills scenario
    """
    try:

        cancelled_orders = []

        # Get order IDs
        # FIX: Check monitor data for limit order IDs if not in chat_data
        limit_order_ids = chat_data.get(LIMIT_ORDER_IDS, [])

        # If no limit IDs in chat_data, check monitor data (for existing positions)
        if not limit_order_ids and ctx_app and hasattr(ctx_app, 'bot_data'):
            try:
                bot_data = ctx_app.bot_data
                chat_data_all = bot_data.get('chat_data', {})
                chat_id = chat_data.get('chat_id') or chat_data.get('_chat_id')
                if chat_id:
                    stored_chat_data = chat_data_all.get(chat_id, {})
                    active_monitors = stored_chat_data.get('active_monitor_task_data_v2', {})

                    # Find monitor for this symbol
                    monitor_key = f"{chat_id}_{symbol}_{approach}"
                    monitor_data = active_monitors.get(monitor_key, {})

                    # Get limit order IDs from monitor data
                    monitor_limit_ids = monitor_data.get('conservative_limit_order_ids', [])
                    if monitor_limit_ids:
                        limit_order_ids = monitor_limit_ids
                        logger.info(f"✅ Found {len(limit_order_ids)} limit order IDs in monitor data")
            except Exception as e:
                logger.debug(f"Could not check monitor data for limit IDs: {e}")

        limits_filled = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])

        # Cancel only unfilled limit orders
        unfilled_limits = [oid for oid in limit_order_ids if oid not in limits_filled]

        for limit_id in unfilled_limits:
            if limit_id:
                logger.info(f"🎯 TP1 hit - cancelling remaining unfilled limit order {limit_id}")
                success = await cancel_order_with_retry(symbol, limit_id)
                if success:
                    cancelled_orders.append(f"Remaining limit order {limit_id[:8]}...")
                    logger.info(f"✅ Cancelled remaining limit order {limit_id}")
                else:
                    logger.warning(f"⚠️ Failed to cancel remaining limit order {limit_id}")

        # Send alert for TP1 hit with fills
        if ctx_app and hasattr(ctx_app, 'bot') and cancelled_orders:
            chat_id = chat_data.get('chat_id') or chat_data.get('_chat_id')
            side = chat_data.get(SIDE, "Unknown")
            approach = chat_data.get(TRADING_APPROACH, "conservative")
            if chat_id:
                # Include SL movement info if available
                additional_info = {
                    "filled_count": len(limits_filled),
                    "total_limits": len(limit_order_ids)
                }
                # Removed breakeven functionality

                await send_trade_alert(
                    bot=ctx_app.bot,
                    chat_id=chat_id,
                    alert_type="tp1_with_fills",
                    symbol=symbol,
                    side=side,
                    approach=approach,
                    pnl=Decimal("0"),
                    entry_price=Decimal("0"),
                    current_price=Decimal("0"),
                    position_size=Decimal("0"),
                    cancelled_orders=cancelled_orders,
                    additional_info=additional_info
                )

        # Mark as processed (different from the original TP1 cancellation)
        chat_data["conservative_tp1_hit_with_fills_processed"] = True

        # DO NOT cancel TP2, TP3, TP4 - they remain active!
        logger.info(f"🎯 TP1 hit processing completed: {len(cancelled_orders)} remaining limits cancelled")
        logger.info(f"✅ TP2, TP3, TP4 remain active for the life of the trade")

        return cancelled_orders

    except Exception as e:
        logger.error(f"❌ Error cancelling remaining conservative limits: {e}", exc_info=True)
        return []

async def cancel_conservative_orders_on_tp1_hit(chat_data: dict, symbol: str, ctx_app=None) -> List[str]:
    """
    Cancel all remaining conservative orders when TP1 hits before limits fill
    ADDED: Send alert for TP1 early hit scenario

    All trades are bot trades now
    """
    try:

        cancelled_orders = []

        # Get order IDs
        limit_order_ids = chat_data.get(LIMIT_ORDER_IDS, [])
        tp_order_ids = chat_data.get(CONSERVATIVE_TP_ORDER_IDS, [])
        sl_order_id = chat_data.get(CONSERVATIVE_SL_ORDER_ID)
        limits_filled = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])

        # PERFORMANCE: Cancel orders in parallel for 70-80% speed improvement
        unfilled_limits = [oid for oid in limit_order_ids if oid not in limits_filled]
        remaining_tp_ids = tp_order_ids[1:] if len(tp_order_ids) > 1 else []  # Skip TP1

        # Collect all orders to cancel
        orders_to_cancel = []
        order_types = []

        for limit_id in unfilled_limits:
            if limit_id:
                orders_to_cancel.append(limit_id)
                order_types.append("Limit")

        for tp_id in remaining_tp_ids:
            if tp_id:
                orders_to_cancel.append(tp_id)
                order_types.append("TP")

        if sl_order_id:
            orders_to_cancel.append(sl_order_id)
            order_types.append("SL")

        if orders_to_cancel:
            logger.info(f"⚡ Cancelling {len(orders_to_cancel)} orders in parallel...")

            # Create cancellation tasks
            cancellation_tasks = [
                cancel_order_with_retry(symbol, order_id)
                for order_id in orders_to_cancel
            ]

            # Execute all cancellations simultaneously
            results = await asyncio.gather(*cancellation_tasks, return_exceptions=True)

            # Process results
            for i, (order_id, order_type, result) in enumerate(zip(orders_to_cancel, order_types, results)):
                if isinstance(result, bool) and result:
                    cancelled_orders.append(f"{order_type} order {order_id[:8]}...")
                    logger.info(f"✅ Cancelled {order_type} order {order_id}")
                else:
                    error_msg = str(result) if isinstance(result, Exception) else "Unknown error"
                    logger.warning(f"⚠️ Failed to cancel {order_type} order {order_id}: {error_msg}")

        # Send alert for TP1 early hit
        if ctx_app and hasattr(ctx_app, 'bot') and cancelled_orders:
            chat_id = chat_data.get('chat_id') or chat_data.get('_chat_id')
            side = chat_data.get(SIDE, "Unknown")
            approach = chat_data.get(TRADING_APPROACH, "conservative")
            if chat_id:
                # Include SL movement info if available
                additional_info = {}
                # Removed breakeven functionality

                await send_trade_alert(
                    bot=ctx_app.bot,
                    chat_id=chat_id,
                    alert_type="tp1_early_hit",
                    symbol=symbol,
                    side=side,
                    approach=approach,
                    pnl=Decimal("0"),
                    entry_price=Decimal("0"),
                    current_price=Decimal("0"),
                    position_size=Decimal("0"),
                    cancelled_orders=cancelled_orders,
                    additional_info=additional_info
                )

        # Mark as processed
        chat_data[CONSERVATIVE_TP1_HIT_BEFORE_LIMITS] = True
        chat_data[CONSERVATIVE_ORDERS_CANCELLED] = True

        logger.info(f"🚨 Conservative TP1 cancellation completed: {len(cancelled_orders)} orders cancelled")

        # Even if no orders were cancelled (they may have been filled), mark as processed
        if len(cancelled_orders) == 0:
            logger.info(f"✅ No orders were cancelled (likely already filled), but marking TP1 cancellation as processed")

        return cancelled_orders

    except Exception as e:
        logger.error(f"❌ Error cancelling conservative orders on TP1 hit: {e}", exc_info=True)
        return []

async def check_conservative_limit_fills(chat_data: dict, symbol: str, ctx_app=None) -> List[str]:
    """
    Check which conservative limit orders have been filled
    ADDED: Send alerts for newly filled limit orders
    ENHANCED: Use robust order identification

    All trades are bot trades now - no read-only monitoring
    """
    try:

        approach = chat_data.get(TRADING_APPROACH, "conservative")
        if approach not in ["conservative", "ggshot"]:
            logger.debug(f"🔍 Skipping limit fill check for {symbol} - approach is {approach}")
            return []

        # FIX: Check monitor data for limit order IDs if not in chat_data
        limit_order_ids = chat_data.get(LIMIT_ORDER_IDS, [])

        # If no limit IDs in chat_data, check monitor data (for existing positions)
        if not limit_order_ids and ctx_app and hasattr(ctx_app, 'bot_data'):
            try:
                bot_data = ctx_app.bot_data
                chat_data_all = bot_data.get('chat_data', {})
                chat_id = chat_data.get('chat_id') or chat_data.get('_chat_id')
                if chat_id:
                    stored_chat_data = chat_data_all.get(chat_id, {})
                    active_monitors = stored_chat_data.get('active_monitor_task_data_v2', {})

                    # Find monitor for this symbol
                    monitor_key = f"{chat_id}_{symbol}_{approach}"
                    monitor_data = active_monitors.get(monitor_key, {})

                    # Get limit order IDs from monitor data
                    monitor_limit_ids = monitor_data.get('conservative_limit_order_ids', [])
                    if monitor_limit_ids:
                        limit_order_ids = monitor_limit_ids
                        logger.info(f"✅ Found {len(limit_order_ids)} limit order IDs in monitor data")
            except Exception as e:
                logger.debug(f"Could not check monitor data for limit IDs: {e}")

        limits_filled = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])

        logger.info(f"🔍 Checking limit fills for {symbol}: {len(limit_order_ids)} limit orders, {len(limits_filled)} already filled")
        logger.info(f"🔍 Limit order IDs: {limit_order_ids}")
        logger.info(f"🔍 Already filled: {limits_filled}")
        logger.info(f"🔍 Chat data has chat_id: {chat_data.get('chat_id') or chat_data.get('_chat_id')}")
        logger.info(f"🔍 ctx_app available: {ctx_app is not None}, has bot: {hasattr(ctx_app, 'bot') if ctx_app else False}")

        newly_filled = []

        # Get position info for context in order identification
        positions = await get_position_info(symbol)
        position = None
        if positions:
            for pos in positions:
                if float(pos.get("size", 0)) > 0:
                    position = pos
                    break

        for i, order_id in enumerate(limit_order_ids):
            if order_id and order_id not in limits_filled:
                # Check order status
                logger.info(f"🔍 Checking order {i+1}/{len(limit_order_ids)}: {order_id[:8]}...")
                order_info = await get_order_info(symbol, order_id)
                if order_info:
                    # Enhanced order type identification
                    order_type, confidence = identify_order_type(order_info, position)
                    logger.debug(f"🔍 Order {order_id[:8]}... identified as {order_type} (confidence: {confidence:.2f})")

                    order_status = order_info.get("orderStatus", "")
                    logger.info(f"🔍 Order {order_id[:8]}... status: {order_status}")
                    if order_status in ["Filled", "PartiallyFilled"]:
                        newly_filled.append(order_id)
                        limits_filled.append(order_id)
                        logger.info(f"✅ Conservative limit order filled: {order_id[:8]}...")

                        # Send alert for limit fill
                        logger.debug(f"🔍 Alert check - ctx_app: {ctx_app is not None}, has bot: {hasattr(ctx_app, 'bot') if ctx_app else False}")
                        if ctx_app and hasattr(ctx_app, 'bot'):
                            chat_id = chat_data.get('chat_id') or chat_data.get('_chat_id')
                            side = chat_data.get(SIDE, "Unknown")
                            logger.debug(f"🔍 Alert params - chat_id: {chat_id}, side: {side}")
                            if chat_id:
                                fill_price = Decimal(str(order_info.get("avgPrice", 0)))
                                fill_size = Decimal(str(order_info.get("cumExecQty", 0)))
                                logger.info(f"📨 Sending limit fill alert for {symbol} - Order {i+1}/{len(limit_order_ids)}, Price: {fill_price}, Size: {fill_size}")
                                await send_trade_alert(
                                    bot=ctx_app.bot,
                                    chat_id=chat_id,
                                    alert_type="limit_filled",
                                    symbol=symbol,
                                    side=side,
                                    approach=approach,
                                    pnl=Decimal("0"),  # No P&L for limit fill
                                    entry_price=fill_price,
                                    current_price=fill_price,
                                    position_size=fill_size,
                                    additional_info={
                                        "limit_number": i + 1,
                                        "total_limits": len(limit_order_ids),
                                        "fill_price": fill_price,
                                        "fill_size": fill_size,
                                        "filled_count": len(limits_filled)
                                    }
                                )
                            else:
                                logger.warning(f"⚠️ No chat_id found for limit fill alert - {symbol}")
                        else:
                            logger.warning(f"⚠️ Cannot send alert - ctx_app or bot not available for {symbol}")
                else:
                    logger.debug(f"🔍 No order info returned for {order_id[:8]}...")

        # Update chat data
        chat_data[CONSERVATIVE_LIMITS_FILLED] = limits_filled

        if newly_filled:
            logger.info(f"✅ {len(newly_filled)} limit orders newly filled for {symbol}")

            # Trigger Conservative rebalancing when limits fill
            try:
                from execution.conservative_rebalancer import rebalance_conservative_on_limit_fill

                logger.info(f"🔄 Triggering Conservative rebalance due to limit fills")
                rebalance_result = await rebalance_conservative_on_limit_fill(
                    chat_data=chat_data,
                    symbol=symbol,
                    filled_limits=len(limits_filled),
                    total_limits=len(limit_order_ids),
                    ctx_app=ctx_app
                )

                if rebalance_result.get("success"):
                    logger.info(f"✅ Conservative rebalance completed - cancelled {rebalance_result.get('cancelled')} orders, created {rebalance_result.get('created')} new orders")
                else:
                    logger.error(f"❌ Conservative rebalance failed: {rebalance_result.get('error')}")

            except Exception as e:
                logger.error(f"Error triggering Conservative rebalance: {e}")

        return newly_filled

    except Exception as e:
        logger.error(f"Error checking conservative limit fills: {e}", exc_info=True)
        return []

# =============================================

async def ensure_conservative_position_monitored(symbol: str, chat_id: int, chat_data: dict) -> bool:
    """
    Ensure a conservative position has proper monitoring
    This prevents issues like JUPUSDT not being found
    """
    try:
        # Get all orders for this symbol
        all_orders = await get_all_open_orders()
        symbol_orders = [o for o in all_orders if o.get('symbol') == symbol]

        # Count TPs
        tp_count = sum(1 for o in symbol_orders if
                      ('TP' in o.get('orderLinkId', '') and o.get('reduceOnly')) or
                      (o.get('stopOrderType') == 'TakeProfit'))

        # If 4 or more TPs, it's conservative
        if tp_count >= 4:
            active_monitors = chat_data.get('active_monitor_task_data_v2', {})
            monitor_key = f"{chat_id}_{symbol}_conservative"

            if monitor_key not in active_monitors:
                logger.info(f"📌 Creating missing conservative monitor for {symbol}")

                # Get position info
                positions = await get_position_info(symbol)
                if positions:
                    position = next((p for p in positions if float(p.get('size', 0)) > 0), None)
                    if position:
                        side = position.get('side')

                        # Create monitor entry
                        active_monitors[monitor_key] = {
                            'symbol': symbol,
                            'side': side,
                            'approach': 'conservative',
                            'started_at': asyncio.get_event_loop().time(),
                            'chat_id': chat_id,
                            'is_conservative': True,
                            'tp_count': tp_count,
                            'auto_created': True
                        }

                        # Extract order IDs
                        tp_order_ids = []
                        for order in symbol_orders:
                            if 'TP' in order.get('orderLinkId', '') and order.get('reduceOnly'):
                                tp_order_ids.append(order.get('orderId'))

                        if tp_order_ids:
                            active_monitors[monitor_key]['conservative_tp_order_ids'] = tp_order_ids[:4]

                        logger.info(f"✅ Created conservative monitor for {symbol}")
                        return True

        return False

    except Exception as e:
        logger.error(f"Error ensuring conservative monitor: {e}")
        return False

# FIXED: ENHANCED FAST APPROACH TP/SL ORDER MANAGEMENT
# =============================================

async def check_tp_hit_and_cancel_sl(chat_data: dict, symbol: str, current_price: Decimal, side: str, ctx_app=None) -> bool:
    """
    Fast approach removed - function disabled
    """
    return False

async def check_sl_hit_and_cancel_tp(chat_data: dict, symbol: str, current_price: Decimal, side: str, ctx_app=None) -> bool:
    """
    Fast approach removed - function disabled
    """
    return False

async def cancel_remaining_orders(chat_data: dict, symbol: str, triggered_order_type: str):
    """
    ENHANCED: Cancel remaining orders when TP or SL is hit - with conservative approach support

    All trades are bot trades now
    """
    try:

        orders_cancelled = []
        approach = chat_data.get(TRADING_APPROACH, "conservative")

        if approach == "conservative":
            # Conservative approach - handle complex order cancellation
            if triggered_order_type == 'TP':
                # TP was hit, cancel SL and remaining TPs
                sl_order_id = chat_data.get(CONSERVATIVE_SL_ORDER_ID)
                if sl_order_id:
                    logger.info(f"🎯 Conservative TP hit for {symbol}, canceling SL order {sl_order_id}")
                    success = await cancel_order_with_retry(symbol, sl_order_id)
                    if success:
                        orders_cancelled.append(f"SL order {sl_order_id[:8]}...")
                        chat_data[CONSERVATIVE_SL_ORDER_ID] = None
                        logger.info(f"✅ Conservative SL order {sl_order_id} cancelled successfully")

                # Cancel remaining TP orders (those that haven't been hit)
                tp_order_ids = chat_data.get(CONSERVATIVE_TP_ORDER_IDS, [])
                for tp_id in tp_order_ids:
                    if tp_id:
                        logger.info(f"🎯 Conservative TP hit for {symbol}, canceling remaining TP order {tp_id}")
                        success = await cancel_order_with_retry(symbol, tp_id)
                        if success:
                            orders_cancelled.append(f"TP order {tp_id[:8]}...")
                            logger.info(f"✅ Conservative TP order {tp_id} cancelled successfully")

                # Clear TP orders from chat data
                chat_data[CONSERVATIVE_TP_ORDER_IDS] = []

            elif triggered_order_type == 'SL':
                # SL was hit, cancel ALL remaining orders (TPs and unfilled limits)
                tp_order_ids = chat_data.get(CONSERVATIVE_TP_ORDER_IDS, [])
                for tp_id in tp_order_ids:
                    if tp_id:
                        logger.info(f"🛡️ Conservative SL hit for {symbol}, canceling TP order {tp_id}")
                        success = await cancel_order_with_retry(symbol, tp_id)
                        if success:
                            orders_cancelled.append(f"TP order {tp_id[:8]}...")
                            logger.info(f"✅ Conservative TP order {tp_id} cancelled successfully")

                # Cancel unfilled limit orders (if any remain)
                limit_order_ids = chat_data.get(LIMIT_ORDER_IDS, [])
                limits_filled = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])
                unfilled_limits = [oid for oid in limit_order_ids if oid not in limits_filled]

                for limit_id in unfilled_limits:
                    if limit_id:
                        logger.info(f"🛡️ Conservative SL hit for {symbol}, canceling unfilled limit {limit_id}")
                        success = await cancel_order_with_retry(symbol, limit_id)
                        if success:
                            orders_cancelled.append(f"Limit order {limit_id[:8]}...")
                            logger.info(f"✅ Conservative limit order {limit_id} cancelled successfully")

                # ENHANCED: Comprehensive cleanup - fetch ALL orders for symbol to ensure nothing is missed
                logger.info(f"🔍 Performing comprehensive order cleanup for {symbol} after SL hit")
                try:
                    from clients.bybit_helpers import get_all_open_orders
                    all_orders = await get_all_open_orders()
                    symbol_orders = [o for o in all_orders if o.get('symbol') == symbol]

                    for order in symbol_orders:
                        order_id = order.get('orderId')
                        order_link_id = order.get('orderLinkId', '')

                        # Skip if already cancelled
                        if order_id in [tp_id for tp_id in tp_order_ids] or order_id in limit_order_ids:
                            continue

                        # Cancel any remaining bot orders for this symbol
                        if 'BOT' in order_link_id or order.get('reduceOnly'):
                            logger.warning(f"🧹 Found orphaned order {order_id[:8]}... for {symbol}, cancelling")
                            success = await cancel_order_with_retry(symbol, order_id)
                            if success:
                                orders_cancelled.append(f"Orphaned order {order_id[:8]}...")
                                logger.info(f"✅ Orphaned order {order_id} cancelled")

                except Exception as cleanup_error:
                    logger.error(f"Error during comprehensive cleanup: {cleanup_error}")

                # Clear orders from chat data
                chat_data[CONSERVATIVE_TP_ORDER_IDS] = []
                chat_data[LIMIT_ORDER_IDS] = []

        else:
            # FIXED: Fast approach - enhanced order cancellation logic
            if triggered_order_type == 'TP':
                # TP was hit, cancel SL order
                sl_order_id = chat_data.get(SL_ORDER_ID) or chat_data.get("sl_order_id")
                if sl_order_id:
                    logger.info(f"🎯 Fast TP hit for {symbol}, canceling SL order {sl_order_id}")
                    success = await cancel_order_with_retry(symbol, sl_order_id)
                    if success:
                        orders_cancelled.append(f"SL order {sl_order_id[:8]}...")
                        chat_data[SL_ORDER_ID] = None
                        chat_data["sl_order_id"] = None
                        logger.info(f"✅ Fast SL order {sl_order_id} cancelled successfully")

                # Clear TP order from tracking (already hit)
                chat_data["tp_order_id"] = None

            elif triggered_order_type == 'SL':
                # SL was hit, cancel TP orders
                tp_order_id = chat_data.get("tp_order_id")
                tp_order_ids = chat_data.get(TP_ORDER_IDS, [])

                # Handle single TP order
                if tp_order_id:
                    logger.info(f"🛡️ Fast SL hit for {symbol}, canceling TP order {tp_order_id}")
                    success = await cancel_order_with_retry(symbol, tp_order_id)
                    if success:
                        orders_cancelled.append(f"TP order {tp_order_id[:8]}...")
                        chat_data["tp_order_id"] = None
                        logger.info(f"✅ Fast TP order {tp_order_id} cancelled successfully")

                # Handle multiple TP orders if any
                for tp_id in tp_order_ids:
                    if tp_id:
                        logger.info(f"🛡️ Fast SL hit for {symbol}, canceling TP order {tp_id}")
                        success = await cancel_order_with_retry(symbol, tp_id)
                        if success:
                            orders_cancelled.append(f"TP order {tp_id[:8]}...")
                            logger.info(f"✅ Fast TP order {tp_id} cancelled successfully")

                # ENHANCED: Comprehensive cleanup for fast approach too
                logger.info(f"🔍 Performing comprehensive order cleanup for {symbol} after SL hit")
                try:
                    from clients.bybit_helpers import get_all_open_orders
                    all_orders = await get_all_open_orders()
                    symbol_orders = [o for o in all_orders if o.get('symbol') == symbol]

                    for order in symbol_orders:
                        order_id = order.get('orderId')
                        order_link_id = order.get('orderLinkId', '')

                        # Skip if already cancelled
                        if order_id == tp_order_id or order_id in tp_order_ids:
                            continue

                        # Cancel any remaining bot orders for this symbol
                        if 'BOT' in order_link_id or order.get('reduceOnly'):
                            logger.warning(f"🧹 Found orphaned order {order_id[:8]}... for {symbol}, cancelling")
                            success = await cancel_order_with_retry(symbol, order_id)
                            if success:
                                orders_cancelled.append(f"Orphaned order {order_id[:8]}...")
                                logger.info(f"✅ Orphaned order {order_id} cancelled")

                except Exception as cleanup_error:
                    logger.error(f"Error during comprehensive cleanup: {cleanup_error}")

                # Clear TP orders from chat data
                chat_data[TP_ORDER_IDS] = []
                chat_data["tp_order_id"] = None

        return orders_cancelled

    except Exception as e:
        logger.error(f"❌ Error canceling remaining orders: {e}", exc_info=True)
        return []

# REFINED: Enhanced P&L calculation with better accuracy
async def calculate_accurate_pnl(position_data: dict, chat_data: dict) -> Decimal:
    """
    REFINED: Calculate accurate P&L using multiple methods for reliability
    """
    try:
        pnl = Decimal("0")

        # Check if position_data is valid
        if not position_data:
            logger.warning("⚠️ No position data provided for P&L calculation")
            # Try to use last known P&L from chat data
            last_known_pnl = chat_data.get("last_known_pnl")
            if last_known_pnl:
                pnl = safe_decimal_conversion(last_known_pnl)
                logger.info(f"📊 P&L from last known (no position data): {pnl}")
                return pnl
            return Decimal("0")

        # Method 1: Calculate from entry/exit prices (most accurate for individual trades)
        entry_price = safe_decimal_conversion(position_data.get("avgPrice", "0"))
        mark_price = safe_decimal_conversion(position_data.get("markPrice", "0"))
        size = safe_decimal_conversion(position_data.get("size", "0"))
        side = position_data.get("side", chat_data.get(SIDE, ""))

        # Get approach-specific keys - conservative approach only
        approach = chat_data.get(TRADING_APPROACH, "conservative")
        size_key = f"{approach}_position_size"
        entry_key = f"{approach}_entry_price"

        # If size is 0, try to get from approach-specific chat data (position was just closed)
        if size == 0:
            size = safe_decimal_conversion(chat_data.get(size_key, "0"))
            # Fallback to general key if approach-specific not found
            if size == 0:
                size = safe_decimal_conversion(chat_data.get(LAST_KNOWN_POSITION_SIZE, "0"))

        # If entry price is 0, try to get from approach-specific chat data
        if entry_price == 0:
            entry_price = safe_decimal_conversion(chat_data.get(entry_key, "0"))
            # Fallback to general key if approach-specific not found
            if entry_price == 0:
                entry_price = safe_decimal_conversion(chat_data.get(PRIMARY_ENTRY_PRICE, "0"))

        if entry_price > 0 and mark_price > 0 and size > 0:
            if side == "Buy":
                pnl = (mark_price - entry_price) * size
            else:  # Sell/Short
                pnl = (entry_price - mark_price) * size
            logger.info(f"📊 P&L calculated from prices: Entry={entry_price}, Exit={mark_price}, Size={size}, P&L={pnl}")
            return pnl

        # Method 2: Use unrealisedPnl ONLY if we couldn't calculate from individual prices
        # NOTE: unrealisedPnl is cumulative for the entire position and may not reflect individual trade P&L
        unrealized_pnl = position_data.get("unrealisedPnl")
        if unrealized_pnl and str(unrealized_pnl) != "0":
            pnl = safe_decimal_conversion(unrealized_pnl)
            logger.warning(f"📊 P&L from unrealisedPnl (cumulative): {pnl} - May not reflect individual trade P&L")
            return pnl

        # Method 3: Use last known P&L from chat data
        last_known_pnl = chat_data.get("last_known_pnl")
        if last_known_pnl:
            pnl = safe_decimal_conversion(last_known_pnl)
            logger.info(f"📊 P&L from last known: {pnl}")
            return pnl

        logger.warning(f"⚠️ Could not calculate P&L - using 0")
        return Decimal("0")

    except Exception as e:
        logger.error(f"Error calculating accurate P&L: {e}")
        return Decimal("0")

async def update_performance_stats_on_close(ctx_app, chat_data: dict, position_data: dict,
                                          close_reason: str, pnl: Decimal = None):
    """
    REFINED: Update performance statistics with duplicate prevention and better accuracy
    FIXED: Force immediate persistence after stats update

    All positions are bot trades now
    """
    try:
        # Get bot data - CRITICAL: Use the application's bot_data directly
        bot_data = ctx_app.bot_data

        # Log the application instance for debugging
        logger.info(f"📊 Using application instance: {type(ctx_app).__name__}")
        logger.info(f"📊 Application has bot_data: {hasattr(ctx_app, 'bot_data')}")

        monitoring_mode = get_monitoring_mode(chat_data)
        is_external = False  # All positions are bot trades now

        logger.info(f"🔄 Updating performance stats ({monitoring_mode}) - Reason: {close_reason}, PnL: {pnl}")

        # REFINED: Calculate accurate P&L if not provided
        if pnl is None or pnl == 0:
            pnl = await calculate_accurate_pnl(position_data, chat_data)

        # Ensure pnl is a Decimal
        pnl = safe_decimal_conversion(pnl)

        # REFINED: Generate unique trade ID to prevent duplicates
        symbol = chat_data.get(SYMBOL, "Unknown")
        side = chat_data.get(SIDE, "Unknown")
        entry_price = safe_decimal_conversion(chat_data.get(PRIMARY_ENTRY_PRICE, "0"))
        close_time = time.time()

        trade_id = await _trade_history.generate_trade_id(
            symbol, side, entry_price, close_time, pnl
        )

        # Check if trade already processed
        if await _trade_history.is_trade_processed(trade_id):
            logger.warning(f"⚠️ Trade {trade_id} already processed, skipping duplicate stats update")
            return

        # Check if we have existing stats before initializing
        has_existing_stats = (
            STATS_TOTAL_TRADES in bot_data and bot_data.get(STATS_TOTAL_TRADES, 0) > 0
        ) or (
            STATS_TOTAL_PNL in bot_data and bot_data.get(STATS_TOTAL_PNL, Decimal("0")) != Decimal("0")
        )

        # Initialize ALL stats with proper defaults and types
        stats_defaults = {
            STATS_TOTAL_PNL: Decimal("0"),
            STATS_TOTAL_WINS: 0,
            STATS_TOTAL_LOSSES: 0,
            STATS_TOTAL_TRADES: 0,
            STATS_TP1_HITS: 0,
            STATS_SL_HITS: 0,
            STATS_OTHER_CLOSURES: 0,
            STATS_WIN_STREAK: 0,
            STATS_LOSS_STREAK: 0,
            STATS_BEST_TRADE: Decimal("0"),
            STATS_WORST_TRADE: Decimal("0"),
            # Enhanced stats for approaches
            STATS_CONSERVATIVE_TRADES: 0,
            # Fast trades stat removed
            STATS_CONSERVATIVE_TP1_CANCELLATIONS: 0,
            # REFINED: Separate stats for external positions
            "STATS_EXTERNAL_TRADES": 0,
            "STATS_EXTERNAL_PNL": Decimal("0"),
            "STATS_EXTERNAL_WINS": 0,
            "STATS_EXTERNAL_LOSSES": 0,
            # Additional stats for dashboard calculations
            'stats_total_wins_pnl': Decimal("0"),
            'stats_total_losses_pnl': Decimal("0"),
            'stats_max_drawdown': Decimal("0"),
            'stats_peak_equity': Decimal("0"),
            'stats_current_drawdown': Decimal("0"),
            'recent_trade_pnls': [],  # List of recent trade P&Ls for trend chart
            'bot_start_time': time.time()
        }

        # Special handling for STATS_LAST_RESET
        if STATS_LAST_RESET not in bot_data:
            # Only set new timestamp if we're truly initializing for the first time
            if not has_existing_stats:
                bot_data[STATS_LAST_RESET] = time.time()
                logger.info(f"First time initialization - setting STATS_LAST_RESET")
            else:
                # We have existing stats but STATS_LAST_RESET is missing - don't reset
                bot_data[STATS_LAST_RESET] = bot_data.get('bot_start_time', time.time() - 86400)  # Default to 24h ago
                logger.warning(f"Found existing stats but STATS_LAST_RESET was missing - preserving stats")

        # Initialize any missing stats
        for stat_key, default_val in stats_defaults.items():
            if stat_key not in bot_data:
                bot_data[stat_key] = default_val
                logger.info(f"Initialized missing stat {stat_key} = {default_val}")

        # Ensure existing stats are proper types
        bot_data[STATS_TOTAL_PNL] = safe_decimal_conversion(bot_data.get(STATS_TOTAL_PNL, Decimal("0")))
        bot_data[STATS_BEST_TRADE] = safe_decimal_conversion(bot_data.get(STATS_BEST_TRADE, Decimal("0")))
        bot_data[STATS_WORST_TRADE] = safe_decimal_conversion(bot_data.get(STATS_WORST_TRADE, Decimal("0")))
        bot_data["STATS_EXTERNAL_PNL"] = safe_decimal_conversion(bot_data.get("STATS_EXTERNAL_PNL", Decimal("0")))
        bot_data['stats_total_wins_pnl'] = safe_decimal_conversion(bot_data.get('stats_total_wins_pnl', Decimal("0")))
        bot_data['stats_total_losses_pnl'] = safe_decimal_conversion(bot_data.get('stats_total_losses_pnl', Decimal("0")))

        # Store trade details
        trade_details = {
            "symbol": symbol,
            "side": side,
            "entry_price": str(entry_price),
            "close_reason": close_reason,
            "pnl": str(pnl),
            "close_time": close_time,
            "monitoring_mode": monitoring_mode,
            "is_external": False,  # All positions are bot trades now
            "approach": chat_data.get(TRADING_APPROACH, "fast")
        }

        # REFINED: Separate stats tracking for external vs bot positions
        if is_external:
            # Update external position stats
            bot_data["STATS_EXTERNAL_TRADES"] = bot_data.get("STATS_EXTERNAL_TRADES", 0) + 1
            bot_data["STATS_EXTERNAL_PNL"] = bot_data["STATS_EXTERNAL_PNL"] + pnl

            if pnl > 0:
                bot_data["STATS_EXTERNAL_WINS"] = bot_data.get("STATS_EXTERNAL_WINS", 0) + 1
            elif pnl < 0:
                bot_data["STATS_EXTERNAL_LOSSES"] = bot_data.get("STATS_EXTERNAL_LOSSES", 0) + 1

            logger.info(f"📊 External Trade #{bot_data['STATS_EXTERNAL_TRADES']} recorded: {pnl}")
        else:
            # Update bot position stats
            bot_data[STATS_TOTAL_TRADES] += 1
            logger.info(f"📊 Bot Trade #{bot_data[STATS_TOTAL_TRADES]} being processed")

            # Handle approach specific stats
            approach = chat_data.get(TRADING_APPROACH, "conservative")
            if approach == "conservative":
                bot_data[STATS_CONSERVATIVE_TRADES] = bot_data.get(STATS_CONSERVATIVE_TRADES, 0) + 1
                # Check if this was a TP1 cancellation scenario
                if chat_data.get(CONSERVATIVE_TP1_HIT_BEFORE_LIMITS, False):
                    bot_data[STATS_CONSERVATIVE_TP1_CANCELLATIONS] = bot_data.get(STATS_CONSERVATIVE_TP1_CANCELLATIONS, 0) + 1
                    logger.info(f"📊 Conservative TP1 cancellation recorded")
            # Update based on close reason and PnL
            if close_reason == "TP1_HIT" or close_reason == "TP_HIT":
                bot_data[STATS_TP1_HITS] = bot_data.get(STATS_TP1_HITS, 0) + 1
                # TP hit is always a win
                bot_data[STATS_TOTAL_WINS] += 1
                bot_data[STATS_WIN_STREAK] += 1
                bot_data[STATS_LOSS_STREAK] = 0
                logger.info(f"✅ TP Hit recorded as WIN #{bot_data[STATS_TOTAL_WINS]}: +{abs(pnl)}")

            elif close_reason == "SL_HIT":
                bot_data[STATS_SL_HITS] = bot_data.get(STATS_SL_HITS, 0) + 1
                # SL hit is always a loss
                bot_data[STATS_TOTAL_LOSSES] += 1
                bot_data[STATS_LOSS_STREAK] += 1
                bot_data[STATS_WIN_STREAK] = 0
                logger.info(f"❌ SL Hit recorded as LOSS #{bot_data[STATS_TOTAL_LOSSES]}: -{abs(pnl)}")

            else:
                # Other closures (manual, etc.) - determine by P&L
                bot_data[STATS_OTHER_CLOSURES] = bot_data.get(STATS_OTHER_CLOSURES, 0) + 1
                if pnl > 0:
                    bot_data[STATS_TOTAL_WINS] += 1
                    bot_data[STATS_WIN_STREAK] += 1
                    bot_data[STATS_LOSS_STREAK] = 0
                    logger.info(f"✅ Manual close recorded as WIN #{bot_data[STATS_TOTAL_WINS]}: +{pnl}")
                elif pnl < 0:
                    bot_data[STATS_TOTAL_LOSSES] += 1
                    bot_data[STATS_LOSS_STREAK] += 1
                    bot_data[STATS_WIN_STREAK] = 0
                    logger.info(f"❌ Manual close recorded as LOSS #{bot_data[STATS_TOTAL_LOSSES]}: {pnl}")
                else:
                    logger.info(f"⚪ Breakeven close recorded: {pnl}")

            # Update PnL tracking
            bot_data[STATS_TOTAL_PNL] = bot_data[STATS_TOTAL_PNL] + pnl

            # Track wins and losses P&L separately for profit factor calculation
            if pnl > 0:
                bot_data['stats_total_wins_pnl'] = bot_data.get('stats_total_wins_pnl', Decimal("0")) + pnl
            elif pnl < 0:
                bot_data['stats_total_losses_pnl'] = bot_data.get('stats_total_losses_pnl', Decimal("0")) + pnl

            # Update best/worst trade
            if pnl > bot_data[STATS_BEST_TRADE]:
                bot_data[STATS_BEST_TRADE] = pnl
                logger.info(f"🏆 New best trade: {pnl}")
            if pnl < bot_data[STATS_WORST_TRADE]:
                bot_data[STATS_WORST_TRADE] = pnl
                logger.info(f"📉 New worst trade: {pnl}")

            # Track recent trade P&Ls for trend chart
            recent_pnls = bot_data.get('recent_trade_pnls', [])
            recent_pnls.append(float(pnl))
            # Keep only last 30 trades
            if len(recent_pnls) > 30:
                recent_pnls = recent_pnls[-30:]
            bot_data['recent_trade_pnls'] = recent_pnls
            logger.info(f"📈 Added to recent trades trend (now {len(recent_pnls)} trades)")

            # Update max drawdown tracking
            current_equity = bot_data.get(STATS_TOTAL_PNL, Decimal("0"))
            peak_equity = bot_data.get('stats_peak_equity', Decimal("0"))

            # Update peak equity if we have a new high
            if current_equity > peak_equity:
                bot_data['stats_peak_equity'] = current_equity
                peak_equity = current_equity
                logger.info(f"🏔️ New peak equity: {peak_equity}")

            # Calculate current drawdown from peak
            if peak_equity > 0:
                current_drawdown = ((peak_equity - current_equity) / peak_equity * 100)
                bot_data['stats_current_drawdown'] = current_drawdown

                # Update max drawdown if current is larger
                max_drawdown = bot_data.get('stats_max_drawdown', Decimal("0"))
                if current_drawdown > max_drawdown:
                    bot_data['stats_max_drawdown'] = current_drawdown
                    logger.info(f"📉 New max drawdown: {current_drawdown:.2f}%")

        # Mark trade as processed
        await _trade_history.mark_trade_processed(trade_id, trade_details)

        # REFINED: Validate stats consistency
        if not is_external:
            total_wins = bot_data[STATS_TOTAL_WINS]
            total_losses = bot_data[STATS_TOTAL_LOSSES]
            total_trades = bot_data[STATS_TOTAL_TRADES]

            # Basic consistency check
            if (total_wins + total_losses) > total_trades:
                logger.warning(f"⚠️ Stats inconsistency detected: Wins({total_wins}) + Losses({total_losses}) > Trades({total_trades})")
                # Auto-correct
                bot_data[STATS_TOTAL_TRADES] = total_wins + total_losses

        # Log enhanced stats summary
        if is_external:
            external_trades = bot_data.get("STATS_EXTERNAL_TRADES", 0)
            external_pnl = bot_data.get("STATS_EXTERNAL_PNL", Decimal("0"))
            external_wins = bot_data.get("STATS_EXTERNAL_WINS", 0)
            external_losses = bot_data.get("STATS_EXTERNAL_LOSSES", 0)

            logger.info(f"📊 EXTERNAL POSITION STATS:")
            logger.info(f"   Total External Trades: {external_trades}")
            logger.info(f"   External Wins: {external_wins} | Losses: {external_losses}")
            logger.info(f"   External Total PnL: {external_pnl}")
        else:
            total_pnl = bot_data.get(STATS_TOTAL_PNL, Decimal("0"))
            win_rate = (bot_data[STATS_TOTAL_WINS] / (bot_data[STATS_TOTAL_WINS] + bot_data[STATS_TOTAL_LOSSES]) * 100) if (bot_data[STATS_TOTAL_WINS] + bot_data[STATS_TOTAL_LOSSES]) > 0 else 0
            conservative_trades = bot_data.get(STATS_CONSERVATIVE_TRADES, 0)
            # Fast approach removed - all trades are conservative
            conservative_cancellations = bot_data.get(STATS_CONSERVATIVE_TP1_CANCELLATIONS, 0)

            logger.info(f"📊 BOT PERFORMANCE STATS:")
            logger.info(f"   Total Bot Trades: {bot_data[STATS_TOTAL_TRADES]}")
            logger.info(f"   Wins: {bot_data[STATS_TOTAL_WINS]} | Losses: {bot_data[STATS_TOTAL_LOSSES]}")
            logger.info(f"   Win Rate: {win_rate:.1f}%")
            logger.info(f"   Total PnL: {total_pnl}")
            logger.info(f"   Conservative Trades: {conservative_trades}")
            # Fast trades removed - all trades are conservative now
            logger.info(f"   TP1 Cancellations: {conservative_cancellations}")

        # FIXED: Force immediate persistence with verification
        logger.info(f"🔄 FORCING IMMEDIATE PERSISTENCE...")

        # Log current stats before persistence
        logger.info(f"📊 STATS BEFORE PERSISTENCE:")
        logger.info(f"   Total Trades: {bot_data.get(STATS_TOTAL_TRADES, 0)}")
        logger.info(f"   Total Wins: {bot_data.get(STATS_TOTAL_WINS, 0)}")
        logger.info(f"   Total Losses: {bot_data.get(STATS_TOTAL_LOSSES, 0)}")
        logger.info(f"   Total P&L: {bot_data.get(STATS_TOTAL_PNL, 0)}")
        logger.info(f"   Wins P&L: {bot_data.get('stats_total_wins_pnl', 0)}")
        logger.info(f"   Losses P&L: {bot_data.get('stats_total_losses_pnl', 0)}")

        try:
            # Check bot_data reference
            logger.info(f"📊 Bot data object ID: {id(bot_data)}")
            logger.info(f"📊 ctx_app bot_data ID: {id(ctx_app.bot_data)}")

            # Ensure we're modifying the right bot_data
            if id(bot_data) != id(ctx_app.bot_data):
                logger.warning(f"⚠️ Bot data mismatch! Using ctx_app.bot_data directly")
                # Copy all stats to ctx_app.bot_data
                for key in [STATS_TOTAL_TRADES, STATS_TOTAL_WINS, STATS_TOTAL_LOSSES,
                           STATS_TOTAL_PNL, 'stats_total_wins_pnl', 'stats_total_losses_pnl']:
                    ctx_app.bot_data[key] = bot_data.get(key)

            # Method 1: Direct persistence call
            await optimize_persistence_update(ctx_app)
            logger.info(f"✅ Persistence update 1 completed")

            # Method 2: Force a second update after a tiny delay
            await asyncio.sleep(0.1)
            await optimize_persistence_update(ctx_app, force=True)
            logger.info(f"✅ Persistence update 2 completed")

            # Method 3: Mark bot data as dirty to force update
            if hasattr(ctx_app, '_bot_data_dirty'):
                ctx_app._bot_data_dirty = True
                await asyncio.sleep(0.1)
                await optimize_persistence_update(ctx_app, force=True)
                logger.info(f"✅ Persistence update 3 completed (dirty flag)")

            # Verify persistence by checking bot_data again
            logger.info(f"📊 STATS AFTER PERSISTENCE:")
            logger.info(f"   Total Trades: {ctx_app.bot_data.get(STATS_TOTAL_TRADES, 0)}")
            logger.info(f"   Total Wins: {ctx_app.bot_data.get(STATS_TOTAL_WINS, 0)}")
            logger.info(f"   Total Losses: {ctx_app.bot_data.get(STATS_TOTAL_LOSSES, 0)}")
            logger.info(f"   Total P&L: {ctx_app.bot_data.get(STATS_TOTAL_PNL, 0)}")

            logger.info(f"✅ Performance stats FORCE PERSISTED successfully (Trade ID: {trade_id})")

            # Backup stats after successful update
            try:
                from utils.stats_backup import backup_stats
                await backup_stats(ctx_app.bot_data)
                logger.info(f"📊 Stats backed up after trade close")
            except Exception as backup_error:
                logger.warning(f"Could not backup stats: {backup_error}")

        except Exception as e:
            logger.error(f"❌ Error force persisting stats: {e}", exc_info=True)
            # Try one more time with a longer delay
            try:
                await asyncio.sleep(1)
                await optimize_persistence_update(ctx_app, force=True)
                logger.info(f"✅ Persistence update 4 completed (after delay)")
            except Exception as e2:
                logger.error(f"❌ Final persistence attempt failed: {e2}")

    except Exception as e:
        logger.error(f"❌ Error updating performance stats: {e}", exc_info=True)

async def start_position_monitoring(ctx_app, chat_id: int, chat_data: dict):
    """
    Start monitoring a position with conservative approach support
    """
    monitoring_mode = get_monitoring_mode(chat_data)
    logger.info(f"🔄 Starting {monitoring_mode} position monitoring for chat {chat_id}")

    # Set position start time for monitoring
    chat_data["position_start_time"] = time.time()

    # Validate required data
    symbol = chat_data.get(SYMBOL)
    if not symbol:
        logger.error(f"❌ No symbol found for monitoring in chat {chat_id}")
        return

    approach = chat_data.get(TRADING_APPROACH, "conservative")

    logger.info(f"📊 Monitoring: {approach} approach, Mode: {monitoring_mode}")

    # Check if monitor is already running for this approach
    task_status = await get_monitor_task_status(chat_id, symbol, approach)
    if task_status.get("running", False):
        logger.info(f"⚠️ {monitoring_mode} monitor already running for {symbol} ({approach}) in chat {chat_id}")
        return

    # Store monitoring info WITHOUT the task object (to prevent pickle errors)
    task_info = {
        "chat_id": chat_id,
        "symbol": symbol,
        "approach": approach,
        "active": True,
        "started_at": time.time(),
        "monitoring_mode": monitoring_mode
    }

    if ACTIVE_MONITOR_TASK not in chat_data:
        chat_data[ACTIVE_MONITOR_TASK] = {}

    chat_data[ACTIVE_MONITOR_TASK] = task_info

    # FIX: Store conservative order IDs in monitor data for persistence
    # This ensures alerts work after bot restart for all conservative positions
    if ctx_app and hasattr(ctx_app, 'bot_data'):
        try:
            bot_data = ctx_app.bot_data
            chat_data_all = bot_data.get('chat_data', {})

            # Get or create chat data storage
            if chat_id not in chat_data_all:
                chat_data_all[chat_id] = {}
            stored_chat_data = chat_data_all[chat_id]

            # Get or create active_monitor_task_data_v2
            if 'active_monitor_task_data_v2' not in stored_chat_data:
                stored_chat_data['active_monitor_task_data_v2'] = {}

            # Create monitor key
            monitor_key = f"{chat_id}_{symbol}_{approach}"

            # Get or create monitor data
            monitor_data = stored_chat_data['active_monitor_task_data_v2'].get(monitor_key, {})
            monitor_data.update({
                'symbol': symbol,
                'side': chat_data.get(SIDE),
                'approach': approach,
                '_chat_id': chat_id
            })

            # Store conservative order IDs if this is a conservative position
            if approach == "conservative":
                # Transfer limit order IDs
                limit_ids = chat_data.get(LIMIT_ORDER_IDS, [])
                if limit_ids:
                    monitor_data['conservative_limit_order_ids'] = limit_ids
                    logger.info(f"✅ Stored {len(limit_ids)} limit order IDs for future persistence")

                # Transfer TP order IDs
                tp_ids = chat_data.get(CONSERVATIVE_TP_ORDER_IDS, [])
                if tp_ids:
                    monitor_data['conservative_tp_order_ids'] = tp_ids
                    logger.info(f"✅ Stored {len(tp_ids)} TP order IDs for future persistence")

                # Transfer SL order ID
                sl_id = chat_data.get(CONSERVATIVE_SL_ORDER_ID)
                if sl_id:
                    monitor_data['conservative_sl_order_id'] = sl_id
                    logger.info(f"✅ Stored SL order ID for future persistence")

            # Store the updated monitor data
            stored_chat_data['active_monitor_task_data_v2'][monitor_key] = monitor_data
            chat_data_all[chat_id] = stored_chat_data
            bot_data['chat_data'] = chat_data_all

            logger.info(f"✅ Conservative order IDs stored in active_monitor_task_data_v2 for {symbol}")
        except Exception as e:
            logger.error(f"Error storing conservative order IDs: {e}")

    # Create enhanced monitoring task with proper metadata
    metadata = {
        "symbol": symbol,
        "approach": approach,
        "monitoring_mode": monitoring_mode
    }

    monitor_task = asyncio.create_task(monitor_position_loop_enhanced(ctx_app, chat_id, chat_data))

    # Register task in global registry with metadata
    await register_monitor_task(chat_id, symbol, monitor_task, metadata)

    # Also store in bot_data for dashboard access
    if ctx_app and hasattr(ctx_app, 'bot_data'):
        bot_data = ctx_app.bot_data
        if 'monitor_tasks' not in bot_data:
            bot_data['monitor_tasks'] = {}

        # Store by approach type for easy counting
        monitor_key = f"{chat_id}_{symbol}_{approach}"

        # Validation: Check for existing monitor with same key
        if monitor_key in bot_data['monitor_tasks']:
            existing_monitor = bot_data['monitor_tasks'][monitor_key]
            if existing_monitor.get('active', False):
                logger.warning(f"⚠️ Monitor already exists for {monitor_key}. Updating instead of creating duplicate.")
                # Update the existing monitor with new information
                existing_monitor.update({
                    'monitoring_mode': monitoring_mode,
                    'updated_at': time.time(),
                    'active': True
                })
                logger.info(f"📊 Updated existing monitor: {approach} approach for {symbol}")
            else:
                # Reactivate inactive monitor
                existing_monitor.update({
                    'monitoring_mode': monitoring_mode,
                    'restarted_at': time.time(),
                    'active': True
                })
                logger.info(f"📊 Reactivated monitor: {approach} approach for {symbol}")
        else:
            # Create new monitor
            bot_data['monitor_tasks'][monitor_key] = {
                'chat_id': chat_id,
                'symbol': symbol,
                'approach': approach,
                'monitoring_mode': monitoring_mode,
                'started_at': time.time(),
                'active': True
            }
            logger.info(f"📊 Created new monitor: {approach} approach for {symbol}")

        # Log monitor separation validation
        same_symbol_monitors = [k for k in bot_data['monitor_tasks'].keys()
                              if k.startswith(f"{chat_id}_{symbol}_")]
        if len(same_symbol_monitors) > 1:
            approaches = [bot_data['monitor_tasks'][k].get('approach') for k in same_symbol_monitors]
            logger.info(f"✅ Monitor separation validated: {symbol} has {len(same_symbol_monitors)} monitors with approaches: {approaches}")

    logger.info(f"✅ {monitoring_mode} position monitoring started for {symbol} in chat {chat_id}")

async def start_mirror_position_monitoring(ctx_app, chat_id: int, chat_data: dict):
    """
    Start monitoring a mirror account position
    """
    if not is_mirror_trading_enabled():
        logger.info(f"Mirror trading not enabled, skipping mirror monitoring")
        return

    monitoring_mode = get_monitoring_mode(chat_data)
    logger.info(f"🔄 Starting MIRROR {monitoring_mode} position monitoring for chat {chat_id}")

    # Set position start time for monitoring (if not already set)
    if "position_start_time" not in chat_data:
        chat_data["position_start_time"] = time.time()

    # Validate required data
    symbol = chat_data.get(SYMBOL)
    if not symbol:
        logger.error(f"❌ No symbol found for mirror monitoring in chat {chat_id}")
        return

    approach = chat_data.get(TRADING_APPROACH, "conservative")

    logger.info(f"📊 Mirror Monitoring: {approach} approach, Mode: {monitoring_mode}")

    # Check if mirror monitor is already running for this approach
    task_status = await get_monitor_task_status(chat_id, symbol, approach, ACCOUNT_TYPE_MIRROR)
    if task_status.get("running", False):
        logger.info(f"⚠️ MIRROR {monitoring_mode} monitor already running for {symbol} ({approach}) in chat {chat_id}")
        return

    # Create a copy of chat_data for mirror monitoring to avoid interference
    mirror_chat_data = chat_data.copy()

    # Store mirror monitoring info
    task_info = {
        "chat_id": chat_id,
        "symbol": symbol,
        "approach": approach,
        "account_type": ACCOUNT_TYPE_MIRROR,
        "active": True,
        "started_at": time.time(),
        "monitoring_mode": f"MIRROR-{monitoring_mode}"
    }

    if MIRROR_ACTIVE_MONITOR_TASK not in mirror_chat_data:
        mirror_chat_data[MIRROR_ACTIVE_MONITOR_TASK] = {}

    mirror_chat_data[MIRROR_ACTIVE_MONITOR_TASK] = task_info

    # Create mirror monitoring task with proper metadata
    metadata = {
        "symbol": symbol,
        "approach": approach,
        "monitoring_mode": f"MIRROR-{monitoring_mode}",
        "account_type": ACCOUNT_TYPE_MIRROR
    }

    # Create mirror monitoring task
    monitor_task = asyncio.create_task(monitor_mirror_position_loop_enhanced(ctx_app, chat_id, mirror_chat_data))

    # Register task in global registry with metadata
    await register_monitor_task(chat_id, symbol, monitor_task, metadata)

    # Also store in bot_data for dashboard access
    if ctx_app and hasattr(ctx_app, 'bot_data'):
        bot_data = ctx_app.bot_data
        if 'monitor_tasks' not in bot_data:
            bot_data['monitor_tasks'] = {}

        # Store by approach type and account for easy counting
        monitor_key = f"{chat_id}_{symbol}_{approach}_{ACCOUNT_TYPE_MIRROR}"

        # Validation: Check for existing mirror monitor with same key
        if monitor_key in bot_data['monitor_tasks']:
            existing_monitor = bot_data['monitor_tasks'][monitor_key]
            if existing_monitor.get('active', False):
                logger.warning(f"⚠️ MIRROR monitor already exists for {monitor_key}. Updating instead of creating duplicate.")
                # Update the existing monitor
                existing_monitor.update({
                    'monitoring_mode': f"MIRROR-{monitoring_mode}",
                    'updated_at': time.time(),
                    'active': True
                })
                logger.info(f"📊 Updated existing MIRROR monitor: {approach} approach for {symbol}")
            else:
                # Reactivate inactive mirror monitor
                existing_monitor.update({
                    'monitoring_mode': f"MIRROR-{monitoring_mode}",
                    'restarted_at': time.time(),
                    'active': True
                })
                logger.info(f"📊 Reactivated MIRROR monitor: {approach} approach for {symbol}")
        else:
            # Create new mirror monitor
            bot_data['monitor_tasks'][monitor_key] = {
                'chat_id': chat_id,
                'symbol': symbol,
                'approach': approach,
                'account_type': ACCOUNT_TYPE_MIRROR,
                'monitoring_mode': f"MIRROR-{monitoring_mode}",
                'started_at': time.time(),
                'active': True
            }
            logger.info(f"📊 Created new MIRROR monitor: {approach} approach for {symbol}")

    logger.info(f"✅ MIRROR {monitoring_mode} position monitoring started for {symbol} in chat {chat_id}")

async def monitor_position_loop_enhanced(ctx_app, chat_id: int, chat_data: dict):
    """
    ENHANCED monitoring loop with conservative approach support and FIXED fast approach TP/SL logic
    FIXED: Force immediate persistence after stats update
    ADDED: Trade execution alerts
    """
    symbol = chat_data.get(SYMBOL)
    position_idx = chat_data.get(POSITION_IDX, 0)
    approach = chat_data.get(TRADING_APPROACH, "conservative")
    monitoring_mode = get_monitoring_mode(chat_data)

    # Store chat_id in chat_data for easy access in alert functions
    chat_data['_chat_id'] = chat_id

    if not symbol:
        logger.error(f"❌ No symbol found for monitoring in chat {chat_id}")
        return

    logger.info(f"🔄 Starting {monitoring_mode} monitoring loop for {symbol} in chat {chat_id}")

    # Monitoring state with memory management
    tp1_hit = False
    # Removed breakeven functionality
    position_closed = False
    last_position_size = None
    last_position_data = None
    last_known_pnl = Decimal("0")
    monitoring_cycles = 0
    position_history = []  # Limited size history
    max_history_size = 10  # Prevent memory growth

    # Circuit breaker for error loops
    consecutive_errors = 0
    max_consecutive_errors = 5
    error_cooldown_until = 0

    # Conservative approach specific tracking (only for FULL monitoring)
    conservative_tp1_cancelled = False

    # Fast approach removed - only conservative approach tracking

    # Get stored order IDs
    if approach == "conservative":
        limit_order_ids = chat_data.get(LIMIT_ORDER_IDS, [])
        tp_order_ids = chat_data.get(CONSERVATIVE_TP_ORDER_IDS, [])
        sl_order_id = chat_data.get(CONSERVATIVE_SL_ORDER_ID)
        logger.info(f"📋 Conservative monitoring - Limits: {len(limit_order_ids)}, TPs: {len(tp_order_ids)}, SL: {bool(sl_order_id)}")
    else:
        tp_order_id = chat_data.get("tp_order_id")
        sl_order_id = chat_data.get(SL_ORDER_ID) or chat_data.get("sl_order_id")
        logger.info(f"📋 Fast monitoring - TP: {tp_order_id}, SL: {sl_order_id}")

    # Get initial position to establish baseline
    try:
        positions = await get_position_info(symbol)
        initial_position = None
        if positions:
            # Find the position with non-zero size
            for pos in positions:
                if float(pos.get("size", 0)) > 0:
                    initial_position = pos
                    break

        if initial_position:
            last_position_size = safe_decimal_conversion(initial_position.get("size", "0"))
            last_position_data = initial_position.copy()
            # Store both general and approach-specific position size
            chat_data[LAST_KNOWN_POSITION_SIZE] = last_position_size
            approach = chat_data.get(TRADING_APPROACH, "conservative")
            # Store approach-specific position size
            chat_data[f"{approach}_position_size"] = last_position_size
            logger.info(f"📊 Initial position: {symbol} - {initial_position.get('side')} {last_position_size}")
        else:
            logger.warning(f"⚠️ No initial position found for {symbol}")
    except Exception as e:
        logger.error(f"❌ Error getting initial position for {symbol}: {e}")

    # Add random stagger to prevent all monitors checking at once
    import random
    stagger_delay = random.uniform(0, 3)  # 0-3 second random delay
    await asyncio.sleep(stagger_delay)
    logger.debug(f"Monitor for {symbol} starting with {stagger_delay:.1f}s stagger")

    try:
        while True:
            try:
                monitoring_cycles += 1

                # Circuit breaker check
                if consecutive_errors >= max_consecutive_errors:
                    if time.time() < error_cooldown_until:
                        # Still in cooldown
                        await asyncio.sleep(30)  # Wait 30 seconds before retry
                        continue
                    else:
                        # Reset after cooldown
                        consecutive_errors = 0
                        logger.info(f"🔄 Resetting error counter for {symbol} monitor after cooldown")

                # MEMORY MANAGEMENT: Periodic cleanup every 100 cycles
                if monitoring_cycles % 100 == 0:
                    gc.collect()  # Force garbage collection
                    logger.debug(f"Memory cleanup performed for {symbol} monitor")

                # Check if monitoring should stop
                if not chat_data.get(ACTIVE_MONITOR_TASK, {}).get("active"):
                    logger.info(f"🛑 {monitoring_mode} monitoring stopped for {symbol} (deactivated)")
                    # Mark monitor as inactive in execution summary
                    if EXECUTION_SUMMARY_AVAILABLE:
                        try:
                            monitor_id = f"{chat_id}_{symbol}_{approach}"
                            await execution_summary.update_monitor_health(monitor_id, {
                                'symbol': symbol,
                                'approach': approach,
                                'account': 'primary',
                                'status': 'inactive',
                                'last_check': time.time()
                            })
                        except Exception as e:
                            logger.debug(f"Failed to mark monitor inactive: {e}")
                    break

                # PERFORMANCE: Smart position monitoring with change detection
                positions = await get_position_info(symbol)
                position = None
                if positions:
                    # Find the position with non-zero size
                    for pos in positions:
                        if float(pos.get("size", 0)) > 0:
                            position = pos
                            break

                if not position:
                    # Check if we had a position before (manual close detection)
                    if last_position_size and last_position_size > 0:
                        logger.info(f"📊 Position appears to be manually closed for {symbol}")
                        # Create a synthetic position data for closure handling
                        position = {
                            "size": "0",
                            "markPrice": str(last_position_data.get("markPrice", "0")) if last_position_data else "0",
                            "side": last_position_data.get("side", "") if last_position_data else "",
                            "avgPrice": str(last_position_data.get("avgPrice", "0")) if last_position_data else "0",
                            "unrealisedPnl": "0",
                            "cumRealisedPnl": str(last_known_pnl) if last_known_pnl else "0"
                        }
                        # Process this as a position closure
                    else:
                        logger.warning(f"⚠️ No position data for {symbol} (cycle {monitoring_cycles})")
                        await asyncio.sleep(5)
                        continue

                # PERFORMANCE: Cache position data to detect changes and reduce processing
                current_size = safe_decimal_conversion(position.get("size", "0"))
                current_price = safe_decimal_conversion(position.get("markPrice", "0"))
                position_key = f"{symbol}_{current_size}_{current_price}"

                # Track position size changes
                size_change = position_size_tracker.track_position_change(symbol, current_size)
                if size_change and size_change != 0:
                    # Position size changed - validate orders
                    validation_result = await position_size_tracker.validate_order_quantities(symbol)
                    if not validation_result['valid']:
                        logger.warning(f"⚠️ Order quantities need adjustment after position size change for {symbol}")
                        # Could trigger rebalancing here if needed

                last_position_key = chat_data.get("_last_position_key")
                if last_position_key == position_key and monitoring_cycles % 5 != 0:
                    # Position unchanged, skip detailed processing except every 5th cycle
                    await asyncio.sleep(POSITION_MONITOR_INTERVAL)
                    continue

                chat_data["_last_position_key"] = position_key

                # Use safe decimal conversion for ALL API data
                current_size = safe_decimal_conversion(position.get("size", "0"))
                current_price = safe_decimal_conversion(position.get("markPrice", "0"))
                side = position.get("side")
                entry_price = safe_decimal_conversion(position.get("avgPrice", "0"))
                unrealized_pnl = safe_decimal_conversion(position.get("unrealisedPnl", "0"))
                cum_realised_pnl = safe_decimal_conversion(position.get("cumRealisedPnl", "0"))

                # Track position history with size limit
                position_history.append({
                    "time": time.time(),
                    "size": current_size,
                    "unrealisedPnl": unrealized_pnl,
                    "cumRealisedPnl": cum_realised_pnl,
                    "markPrice": current_price
                })

                # Keep only last N entries to prevent memory growth
                if len(position_history) > max_history_size:
                    position_history.pop(0)

                # Update last known P&L if position is open
                if current_size > 0 and unrealized_pnl != 0:
                    last_known_pnl = unrealized_pnl
                    chat_data["last_known_pnl"] = str(last_known_pnl)  # Store for accurate calculation

                # Report monitor health to execution summary
                if EXECUTION_SUMMARY_AVAILABLE and monitoring_cycles % 10 == 0:  # Report every 10 cycles
                    try:
                        monitor_id = f"{chat_id}_{symbol}_{approach}"
                        health_data = {
                            'symbol': symbol,
                            'approach': approach,
                            'account': 'primary',
                            'status': 'active',
                            'last_check': time.time(),
                            'errors': 0,
                            'restarts': 0,
                            'position_size': float(current_size),
                            'unrealized_pnl': float(unrealized_pnl),
                            'monitoring_mode': monitoring_mode,
                            'cycles': monitoring_cycles
                        }
                        await execution_summary.update_monitor_health(monitor_id, health_data)
                    except Exception as e:
                        logger.debug(f"Failed to report monitor health: {e}")

                # ENHANCED: Conservative/GGShot approach monitoring with dual TP1 logic
                if ((approach == "conservative" or approach == "ggshot") and
                    current_size > 0 and
                    not conservative_tp1_cancelled):

                    logger.debug(f"🔍 Checking {approach} fills for {symbol} - current_size: {current_size}, tp1_cancelled: {conservative_tp1_cancelled}")

                    # Check for limit order fills first
                    newly_filled = await check_conservative_limit_fills(chat_data, symbol, ctx_app)
                    if newly_filled:
                        logger.info(f"✅ {approach.capitalize()} limit orders filled: {len(newly_filled)}")
                    else:
                        # Log why no fills detected
                        limit_order_ids = chat_data.get(LIMIT_ORDER_IDS, [])
                        if not limit_order_ids:
                            logger.warning(f"⚠️ No LIMIT_ORDER_IDS found for {symbol} conservative monitor - alerts won't work!")
                        else:
                            logger.debug(f"No new limit fills for {symbol} (checking {len(limit_order_ids)} orders)")

                    # SCENARIO 1: TP1 hits before ANY limits are filled (original logic)
                    # For GGShot: Market order is pre-filled, so check if NO additional limits filled
                    tp1_hit_before_any_limits = await check_conservative_tp1_hit(chat_data, symbol, current_price, side)

                    if tp1_hit_before_any_limits and not chat_data.get(CONSERVATIVE_ORDERS_CANCELLED, False):
                        logger.info(f"🚨 {approach.capitalize()} TP1 hit before ANY limits filled for {symbol} - cancelling ALL orders")

                        # Store position data BEFORE any actions
                        position_before_tp1 = position.copy()

                        cancelled_orders = await cancel_conservative_orders_on_tp1_hit(chat_data, symbol, ctx_app)
                        conservative_tp1_cancelled = True

                        if cancelled_orders:
                            logger.info(f"🚨 {approach.capitalize()} full cancellation completed: {', '.join(cancelled_orders)}")

                        # CRITICAL: Verify TP1 actually executed and closed 85% of position
                        await asyncio.sleep(2.0)  # Wait for TP1 order to execute

                        # Get updated position after TP1 should have executed
                        positions_after = await get_position_info(symbol)
                        position_after_tp1 = None
                        if positions_after:
                            position_after_tp1 = next((p for p in positions_after if float(p.get("size", 0)) > 0),
                                                    {"size": "0"})
                        else:
                            position_after_tp1 = {"size": "0"}

                        # Verify TP1 execution (85% for conservative)
                        from utils.tp_execution_verifier import tp_execution_verifier

                        verification_result = await tp_execution_verifier.verify_tp_execution(
                            symbol=symbol,
                            tp_number=1,
                            expected_percentage=0.85,  # TP1 should close 85%
                            position_before=position_before_tp1,
                            position_after=position_after_tp1,
                            chat_data=chat_data
                        )

                        if not verification_result.get("verified"):
                            logger.error(f"❌ TP1 execution verification FAILED for {symbol}!")
                            # Send alert about verification failure
                            if ctx_app and hasattr(ctx_app, 'bot'):
                                chat_id = chat_data.get('chat_id') or chat_data.get('_chat_id')
                                if chat_id:
                                    error_msg = (
                                        f"⚠️ <b>TP1 EXECUTION WARNING</b>\n"
                                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                        f"Symbol: {symbol}\n"
                                        f"Expected to close: 85%\n"
                                        f"Actually closed: {verification_result.get('actual_percentage', 0)*100:.1f}%\n"
                                        f"Position before: {verification_result.get('size_before', 0):.4f}\n"
                                        f"Position after: {verification_result.get('size_after', 0):.4f}\n"
                                    )

                                    if verification_result.get("corrective_action", {}).get("action") == "corrective_order_placed":
                                        error_msg += (
                                            f"\n✅ <b>Corrective action taken:</b>\n"
                                            f"Placed market order to close additional "
                                            f"{verification_result['corrective_action']['qty']:.4f} units"
                                        )

                                    try:
                                        await ctx_app.bot.send_message(
                                            chat_id=chat_id,
                                            text=error_msg,
                                            parse_mode="HTML"
                                        )
                                    except Exception as e:
                                        logger.error(f"Failed to send TP1 verification warning: {e}")
                        else:
                            logger.info(f"✅ TP1 execution verified: closed {verification_result.get('actual_percentage', 0)*100:.1f}% of position")

                        # Mark TP1 as hit in tracking
                        if "conservative_tps_hit" not in chat_data:
                            chat_data["conservative_tps_hit"] = []
                        if "TP1" not in chat_data["conservative_tps_hit"]:
                            chat_data["conservative_tps_hit"].append("TP1")
                            logger.info(f"📝 Marked TP1 as hit for {symbol}")

                        # Update position size based on actual execution
                        actual_size_after = safe_decimal_conversion(position_after_tp1.get("size", "0"))
                        chat_data[LAST_KNOWN_POSITION_SIZE] = actual_size_after
                        # Store approach-specific position size
                        chat_data[f"{approach}_position_size"] = actual_size_after

                        # Rebalance SL quantity after TP1 hit (no price change)
                        sl_movement_info = {}
                        logger.info(f"🔄 Triggering SL quantity rebalance after TP1 hit for {symbol}")

                        # Trigger SL quantity rebalancing after TP1
                        try:
                            from execution.conservative_rebalancer import rebalance_sl_quantity_after_tp1

                            sl_order_id = chat_data.get(SL_ORDER_ID) or chat_data.get("sl_order_id")
                            if sl_order_id:
                                sl_rebalance_result = await rebalance_sl_quantity_after_tp1(
                                    chat_data=chat_data,
                                    symbol=symbol,
                                    sl_order_id=sl_order_id
                                )

                                if sl_rebalance_result.get("success"):
                                    logger.info(f"✅ SL quantity rebalanced after TP1 hit - new quantity: {sl_rebalance_result.get('new_quantity')}")
                                else:
                                    logger.warning(f"⚠️ SL quantity rebalance failed: {sl_rebalance_result.get('error', 'Unknown error')}")
                            else:
                                logger.warning(f"⚠️ No SL order ID found to rebalance for {symbol}")
                        except Exception as e:
                            logger.error(f"❌ Error rebalancing SL quantity: {e}")
                    elif tp1_hit_before_any_limits and chat_data.get(CONSERVATIVE_ORDERS_CANCELLED, False):
                        logger.info(f"✅ {symbol} TP1 cancellation already processed, skipping repeated attempts")

                    # SCENARIO 2: TP1 hits AFTER some limits are filled (new logic)
                    elif not conservative_tp1_cancelled:
                        tp1_hit_with_fills = await check_conservative_tp1_hit_with_fills(chat_data, symbol, current_price, side)

                        if tp1_hit_with_fills:
                            logger.info(f"🎯 {approach.capitalize()} TP1 hit WITH some fills for {symbol} - cancelling remaining limits only")

                            # VALIDATION: Check TP1 order before it executes
                            try:
                                # Get TP1 order details
                                tp_orders = await get_open_orders(symbol)
                                tp1_order = None
                                for order in tp_orders:
                                    if 'TP1' in order.get('orderLinkId', ''):
                                        tp1_order = order
                                        break

                                if tp1_order:
                                    # Validate TP1 order quantity
                                    is_valid, correction = await order_execution_guard.validate_before_execution(
                                        symbol=symbol,
                                        order=tp1_order,
                                        expected_percentage=0.85
                                    )

                                    if not is_valid and correction:
                                        logger.warning(f"⚠️ TP1 order needs correction before execution")
                                        # Attempt to correct the order
                                        qty_step = safe_decimal_conversion(chat_data.get(INSTRUMENT_QTY_STEP, "0.001"))
                                        corrected = await order_execution_guard.correct_order_quantity(
                                            symbol=symbol,
                                            correction=correction,
                                            qty_step=qty_step
                                        )
                                        if corrected:
                                            logger.info(f"✅ TP1 order corrected successfully")
                                        else:
                                            logger.error(f"❌ Failed to correct TP1 order")
                            except Exception as e:
                                logger.error(f"Error validating TP1 order: {e}")

                            # Store position data BEFORE any actions
                            position_before_tp1 = position.copy()

                            cancelled_limits = await cancel_remaining_conservative_limits_only(chat_data, symbol, ctx_app)

                            if cancelled_limits:
                                logger.info(f"🎯 {approach.capitalize()} partial cancellation completed: {', '.join(cancelled_limits)}")
                                logger.info(f"✅ TP2, TP3, TP4 remain ACTIVE for the life of the trade")

                            # CRITICAL: Verify TP1 actually executed and closed 85% of position
                            await asyncio.sleep(2.0)  # Wait for TP1 order to execute

                            # Get updated position after TP1 should have executed
                            positions_after = await get_position_info(symbol)
                            position_after_tp1 = None
                            if positions_after:
                                position_after_tp1 = next((p for p in positions_after if float(p.get("size", 0)) > 0),
                                                        {"size": "0"})
                            else:
                                position_after_tp1 = {"size": "0"}

                            # Verify TP1 execution (85% for conservative)
                            from utils.tp_execution_verifier import tp_execution_verifier

                            verification_result = await tp_execution_verifier.verify_tp_execution(
                                symbol=symbol,
                                tp_number=1,
                                expected_percentage=0.85,  # TP1 should close 85%
                                position_before=position_before_tp1,
                                position_after=position_after_tp1,
                                chat_data=chat_data
                            )

                            if not verification_result.get("verified"):
                                logger.error(f"❌ TP1 execution verification FAILED for {symbol} (with fills)!")
                                # Send alert about verification failure
                                if ctx_app and hasattr(ctx_app, 'bot'):
                                    chat_id = chat_data.get('chat_id') or chat_data.get('_chat_id')
                                    if chat_id:
                                        error_msg = (
                                            f"⚠️ <b>TP1 EXECUTION WARNING</b>\n"
                                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                            f"Symbol: {symbol}\n"
                                            f"Expected to close: 85%\n"
                                            f"Actually closed: {verification_result.get('actual_percentage', 0)*100:.1f}%\n"
                                            f"Position before: {verification_result.get('size_before', 0):.4f}\n"
                                            f"Position after: {verification_result.get('size_after', 0):.4f}\n"
                                        )

                                        if verification_result.get("corrective_action", {}).get("action") == "corrective_order_placed":
                                            error_msg += (
                                                f"\n✅ <b>Corrective action taken:</b>\n"
                                                f"Placed market order to close additional "
                                                f"{verification_result['corrective_action']['qty']:.4f} units"
                                            )

                                        try:
                                            await ctx_app.bot.send_message(
                                                chat_id=chat_id,
                                                text=error_msg,
                                                parse_mode="HTML"
                                            )
                                        except Exception as e:
                                            logger.error(f"Failed to send TP1 verification warning: {e}")
                            else:
                                logger.info(f"✅ TP1 execution verified: closed {verification_result.get('actual_percentage', 0)*100:.1f}% of position")

                            # Mark TP1 as hit in tracking
                            if "conservative_tps_hit" not in chat_data:
                                chat_data["conservative_tps_hit"] = []
                            if "TP1" not in chat_data["conservative_tps_hit"]:
                                chat_data["conservative_tps_hit"].append("TP1")
                                logger.info(f"📝 Marked TP1 as hit for {symbol}")

                            # Update position size based on actual execution
                            actual_size_after = safe_decimal_conversion(position_after_tp1.get("size", "0"))
                            chat_data[LAST_KNOWN_POSITION_SIZE] = actual_size_after
                            if approach != "fast":
                                chat_data[f"{approach}_position_size"] = actual_size_after

                            # Trigger Conservative rebalancing after TP1 verification
                            try:
                                from execution.conservative_rebalancer import rebalance_conservative_on_tp_hit

                                logger.info(f"🔄 Triggering Conservative rebalance for {symbol} after TP1 hit")
                                rebalance_result = await rebalance_conservative_on_tp_hit(
                                    chat_data=chat_data,
                                    symbol=symbol,
                                    tp_number=1,
                                    ctx_app=ctx_app
                                )

                                if rebalance_result.get("success"):
                                    logger.info(f"✅ Conservative rebalance completed after TP1")
                                else:
                                    logger.error(f"❌ Conservative rebalance failed: {rebalance_result.get('error')}")

                            except Exception as e:
                                logger.error(f"Error triggering Conservative rebalance: {e}")

                            # Rebalance SL quantity after TP1 hit (no price change)
                            sl_movement_info = {}
                            logger.info(f"🔄 Triggering SL quantity rebalance after TP1 hit for {symbol}")

                            # Trigger SL quantity rebalancing after TP1
                            try:
                                from execution.conservative_rebalancer import rebalance_sl_quantity_after_tp1

                                sl_order_id = chat_data.get(SL_ORDER_ID) or chat_data.get("sl_order_id")
                                if sl_order_id:
                                    sl_rebalance_result = await rebalance_sl_quantity_after_tp1(
                                        chat_data=chat_data,
                                        symbol=symbol,
                                        sl_order_id=sl_order_id
                                    )

                                    if sl_rebalance_result.get("success"):
                                        logger.info(f"✅ SL quantity rebalanced after TP1 hit - new quantity: {sl_rebalance_result.get('new_quantity')}")
                                    else:
                                        logger.warning(f"⚠️ SL quantity rebalance failed: {sl_rebalance_result.get('error', 'Unknown error')}")
                                else:
                                    logger.warning(f"⚠️ No SL order ID found to rebalance for {symbol}")
                            except Exception as e:
                                logger.error(f"❌ Error rebalancing SL quantity: {e}")

                    # Check for other TP hits (TP2, TP3, TP4) if TP1 was handled
                    if not conservative_tp1_cancelled:
                        await check_conservative_other_tp_hits(chat_data, symbol, current_price, side, ctx_app)

                    # Check for SL hit
                    sl_hit = await check_conservative_sl_hit(chat_data, symbol, current_price, side, ctx_app)
                    if sl_hit:
                        logger.info(f"🛡️ {approach.capitalize()} SL hit for {symbol} - all orders cancelled")

                # FIXED: Fast approach TP/SL monitoring with proper order cancellation
                # Fast approach monitoring removed - only conservative approach supported

                # ENHANCED: Position closure detection with automatic order cancellation (for ALL monitoring types)
                if current_size == 0:
                    if not position_closed and last_position_size and last_position_size > 0:
                        logger.info(f"🎯 POSITION CLOSED DETECTED for {symbol} ({monitoring_mode})")

                        # Determine close reason and final P&L
                        close_reason = "MANUAL_CLOSE"
                        final_pnl = last_known_pnl

                        # REFINED: Better P&L calculation - use last_position_data if position is empty
                        position_for_pnl = last_position_data if last_position_data else position
                        if position_for_pnl:
                            final_pnl = await calculate_accurate_pnl(position_for_pnl, chat_data)
                        else:
                            # Fallback to last known P&L
                            final_pnl = last_known_pnl
                        logger.info(f"📊 Position closed - Final P&L calculated: {final_pnl}")

                        # Determine close reason based on conservative approach flags
                        if approach == "conservative":
                            if conservative_tp1_cancelled:
                                close_reason = "TP_HIT"
                            # Could add SL logic for conservative here if needed

                        # Cancel remaining orders automatically
                        cancelled_orders = []
                        if close_reason == "TP_HIT":
                            cancelled_orders = await cancel_remaining_orders(chat_data, symbol, 'TP')

                            # Trigger Conservative rebalancing when TP hits (before cancelling all orders)
                            if approach in ["conservative", "ggshot"]:
                                try:
                                    from execution.conservative_rebalancer import rebalance_conservative_on_limit_fill

                                    logger.info(f"🔄 Triggering Conservative rebalance due to TP hit")
                                    rebalance_result = await rebalance_conservative_on_limit_fill(
                                        chat_data=chat_data,
                                        symbol=symbol,
                                        filled_limits=1,  # TP hit
                                        total_limits=4,   # Total TPs
                                        ctx_app=ctx_app
                                    )

                                    if rebalance_result.get("success") and rebalance_result.get("created", 0) > 0:
                                        logger.info(f"✅ Conservative rebalance after TP hit completed - adjusted {rebalance_result.get('created')} orders")

                                except Exception as e:
                                    logger.error(f"Error triggering Conservative rebalance on TP hit: {e}")

                        elif close_reason == "SL_HIT":
                            cancelled_orders = await cancel_remaining_orders(chat_data, symbol, 'SL')

                        # Update performance stats (for ALL monitoring types)
                        logger.info(f"📊 Calling update_performance_stats_on_close - Reason: {close_reason}, P&L: {final_pnl}")
                        # Make sure we have valid position data for stats update
                        stats_position_data = last_position_data or position
                        if not stats_position_data or stats_position_data.get("size") == "0":
                            # Get approach-specific entry price and position size for accurate individual trade stats
                            # Conservative approach only - use approach-specific keys
                            approach_entry_key = f"{approach}_entry_price"
                            approach_size_key = f"{approach}_position_size"

                            approach_entry_price = safe_decimal_conversion(chat_data.get(approach_entry_key, entry_price))
                            approach_position_size = safe_decimal_conversion(chat_data.get(approach_size_key, last_position_size))

                            # Create synthetic position data for stats using approach-specific values
                            stats_position_data = {
                                "symbol": symbol,
                                "side": side,
                                "size": str(approach_position_size) if approach_position_size else "0",
                                "avgPrice": str(approach_entry_price) if approach_entry_price else "0",
                                "markPrice": str(current_price) if current_price else "0",
                                "cumRealisedPnl": str(final_pnl) if final_pnl else "0",
                                "unrealisedPnl": "0"
                            }
                        await update_performance_stats_on_close(
                            ctx_app, chat_data, stats_position_data, close_reason, final_pnl
                        )

                        # Send position closed summary alert
                        if ctx_app and hasattr(ctx_app, 'bot'):
                            chat_id = chat_data.get('chat_id') or chat_data.get('_chat_id')
                            if chat_id:
                                # Calculate duration
                                position_created_time = chat_data.get("position_created_time", 0)
                                trade_initiated_at = chat_data.get("trade_initiated_at", position_created_time)
                                if trade_initiated_at:
                                    duration_minutes = int((time.time() - trade_initiated_at) / 60)
                                else:
                                    duration_minutes = 0

                                # Get final prices
                                exit_price = safe_decimal_conversion(position.get("markPrice", "0"))
                                if exit_price == 0:
                                    exit_price = current_price

                                # Get approach-specific entry price for alert
                                approach_entry_key = f"{approach}_entry_price" if approach != "fast" else PRIMARY_ENTRY_PRICE
                                approach_size_key = f"{approach}_position_size" if approach != "fast" else LAST_KNOWN_POSITION_SIZE

                                alert_entry_price = safe_decimal_conversion(chat_data.get(approach_entry_key, entry_price))
                                alert_position_size = safe_decimal_conversion(chat_data.get(approach_size_key, last_position_size))

                                await send_position_closed_summary(
                                    bot=ctx_app.bot,
                                    chat_id=chat_id,
                                    symbol=symbol,
                                    side=side,
                                    approach=approach,
                                    entry_price=alert_entry_price,
                                    exit_price=exit_price,
                                    position_size=alert_position_size,
                                    pnl=final_pnl,
                                    close_reason=close_reason,
                                    duration_minutes=duration_minutes
                                )

                        # ENHANCED: Comprehensive cleanup when position closes
                        logger.info(f"🧹 Performing comprehensive cleanup for {symbol} after position closure")
                        try:
                            from clients.bybit_helpers import get_all_open_orders
                            all_orders = await get_all_open_orders()
                            symbol_orders = [o for o in all_orders if o.get('symbol') == symbol]

                            cleanup_count = 0
                            for order in symbol_orders:
                                order_id = order.get('orderId')
                                order_link_id = order.get('orderLinkId', '')

                                # Cancel any remaining orders for this symbol
                                if 'BOT' in order_link_id or order.get('reduceOnly'):
                                    logger.warning(f"🧹 Found orphaned order {order_id[:8]}... for closed position {symbol}, cancelling")
                                    success = await cancel_order_with_retry(symbol, order_id)
                                    if success:
                                        cleanup_count += 1
                                        cancelled_orders.append(f"Cleanup: {order_id[:8]}...")
                                        logger.info(f"✅ Cleaned up orphaned order {order_id}")

                            if cleanup_count > 0:
                                logger.info(f"✅ Cleaned up {cleanup_count} orphaned orders for {symbol}")

                        except Exception as cleanup_error:
                            logger.error(f"Error during position closure cleanup: {cleanup_error}")

                        position_closed = True

                        # Log completion
                        logger.info(f"✅ {monitoring_mode} position closed for {symbol} - Reason: {close_reason}, PnL: {final_pnl}")
                        if cancelled_orders:
                            logger.info(f"🔄 Auto-cancelled orders: {', '.join(cancelled_orders)}")
                        if conservative_tp1_cancelled:
                            logger.info(f"🚨 Conservative TP1 cancellation was triggered")
                        # Fast approach removed - only conservative approach supported
                        logger.info(f"📊 Performance stats updated ({monitoring_mode})")

                        # Stop monitoring
                        logger.info(f"✅ {monitoring_mode} monitoring completed for {symbol}")

                        # Clear Conservative TP tracking when position closes
                        if approach in ["conservative", "ggshot"] and "conservative_tps_hit" in chat_data:
                            chat_data["conservative_tps_hit"] = []
                            logger.info(f"🧹 Cleared Conservative TP hit tracking for {symbol}")

                        # Mark monitor as inactive in chat data
                        if ACTIVE_MONITOR_TASK in chat_data:
                            chat_data[ACTIVE_MONITOR_TASK]["active"] = False

                        # Stop auto-refresh if no more positions
                        try:
                            from handlers.commands import stop_auto_refresh
                            positions = await get_position_info(symbol, None)
                            all_positions = await get_all_positions()
                            active_count = len([p for p in all_positions if float(p.get('size', 0)) > 0])
                            if active_count == 0:
                                await stop_auto_refresh(chat_id, ctx_app)
                                logger.info(f"Stopped auto-refresh as no positions remain")
                        except Exception as e:
                            logger.debug(f"Could not stop auto-refresh: {e}")

                        # Clean up monitor from bot_data immediately
                        if ctx_app and hasattr(ctx_app, 'bot_data'):
                            bot_data = ctx_app.bot_data
                            monitor_key = f"{chat_id}_{symbol}_{approach}"
                            if 'monitor_tasks' in bot_data and monitor_key in bot_data['monitor_tasks']:
                                bot_data['monitor_tasks'][monitor_key]['active'] = False
                                logger.info(f"📊 Marked monitor as inactive in bot_data: {monitor_key}")

                        break

                else:
                    # Position is still open - update tracking data
                    last_position_size = current_size
                    last_position_data = position.copy()
                    # Store both general and approach-specific position size
                    chat_data[LAST_KNOWN_POSITION_SIZE] = current_size
                    approach = chat_data.get(TRADING_APPROACH, "conservative")
                    # Store approach-specific position size
                    chat_data[f"{approach}_position_size"] = current_size

                    # Track P&L while position is open
                    if unrealized_pnl != 0:
                        last_known_pnl = unrealized_pnl
                        chat_data["last_known_pnl"] = str(last_known_pnl)

                # Log monitoring status every 20 cycles (reduced frequency)
                if monitoring_cycles % 20 == 0:
                    logger.info(f"🔄 {monitoring_mode} monitoring {symbol} - Cycle {monitoring_cycles}, Size: {current_size}, PnL: {unrealized_pnl}")


                # Sleep before next check (8 seconds for better stability)
                await asyncio.sleep(8)

                # Reset error counter on successful cycle
                if consecutive_errors > 0:
                    consecutive_errors = 0
                    logger.debug(f"✅ Error counter reset for {symbol} monitor after successful cycle")

            except Exception as e:
                # Check for specific error patterns that indicate circuit breaker should trigger
                error_msg = str(e)
                if "current position is zero" in error_msg or "cannot fix reduce-only order qty" in error_msg:
                    consecutive_errors += 1
                    logger.error(f"❌ Zero position error #{consecutive_errors} for {symbol}: {error_msg}")

                    if consecutive_errors >= max_consecutive_errors:
                        # Trigger circuit breaker
                        error_cooldown_until = time.time() + 300  # 5 minute cooldown
                        logger.warning(
                            f"⚠️ Circuit breaker triggered for {symbol} monitor after {consecutive_errors} errors. "
                            f"Entering 5-minute cooldown."
                        )

                        # Send alert to user about circuit breaker
                        if ctx_app and hasattr(ctx_app, 'bot'):
                            try:
                                await ctx_app.bot.send_message(
                                    chat_id=chat_id,
                                    text=(
                                        f"⚡ <b>MONITOR CIRCUIT BREAKER ACTIVATED</b>\n"
                                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                        f"Symbol: {symbol}\n"
                                        f"Reason: Repeated 'zero position' errors\n"
                                        f"Action: Monitor paused for 5 minutes\n\n"
                                        f"This usually means the position was closed externally.\n"
                                        f"Monitor will auto-resume after cooldown."
                                    ),
                                    parse_mode="HTML"
                                )
                            except Exception:
                                pass
                else:
                    # Other errors - reset consecutive counter
                    consecutive_errors = 0
                    logger.error(f"❌ Error in {monitoring_mode} monitor loop: {e}", exc_info=True)

                # Report error to execution summary
                if EXECUTION_SUMMARY_AVAILABLE:
                    try:
                        monitor_id = f"{chat_id}_{symbol}_{approach}"
                        health_data = await execution_summary._monitor_health.get(monitor_id, {})
                        error_count = health_data.get('errors', 0) + 1
                        await execution_summary.update_monitor_health(monitor_id, {
                            'symbol': symbol,
                            'approach': approach,
                            'account': 'primary',
                            'status': 'error',
                            'last_check': time.time(),
                            'errors': error_count,
                            'last_error': str(e)
                        })
                    except Exception as health_error:
                        logger.debug(f"Failed to report monitor error: {health_error}")
                await asyncio.sleep(15)  # Wait longer on error

    finally:
        # ENHANCED CLEANUP
        logger.info(f"🏁 {monitoring_mode} monitoring ended for {symbol}")

        # Clear monitoring data
        chat_data[ACTIVE_MONITOR_TASK] = {}

        # Unregister task
        approach = chat_data.get(TRADING_APPROACH, 'fast')
        await unregister_monitor_task(chat_id, symbol, approach)

        # Remove from bot_data if available - ENHANCED cleanup
        if ctx_app and hasattr(ctx_app, 'bot_data'):
            bot_data = ctx_app.bot_data
            approach = chat_data.get(TRADING_APPROACH, 'fast')
            monitor_key = f"{chat_id}_{symbol}_{approach}"

            # Check and remove from monitor_tasks
            if 'monitor_tasks' in bot_data:
                if monitor_key in bot_data['monitor_tasks']:
                    # Mark as inactive first
                    bot_data['monitor_tasks'][monitor_key]['active'] = False
                    # Then delete completely
                    del bot_data['monitor_tasks'][monitor_key]
                    logger.info(f"📊 Cleaned up monitor from bot_data: {symbol} ({approach})")

                # Also check for any other monitors for same symbol (edge case)
                keys_to_remove = []
                for key in bot_data['monitor_tasks']:
                    if key.startswith(f"{chat_id}_{symbol}_"):
                        keys_to_remove.append(key)

                for key in keys_to_remove:
                    if key != monitor_key and key in bot_data['monitor_tasks']:
                        del bot_data['monitor_tasks'][key]
                        logger.info(f"📊 Also cleaned up related monitor: {key}")

                # Force persistence update
                try:
                    if hasattr(ctx_app, 'update_persistence'):
                        await optimize_persistence_update(ctx_app)
                        logger.info(f"✅ Persistence updated after monitor cleanup")
                except Exception as e:
                    logger.warning(f"Could not update persistence: {e}")

        # Clear local variables to help GC
        position_history.clear()
        last_position_data = None

        # Force garbage collection
        gc.collect()

        logger.info(f"🧹 Memory cleanup completed for {symbol} monitor")

async def monitor_mirror_position_loop_enhanced(ctx_app, chat_id: int, chat_data: dict):
    """
    Mirror account monitoring loop - monitors positions on the second Bybit account
    Reuses the same monitoring logic as primary account but queries mirror account data

    IMPORTANT: Mirror account monitoring operates silently without sending Telegram alerts.
    This prevents duplicate notifications since users are already alerted about main account activity.
    All position changes, TP/SL hits, and closures are logged but not sent as user notifications.
    """
    symbol = chat_data.get(SYMBOL)
    position_idx = chat_data.get(POSITION_IDX, 0)
    approach = chat_data.get(TRADING_APPROACH, "conservative")
    monitoring_mode = f"MIRROR-{get_monitoring_mode(chat_data)}"

    # Store chat_id in chat_data for easy access in alert functions
    chat_data['_chat_id'] = chat_id

    if not symbol:
        logger.error(f"❌ No symbol found for mirror monitoring in chat {chat_id}")
        return

    logger.info(f"🔄 Starting {monitoring_mode} monitoring loop for {symbol} in chat {chat_id}")

    # Log mirror alert configuration
    if not ENABLE_MIRROR_ALERTS:
        logger.info(f"📵 Mirror account alerts are DISABLED - all events will be logged only")

    # Monitoring state
    tp1_hit = False
    # Removed breakeven functionality
    position_closed = False
    last_position_size = None
    last_position_data = None
    last_known_pnl = Decimal("0")
    monitoring_cycles = 0
    position_history = []
    max_history_size = 10

    # Conservative approach specific tracking
    conservative_tp1_cancelled = False

    # Get stored order IDs (with _MIRROR suffix)
    if approach == "conservative":
        # Mirror orders have _MIRROR suffix
        limit_order_ids = [f"{oid}_MIRROR" for oid in chat_data.get(LIMIT_ORDER_IDS, []) if oid]
        tp_order_ids = [f"{oid}_MIRROR" for oid in chat_data.get(CONSERVATIVE_TP_ORDER_IDS, []) if oid]
        sl_order_id = chat_data.get(CONSERVATIVE_SL_ORDER_ID)
        if sl_order_id:
            sl_order_id = f"{sl_order_id}_MIRROR"
        logger.info(f"📋 Mirror Conservative monitoring - Limits: {len(limit_order_ids)}, TPs: {len(tp_order_ids)}, SL: {bool(sl_order_id)}")
    else:
        tp_order_id = chat_data.get("tp_order_id")
        if tp_order_id:
            tp_order_id = f"{tp_order_id}_MIRROR"
        sl_order_id = chat_data.get(SL_ORDER_ID) or chat_data.get("sl_order_id")
        if sl_order_id:
            sl_order_id = f"{sl_order_id}_MIRROR"
        logger.info(f"📋 Mirror Fast monitoring - TP: {tp_order_id}, SL: {sl_order_id}")

    # Get initial mirror position
    try:
        positions = await get_mirror_position_info(symbol)
        initial_position = None
        if positions:
            for pos in positions:
                if float(pos.get("size", 0)) > 0:
                    initial_position = pos
                    break

        if initial_position:
            last_position_size = safe_decimal_conversion(initial_position.get("size", "0"))
            last_position_data = initial_position.copy()
            # Store both general and approach-specific position size for mirror
            chat_data[LAST_KNOWN_POSITION_SIZE] = last_position_size
            approach = chat_data.get(TRADING_APPROACH, "conservative")
            # Store approach-specific position size
            chat_data[f"{approach}_position_size"] = last_position_size
            logger.info(f"📊 Initial MIRROR position: {symbol} - {initial_position.get('side')} {last_position_size}")
        else:
            logger.warning(f"⚠️ No initial MIRROR position found for {symbol}")
    except Exception as e:
        logger.error(f"❌ Error getting initial MIRROR position for {symbol}: {e}")

    try:
        while True:
            try:
                monitoring_cycles += 1

                # Memory cleanup
                if monitoring_cycles % 100 == 0:
                    gc.collect()
                    logger.debug(f"Memory cleanup performed for MIRROR {symbol} monitor")

                # Check if monitoring should stop
                mirror_task_info = chat_data.get(MIRROR_ACTIVE_MONITOR_TASK, {})
                if not mirror_task_info.get("active", True):
                    logger.info(f"🛑 {monitoring_mode} monitoring stopped for {symbol} (deactivated)")
                    # Mark mirror monitor as inactive in execution summary
                    if EXECUTION_SUMMARY_AVAILABLE:
                        try:
                            monitor_id = f"{chat_id}_{symbol}_{approach}_mirror"
                            await execution_summary.update_monitor_health(monitor_id, {
                                'symbol': symbol,
                                'approach': approach,
                                'account': 'mirror',
                                'status': 'inactive',
                                'last_check': time.time()
                            })
                        except Exception as e:
                            logger.debug(f"Failed to mark mirror monitor inactive: {e}")
                    break

                # Get mirror position data
                positions = await get_mirror_position_info(symbol)
                position = None
                if positions:
                    for pos in positions:
                        if float(pos.get("size", 0)) > 0:
                            position = pos
                            break

                if not position:
                    # Reduce log spam for missing mirror positions
                    if monitoring_cycles % 10 == 0:  # Log every 10th cycle instead of every cycle
                        logger.debug(f"⚠️ No MIRROR position data for {symbol} (cycle {monitoring_cycles})")

                    # If no position found for many cycles, the position might be closed
                    if monitoring_cycles > 50:  # After 50 cycles (~8 minutes), position likely closed
                        logger.info(f"📝 MIRROR position monitoring stopped for {symbol} - position appears closed after {monitoring_cycles} cycles")
                        try:
                            # Update task status
                            task_key = f"{symbol}_{chat_data.get(TRADING_APPROACH, 'fast')}_{chat_id}_{ACCOUNT_TYPE_MIRROR}"
                            chat_data.setdefault(ACTIVE_MONITOR_TASKS, {}).setdefault(task_key, {}).update({
                                'status': 'inactive',
                                'last_check': time.time()
                            })
                        except Exception as e:
                            logger.debug(f"Failed to mark mirror monitor inactive: {e}")
                        break

                    await asyncio.sleep(5)
                    continue

                # Cache position data
                current_size = safe_decimal_conversion(position.get("size", "0"))
                current_price = safe_decimal_conversion(position.get("markPrice", "0"))
                position_key = f"{symbol}_{current_size}_{current_price}"

                last_position_key = chat_data.get("_last_mirror_position_key")
                if last_position_key == position_key and monitoring_cycles % 5 != 0:
                    await asyncio.sleep(POSITION_MONITOR_INTERVAL)
                    continue

                chat_data["_last_mirror_position_key"] = position_key

                # Process position data
                current_size = safe_decimal_conversion(position.get("size", "0"))
                current_price = safe_decimal_conversion(position.get("markPrice", "0"))
                side = position.get("side")
                entry_price = safe_decimal_conversion(position.get("avgPrice", "0"))
                unrealized_pnl = safe_decimal_conversion(position.get("unrealisedPnl", "0"))
                cum_realised_pnl = safe_decimal_conversion(position.get("cumRealisedPnl", "0"))

                # Track position history
                position_history.append({
                    "time": time.time(),
                    "size": current_size,
                    "unrealisedPnl": unrealized_pnl,
                    "cumRealisedPnl": cum_realised_pnl,
                    "markPrice": current_price
                })

                if len(position_history) > max_history_size:
                    position_history.pop(0)

                # Update last known P&L
                if current_size > 0 and unrealized_pnl != 0:
                    last_known_pnl = unrealized_pnl
                    chat_data["last_known_mirror_pnl"] = str(last_known_pnl)

                # Report mirror monitor health to execution summary
                if EXECUTION_SUMMARY_AVAILABLE and monitoring_cycles % 10 == 0:  # Report every 10 cycles
                    try:
                        monitor_id = f"{chat_id}_{symbol}_{approach}_mirror"
                        health_data = {
                            'symbol': symbol,
                            'approach': approach,
                            'account': 'mirror',
                            'status': 'active',
                            'last_check': time.time(),
                            'errors': 0,
                            'restarts': 0,
                            'position_size': float(current_size),
                            'unrealized_pnl': float(unrealized_pnl),
                            'monitoring_mode': monitoring_mode,
                            'cycles': monitoring_cycles
                        }
                        await execution_summary.update_monitor_health(monitor_id, health_data)
                    except Exception as e:
                        logger.debug(f"Failed to report mirror monitor health: {e}")

                # Check for TP1 hit and move SL to breakeven for conservative/ggshot approaches
                if approach in ["conservative", "ggshot"] and current_size > 0:
                    # CHECK FOR CONSERVATIVE LIMIT FILLS FOR MIRROR ACCOUNT
                    if approach == "conservative":
                        # Get mirror limit order IDs
                        mirror_limit_order_ids = chat_data.get("mirror_limit_order_ids", [])
                        if mirror_limit_order_ids:
                            logger.debug(f"🔍 Checking mirror Conservative limit fills for {symbol}")

                            # Track filled limits
                            mirror_limits_filled = chat_data.get("mirror_conservative_limits_filled", [])
                            newly_filled = []

                            # Check each limit order
                            for i, order_id in enumerate(mirror_limit_order_ids):
                                if order_id and order_id not in mirror_limits_filled:
                                    try:
                                        from clients.bybit_helpers import get_order_info_mirror
                                        order_info = await get_order_info_mirror(symbol, order_id)

                                        if order_info and order_info.get("orderStatus") in ["Filled", "PartiallyFilled"]:
                                            logger.info(f"✅ MIRROR Conservative Limit {i+1} FILLED for {symbol}")
                                            mirror_limits_filled.append(order_id)
                                            newly_filled.append(order_id)
                                    except Exception as e:
                                        logger.debug(f"Could not check mirror limit order {i+1}: {e}")

                            # Update tracking
                            chat_data["mirror_conservative_limits_filled"] = mirror_limits_filled

                            # If we have newly filled limits, trigger rebalancing
                            if newly_filled:
                                logger.info(f"✅ {len(newly_filled)} mirror limit orders newly filled for {symbol}")

                                # Trigger mirror Conservative rebalancing
                                try:
                                    from execution.conservative_rebalancer import rebalance_conservative_mirror

                                    logger.info(f"🔄 Triggering MIRROR Conservative rebalance due to limit fills")
                                    mirror_rebalance_result = await rebalance_conservative_mirror(
                                        chat_data=chat_data,
                                        symbol=symbol,
                                        trigger="limit_fill"
                                    )

                                    if mirror_rebalance_result.get("success"):
                                        logger.info(f"✅ MIRROR Conservative rebalance completed")
                                    else:
                                        logger.error(f"❌ MIRROR Conservative rebalance failed: {mirror_rebalance_result.get('error')}")

                                except Exception as e:
                                    logger.error(f"Error triggering MIRROR Conservative rebalance: {e}")

                    # Check if we have mirror TP order IDs
                    mirror_tp_order_ids = chat_data.get("mirror_conservative_tp_order_ids", [])

                    if mirror_tp_order_ids and len(mirror_tp_order_ids) > 0:
                        # Check TP1 status (first TP order)
                        tp1_order_id = mirror_tp_order_ids[0]

                        try:
                            # Get order info from mirror account
                            from clients.bybit_helpers import get_order_info_mirror
                            tp1_info = await get_order_info_mirror(symbol, tp1_order_id)

                            if tp1_info and tp1_info.get("orderStatus") in ["Filled", "PartiallyFilled"]:
                                logger.info(f"🎯 MIRROR TP1 HIT DETECTED for {symbol}")

                                # Store position data BEFORE any actions
                                position_before_tp1 = position.copy()

                                # CRITICAL: Verify TP1 actually executed and closed 85% of position
                                await asyncio.sleep(2.0)  # Wait for TP1 order to execute

                                # Get updated mirror position after TP1 should have executed
                                positions_after = await get_mirror_position_info(symbol)
                                position_after_tp1 = None
                                if positions_after:
                                    position_after_tp1 = next((p for p in positions_after if float(p.get("size", 0)) > 0),
                                                            {"size": "0"})
                                else:
                                    position_after_tp1 = {"size": "0"}

                                # Verify TP1 execution (85% for conservative)
                                from utils.tp_execution_verifier import tp_execution_verifier

                                verification_result = await tp_execution_verifier.verify_tp_execution(
                                    symbol=symbol,
                                    tp_number=1,
                                    expected_percentage=0.85,  # TP1 should close 85%
                                    position_before=position_before_tp1,
                                    position_after=position_after_tp1,
                                    chat_data=chat_data
                                )

                                if not verification_result.get("verified"):
                                    logger.error(f"❌ MIRROR TP1 execution verification FAILED for {symbol}!")

                                    # For mirror account, place corrective order using mirror functions
                                    if verification_result.get("corrective_action", {}).get("action") != "corrective_order_placed":
                                        # Need to place corrective order ourselves for mirror account
                                        expected_final_size = safe_decimal_conversion(position_before_tp1.get("size", "0")) * Decimal("0.15")  # 15% should remain
                                        current_size_after = safe_decimal_conversion(position_after_tp1.get("size", "0"))
                                        additional_close_needed = current_size_after - expected_final_size

                                        if additional_close_needed > 0:
                                            from execution.mirror_trader import place_mirror_market_order
                                            from clients.bybit_helpers import get_instrument_info

                                            # Get symbol info for precision
                                            symbol_info = await get_instrument_info(symbol)
                                            qty_step = safe_decimal_conversion(symbol_info.get("lotSizeFilter", {}).get("qtyStep", "0.001"))
                                            close_qty = value_adjusted_to_step(additional_close_needed, qty_step)

                                            close_side = "Sell" if side == "Buy" else "Buy"
                                            order_link_id = f"BOT_TP1_CORRECTIVE_MIRROR_{int(time.time())}"

                                            logger.warning(f"⚠️ MIRROR: Placing corrective market order to close {close_qty} units")

                                            corrective_result = await place_mirror_market_order(
                                                symbol=symbol,
                                                side=close_side,
                                                qty=str(close_qty),
                                                reduce_only=True,
                                                order_link_id=order_link_id
                                            )

                                            if corrective_result:
                                                logger.info(f"✅ MIRROR corrective order placed successfully")
                                            else:
                                                logger.error(f"❌ Failed to place MIRROR corrective order")
                                else:
                                    logger.info(f"✅ MIRROR TP1 execution verified: closed {verification_result.get('actual_percentage', 0)*100:.1f}% of position")

                                # Update position size based on actual execution
                                actual_size_after = safe_decimal_conversion(position_after_tp1.get("size", "0"))
                                chat_data["last_known_mirror_position_size"] = actual_size_after

                                # Trigger mirror Conservative rebalancing after TP1 verification
                                try:
                                    from execution.conservative_rebalancer import rebalance_conservative_mirror

                                    logger.info(f"🔄 Triggering MIRROR Conservative rebalance after TP1 hit")
                                    mirror_rebalance_result = await rebalance_conservative_mirror(
                                        chat_data=chat_data,
                                        symbol=symbol,
                                        trigger="tp_hit",
                                        tp_number=1
                                    )

                                    if mirror_rebalance_result.get("success"):
                                        logger.info(f"✅ MIRROR Conservative rebalance completed after TP1")
                                    else:
                                        logger.error(f"❌ MIRROR Conservative rebalance failed: {mirror_rebalance_result.get('error')}")

                                except Exception as e:
                                    logger.error(f"Error triggering MIRROR Conservative rebalance: {e}")

                                # Rebalance SL quantity after TP1 hit for mirror account (no price change)
                                logger.info(f"🔄 Triggering MIRROR SL quantity rebalance after TP1 hit for {symbol}")

                                # Trigger SL quantity rebalancing for mirror
                                try:
                                    from execution.conservative_rebalancer import rebalance_sl_quantity_after_tp1

                                    mirror_sl_order_id = chat_data.get("mirror_sl_order_id") or chat_data.get("mirror_conservative_sl_order_id")
                                    if mirror_sl_order_id:
                                        sl_rebalance_result = await rebalance_sl_quantity_after_tp1(
                                            chat_data=chat_data,
                                            symbol=symbol,
                                            sl_order_id=mirror_sl_order_id,
                                            is_mirror=True
                                        )

                                        if sl_rebalance_result.get("success"):
                                            logger.info(f"✅ MIRROR SL quantity rebalanced after TP1 hit - new quantity: {sl_rebalance_result.get('new_quantity')}")
                                        else:
                                            logger.warning(f"⚠️ MIRROR SL quantity rebalance failed: {sl_rebalance_result.get('error', 'Unknown error')}")
                                    else:
                                        logger.warning(f"⚠️ No MIRROR SL order ID found to rebalance for {symbol}")
                                except Exception as e:
                                    logger.error(f"❌ Error rebalancing MIRROR SL quantity: {e}")

                                # Mark that we've handled TP1 for mirror
                                chat_data["mirror_tp1_verified"] = True
                        except Exception as e:
                            logger.debug(f"Could not check mirror TP1 status: {e}")

                    # Check for other TP hits (TP2, TP3, TP4) and trigger rebalancing
                    await check_mirror_conservative_tp_hits(chat_data, symbol)

                # FIXED: Fast approach TP/SL monitoring for MIRROR account
                elif False and current_size > 0:

                    # Check for TP hit and cancel SL using same function as main account
                    if not fast_tp_hit:
                        # Pass None for ctx_app to prevent alerts (mirror accounts don't send alerts)
                        tp_hit = await check_tp_hit_and_cancel_sl(chat_data, symbol, current_price, side, None)
                        if tp_hit:
                            fast_tp_hit = True
                            logger.info(f"🎯 MIRROR Fast approach TP hit for {symbol} - SL cancelled")

                            # Log the TP hit details
                            tp_order_id = chat_data.get("tp_order_id") or (chat_data.get("tp_order_ids", []) or [None])[0]
                            if tp_order_id:
                                logger.info(f"📊 MIRROR TP order {tp_order_id[:8]}... was triggered/filled")

                    # Check for SL hit and cancel TP using same function as main account
                    if not fast_sl_hit:
                        # Pass None for ctx_app to prevent alerts (mirror accounts don't send alerts)
                        sl_hit = await check_sl_hit_and_cancel_tp(chat_data, symbol, current_price, side, None)
                        if sl_hit:
                            fast_sl_hit = True
                            logger.info(f"🛡️ MIRROR Fast approach SL hit for {symbol} - TP cancelled")

                            # Log the SL hit details
                            sl_order_id = chat_data.get("sl_order_id") or chat_data.get("stop_loss_order_id")
                            if sl_order_id:
                                logger.info(f"📊 MIRROR SL order {sl_order_id[:8]}... was triggered/filled")

                # Position closure detection
                if current_size == 0:
                    if not position_closed and last_position_size and last_position_size > 0:
                        logger.info(f"🎯 MIRROR POSITION CLOSED DETECTED for {symbol}")

                        # ENHANCED: Comprehensive cleanup for mirror account too
                        logger.info(f"🧹 Performing comprehensive cleanup for MIRROR {symbol} after position closure")
                        try:
                            from clients.bybit_helpers import get_all_open_orders
                            # Use mirror client to get mirror orders
                            if bybit_client_2:
                                all_orders = await get_all_open_orders(client=bybit_client_2)
                                symbol_orders = [o for o in all_orders if o.get('symbol') == symbol]

                                cleanup_count = 0
                                for order in symbol_orders:
                                    order_id = order.get('orderId')
                                    order_link_id = order.get('orderLinkId', '')

                                    # Cancel any remaining orders for this symbol
                                    if 'BOT' in order_link_id or order.get('reduceOnly'):
                                        logger.warning(f"🧹 Found orphaned MIRROR order {order_id[:8]}... for closed position {symbol}, cancelling")
                                        # Use mirror client for cancellation
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
                                            cleanup_count += 1
                                            logger.info(f"✅ Cleaned up orphaned MIRROR order {order_id}")

                                if cleanup_count > 0:
                                    logger.info(f"✅ Cleaned up {cleanup_count} orphaned MIRROR orders for {symbol}")

                        except Exception as cleanup_error:
                            logger.error(f"Error during MIRROR position closure cleanup: {cleanup_error}")

                        # Log closure but don't update primary account stats
                        close_reason = "MANUAL_CLOSE"
                        final_pnl = last_known_pnl

                        logger.info(f"📊 MIRROR Position closed: {symbol} - Reason: {close_reason}, P&L: {final_pnl}")

                        # NOTE: No Telegram alerts are sent for mirror account positions
                        # This is intentional to prevent duplicate notifications (ENABLE_MIRROR_ALERTS=False)

                        # Clear Conservative TP tracking for mirror position when it closes
                        if approach in ["conservative", "ggshot"] and "conservative_tps_hit" in chat_data:
                            chat_data["conservative_tps_hit"] = []
                            logger.info(f"🧹 Cleared Conservative TP hit tracking for MIRROR {symbol}")

                        position_closed = True
                        break

                # Update tracking variables
                last_position_size = current_size
                last_position_data = position.copy()

                # Sleep before next iteration
                await asyncio.sleep(POSITION_MONITOR_INTERVAL)

            except asyncio.CancelledError:
                logger.info(f"🛑 MIRROR Monitor task cancelled for {symbol}")
                break
            except Exception as e:
                logger.error(f"❌ Error in MIRROR monitoring loop for {symbol}: {e}", exc_info=True)
                await asyncio.sleep(POSITION_MONITOR_INTERVAL)

    except Exception as e:
        logger.error(f"❌ Fatal error in MIRROR monitoring for {symbol}: {e}", exc_info=True)

    finally:
        # Cleanup
        logger.info(f"🧹 Cleaning up MIRROR monitoring for {symbol}")

        # Update mirror task status
        if MIRROR_ACTIVE_MONITOR_TASK in chat_data:
            chat_data[MIRROR_ACTIVE_MONITOR_TASK]["active"] = False

        # Unregister mirror monitor task
        await unregister_monitor_task(chat_id, symbol, approach, ACCOUNT_TYPE_MIRROR)

        # Clear from bot_data
        if ctx_app and hasattr(ctx_app, 'bot_data'):
            bot_data = ctx_app.bot_data
            monitor_key = f"{chat_id}_{symbol}_{approach}_{ACCOUNT_TYPE_MIRROR}"
            if 'monitor_tasks' in bot_data and monitor_key in bot_data['monitor_tasks']:
                del bot_data['monitor_tasks'][monitor_key]
                logger.info(f"📊 Removed MIRROR monitor from bot_data: {approach} approach for {symbol}")

        # Memory cleanup
        position_history.clear()
        last_position_data = None
        gc.collect()

        logger.info(f"🧹 MIRROR memory cleanup completed for {symbol} monitor")

async def stop_position_monitoring(chat_data: dict, ctx_app=None):
    """Stop monitoring for a position with enhanced cleanup"""
    if ACTIVE_MONITOR_TASK in chat_data:
        task_info = chat_data[ACTIVE_MONITOR_TASK]
        task_info["active"] = False

        # Also unregister from global registry
        symbol = task_info.get("symbol", "")
        chat_id = task_info.get("chat_id", 0)
        if symbol and chat_id:
            approach = task_info.get("approach", "conservative")
            await unregister_monitor_task(chat_id, symbol, approach)

            # Remove from bot_data monitor_tasks
            if ctx_app and hasattr(ctx_app, 'bot_data'):
                bot_data = ctx_app.bot_data
                monitor_key = f"{chat_id}_{symbol}_{approach}"
                if 'monitor_tasks' in bot_data and monitor_key in bot_data['monitor_tasks']:
                    # Mark as inactive first
                    bot_data['monitor_tasks'][monitor_key]['active'] = False
                    # Then delete
                    del bot_data['monitor_tasks'][monitor_key]
                    logger.info(f"📊 Removed monitor from bot_data: {symbol} ({approach})")

                    # Force persistence update
                    try:
                        if hasattr(ctx_app, 'update_persistence'):
                            await ctx_app.update_persistence()
                    except Exception as e:
                        logger.warning(f"Could not update persistence: {e}")

        monitoring_mode = task_info.get("monitoring_mode", "UNKNOWN")
        chat_data[ACTIVE_MONITOR_TASK] = {}
        logger.info(f"🛑 {monitoring_mode} position monitoring stopped")

async def stop_mirror_position_monitoring(chat_data: dict, ctx_app=None):
    """Stop monitoring for a mirror account position"""
    if MIRROR_ACTIVE_MONITOR_TASK in chat_data:
        task_info = chat_data[MIRROR_ACTIVE_MONITOR_TASK]
        task_info["active"] = False

        # Also unregister from global registry
        symbol = task_info.get("symbol", "")
        chat_id = task_info.get("chat_id", 0)
        if symbol and chat_id:
            approach = task_info.get("approach", "conservative")
            await unregister_monitor_task(chat_id, symbol, approach, ACCOUNT_TYPE_MIRROR)

            # Remove from bot_data monitor_tasks
            if ctx_app and hasattr(ctx_app, 'bot_data'):
                bot_data = ctx_app.bot_data
                monitor_key = f"{chat_id}_{symbol}_{approach}_{ACCOUNT_TYPE_MIRROR}"
                if 'monitor_tasks' in bot_data and monitor_key in bot_data['monitor_tasks']:
                    # Mark as inactive first
                    bot_data['monitor_tasks'][monitor_key]['active'] = False
                    # Then delete
                    del bot_data['monitor_tasks'][monitor_key]
                    logger.info(f"📊 Removed MIRROR monitor from bot_data: {symbol} ({approach})")

                    # Force persistence update
                    try:
                        if hasattr(ctx_app, 'update_persistence'):
                            await ctx_app.update_persistence()
                    except Exception as e:
                        logger.warning(f"Could not update persistence: {e}")

        monitoring_mode = task_info.get("monitoring_mode", "MIRROR-UNKNOWN")
        chat_data[MIRROR_ACTIVE_MONITOR_TASK] = {}
        logger.info(f"🛑 {monitoring_mode} position monitoring stopped")

def get_monitoring_status(chat_data: dict) -> dict:
    """Get current monitoring status"""
    task_info = chat_data.get(ACTIVE_MONITOR_TASK, {})

    status = {
        "active": task_info.get("active", False),
        "symbol": task_info.get("symbol", "None"),
        "approach": task_info.get("approach", "conservative"),
        "chat_id": task_info.get("chat_id", "None"),
        "started_at": task_info.get("started_at", 0),
        "running_time": time.time() - task_info.get("started_at", time.time()) if task_info.get("started_at") else 0,
        "monitoring_mode": task_info.get("monitoring_mode", "UNKNOWN")
    }

    return status

def get_monitor_registry_stats() -> Dict[str, Any]:
    """Get monitoring registry statistics for debugging"""
    return _task_registry.get_stats()

def get_monitor_counts_by_approach(bot_data: Dict[str, Any]) -> Dict[str, int]:
    """Get monitor counts by approach type"""
    counts = {
        'total': 0,
        'fast': 0,
        'conservative': 0,
        'ggshot': 0
    }

    # Count from monitor_tasks in bot_data
    monitor_tasks = bot_data.get('monitor_tasks', {})
    for monitor_key, task_info in monitor_tasks.items():
        if isinstance(task_info, dict) and task_info.get('active', False):
            counts['total'] += 1

            approach = task_info.get('approach', 'unknown')
            if False:
                counts['fast'] += 1
            elif approach == 'conservative':
                counts['conservative'] += 1
            elif approach == 'ggshot':
                counts['ggshot'] += 1

    return counts

# REFINED: Get trade history for debugging
def get_trade_history_summary() -> Dict[str, Any]:
    """Get summary of trade history tracking"""
    return {
        "total_processed_trades": len(_trade_history._completed_trades),
        "max_history_size": _trade_history._max_history,
        "recent_trades": len(_trade_history._trade_details)
    }

# =============================================
# CONSERVATIVE APPROACH MONITORING FUNCTIONS
# =============================================

async def check_conservative_tp1_hit(chat_data: dict, symbol: str, current_price: Decimal, side: str) -> bool:
    """
    Check if TP1 has been hit BEFORE any limit orders filled
    This is Scenario 1: Early TP hit
    For GGShot: Checks if TP1 hit with only the initial market order filled
    """
    try:
        approach = chat_data.get(TRADING_APPROACH, "conservative")
        filled_limits = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])

        if approach == "ggshot":
            # For GGShot: Market order is pre-filled, check if NO additional limits filled
            # Should have exactly 1 filled order (the market order)
            if len(filled_limits) > 1:
                return False  # Additional limits have filled
        else:
            # For Conservative: Check if ANY limits have filled
            if filled_limits:
                return False  # This function only handles the case where NO limits filled

        # Get TP1 price - check both conservative and ggshot TP order IDs
        tp_order_ids = chat_data.get(CONSERVATIVE_TP_ORDER_IDS, [])
        if not tp_order_ids and approach == "ggshot":
            tp_order_ids = chat_data.get(GGSHOT_TP_ORDER_IDS, [])

        if not tp_order_ids:
            return False

        # Check first TP order (TP1)
        tp1_order_id = tp_order_ids[0] if tp_order_ids else None
        if not tp1_order_id:
            return False

        tp1_info = await get_order_info(symbol, tp1_order_id)
        if not tp1_info:
            return False

        tp1_price = safe_decimal_conversion(tp1_info.get("triggerPrice", "0"))

        # DISABLED: Old TP1 detection logic - using Enhanced TP/SL system instead
        # The enhanced system handles all TP/SL logic internally
        tp1_hit = False  # Always false to prevent interference

        if False:  # Disabled old logic
            if approach == "ggshot":
                logger.info(f"🚨 GGShot TP1 hit at {current_price} (target: {tp1_price}) with only market order filled!")
            else:
                logger.info(f"🚨 Conservative TP1 hit at {current_price} (target: {tp1_price}) with NO limit fills!")
            chat_data[CONSERVATIVE_TP1_HIT_BEFORE_LIMITS] = True
            return True

        return False

    except Exception as e:
        logger.error(f"Error checking conservative TP1 hit: {e}")
        return False

async def check_conservative_tp1_hit_with_fills(chat_data: dict, symbol: str, current_price: Decimal, side: str) -> bool:
    """
    Check if TP1 has been hit AFTER some limit orders filled
    This is Scenario 2: TP hit with partial fills
    For GGShot: Checks if TP1 hit after market + at least 1 limit filled
    """
    try:
        approach = chat_data.get(TRADING_APPROACH, "conservative")
        filled_limits = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])

        if approach == "ggshot":
            # For GGShot: Need more than 1 filled order (market + at least 1 limit)
            if len(filled_limits) <= 1:
                return False  # Only market order filled
        else:
            # For Conservative: Need at least 1 filled limit
            if not filled_limits:
                return False  # This function only handles the case where SOME limits filled

        # Don't trigger if we already handled scenario 1
        if chat_data.get(CONSERVATIVE_TP1_HIT_BEFORE_LIMITS, False):
            return False

        # Get TP1 price - check both conservative and ggshot TP order IDs
        tp_order_ids = chat_data.get(CONSERVATIVE_TP_ORDER_IDS, [])
        if not tp_order_ids and approach == "ggshot":
            tp_order_ids = chat_data.get(GGSHOT_TP_ORDER_IDS, [])

        if not tp_order_ids:
            return False

        # Check first TP order (TP1)
        tp1_order_id = tp_order_ids[0] if tp_order_ids else None
        if not tp1_order_id:
            return False

        tp1_info = await get_order_info(symbol, tp1_order_id)
        if not tp1_info:
            return False

        tp1_price = safe_decimal_conversion(tp1_info.get("triggerPrice", "0"))

        # DISABLED: Old TP1 detection logic - using Enhanced TP/SL system instead
        # The enhanced system handles all TP/SL logic internally
        tp1_hit = False  # Always false to prevent interference

        if False:  # Disabled old logic
            if approach == "ggshot":
                additional_fills = len(filled_limits) - 1  # Subtract market order
                logger.info(f"🎯 GGShot TP1 hit at {current_price} with market + {additional_fills} limit fills!")
            else:
                logger.info(f"🎯 Conservative TP1 hit at {current_price} with {len(filled_limits)} limit fills!")
            chat_data[CONSERVATIVE_TP1_HIT_WITH_FILLS] = True
            return True

        return False

    except Exception as e:
        logger.error(f"Error checking conservative TP1 hit with fills: {e}")
        return False

async def cancel_conservative_orders_on_tp1_hit(chat_data: dict, symbol: str, ctx_app=None) -> List[str]:
    """
    Cancel ALL orders when TP1 hits before any limits fill (Scenario 1)
    Cancels: All unfilled limits + All TPs + SL
    Works for both Conservative and GGShot approaches
    ADDED: Send alert when TP1 hits early
    """
    cancelled_orders = []
    cancelled_order_details = []

    try:
        approach = chat_data.get(TRADING_APPROACH, "conservative")
        side = chat_data.get(SIDE, "Unknown")

        # Cancel all unfilled limit orders
        limit_order_ids = chat_data.get(LIMIT_ORDER_IDS, [])
        filled_limits = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])

        cancellation_tasks = []

        for order_id in limit_order_ids:
            if order_id not in filled_limits:
                cancellation_tasks.append(cancel_order_with_retry(symbol, order_id))

        # Cancel all TP orders - check both conservative and ggshot
        tp_order_ids = chat_data.get(CONSERVATIVE_TP_ORDER_IDS, [])
        if not tp_order_ids and approach == "ggshot":
            tp_order_ids = chat_data.get(GGSHOT_TP_ORDER_IDS, [])

        for order_id in tp_order_ids:
            cancellation_tasks.append(cancel_order_with_retry(symbol, order_id))

        # Cancel SL order - check both conservative and ggshot
        sl_order_id = chat_data.get(CONSERVATIVE_SL_ORDER_ID)
        if not sl_order_id and approach == "ggshot":
            sl_order_id = chat_data.get(GGSHOT_SL_ORDER_ID)

        if sl_order_id:
            cancellation_tasks.append(cancel_order_with_retry(symbol, sl_order_id))

        # Execute all cancellations in parallel
        if cancellation_tasks:
            results = await asyncio.gather(*cancellation_tasks, return_exceptions=True)

            # Track successful cancellations
            all_order_ids = (
                [oid for oid in limit_order_ids if oid not in filled_limits] +
                tp_order_ids +
                ([sl_order_id] if sl_order_id else [])
            )

            # Build list of cancelled order descriptions
            limit_count = 0
            tp_count = 0

            for order_id, result in zip(all_order_ids, results):
                if not isinstance(result, Exception) and result:
                    cancelled_orders.append(order_id)

                    # Categorize cancelled orders for alert
                    if order_id in limit_order_ids:
                        limit_count += 1
                        cancelled_order_details.append(f"Limit order {order_id[:8]}...")
                    elif order_id in tp_order_ids:
                        tp_count += 1
                        cancelled_order_details.append(f"TP{tp_count} order {order_id[:8]}...")
                    elif order_id == sl_order_id:
                        cancelled_order_details.append(f"Stop Loss order {order_id[:8]}...")

                    logger.info(f"✅ Cancelled order {order_id[:8]}...")
                else:
                    logger.warning(f"⚠️ Failed to cancel order {order_id[:8]}...")

        # Send alert for TP1 early hit
        if ctx_app and hasattr(ctx_app, 'bot') and cancelled_orders:
            chat_id = chat_data.get('chat_id') or chat_data.get('_chat_id')
            if chat_id:
                await send_trade_alert(
                    bot=ctx_app.bot,
                    chat_id=chat_id,
                    alert_type="tp1_early_hit",
                    symbol=symbol,
                    side=side,
                    approach=approach,
                    pnl=Decimal("0"),  # No P&L for early TP1
                    entry_price=Decimal("0"),
                    current_price=Decimal("0"),
                    position_size=Decimal("0"),
                    cancelled_orders=cancelled_order_details,
                    additional_info={
                        "total_cancelled": len(cancelled_orders)
                    }
                )

        logger.info(f"🚨 {approach.capitalize()} TP1 early hit - cancelled {len(cancelled_orders)} orders")

    except Exception as e:
        logger.error(f"Error cancelling {approach} orders on TP1 hit: {e}")

    return cancelled_orders

async def cancel_remaining_conservative_limits_only(chat_data: dict, symbol: str, ctx_app=None) -> List[str]:
    """
    Cancel only remaining unfilled limit orders when TP1 hits after some fills (Scenario 2)
    Keeps: All TPs (TP2, TP3, TP4) and SL active
    ADDED: Send alert when TP1 hits with fills
    """
    cancelled_orders = []
    cancelled_order_details = []

    try:
        approach = chat_data.get(TRADING_APPROACH, "conservative")
        side = chat_data.get(SIDE, "Unknown")

        # Only cancel unfilled limit orders
        limit_order_ids = chat_data.get(LIMIT_ORDER_IDS, [])
        filled_limits = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])

        cancellation_tasks = []
        unfilled_limits = []

        for order_id in limit_order_ids:
            if order_id not in filled_limits:
                unfilled_limits.append(order_id)
                cancellation_tasks.append(cancel_order_with_retry(symbol, order_id))

        # Execute cancellations in parallel
        if cancellation_tasks:
            results = await asyncio.gather(*cancellation_tasks, return_exceptions=True)

            for order_id, result in zip(unfilled_limits, results):
                if not isinstance(result, Exception) and result:
                    cancelled_orders.append(order_id)
                    cancelled_order_details.append(f"Unfilled limit {order_id[:8]}...")
                    logger.info(f"✅ Cancelled unfilled limit {order_id[:8]}...")
                else:
                    logger.warning(f"⚠️ Failed to cancel limit {order_id[:8]}...")

        # Send alert for TP1 hit with fills
        if ctx_app and hasattr(ctx_app, 'bot'):
            chat_id = chat_data.get('chat_id') or chat_data.get('_chat_id')
            if chat_id:
                await send_trade_alert(
                    bot=ctx_app.bot,
                    chat_id=chat_id,
                    alert_type="tp1_with_fills",
                    symbol=symbol,
                    side=side,
                    approach=approach,
                    pnl=Decimal("0"),  # No P&L yet
                    entry_price=Decimal("0"),
                    current_price=Decimal("0"),
                    position_size=Decimal("0"),
                    cancelled_orders=cancelled_order_details,
                    additional_info={
                        "filled_count": len(filled_limits),
                        "total_limits": len(limit_order_ids)
                    }
                )

        logger.info(f"🎯 Conservative TP1 with fills - cancelled {len(cancelled_orders)} unfilled limits")
        logger.info(f"✅ Keeping TP2, TP3, TP4 and SL orders active")

    except Exception as e:
        logger.error(f"Error cancelling remaining conservative limits: {e}")

    return cancelled_orders

async def check_conservative_other_tp_hits(chat_data: dict, symbol: str, current_price: Decimal, side: str, ctx_app=None) -> bool:
    """
    Check if TP2, TP3, or TP4 have been hit for conservative approach
    ADDED: Send alerts for each TP hit
    """
    try:
        approach = chat_data.get(TRADING_APPROACH, "conservative")
        if approach not in ["conservative", "ggshot"]:
            return False

        # Get TP order IDs
        tp_order_ids = chat_data.get(CONSERVATIVE_TP_ORDER_IDS, [])
        if not tp_order_ids and approach == "ggshot":
            tp_order_ids = chat_data.get(GGSHOT_TP_ORDER_IDS, [])

        if len(tp_order_ids) < 2:  # Need at least TP2
            return False

        # Track which TPs have been hit
        tps_hit = chat_data.get("conservative_tps_hit", [])

        hit_any = False

        # Check TP2, TP3, TP4 (skip TP1 which is index 0)
        for i, tp_order_id in enumerate(tp_order_ids[1:], start=2):
            if tp_order_id and f"TP{i}" not in tps_hit:
                tp_info = await get_order_info(symbol, tp_order_id)
                if tp_info:
                    tp_status = tp_info.get("orderStatus", "")
                    if tp_status in ["Filled", "PartiallyFilled"]:
                        # TP hit!
                        tps_hit.append(f"TP{i}")
                        hit_any = True

                        # Calculate P&L for this TP
                        entry_price = safe_decimal_conversion(chat_data.get(PRIMARY_ENTRY_PRICE, "0"))
                        tp_price = safe_decimal_conversion(tp_info.get("triggerPrice", "0"))
                        tp_qty = safe_decimal_conversion(tp_info.get("cumExecQty", "0"))

                        if side == "Buy":
                            pnl = (tp_price - entry_price) * tp_qty
                        else:  # Sell
                            pnl = (entry_price - tp_price) * tp_qty

                        logger.info(f"🎯 {approach.capitalize()} TP{i} hit at {tp_price} for {symbol}")

                        # VERIFICATION: Store position data before sending alert
                        position_before = {
                            "size": str(position_size),
                            "side": side
                        }

                        # Send alert
                        if ctx_app and hasattr(ctx_app, 'bot'):
                            chat_id = chat_data.get('chat_id') or chat_data.get('_chat_id')
                            if chat_id:
                                # Get remaining active TPs
                                remaining_tps = []
                                for j, tp_id in enumerate(tp_order_ids, start=1):
                                    if f"TP{j}" not in tps_hit and tp_id:
                                        remaining_tps.append(f"TP{j}")

                                position_size = safe_decimal_conversion(chat_data.get(LAST_KNOWN_POSITION_SIZE, "0"))

                                await send_trade_alert(
                                    bot=ctx_app.bot,
                                    chat_id=chat_id,
                                    alert_type="tp_hit",
                                    symbol=symbol,
                                    side=side,
                                    approach=approach,
                                    pnl=pnl,
                                    entry_price=entry_price,
                                    current_price=tp_price,
                                    position_size=tp_qty,
                                    cancelled_orders=[],
                                    additional_info={
                                        "tp_number": i,
                                        "remaining_tps": remaining_tps
                                    }
                                )

                        # VERIFICATION: Check actual position reduction after TP execution
                        # Wait a moment for order to fully execute
                        await asyncio.sleep(1.0)

                        # Get updated position
                        positions_after = await get_position_info(symbol)
                        position_after = None
                        if positions_after:
                            position_after = next((p for p in positions_after if float(p.get("size", 0)) > 0),
                                                {"size": "0"})
                        else:
                            position_after = {"size": "0"}

                        # Verify TP execution
                        tp_percentages = [0.85, 0.05, 0.05, 0.05]  # Conservative TP percentages
                        expected_percentage = tp_percentages[i-1] if i <= len(tp_percentages) else 0.05

                        verification_result = await tp_execution_verifier.verify_tp_execution(
                            symbol=symbol,
                            tp_number=i,
                            expected_percentage=expected_percentage,
                            position_before=position_before,
                            position_after=position_after,
                            chat_data=chat_data
                        )

                        if not verification_result.get("verified"):
                            logger.error(f"❌ TP{i} execution verification failed for {symbol}!")
                            # Send alert about verification failure
                            if ctx_app and hasattr(ctx_app, 'bot') and chat_id:
                                error_msg = (
                                    f"⚠️ <b>TP{i} EXECUTION WARNING</b>\n"
                                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                    f"Expected to close: {expected_percentage*100:.0f}%\n"
                                    f"Actually closed: {verification_result.get('actual_percentage', 0)*100:.1f}%\n"
                                    f"Position before: {verification_result.get('size_before', 0):.4f}\n"
                                    f"Position after: {verification_result.get('size_after', 0):.4f}\n"
                                )

                                if verification_result.get("corrective_action", {}).get("action") == "corrective_order_placed":
                                    error_msg += (
                                        f"\n✅ <b>Corrective action taken:</b>\n"
                                        f"Placed market order to close additional "
                                        f"{verification_result['corrective_action']['qty']:.4f} units"
                                    )

                                try:
                                    await ctx_app.bot.send_message(
                                        chat_id=chat_id,
                                        text=error_msg,
                                        parse_mode="HTML"
                                    )
                                except Exception as e:
                                    logger.error(f"Failed to send TP verification warning: {e}")

                        # Update position size in chat_data based on actual reduction
                        actual_size_after = safe_decimal_conversion(position_after.get("size", "0"))
                        chat_data[LAST_KNOWN_POSITION_SIZE] = actual_size_after
                        # Store approach-specific position size
                        chat_data[f"{approach}_position_size"] = actual_size_after

                        # Trigger Conservative rebalancing after TP hit
                        try:
                            from execution.conservative_rebalancer import rebalance_conservative_on_tp_hit

                            logger.info(f"🔄 Triggering Conservative rebalance for {symbol} after TP{i} hit")
                            rebalance_result = await rebalance_conservative_on_tp_hit(
                                chat_data=chat_data,
                                symbol=symbol,
                                tp_number=i,
                                ctx_app=ctx_app
                            )

                            if rebalance_result.get("success"):
                                logger.info(f"✅ Conservative rebalance completed after TP{i} hit")
                            else:
                                logger.error(f"❌ Conservative rebalance failed: {rebalance_result.get('error')}")

                        except Exception as e:
                            logger.error(f"Error triggering Conservative rebalance after TP hit: {e}")

        # Update chat data
        chat_data["conservative_tps_hit"] = tps_hit

        return hit_any

    except Exception as e:
        logger.error(f"Error checking conservative TP hits: {e}")
        return False

async def check_conservative_sl_hit(chat_data: dict, symbol: str, current_price: Decimal, side: str, ctx_app=None) -> bool:
    """
    Check if SL has been hit for conservative approach
    ADDED: Send alert with total loss and cancelled orders
    """
    try:
        approach = chat_data.get(TRADING_APPROACH, "conservative")
        if approach not in ["conservative", "ggshot"]:
            return False

        # Check if SL already processed
        if chat_data.get("conservative_sl_hit_processed", False):
            return False

        # Get SL order ID
        sl_order_id = chat_data.get(CONSERVATIVE_SL_ORDER_ID)
        if not sl_order_id and approach == "ggshot":
            sl_order_id = chat_data.get(GGSHOT_SL_ORDER_ID)

        if not sl_order_id:
            return False

        # Check SL order status
        sl_info = await get_order_info(symbol, sl_order_id)
        if not sl_info:
            return False

        sl_status = sl_info.get("orderStatus", "")
        if sl_status in ["Filled", "PartiallyFilled"]:
            logger.info(f"🛡️ {approach.capitalize()} SL HIT for {symbol}")

            # Get position info for alert
            entry_price = safe_decimal_conversion(chat_data.get(PRIMARY_ENTRY_PRICE, "0"))
            sl_price = safe_decimal_conversion(sl_info.get("triggerPrice", "0"))
            position_size = safe_decimal_conversion(chat_data.get(LAST_KNOWN_POSITION_SIZE, "0"))

            # Calculate total loss
            if side == "Buy":
                pnl = (sl_price - entry_price) * position_size
            else:  # Sell
                pnl = (entry_price - sl_price) * position_size

            # Cancel all remaining orders
            cancelled_orders = []
            cancelled_order_details = []

            # Cancel unfilled limits
            limit_order_ids = chat_data.get(LIMIT_ORDER_IDS, [])
            filled_limits = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])

            for order_id in limit_order_ids:
                if order_id not in filled_limits:
                    success = await cancel_order_with_retry(symbol, order_id)
                    if success:
                        cancelled_orders.append(order_id)
                        cancelled_order_details.append(f"Unfilled limit {order_id[:8]}...")

            # Cancel remaining TPs
            tp_order_ids = chat_data.get(CONSERVATIVE_TP_ORDER_IDS, [])
            if not tp_order_ids and approach == "ggshot":
                tp_order_ids = chat_data.get(GGSHOT_TP_ORDER_IDS, [])

            tps_hit = chat_data.get("conservative_tps_hit", [])

            for i, tp_order_id in enumerate(tp_order_ids, start=1):
                if tp_order_id and f"TP{i}" not in tps_hit:
                    success = await cancel_order_with_retry(symbol, tp_order_id)
                    if success:
                        cancelled_orders.append(tp_order_id)
                        cancelled_order_details.append(f"TP{i} order {tp_order_id[:8]}...")

            # Send alert
            if ctx_app and hasattr(ctx_app, 'bot'):
                chat_id = chat_data.get('chat_id') or chat_data.get('_chat_id')
                if chat_id:
                    await send_trade_alert(
                        bot=ctx_app.bot,
                        chat_id=chat_id,
                        alert_type="sl_hit",
                        symbol=symbol,
                        side=side,
                        approach=approach,
                        pnl=pnl,
                        entry_price=entry_price,
                        current_price=sl_price,
                        position_size=position_size,
                        cancelled_orders=cancelled_order_details
                    )

            # Mark SL as processed
            chat_data["conservative_sl_hit_processed"] = True
            return True

        return False

    except Exception as e:
        logger.error(f"Error checking conservative SL hit: {e}")
        return False

async def check_mirror_conservative_tp_hits(chat_data: dict, symbol: str) -> bool:
    """
    Check if TP2, TP3, or TP4 have been hit for mirror conservative positions
    Triggers rebalancing when TPs are hit
    """
    try:
        approach = chat_data.get(TRADING_APPROACH, "conservative")
        if approach not in ["conservative", "ggshot"]:
            return False

        # Get mirror TP order IDs
        tp_order_ids = chat_data.get("mirror_conservative_tp_order_ids", [])
        if not tp_order_ids:
            return False

        # Track which TPs have been hit
        mirror_tps_hit = chat_data.get("mirror_conservative_tps_hit", [])

        hit_any = False

        # Check TP2, TP3, TP4 (skip TP1 which is index 0)
        for i, tp_order_id in enumerate(tp_order_ids[1:], start=2):
            if tp_order_id and f"TP{i}" not in mirror_tps_hit:
                # Get order info from mirror account
                from clients.bybit_helpers import get_order_info_mirror
                tp_info = await get_order_info_mirror(symbol, tp_order_id)

                if tp_info:
                    tp_status = tp_info.get("orderStatus", "")
                    if tp_status in ["Filled", "PartiallyFilled"]:
                        # TP hit!
                        mirror_tps_hit.append(f"TP{i}")
                        hit_any = True

                        logger.info(f"🎯 MIRROR {approach.capitalize()} TP{i} hit for {symbol}")

                        # Trigger mirror rebalancing
                        try:
                            from execution.conservative_rebalancer import rebalance_conservative_mirror

                            logger.info(f"🔄 Triggering MIRROR Conservative rebalance after TP{i} hit")
                            mirror_rebalance_result = await rebalance_conservative_mirror(
                                chat_data=chat_data,
                                symbol=symbol,
                                trigger="tp_hit",
                                tp_number=i
                            )

                            if mirror_rebalance_result.get("success"):
                                logger.info(f"✅ MIRROR Conservative rebalance completed after TP{i} hit")
                            else:
                                logger.error(f"❌ MIRROR Conservative rebalance failed: {mirror_rebalance_result.get('error')}")

                        except Exception as e:
                            logger.error(f"Error triggering MIRROR Conservative rebalance: {e}")

        # Update chat data
        chat_data["mirror_conservative_tps_hit"] = mirror_tps_hit

        return hit_any

    except Exception as e:
        logger.error(f"Error checking mirror conservative TP hits: {e}")
        return False

# =============================================
# PERIODIC CLEANUP TASK
# =============================================

async def periodic_monitor_cleanup():
    """Periodic cleanup of stale monitors and memory"""
    while True:
        try:
            await asyncio.sleep(600)  # Run every 10 minutes

            # Cleanup stale tasks
            _task_registry.cleanup_stale_tasks()

            # Force garbage collection
            gc.collect()

            # Log stats
            stats = _task_registry.get_stats()
            logger.info(f"🧹 Monitor cleanup: {stats['active_tasks']} active tasks, {stats['running_tasks']} running")

        except Exception as e:
            logger.error(f"Error in periodic monitor cleanup: {e}")
            await asyncio.sleep(60)  # Wait before retrying

def start_monitor_cleanup_task():
    """Start the periodic monitor cleanup task"""
    try:
        asyncio.create_task(periodic_monitor_cleanup())
        logger.info("✅ Monitor cleanup task started")
    except Exception as e:
        logger.error(f"Error starting monitor cleanup task: {e}")

# Export main functions including periodic_monitor_cleanup for imports
__all__ = [
    'start_position_monitoring',
    'stop_position_monitoring',
    'get_monitoring_status',
    'get_monitor_registry_stats',
    'get_monitor_counts_by_approach',
    'register_monitor_task',
    'unregister_monitor_task',
    'get_monitor_task_status',
    'get_monitoring_mode',
    'periodic_monitor_cleanup',
    'start_monitor_cleanup_task',
    'get_trade_history_summary',
    'check_conservative_limit_fills',
    'check_conservative_tp1_hit',
    'check_conservative_tp1_hit_with_fills',
    'cancel_conservative_orders_on_tp1_hit',
    'cancel_remaining_conservative_limits_only'
]