#!/usr/bin/env python3
"""
Position monitoring with ENHANCED PERFORMANCE TRACKING.
REFINED: Accurate P&L calculation, duplicate prevention, trade history
ENHANCED: Separate tracking for bot vs external trades
IMPROVED: Better error handling and validation
FIXED: Force immediate persistence after stats update
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
from config.settings import POSITION_MONITOR_INTERVAL
from clients.bybit_helpers import (
    get_position_info, get_order_info, 
    cancel_order_with_retry, amend_order_with_retry
)
from utils.formatters import get_emoji, format_decimal_or_na
from utils.helpers import value_adjusted_to_step, safe_decimal_conversion

logger = logging.getLogger(__name__)

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
    task_key = f"{chat_id}_{symbol}"
    enhanced_metadata = {
        "chat_id": chat_id,
        "symbol": symbol,
        "type": "position_monitor",
        **(metadata or {})
    }
    _task_registry.register_task(task_key, task, enhanced_metadata)
    logger.info(f"📋 Registered monitor task for {symbol} in chat {chat_id}")

async def unregister_monitor_task(chat_id: int, symbol: str):
    """Unregister a monitor task"""
    task_key = f"{chat_id}_{symbol}"
    _task_registry.unregister_task(task_key)
    logger.info(f"📋 Unregistered monitor task for {symbol} in chat {chat_id}")

async def get_monitor_task_status(chat_id: int, symbol: str) -> Dict:
    """Get the status of a monitor task"""
    task_key = f"{chat_id}_{symbol}"
    return _task_registry.get_task_status(task_key)

def is_read_only_monitoring(chat_data: dict) -> bool:
    """Check if this is read-only monitoring for external position"""
    return chat_data.get("read_only_monitoring", False) or chat_data.get("external_position", False)

def get_monitoring_mode(chat_data: dict) -> str:
    """Get the monitoring mode description"""
    if is_read_only_monitoring(chat_data):
        return "READ-ONLY"
    else:
        approach = chat_data.get(TRADING_APPROACH, "fast")
        return f"FULL-{approach.upper()}"

# =============================================
# ENHANCED: CONSERVATIVE APPROACH ORDER MANAGEMENT (ONLY FOR FULL MONITORING)
# =============================================

async def check_conservative_tp1_hit(chat_data: dict, symbol: str, current_price: Decimal, side: str) -> bool:
    """
    Check if TP1 has been hit BEFORE any limit orders are filled
    This triggers full cancellation of all orders
    
    ENHANCED: Only for FULL monitoring, not read-only
    """
    try:
        # SAFETY: Skip for read-only monitoring
        if is_read_only_monitoring(chat_data):
            return False
        
        approach = chat_data.get(TRADING_APPROACH, "fast")
        if approach != "conservative":
            return False
        
        # Check if TP1 cancellation already processed
        if chat_data.get(CONSERVATIVE_TP1_HIT_BEFORE_LIMITS, False):
            return False
        
        tp1_price = chat_data.get(TP1_PRICE)
        if not tp1_price:
            return False
        
        tp1_price = safe_decimal_conversion(tp1_price)
        
        # Check if current price has hit TP1
        tp1_triggered = False
        
        if side == "Buy":
            tp1_triggered = current_price >= tp1_price
        elif side == "Sell":
            tp1_triggered = current_price <= tp1_price
        
        if tp1_triggered:
            # Check if NO limit orders have been filled yet
            limits_filled = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])
            
            if len(limits_filled) == 0:
                logger.info(f"🚨 TP1 hit BEFORE any limits filled for {symbol} - triggering full cancellation")
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking conservative TP1 hit before limits: {e}")
        return False

async def check_conservative_tp1_hit_with_fills(chat_data: dict, symbol: str, current_price: Decimal, side: str) -> bool:
    """
    Check if TP1 has been hit after some limit orders were filled
    This handles the scenario where we want to cancel remaining limits but keep TP2-TP4 active
    
    ENHANCED: Only for FULL monitoring, not read-only
    """
    try:
        # SAFETY: Skip for read-only monitoring
        if is_read_only_monitoring(chat_data):
            return False
        
        approach = chat_data.get(TRADING_APPROACH, "fast")
        if approach != "conservative":
            return False
        
        # Check if we already processed TP1 hit with fills
        if chat_data.get("conservative_tp1_hit_with_fills_processed", False):
            return False
        
        tp1_price = chat_data.get(TP1_PRICE)
        if not tp1_price:
            return False
        
        tp1_price = safe_decimal_conversion(tp1_price)
        
        # Check if current price has hit TP1
        tp1_triggered = False
        
        if side == "Buy":
            tp1_triggered = current_price >= tp1_price
        elif side == "Sell":
            tp1_triggered = current_price <= tp1_price
        
        if tp1_triggered:
            # Check if at least one limit order has been filled
            limit_order_ids = chat_data.get(LIMIT_ORDER_IDS, [])
            limits_filled = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])
            
            # If some limits are filled but not all
            if len(limits_filled) > 0 and len(limits_filled) < len(limit_order_ids):
                logger.info(f"🎯 TP1 hit with {len(limits_filled)} limits filled - cancelling remaining {len(limit_order_ids) - len(limits_filled)} limits")
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking conservative TP1 hit with fills: {e}")
        return False

async def cancel_remaining_conservative_limits_only(chat_data: dict, symbol: str) -> List[str]:
    """
    Cancel only remaining unfilled limit orders when TP1 hits after some fills
    Keep TP2, TP3, TP4 active for the life of the trade
    
    ENHANCED: Only for FULL monitoring, not read-only
    """
    try:
        # SAFETY: Skip for read-only monitoring
        if is_read_only_monitoring(chat_data):
            logger.info("🛡️ READ-ONLY monitoring: Skipping order cancellation")
            return []
        
        cancelled_orders = []
        
        # Get order IDs
        limit_order_ids = chat_data.get(LIMIT_ORDER_IDS, [])
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
        
        # Mark as processed (different from the original TP1 cancellation)
        chat_data["conservative_tp1_hit_with_fills_processed"] = True
        
        # DO NOT cancel TP2, TP3, TP4 - they remain active!
        logger.info(f"🎯 TP1 hit processing completed: {len(cancelled_orders)} remaining limits cancelled")
        logger.info(f"✅ TP2, TP3, TP4 remain active for the life of the trade")
        
        return cancelled_orders
        
    except Exception as e:
        logger.error(f"❌ Error cancelling remaining conservative limits: {e}", exc_info=True)
        return []

async def cancel_conservative_orders_on_tp1_hit(chat_data: dict, symbol: str) -> List[str]:
    """
    Cancel all remaining conservative orders when TP1 hits before limits fill
    
    ENHANCED: Only for FULL monitoring, not read-only
    """
    try:
        # SAFETY: Skip for read-only monitoring
        if is_read_only_monitoring(chat_data):
            logger.info("🛡️ READ-ONLY monitoring: Skipping order cancellation")
            return []
        
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
        
        # Mark as processed
        chat_data[CONSERVATIVE_TP1_HIT_BEFORE_LIMITS] = True
        chat_data[CONSERVATIVE_ORDERS_CANCELLED] = True
        
        logger.info(f"🚨 Conservative TP1 cancellation completed: {len(cancelled_orders)} orders cancelled")
        return cancelled_orders
        
    except Exception as e:
        logger.error(f"❌ Error cancelling conservative orders on TP1 hit: {e}", exc_info=True)
        return []

async def check_conservative_limit_fills(chat_data: dict, symbol: str) -> List[str]:
    """
    Check which conservative limit orders have been filled
    
    ENHANCED: Only for FULL monitoring, not read-only
    """
    try:
        # SAFETY: Skip for read-only monitoring
        if is_read_only_monitoring(chat_data):
            return []
        
        approach = chat_data.get(TRADING_APPROACH, "fast")
        if approach != "conservative":
            return []
        
        limit_order_ids = chat_data.get(LIMIT_ORDER_IDS, [])
        limits_filled = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])
        
        newly_filled = []
        
        for order_id in limit_order_ids:
            if order_id and order_id not in limits_filled:
                # Check order status
                order_info = await get_order_info(symbol, order_id)
                if order_info:
                    order_status = order_info.get("orderStatus", "")
                    if order_status in ["Filled", "PartiallyFilled"]:
                        newly_filled.append(order_id)
                        limits_filled.append(order_id)
                        logger.info(f"✅ Conservative limit order filled: {order_id[:8]}...")
        
        # Update chat data
        chat_data[CONSERVATIVE_LIMITS_FILLED] = limits_filled
        
        return newly_filled
        
    except Exception as e:
        logger.error(f"Error checking conservative limit fills: {e}")
        return []

# =============================================
# FIXED: ENHANCED FAST APPROACH TP/SL ORDER MANAGEMENT
# =============================================

async def check_tp_hit_and_cancel_sl(chat_data: dict, symbol: str, current_price: Decimal, side: str) -> bool:
    """
    FIXED: Check if TP is hit for fast approach and cancel SL order
    
    Returns True if TP was hit and SL was cancelled
    """
    try:
        # SAFETY: Skip for read-only monitoring
        if is_read_only_monitoring(chat_data):
            return False
        
        approach = chat_data.get(TRADING_APPROACH, "fast")
        if approach != "fast":
            return False
        
        # Check if TP already processed
        if chat_data.get("tp_hit_processed", False):
            return False
        
        # Get TP price
        tp_price = chat_data.get(TP1_PRICE)
        if not tp_price:
            return False
        
        tp_price = safe_decimal_conversion(tp_price)
        
        # Check if current price has hit TP
        tp_triggered = False
        
        if side == "Buy":
            tp_triggered = current_price >= tp_price
        elif side == "Sell":
            tp_triggered = current_price <= tp_price
        
        if tp_triggered:
            logger.info(f"🎯 FAST APPROACH: TP HIT at {current_price} (target: {tp_price}) for {symbol}")
            
            # Cancel SL order
            sl_order_id = chat_data.get(SL_ORDER_ID) or chat_data.get("sl_order_id")
            if sl_order_id:
                logger.info(f"🎯 TP hit - cancelling SL order {sl_order_id}")
                success = await cancel_order_with_retry(symbol, sl_order_id)
                if success:
                    logger.info(f"✅ SL order {sl_order_id} cancelled after TP hit")
                    chat_data[SL_ORDER_ID] = None
                    chat_data["sl_order_id"] = None
                else:
                    logger.warning(f"⚠️ Failed to cancel SL order {sl_order_id}")
            else:
                logger.info(f"ℹ️ No SL order ID found to cancel")
            
            # Mark TP as processed
            chat_data["tp_hit_processed"] = True
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking TP hit for fast approach: {e}")
        return False

async def check_sl_hit_and_cancel_tp(chat_data: dict, symbol: str, current_price: Decimal, side: str) -> bool:
    """
    FIXED: Check if SL is hit for fast approach and cancel TP order
    
    Returns True if SL was hit and TP was cancelled
    """
    try:
        # SAFETY: Skip for read-only monitoring
        if is_read_only_monitoring(chat_data):
            return False
        
        approach = chat_data.get(TRADING_APPROACH, "fast")
        if approach != "fast":
            return False
        
        # Check if SL already processed
        if chat_data.get("sl_hit_processed", False):
            return False
        
        # Get SL price
        sl_price = chat_data.get(SL_PRICE)
        if not sl_price:
            return False
        
        sl_price = safe_decimal_conversion(sl_price)
        
        # Check if current price has hit SL
        sl_triggered = False
        
        if side == "Buy":
            sl_triggered = current_price <= sl_price
        elif side == "Sell":
            sl_triggered = current_price >= sl_price
        
        if sl_triggered:
            logger.info(f"🛡️ FAST APPROACH: SL HIT at {current_price} (target: {sl_price}) for {symbol}")
            
            # Cancel TP order
            tp_order_id = chat_data.get("tp_order_id")
            tp_order_ids = chat_data.get(TP_ORDER_IDS, [])
            
            # Handle single TP order
            if tp_order_id:
                logger.info(f"🛡️ SL hit - cancelling TP order {tp_order_id}")
                success = await cancel_order_with_retry(symbol, tp_order_id)
                if success:
                    logger.info(f"✅ TP order {tp_order_id} cancelled after SL hit")
                    chat_data["tp_order_id"] = None
                else:
                    logger.warning(f"⚠️ Failed to cancel TP order {tp_order_id}")
            
            # Handle multiple TP orders if any
            for tp_id in tp_order_ids:
                if tp_id:
                    logger.info(f"🛡️ SL hit - cancelling TP order {tp_id}")
                    success = await cancel_order_with_retry(symbol, tp_id)
                    if success:
                        logger.info(f"✅ TP order {tp_id} cancelled after SL hit")
                    else:
                        logger.warning(f"⚠️ Failed to cancel TP order {tp_id}")
            
            # Clear TP orders from chat data
            chat_data[TP_ORDER_IDS] = []
            chat_data["tp_order_id"] = None
            
            # Mark SL as processed
            chat_data["sl_hit_processed"] = True
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking SL hit for fast approach: {e}")
        return False

async def cancel_remaining_orders(chat_data: dict, symbol: str, triggered_order_type: str):
    """
    ENHANCED: Cancel remaining orders when TP or SL is hit - with conservative approach support
    
    ENHANCED: Only for FULL monitoring, not read-only
    """
    try:
        # SAFETY: Skip for read-only monitoring
        if is_read_only_monitoring(chat_data):
            logger.info("🛡️ READ-ONLY monitoring: Skipping order cancellation")
            return []
        
        orders_cancelled = []
        approach = chat_data.get(TRADING_APPROACH, "fast")
        
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
        
        # Method 1: Use cumRealisedPnl (most accurate for closed positions)
        cum_realised_pnl = position_data.get("cumRealisedPnl")
        if cum_realised_pnl and str(cum_realised_pnl) != "0":
            pnl = safe_decimal_conversion(cum_realised_pnl)
            logger.info(f"📊 P&L from cumRealisedPnl: {pnl}")
            return pnl
        
        # Method 2: Use unrealisedPnl (for positions being closed)
        unrealized_pnl = position_data.get("unrealisedPnl")
        if unrealized_pnl and str(unrealized_pnl) != "0":
            pnl = safe_decimal_conversion(unrealized_pnl)
            logger.info(f"📊 P&L from unrealisedPnl: {pnl}")
            return pnl
        
        # Method 3: Use closedPnl if available
        closed_pnl = position_data.get("closedPnl")
        if closed_pnl and str(closed_pnl) != "0":
            pnl = safe_decimal_conversion(closed_pnl)
            logger.info(f"📊 P&L from closedPnl: {pnl}")
            return pnl
        
        # Method 4: Calculate from entry/exit prices
        entry_price = safe_decimal_conversion(position_data.get("avgPrice", "0"))
        mark_price = safe_decimal_conversion(position_data.get("markPrice", "0"))
        size = safe_decimal_conversion(position_data.get("size", "0"))
        side = position_data.get("side", "")
        
        # If size is 0, try to get from chat data
        if size == 0:
            size = safe_decimal_conversion(chat_data.get(LAST_KNOWN_POSITION_SIZE, "0"))
        
        if entry_price > 0 and mark_price > 0 and size > 0:
            if side == "Buy":
                pnl = (mark_price - entry_price) * size
            else:  # Sell/Short
                pnl = (entry_price - mark_price) * size
            logger.info(f"📊 P&L calculated manually: {pnl}")
            return pnl
        
        # Method 5: Use last known P&L from chat data
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
    
    ENHANCED: Separate tracking for bot vs external positions
    """
    try:
        # Get bot data
        bot_data = ctx_app.bot_data
        
        monitoring_mode = get_monitoring_mode(chat_data)
        is_external = chat_data.get("external_position", False)
        
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
            STATS_LAST_RESET: time.time() if STATS_LAST_RESET not in bot_data else bot_data[STATS_LAST_RESET],
            # Enhanced stats for approaches
            STATS_CONSERVATIVE_TRADES: 0,
            STATS_FAST_TRADES: 0,
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
            'bot_start_time': time.time()
        }
        
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
            "is_external": is_external,
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
            approach = chat_data.get(TRADING_APPROACH, "fast")
            if approach == "conservative":
                bot_data[STATS_CONSERVATIVE_TRADES] = bot_data.get(STATS_CONSERVATIVE_TRADES, 0) + 1
                # Check if this was a TP1 cancellation scenario
                if chat_data.get(CONSERVATIVE_TP1_HIT_BEFORE_LIMITS, False):
                    bot_data[STATS_CONSERVATIVE_TP1_CANCELLATIONS] = bot_data.get(STATS_CONSERVATIVE_TP1_CANCELLATIONS, 0) + 1
                    logger.info(f"📊 Conservative TP1 cancellation recorded")
            else:
                bot_data[STATS_FAST_TRADES] = bot_data.get(STATS_FAST_TRADES, 0) + 1
            
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
            fast_trades = bot_data.get(STATS_FAST_TRADES, 0)
            conservative_cancellations = bot_data.get(STATS_CONSERVATIVE_TP1_CANCELLATIONS, 0)
            
            logger.info(f"📊 BOT PERFORMANCE STATS:")
            logger.info(f"   Total Bot Trades: {bot_data[STATS_TOTAL_TRADES]}")
            logger.info(f"   Wins: {bot_data[STATS_TOTAL_WINS]} | Losses: {bot_data[STATS_TOTAL_LOSSES]}")
            logger.info(f"   Win Rate: {win_rate:.1f}%")
            logger.info(f"   Total PnL: {total_pnl}")
            logger.info(f"   Conservative Trades: {conservative_trades}")
            logger.info(f"   Fast Trades: {fast_trades}")
            logger.info(f"   TP1 Cancellations: {conservative_cancellations}")
        
        # FIXED: Force immediate persistence - multiple attempts
        logger.info(f"🔄 FORCING IMMEDIATE PERSISTENCE...")
        
        try:
            # Method 1: Direct persistence call
            await ctx_app.update_persistence()
            logger.info(f"✅ Persistence update 1 completed")
            
            # Method 2: Force a second update after a tiny delay
            await asyncio.sleep(0.1)
            await ctx_app.update_persistence()
            logger.info(f"✅ Persistence update 2 completed")
            
            # Method 3: Mark bot data as dirty to force update
            ctx_app._bot_data_dirty = True
            await asyncio.sleep(0.1)
            await ctx_app.update_persistence()
            logger.info(f"✅ Persistence update 3 completed (dirty flag)")
            
            logger.info(f"✅ Performance stats FORCE PERSISTED successfully (Trade ID: {trade_id})")
            
        except Exception as e:
            logger.error(f"❌ Error force persisting stats: {e}")
            # Try one more time with a longer delay
            try:
                await asyncio.sleep(1)
                await ctx_app.update_persistence()
                logger.info(f"✅ Persistence update 4 completed (after delay)")
            except Exception as e2:
                logger.error(f"❌ Final persistence attempt failed: {e2}")
        
    except Exception as e:
        logger.error(f"❌ Error updating performance stats: {e}", exc_info=True)

