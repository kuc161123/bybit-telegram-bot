#!/usr/bin/env python3
"""
Robust order management system with enhanced retry logic and error handling
Provides atomic operations, rollback capabilities, and better error recovery
"""
import asyncio
import logging
import time
import hashlib
from typing import Optional, Dict, Any, List, Tuple, Set
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

from config.constants import *
from clients.bybit_helpers import (
    cancel_order_with_retry, amend_order_with_retry,
    get_order_info, place_order_with_retry
)

logger = logging.getLogger(__name__)

# Constants for robust order management
ORDER_RETRY_ATTEMPTS = 5
ORDER_RETRY_DELAY = 0.5
OPERATION_TIMEOUT = 30  # seconds
IDEMPOTENCY_CACHE_TTL = 300  # 5 minutes

class OrderOperationType(Enum):
    """Types of order operations"""
    PLACE = "place"
    CANCEL = "cancel"
    AMEND = "amend"

@dataclass
class OrderOperation:
    """Data class for order operations"""
    operation_type: OrderOperationType
    symbol: str
    order_id: Optional[str] = None
    params: Dict[str, Any] = None
    timestamp: float = None
    success: bool = False
    error: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.params is None:
            self.params = {}

class OrderOperationLock:
    """Distributed lock for order operations to prevent race conditions"""

    _locks: Dict[str, asyncio.Lock] = {}
    _lock_creation_lock = asyncio.Lock()

    @classmethod
    async def get_lock(cls, symbol: str, operation: str) -> asyncio.Lock:
        """Get or create a lock for specific symbol and operation"""
        lock_key = f"{symbol}:{operation}"

        async with cls._lock_creation_lock:
            if lock_key not in cls._locks:
                cls._locks[lock_key] = asyncio.Lock()
            return cls._locks[lock_key]

    @classmethod
    def clear_locks(cls):
        """Clear all locks (for testing)"""
        cls._locks.clear()

class IdempotencyManager:
    """Manage idempotent operations to prevent duplicates"""

    def __init__(self, ttl: int = IDEMPOTENCY_CACHE_TTL):
        self.ttl = ttl
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    def _generate_key(self, operation: str, params: Dict[str, Any]) -> str:
        """Generate unique key for operation"""
        # Create a deterministic string from parameters
        param_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(f"{operation}:{param_str}".encode()).hexdigest()

    async def execute_once(self, operation: str, func, *args, **kwargs) -> Tuple[Any, bool]:
        """
        Execute operation only once, return cached result if already done
        Returns: (result, was_cached)
        """
        params = {"args": args, "kwargs": kwargs}
        key = self._generate_key(operation, params)

        async with self._lock:
            # Check cache
            if key in self._cache:
                result, timestamp = self._cache[key]
                if time.time() - timestamp < self.ttl:
                    logger.debug(f"Returning cached result for {operation}")
                    return result, True

            # Execute operation
            result = await func(*args, **kwargs)

            # Cache result
            self._cache[key] = (result, time.time())

            # Cleanup old entries
            await self._cleanup_expired()

            return result, False

    async def _cleanup_expired(self):
        """Remove expired cache entries"""
        current_time = time.time()
        expired_keys = [
            k for k, (_, ts) in self._cache.items()
            if current_time - ts > self.ttl
        ]
        for key in expired_keys:
            del self._cache[key]