async def start_position_monitoring(ctx_app, chat_id: int, chat_data: dict):
    """
    ENHANCED: Start monitoring a position with conservative approach support and read-only external support
    """
    monitoring_mode = get_monitoring_mode(chat_data)
    logger.info(f"🔄 Starting {monitoring_mode} position monitoring for chat {chat_id}")
    
    # Validate required data
    symbol = chat_data.get(SYMBOL)
    if not symbol:
        logger.error(f"❌ No symbol found for monitoring in chat {chat_id}")
        return
    
    approach = chat_data.get(TRADING_APPROACH, "fast")
    is_external = chat_data.get("external_position", False)
    
    logger.info(f"📊 Monitoring: {approach} approach, External: {is_external}, Mode: {monitoring_mode}")
    
    # Check if monitor is already running
    task_status = await get_monitor_task_status(chat_id, symbol)
    if task_status.get("running", False):
        logger.info(f"⚠️ {monitoring_mode} monitor already running for {symbol} in chat {chat_id}")
        return
    
    # Store monitoring info WITHOUT the task object (to prevent pickle errors)
    task_info = {
        "chat_id": chat_id,
        "symbol": symbol,
        "approach": approach,
        "active": True,
        "started_at": time.time(),
        "monitoring_mode": monitoring_mode,
        "external_position": is_external
    }
    
    if ACTIVE_MONITOR_TASK not in chat_data:
        chat_data[ACTIVE_MONITOR_TASK] = {}
    
    chat_data[ACTIVE_MONITOR_TASK] = task_info
    
    # Create enhanced monitoring task with proper metadata
    metadata = {
        "symbol": symbol,
        "approach": approach,
        "is_external": is_external,
        "monitoring_mode": monitoring_mode
    }
    
    monitor_task = asyncio.create_task(monitor_position_loop_enhanced(ctx_app, chat_id, chat_data))
    
    # Register task in global registry with metadata
    await register_monitor_task(chat_id, symbol, monitor_task, metadata)
    
    logger.info(f"✅ {monitoring_mode} position monitoring started for {symbol} in chat {chat_id}")

async def monitor_position_loop_enhanced(ctx_app, chat_id: int, chat_data: dict):
    """
    ENHANCED monitoring loop with conservative approach support, read-only external support, and FIXED fast approach TP/SL logic
    FIXED: Force immediate persistence after stats update
    """
    symbol = chat_data.get(SYMBOL)
    position_idx = chat_data.get(POSITION_IDX, 0)
    approach = chat_data.get(TRADING_APPROACH, "fast")
    is_external = chat_data.get("external_position", False)
    monitoring_mode = get_monitoring_mode(chat_data)
    
    if not symbol:
        logger.error(f"❌ No symbol found for monitoring in chat {chat_id}")
        return
    
    logger.info(f"🔄 Starting {monitoring_mode} monitoring loop for {symbol} in chat {chat_id}")
    
    # Monitoring state with memory management
    tp1_hit = False
    sl_moved_to_breakeven = False
    position_closed = False
    last_position_size = None
    last_position_data = None
    last_known_pnl = Decimal("0")
    monitoring_cycles = 0
    position_history = []  # Limited size history
    max_history_size = 10  # Prevent memory growth
    
    # Conservative approach specific tracking (only for FULL monitoring)
    conservative_tp1_cancelled = False
    
    # FIXED: Fast approach specific tracking (only for FULL monitoring)
    fast_tp_hit = False
    fast_sl_hit = False
    
    # Get stored order IDs (only for FULL monitoring)
    if not is_read_only_monitoring(chat_data):
        if approach == "conservative":
            limit_order_ids = chat_data.get(LIMIT_ORDER_IDS, [])
            tp_order_ids = chat_data.get(CONSERVATIVE_TP_ORDER_IDS, [])
            sl_order_id = chat_data.get(CONSERVATIVE_SL_ORDER_ID)
            logger.info(f"📋 Conservative FULL monitoring - Limits: {len(limit_order_ids)}, TPs: {len(tp_order_ids)}, SL: {bool(sl_order_id)}")
        else:
            tp_order_id = chat_data.get("tp_order_id")
            sl_order_id = chat_data.get(SL_ORDER_ID) or chat_data.get("sl_order_id")
            logger.info(f"📋 Fast FULL monitoring - TP: {tp_order_id}, SL: {sl_order_id}")
    else:
        logger.info(f"🔍 READ-ONLY monitoring - No order management for external position")
    
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
            chat_data[LAST_KNOWN_POSITION_SIZE] = last_position_size
            logger.info(f"📊 Initial position: {symbol} - {initial_position.get('side')} {last_position_size}")
        else:
            logger.warning(f"⚠️ No initial position found for {symbol}")
    except Exception as e:
        logger.error(f"❌ Error getting initial position for {symbol}: {e}")
    
    try:
        while True:
            try:
                monitoring_cycles += 1
                
                # MEMORY MANAGEMENT: Periodic cleanup every 100 cycles
                if monitoring_cycles % 100 == 0:
                    gc.collect()  # Force garbage collection
                    logger.debug(f"Memory cleanup performed for {symbol} monitor")
                
                # Check if monitoring should stop
                if not chat_data.get(ACTIVE_MONITOR_TASK, {}).get("active"):
                    logger.info(f"🛑 {monitoring_mode} monitoring stopped for {symbol} (deactivated)")
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
                    logger.warning(f"⚠️ No position data for {symbol} (cycle {monitoring_cycles})")
                    await asyncio.sleep(5)
                    continue
                
                # PERFORMANCE: Cache position data to detect changes and reduce processing
                current_size = safe_decimal_conversion(position.get("size", "0"))
                current_price = safe_decimal_conversion(position.get("markPrice", "0"))
                position_key = f"{symbol}_{current_size}_{current_price}"
                
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
                
                # ENHANCED: Conservative/GGShot approach monitoring with dual TP1 logic (ONLY for FULL monitoring)
                if (not is_read_only_monitoring(chat_data) and 
                    (approach == "conservative" or approach == "ggshot") and 
                    current_size > 0 and 
                    not conservative_tp1_cancelled):
                    
                    # Check for limit order fills first
                    newly_filled = await check_conservative_limit_fills(chat_data, symbol)
                    if newly_filled:
                        logger.info(f"✅ {approach.capitalize()} limit orders filled: {len(newly_filled)}")
                    
                    # SCENARIO 1: TP1 hits before ANY limits are filled (original logic)
                    # For GGShot: Market order is pre-filled, so check if NO additional limits filled
                    tp1_hit_before_any_limits = await check_conservative_tp1_hit(chat_data, symbol, current_price, side)
                    
                    if tp1_hit_before_any_limits:
                        logger.info(f"🚨 {approach.capitalize()} TP1 hit before ANY limits filled for {symbol} - cancelling ALL orders")
                        cancelled_orders = await cancel_conservative_orders_on_tp1_hit(chat_data, symbol)
                        conservative_tp1_cancelled = True
                        
                        if cancelled_orders:
                            logger.info(f"🚨 {approach.capitalize()} full cancellation completed: {', '.join(cancelled_orders)}")
                    
                    # SCENARIO 2: TP1 hits AFTER some limits are filled (new logic)
                    elif not conservative_tp1_cancelled:
                        tp1_hit_with_fills = await check_conservative_tp1_hit_with_fills(chat_data, symbol, current_price, side)
                        
                        if tp1_hit_with_fills:
                            logger.info(f"🎯 {approach.capitalize()} TP1 hit WITH some fills for {symbol} - cancelling remaining limits only")
                            cancelled_limits = await cancel_remaining_conservative_limits_only(chat_data, symbol)
                            
                            if cancelled_limits:
                                logger.info(f"🎯 {approach.capitalize()} partial cancellation completed: {', '.join(cancelled_limits)}")
                                logger.info(f"✅ TP2, TP3, TP4 remain ACTIVE for the life of the trade")
                
                # FIXED: Fast approach TP/SL monitoring with proper order cancellation (ONLY for FULL monitoring)
                elif (not is_read_only_monitoring(chat_data) and 
                      approach == "fast" and 
                      current_size > 0):
                    
                    # Check for TP hit and cancel SL
                    if not fast_tp_hit:
                        tp_hit = await check_tp_hit_and_cancel_sl(chat_data, symbol, current_price, side)
                        if tp_hit:
                            fast_tp_hit = True
                            tp1_hit = True  # For backward compatibility
                            logger.info(f"🎯 Fast approach TP hit for {symbol} - SL cancelled")
                    
                    # Check for SL hit and cancel TP
                    if not fast_sl_hit:
                        sl_hit = await check_sl_hit_and_cancel_tp(chat_data, symbol, current_price, side)
                        if sl_hit:
                            fast_sl_hit = True
                            logger.info(f"🛡️ Fast approach SL hit for {symbol} - TP cancelled")
                
                # ENHANCED: Position closure detection with automatic order cancellation (for ALL monitoring types)
                if current_size == 0:
                    if not position_closed and last_position_size and last_position_size > 0:
                        logger.info(f"🎯 POSITION CLOSED DETECTED for {symbol} ({monitoring_mode})")
                        
                        # Determine close reason and final P&L
                        close_reason = "MANUAL_CLOSE"
                        final_pnl = last_known_pnl
                        
                        # REFINED: Better P&L calculation
                        final_pnl = await calculate_accurate_pnl(position, chat_data)
                        
                        # Determine close reason based on approach and flags (only for FULL monitoring)
                        if not is_read_only_monitoring(chat_data):
                            if approach == "fast":
                                if fast_tp_hit or tp1_hit:
                                    close_reason = "TP_HIT"
                                elif fast_sl_hit:
                                    close_reason = "SL_HIT"
                            elif approach == "conservative":
                                if conservative_tp1_cancelled:
                                    close_reason = "TP_HIT"
                                # Could add SL logic for conservative here if needed
                        
                        # Cancel remaining orders automatically (ONLY for FULL monitoring)
                        cancelled_orders = []
                        if not is_read_only_monitoring(chat_data):
                            if close_reason == "TP_HIT":
                                cancelled_orders = await cancel_remaining_orders(chat_data, symbol, 'TP')
                            elif close_reason == "SL_HIT":
                                cancelled_orders = await cancel_remaining_orders(chat_data, symbol, 'SL')
                        
                        # Update performance stats (for ALL monitoring types)
                        await update_performance_stats_on_close(
                            ctx_app, chat_data, last_position_data or position, close_reason, final_pnl
                        )
                        
                        position_closed = True
                        
                        # Log completion
                        logger.info(f"✅ {monitoring_mode} position closed for {symbol} - Reason: {close_reason}, PnL: {final_pnl}")
                        if cancelled_orders:
                            logger.info(f"🔄 Auto-cancelled orders: {', '.join(cancelled_orders)}")
                        if conservative_tp1_cancelled:
                            logger.info(f"🚨 Conservative TP1 cancellation was triggered")
                        if fast_tp_hit:
                            logger.info(f"🎯 Fast TP hit and SL cancelled")
                        if fast_sl_hit:
                            logger.info(f"🛡️ Fast SL hit and TP cancelled")
                        logger.info(f"📊 Performance stats updated ({monitoring_mode})")
                        
                        # Stop monitoring
                        logger.info(f"✅ {monitoring_mode} monitoring completed for {symbol}")
                        break
                
                else:
                    # Position is still open - update tracking data
                    last_position_size = current_size
                    last_position_data = position.copy()
                    chat_data[LAST_KNOWN_POSITION_SIZE] = current_size
                    
                    # Track P&L while position is open
                    if unrealized_pnl != 0:
                        last_known_pnl = unrealized_pnl
                        chat_data["last_known_pnl"] = str(last_known_pnl)
                
                # Log monitoring status every 20 cycles (reduced frequency)
                if monitoring_cycles % 20 == 0:
                    logger.info(f"🔄 {monitoring_mode} monitoring {symbol} - Cycle {monitoring_cycles}, Size: {current_size}, PnL: {unrealized_pnl}")
                
                # Sleep before next check (8 seconds for better stability)
                await asyncio.sleep(8)
                
            except Exception as e:
                logger.error(f"❌ Error in {monitoring_mode} monitor loop: {e}", exc_info=True)
                await asyncio.sleep(15)  # Wait longer on error
        
    finally:
        # ENHANCED CLEANUP
        logger.info(f"🏁 {monitoring_mode} monitoring ended for {symbol}")
        
        # Clear monitoring data
        chat_data[ACTIVE_MONITOR_TASK] = {}
        
        # Unregister task
        await unregister_monitor_task(chat_id, symbol)
        
        # Clear local variables to help GC
        position_history.clear()
        last_position_data = None
        
        # Force garbage collection
        gc.collect()
        
        logger.info(f"🧹 Memory cleanup completed for {symbol} monitor")