class AtomicOrderOperation:
    """Context manager for atomic order operations with rollback capability"""

    def __init__(self, chat_data: dict, operation_name: str):
        self.chat_data = chat_data
        self.operation_name = operation_name
        self.original_state: Dict[str, Any] = {}
        self.operations_log: List[OrderOperation] = []
        self.success = False

    async def __aenter__(self):
        """Backup critical state before operations"""
        # Backup order-related state
        self.original_state = {
            SL_ORDER_ID: self.chat_data.get(SL_ORDER_ID),
            TP_ORDER_IDS: self.chat_data.get(TP_ORDER_IDS, []).copy() if self.chat_data.get(TP_ORDER_IDS) else [],
            LIMIT_ORDER_IDS: self.chat_data.get(LIMIT_ORDER_IDS, []).copy() if self.chat_data.get(LIMIT_ORDER_IDS) else [],
            "position_status": self.chat_data.get("position_status"),
            "monitor_task": self.chat_data.get("monitor_task"),
        }

        logger.debug(f"Starting atomic operation: {self.operation_name}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Handle cleanup and potential rollback"""
        if exc_val:
            logger.error(f"Error in atomic operation {self.operation_name}: {exc_val}")
            await self._rollback()
            return False  # Don't suppress the exception

        self.success = True
        logger.debug(f"Completed atomic operation: {self.operation_name}")
        return True

    async def _rollback(self):
        """Attempt to rollback changes"""
        logger.warning(f"Rolling back operation: {self.operation_name}")

        # Restore original state
        for key, value in self.original_state.items():
            if value is not None:
                self.chat_data[key] = value

        # Log operations that couldn't be rolled back
        for op in self.operations_log:
            if op.success and op.operation_type == OrderOperationType.CANCEL:
                logger.warning(f"Cannot rollback order cancellation: {op.order_id}")

    def log_operation(self, operation: OrderOperation):
        """Log an operation for potential rollback"""
        self.operations_log.append(operation)

class RobustOrderManager:
    """Enhanced order manager with robust error handling and retry logic"""

    def __init__(self):
        self.idempotency_manager = IdempotencyManager()
        self._operation_history: List[OrderOperation] = []
        self._max_history = 1000

    async def cancel_orders_atomic(self, symbol: str, order_ids: List[str],
                                 chat_data: dict, order_type: str = "order") -> Tuple[List[str], List[str]]:
        """
        Cancel multiple orders atomically with enhanced error handling
        Returns: (successful_cancellations, failed_cancellations)
        """
        if not order_ids:
            return [], []

        # Get lock for this operation
        lock = await OrderOperationLock.get_lock(symbol, f"cancel_{order_type}")

        async with lock:
            async with AtomicOrderOperation(chat_data, f"cancel_{order_type}_orders") as atomic_op:
                successful = []
                failed = []

                # Process cancellations concurrently but with controlled concurrency
                semaphore = asyncio.Semaphore(3)  # Limit concurrent cancellations

                async def cancel_single(order_id: str) -> Tuple[str, bool, Optional[str]]:
                    async with semaphore:
                        try:
                            # Use idempotency manager to prevent duplicate cancellations
                            success, was_cached = await self.idempotency_manager.execute_once(
                                f"cancel_{symbol}_{order_id}",
                                self._cancel_order_enhanced,
                                symbol, order_id
                            )

                            # Log operation
                            op = OrderOperation(
                                operation_type=OrderOperationType.CANCEL,
                                symbol=symbol,
                                order_id=order_id,
                                success=success,
                                error=None if success else "Cancellation failed"
                            )
                            atomic_op.log_operation(op)

                            return order_id, success, None

                        except Exception as e:
                            error_msg = str(e)

                            # Check if order is already cancelled
                            if any(msg in error_msg.lower() for msg in ["order not found", "already cancelled", "not exist"]):
                                logger.info(f"Order {order_id} already cancelled or not found")
                                return order_id, True, "already_cancelled"

                            logger.error(f"Error cancelling order {order_id}: {e}")
                            return order_id, False, error_msg

                # Execute cancellations
                results = await asyncio.gather(
                    *[cancel_single(order_id) for order_id in order_ids],
                    return_exceptions=True
                )

                # Process results
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"Unexpected error in cancellation: {result}")
                        failed.append(str(result))
                    else:
                        order_id, success, error = result
                        if success:
                            successful.append(order_id)
                        else:
                            failed.append(f"{order_id}: {error or 'Unknown error'}")

                # Update chat data only if all critical cancellations succeeded
                if order_type == "sl" and successful:
                    chat_data[SL_ORDER_ID] = None
                elif order_type == "tp" and successful:
                    # Remove cancelled TPs from list
                    remaining_tps = [tp for tp in chat_data.get(TP_ORDER_IDS, []) if tp not in successful]
                    chat_data[TP_ORDER_IDS] = remaining_tps
                elif order_type == "limit" and successful:
                    # Remove cancelled limits from list
                    remaining_limits = [lim for lim in chat_data.get(LIMIT_ORDER_IDS, []) if lim not in successful]
                    chat_data[LIMIT_ORDER_IDS] = remaining_limits

                return successful, failed

    async def _cancel_order_enhanced(self, symbol: str, order_id: str) -> bool:
        """Enhanced order cancellation with better error handling"""
        max_attempts = ORDER_RETRY_ATTEMPTS

        for attempt in range(max_attempts):
            try:
                # First check if order exists and is active
                order_info = await get_order_info(symbol, order_id)

                if not order_info:
                    logger.debug(f"Order {order_id} not found, treating as already cancelled")
                    return True

                order_status = order_info.get("orderStatus", "")

                # Check if order is already in terminal state
                if order_status in ["Cancelled", "Filled", "Rejected", "Expired"]:
                    logger.info(f"Order {order_id} already in terminal state: {order_status}")
                    return True

                # Proceed with cancellation
                success = await cancel_order_with_retry(symbol, order_id, max_retries=3)

                if success:
                    self._record_operation(OrderOperation(
                        operation_type=OrderOperationType.CANCEL,
                        symbol=symbol,
                        order_id=order_id,
                        success=True
                    ))
                    return True

                # If not last attempt, wait before retry
                if attempt < max_attempts - 1:
                    delay = ORDER_RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                    await asyncio.sleep(delay)

            except Exception as e:
                logger.error(f"Exception in enhanced cancel for {order_id}: {e}")
                if attempt == max_attempts - 1:
                    raise

                await asyncio.sleep(ORDER_RETRY_DELAY)

        return False

    async def amend_order_atomic(self, symbol: str, order_id: str,
                               new_params: Dict[str, Any], chat_data: dict) -> bool:
        """Amend order with atomic operation and rollback capability"""
        lock = await OrderOperationLock.get_lock(symbol, f"amend_{order_id}")

        async with lock:
            async with AtomicOrderOperation(chat_data, f"amend_order_{order_id}") as atomic_op:
                try:
                    # Get current order state for potential rollback
                    original_order = await get_order_info(symbol, order_id)

                    if not original_order:
                        logger.error(f"Cannot amend - order {order_id} not found")
                        return False

                    # Perform amendment
                    success, _ = await self.idempotency_manager.execute_once(
                        f"amend_{symbol}_{order_id}_{time.time()}",
                        self._amend_order_enhanced,
                        symbol, order_id, new_params, original_order
                    )

                    # Log operation
                    op = OrderOperation(
                        operation_type=OrderOperationType.AMEND,
                        symbol=symbol,
                        order_id=order_id,
                        params=new_params,
                        success=success
                    )
                    atomic_op.log_operation(op)

                    return success

                except Exception as e:
                    logger.error(f"Error in atomic amend operation: {e}")
                    raise

    async def _amend_order_enhanced(self, symbol: str, order_id: str,
                                  new_params: Dict[str, Any], original_order: Dict[str, Any]) -> bool:
        """Enhanced order amendment with validation"""
        try:
            # Validate new parameters
            if not self._validate_amend_params(new_params, original_order):
                logger.error(f"Invalid amendment parameters for order {order_id}")
                return False

            # Perform amendment
            success = await amend_order_with_retry(
                symbol=symbol,
                order_id=order_id,
                **new_params
            )

            if success:
                self._record_operation(OrderOperation(
                    operation_type=OrderOperationType.AMEND,
                    symbol=symbol,
                    order_id=order_id,
                    params=new_params,
                    success=True
                ))

            return success

        except Exception as e:
            logger.error(f"Error amending order {order_id}: {e}")
            return False

    def _validate_amend_params(self, new_params: Dict[str, Any],
                              original_order: Dict[str, Any]) -> bool:
        """Validate amendment parameters"""
        # Check if order is in amendable state
        order_status = original_order.get("orderStatus", "")
        if order_status not in ["New", "PartiallyFilled", "Untriggered"]:
            logger.error(f"Order in non-amendable state: {order_status}")
            return False

        # Validate price changes
        if "price" in new_params:
            try:
                new_price = Decimal(str(new_params["price"]))
                if new_price <= 0:
                    logger.error("Invalid price: must be positive")
                    return False
            except Exception:
                logger.error("Invalid price format")
                return False

        # Validate quantity changes
        if "qty" in new_params:
            try:
                new_qty = Decimal(str(new_params["qty"]))
                if new_qty <= 0:
                    logger.error("Invalid quantity: must be positive")
                    return False
            except Exception:
                logger.error("Invalid quantity format")
                return False

        return True

    def _record_operation(self, operation: OrderOperation):
        """Record operation in history"""
        self._operation_history.append(operation)

        # Limit history size
        if len(self._operation_history) > self._max_history:
            self._operation_history = self._operation_history[-self._max_history:]

    def get_operation_history(self, symbol: Optional[str] = None,
                            operation_type: Optional[OrderOperationType] = None) -> List[OrderOperation]:
        """Get operation history with optional filters"""
        history = self._operation_history

        if symbol:
            history = [op for op in history if op.symbol == symbol]

        if operation_type:
            history = [op for op in history if op.operation_type == operation_type]

        return history