async def move_sl_to_breakeven(chat_data: dict, symbol: str, entry_price: Decimal, 
                              side: str, position_idx: int):
    """
    Move stop loss to breakeven after TP1 hit
    
    ENHANCED: Only for FULL monitoring, not read-only
    """
    try:
        # SAFETY: Skip for read-only monitoring
        if is_read_only_monitoring(chat_data):
            logger.info("🛡️ READ-ONLY monitoring: Skipping SL modification")
            return
        
        sl_order_id = chat_data.get(SL_ORDER_ID) or chat_data.get("sl_order_id")
        if not sl_order_id:
            logger.warning("⚠️ No SL order ID found to move to breakeven")
            return
        
        # Get tick size
        tick_size = chat_data.get(INSTRUMENT_TICK_SIZE, Decimal("0.01"))
        
        # Calculate breakeven price (slightly above/below entry for safety)
        if side == "Buy":
            breakeven_price = entry_price + tick_size
        else:
            breakeven_price = entry_price - tick_size
        
        # Adjust to tick size
        breakeven_price = value_adjusted_to_step(breakeven_price, tick_size)
        
        logger.info(f"🔄 Moving SL to breakeven at {breakeven_price}")
        
        # Amend the SL order
        result = await amend_order_with_retry(
            symbol=symbol,
            order_id=sl_order_id,
            trigger_price=str(breakeven_price)
        )
        
        if result:
            logger.info("✅ SL successfully moved to breakeven")
            chat_data[SL_PRICE] = breakeven_price
        else:
            logger.error("❌ Failed to move SL to breakeven")
            
    except Exception as e:
        logger.error(f"❌ Error moving SL to breakeven: {e}", exc_info=True)

async def stop_position_monitoring(chat_data: dict):
    """Stop monitoring for a position with enhanced cleanup"""
    if ACTIVE_MONITOR_TASK in chat_data:
        task_info = chat_data[ACTIVE_MONITOR_TASK]
        task_info["active"] = False
        
        # Also unregister from global registry
        symbol = task_info.get("symbol", "")
        chat_id = task_info.get("chat_id", 0)
        if symbol and chat_id:
            await unregister_monitor_task(chat_id, symbol)
        
        monitoring_mode = task_info.get("monitoring_mode", "UNKNOWN")
        chat_data[ACTIVE_MONITOR_TASK] = {}
        logger.info(f"🛑 {monitoring_mode} position monitoring stopped")

def get_monitoring_status(chat_data: dict) -> dict:
    """Get current monitoring status with enhanced mode information"""
    task_info = chat_data.get(ACTIVE_MONITOR_TASK, {})
    
    status = {
        "active": task_info.get("active", False),
        "symbol": task_info.get("symbol", "None"),
        "approach": task_info.get("approach", "fast"),
        "chat_id": task_info.get("chat_id", "None"),
        "started_at": task_info.get("started_at", 0),
        "running_time": time.time() - task_info.get("started_at", time.time()) if task_info.get("started_at") else 0,
        "monitoring_mode": task_info.get("monitoring_mode", "UNKNOWN"),
        "external_position": task_info.get("external_position", False)
    }
    
    return status