class OrderValidation:
    """Validate orders before placement to prevent errors"""

    @staticmethod
    def validate_order_params(symbol: str, side: str, order_type: str,
                            qty: Decimal, price: Optional[Decimal] = None,
                            stop_price: Optional[Decimal] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate order parameters
        Returns: (is_valid, error_message)
        """
        # Validate side
        if side not in ["Buy", "Sell"]:
            return False, f"Invalid side: {side}"

        # Validate order type
        valid_types = ["Market", "Limit", "Stop", "StopLimit"]
        if order_type not in valid_types:
            return False, f"Invalid order type: {order_type}"

        # Validate quantity
        if qty <= 0:
            return False, "Quantity must be positive"

        # Validate prices for limit/stop orders
        if order_type in ["Limit", "StopLimit"] and not price:
            return False, f"{order_type} order requires price"

        if order_type in ["Stop", "StopLimit"] and not stop_price:
            return False, f"{order_type} order requires stop price"

        if price and price <= 0:
            return False, "Price must be positive"

        if stop_price and stop_price <= 0:
            return False, "Stop price must be positive"

        return True, None

# Singleton instance
_robust_order_manager: Optional[RobustOrderManager] = None

def get_robust_order_manager() -> RobustOrderManager:
    """Get or create the robust order manager singleton"""
    global _robust_order_manager

    if _robust_order_manager is None:
        _robust_order_manager = RobustOrderManager()

    return _robust_order_manager