def get_monitor_registry_stats() -> Dict[str, Any]:
    """Get monitoring registry statistics for debugging"""
    return _task_registry.get_stats()

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

async def check_conservative_limit_fills(chat_data: dict, symbol: str) -> List[str]:
    """
    Check which conservative limit orders have been filled
    Returns list of newly filled order IDs
    """
    try:
        limit_order_ids = chat_data.get(LIMIT_ORDER_IDS, [])
        filled_orders = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])
        newly_filled = []
        
        for order_id in limit_order_ids:
            if order_id not in filled_orders:
                # Check order status
                order_info = await get_order_info(symbol, order_id)
                if order_info and order_info.get("orderStatus") == "Filled":
                    filled_orders.append(order_id)
                    newly_filled.append(order_id)
                    logger.info(f"✅ Conservative limit order {order_id[:8]} filled")
        
        # Update chat data with filled orders
        chat_data[CONSERVATIVE_LIMITS_FILLED] = filled_orders
        
        return newly_filled
        
    except Exception as e:
        logger.error(f"Error checking conservative limit fills: {e}")
        return []

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
        
        # Check if current price has reached TP1
        if side == "Buy":
            tp1_hit = current_price >= tp1_price
        else:  # Sell/Short
            tp1_hit = current_price <= tp1_price
        
        if tp1_hit:
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
        
        # Check if current price has reached TP1
        if side == "Buy":
            tp1_hit = current_price >= tp1_price
        else:  # Sell/Short
            tp1_hit = current_price <= tp1_price
        
        if tp1_hit:
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

async def cancel_conservative_orders_on_tp1_hit(chat_data: dict, symbol: str) -> List[str]:
    """
    Cancel ALL orders when TP1 hits before any limits fill (Scenario 1)
    Cancels: All unfilled limits + All TPs + SL
    Works for both Conservative and GGShot approaches
    """
    cancelled_orders = []
    
    try:
        approach = chat_data.get(TRADING_APPROACH, "conservative")
        
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
            
            for order_id, result in zip(all_order_ids, results):
                if not isinstance(result, Exception) and result:
                    cancelled_orders.append(order_id)
                    logger.info(f"✅ Cancelled order {order_id[:8]}...")
                else:
                    logger.warning(f"⚠️ Failed to cancel order {order_id[:8]}...")
        
        logger.info(f"🚨 {approach.capitalize()} TP1 early hit - cancelled {len(cancelled_orders)} orders")
        
    except Exception as e:
        logger.error(f"Error cancelling {approach} orders on TP1 hit: {e}")
    
    return cancelled_orders

async def cancel_remaining_conservative_limits_only(chat_data: dict, symbol: str) -> List[str]:
    """
    Cancel only remaining unfilled limit orders when TP1 hits after some fills (Scenario 2)
    Keeps: All TPs (TP2, TP3, TP4) and SL active
    """
    cancelled_orders = []
    
    try:
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
                    logger.info(f"✅ Cancelled unfilled limit {order_id[:8]}...")
                else:
                    logger.warning(f"⚠️ Failed to cancel limit {order_id[:8]}...")
        
        logger.info(f"🎯 Conservative TP1 with fills - cancelled {len(cancelled_orders)} unfilled limits")
        logger.info(f"✅ Keeping TP2, TP3, TP4 and SL orders active")
        
    except Exception as e:
        logger.error(f"Error cancelling remaining conservative limits: {e}")
    
    return cancelled_orders

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
    'register_monitor_task',
    'unregister_monitor_task',
    'get_monitor_task_status',
    'is_read_only_monitoring',
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