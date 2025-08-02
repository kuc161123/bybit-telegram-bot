#!/usr/bin/env python3
"""
Robust alert delivery system with retry logic, circuit breaker, and priority queue
Enhances the existing alert system with production-grade reliability features
"""
import asyncio
import logging
import time
import random
import json
import os
from typing import Optional, Dict, Any, List, Tuple, Callable
from decimal import Decimal
from datetime import datetime, timedelta
from collections import deque
from enum import Enum
from dataclasses import dataclass
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from config.constants import *
from utils.alert_helpers import (
    format_tp_hit_alert, format_sl_hit_alert, format_limit_filled_alert,
    format_tp_early_hit_alert, format_tp_with_fills_alert
)

logger = logging.getLogger(__name__)

# Constants for robust alert system
MAX_RETRY_ATTEMPTS = 3
INITIAL_RETRY_DELAY = 1.0  # seconds
MAX_RETRY_DELAY = 30.0  # seconds
ALERT_QUEUE_SIZE = 1000
FAILED_ALERTS_FILE = "failed_alerts.json"
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_TIMEOUT = 60  # seconds
ALERT_CACHE_TTL = 300  # 5 minutes to prevent duplicate alerts

class AlertPriority(Enum):
    """Priority levels for alerts"""
    CRITICAL = 1  # Position closed, SL hit
    HIGH = 2      # TP hit, important updates
    MEDIUM = 3    # Limit filled
    LOW = 4       # Informational

class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class AlertMessage:
    """Data class for alert messages"""
    chat_id: int
    alert_type: str
    symbol: str
    side: str
    approach: str
    priority: AlertPriority
    data: Dict[str, Any]
    retry_count: int = 0
    created_at: float = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "chat_id": self.chat_id,
            "alert_type": self.alert_type,
            "symbol": self.symbol,
            "side": self.side,
            "approach": self.approach,
            "priority": self.priority.value,
            "data": self.data,
            "retry_count": self.retry_count,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AlertMessage':
        """Create from dictionary"""
        return cls(
            chat_id=data["chat_id"],
            alert_type=data["alert_type"],
            symbol=data["symbol"],
            side=data["side"],
            approach=data["approach"],
            priority=AlertPriority(data["priority"]),
            data=data["data"],
            retry_count=data.get("retry_count", 0),
            created_at=data.get("created_at", time.time())
        )

class CircuitBreaker:
    """Enhanced circuit breaker for handling service failures with 2025 improvements"""

    def __init__(self, failure_threshold: int = CIRCUIT_BREAKER_THRESHOLD,
                 timeout: int = CIRCUIT_BREAKER_TIMEOUT):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_success_time = None
        self.state = CircuitBreakerState.CLOSED
        self._lock = asyncio.Lock()
        self._state_change_history = deque(maxlen=10)  # Track recent state changes

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        async with self._lock:
            # Check if circuit should be opened
            if self.state == CircuitBreakerState.OPEN:
                if time.time() - self.last_failure_time > self.timeout:
                    logger.info("Circuit breaker entering half-open state")
                    self.state = CircuitBreakerState.HALF_OPEN
                else:
                    raise Exception(f"Circuit breaker is open, retry after {self.timeout}s")

        try:
            result = await func(*args, **kwargs)

            async with self._lock:
                self.success_count += 1
                self.last_success_time = time.time()
                
                if self.state == CircuitBreakerState.HALF_OPEN:
                    logger.info("🔄 Circuit breaker closing after successful call")
                    old_state = self.state
                    self.state = CircuitBreakerState.CLOSED
                    self.failure_count = 0
                    self._record_state_change(old_state, self.state, "successful_call")

            return result

        except Exception as e:
            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()

                if self.failure_count >= self.failure_threshold:
                    logger.error(f"🚨 Circuit breaker opening after {self.failure_count} failures: {e}")
                    old_state = self.state
                    self.state = CircuitBreakerState.OPEN
                    self._record_state_change(old_state, self.state, f"failures_exceeded: {e}")

            raise

    def _record_state_change(self, old_state: CircuitBreakerState, new_state: CircuitBreakerState, reason: str):
        """Record state change for monitoring"""
        self._state_change_history.append({
            "timestamp": time.time(),
            "old_state": old_state.value,
            "new_state": new_state.value,
            "reason": reason
        })

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.failure_threshold,
            "timeout_seconds": self.timeout,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "recent_state_changes": list(self._state_change_history)
        }

class AlertDeduplicator:
    """Enhanced duplicate alert prevention with account-aware keys (2025 best practices)"""

    def __init__(self, ttl: int = ALERT_CACHE_TTL):
        self.ttl = ttl
        self._cache: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._duplicate_count = 0
        self._last_cleanup = time.time()

    def _generate_key(self, alert: AlertMessage) -> str:
        """Generate unique key for alert with account awareness"""
        account_type = alert.data.get("additional_info", {}).get("account_type", "main")
        return f"{alert.chat_id}:{alert.alert_type}:{alert.symbol}:{alert.side}:{account_type}"

    async def is_duplicate(self, alert: AlertMessage) -> bool:
        """Check if alert is a duplicate with enhanced logic"""
        async with self._lock:
            key = self._generate_key(alert)
            now = time.time()

            # Periodic cleanup (every 5 minutes)
            if now - self._last_cleanup > 300:
                await self._cleanup_expired_entries()
                self._last_cleanup = now

            # Check if duplicate
            if key in self._cache:
                age = now - self._cache[key]
                self._duplicate_count += 1
                logger.debug(f"🔄 Duplicate alert detected: {key} (age: {age:.1f}s, total duplicates: {self._duplicate_count})")
                return True

            # Add to cache
            self._cache[key] = now
            return False

    async def _cleanup_expired_entries(self):
        """Clean expired entries from cache"""
        now = time.time()
        expired_keys = [k for k, v in self._cache.items() if now - v > self.ttl]
        for k in expired_keys:
            del self._cache[k]
        
        if expired_keys:
            logger.debug(f"🧹 Cleaned {len(expired_keys)} expired alert cache entries")

    def get_stats(self) -> Dict[str, int]:
        """Get deduplication statistics"""
        return {
            "cached_alerts": len(self._cache),
            "duplicates_prevented": self._duplicate_count,
            "cache_ttl_seconds": self.ttl
        }

class FailedAlertStorage:
    """Persistent storage for failed alerts"""

    def __init__(self, filename: str = FAILED_ALERTS_FILE):
        self.filename = filename
        self._lock = asyncio.Lock()

    async def save_alert(self, alert: AlertMessage):
        """Save failed alert to file"""
        async with self._lock:
            try:
                alerts = await self._load_alerts()
                alerts.append(alert.to_dict())

                # Keep only last 100 failed alerts
                if len(alerts) > 100:
                    alerts = alerts[-100:]

                with open(self.filename, 'w') as f:
                    json.dump(alerts, f, indent=2)

                logger.info(f"Saved failed alert to storage: {alert.alert_type}")

            except Exception as e:
                logger.error(f"Error saving failed alert: {e}")

    async def _load_alerts(self) -> List[Dict[str, Any]]:
        """Load alerts from file"""
        if not os.path.exists(self.filename):
            return []

        try:
            with open(self.filename, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading failed alerts: {e}")
            return []

    async def get_failed_alerts(self) -> List[AlertMessage]:
        """Get all failed alerts"""
        async with self._lock:
            try:
                data = await self._load_alerts()
                return [AlertMessage.from_dict(d) for d in data]
            except Exception as e:
                logger.error(f"Error getting failed alerts: {e}")
                return []

    async def clear_alerts(self):
        """Clear all failed alerts"""
        async with self._lock:
            try:
                if os.path.exists(self.filename):
                    os.remove(self.filename)
                logger.info("Cleared failed alerts storage")
            except Exception as e:
                logger.error(f"Error clearing failed alerts: {e}")

class RobustAlertSystem:
    """Main robust alert delivery system"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.circuit_breaker = CircuitBreaker()
        self.deduplicator = AlertDeduplicator()
        self.failed_storage = FailedAlertStorage()
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=ALERT_QUEUE_SIZE)
        self._processing = False
        self._stop_event = asyncio.Event()
        self._retry_queue: deque = deque(maxlen=100)

    async def send_alert(self, alert_type: str, chat_id: int, symbol: str,
                        side: str, approach: str, priority: AlertPriority = AlertPriority.MEDIUM,
                        **kwargs) -> bool:
        """Send alert with automatic retry and queueing"""

        # Create alert message
        alert = AlertMessage(
            chat_id=chat_id,
            alert_type=alert_type,
            symbol=symbol,
            side=side,
            approach=approach,
            priority=priority,
            data=kwargs
        )

        # Check for duplicates
        if await self.deduplicator.is_duplicate(alert):
            logger.debug(f"Skipping duplicate alert: {alert_type} for {symbol}")
            return True

        # Add to queue
        try:
            await self._queue.put((priority.value, alert.created_at, alert))

            # Start processing if not already running
            if not self._processing:
                asyncio.create_task(self._process_alerts())

            return True

        except asyncio.QueueFull:
            logger.error("Alert queue is full, saving to failed storage")
            await self.failed_storage.save_alert(alert)
            return False

    async def _process_alerts(self):
        """Process alerts from queue"""
        self._processing = True
        logger.info("Starting alert processing")

        while not self._stop_event.is_set():
            try:
                # Get alert from queue with timeout
                priority, created_at, alert = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=5.0
                )

                # Send alert with retry
                success = await self._send_alert_with_retry(alert)

                if not success:
                    # Save to failed storage
                    await self.failed_storage.save_alert(alert)

            except asyncio.TimeoutError:
                # Process retry queue
                await self._process_retry_queue()

                # Check if queue is empty
                if self._queue.empty() and not self._retry_queue:
                    self._processing = False
                    logger.info("Alert processing stopped - queue empty")
                    break

            except Exception as e:
                logger.error(f"Error processing alerts: {e}")

        self._processing = False

    async def _send_alert_with_retry(self, alert: AlertMessage) -> bool:
        """Send alert with exponential backoff retry"""

        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                # Use circuit breaker
                success = await self.circuit_breaker.call(
                    self._send_single_alert,
                    alert
                )

                if success:
                    logger.info(f"Alert sent successfully on attempt {attempt + 1}: {alert.alert_type}")
                    return True

            except Exception as e:
                error_str = str(e).lower()

                # Check for permanent errors
                if any(err in error_str for err in ["chat not found", "bot was blocked", "user is deactivated"]):
                    logger.error(f"Permanent error, not retrying: {e}")
                    return False

                # Calculate retry delay with jitter
                delay = min(
                    INITIAL_RETRY_DELAY * (2 ** attempt) + random.uniform(0, 1),
                    MAX_RETRY_DELAY
                )

                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    logger.warning(f"Alert failed on attempt {attempt + 1}, retrying in {delay:.1f}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Alert failed after {MAX_RETRY_ATTEMPTS} attempts: {e}")
                    alert.retry_count = MAX_RETRY_ATTEMPTS

                    # Add to retry queue for later
                    if alert.retry_count < MAX_RETRY_ATTEMPTS * 2:
                        self._retry_queue.append(alert)

        return False

    async def _send_single_alert(self, alert: AlertMessage) -> bool:
        """Send a single alert message"""
        try:
            # Format message based on alert type
            message = self._format_alert_message(alert)

            if not message:
                logger.error(f"Failed to format message for alert type: {alert.alert_type}")
                return False

            # Send message
            await self.bot.send_message(
                chat_id=alert.chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )

            return True

        except TelegramError as e:
            raise  # Re-raise for circuit breaker
        except Exception as e:
            logger.error(f"Unexpected error sending alert: {e}")
            raise

    def _format_alert_message(self, alert: AlertMessage) -> Optional[str]:
        """Format alert message based on type"""
        data = alert.data

        # Extract common data
        pnl = data.get("pnl", Decimal("0"))
        entry_price = data.get("entry_price", Decimal("0"))
        current_price = data.get("current_price", Decimal("0"))
        position_size = data.get("position_size", Decimal("0"))
        cancelled_orders = data.get("cancelled_orders", [])
        additional_info = data.get("additional_info", {})

        # Calculate P&L percentage
        if entry_price > 0:
            if alert.side == "Buy":
                pnl_percent = ((current_price - entry_price) / entry_price) * 100
            else:
                pnl_percent = ((entry_price - current_price) / entry_price) * 100
        else:
            pnl_percent = Decimal("0")

        # Format based on alert type
        if alert.alert_type == "tp_hit":
            return format_tp_hit_alert(
                alert.symbol, alert.side, alert.approach, pnl, pnl_percent,
                entry_price, current_price, position_size,
                cancelled_orders, additional_info
            )
        elif alert.alert_type == "sl_hit":
            return format_sl_hit_alert(
                alert.symbol, alert.side, alert.approach, pnl, pnl_percent,
                entry_price, current_price, position_size,
                cancelled_orders, additional_info
            )
        elif alert.alert_type == "limit_filled":
            return format_limit_filled_alert(
                alert.symbol, alert.side, alert.approach, additional_info
            )
        elif alert.alert_type == "tp_early_hit":
            return format_tp_early_hit_alert(
                alert.symbol, alert.side, alert.approach, cancelled_orders, additional_info
            )
        elif alert.alert_type == "tp_with_fills":
            return format_tp_with_fills_alert(
                alert.symbol, alert.side, alert.approach, cancelled_orders, additional_info
            )

        return None

    async def _process_retry_queue(self):
        """Process alerts from retry queue"""
        if not self._retry_queue:
            return

        # Process up to 5 alerts from retry queue
        for _ in range(min(5, len(self._retry_queue))):
            try:
                alert = self._retry_queue.popleft()
                alert.retry_count += 1

                # Add back to main queue with lower priority
                new_priority = min(alert.priority.value + 1, AlertPriority.LOW.value)
                await self._queue.put((new_priority, alert.created_at, alert))

            except Exception as e:
                logger.error(f"Error processing retry queue: {e}")

    async def retry_failed_alerts(self) -> int:
        """Retry all failed alerts from storage"""
        failed_alerts = await self.failed_storage.get_failed_alerts()

        if not failed_alerts:
            logger.info("No failed alerts to retry")
            return 0

        logger.info(f"Retrying {len(failed_alerts)} failed alerts")

        success_count = 0
        for alert in failed_alerts:
            # Reset retry count
            alert.retry_count = 0

            # Add to queue
            try:
                await self._queue.put((alert.priority.value, alert.created_at, alert))
                success_count += 1
            except asyncio.QueueFull:
                logger.error("Queue full while retrying failed alerts")
                break

        # Clear storage if all alerts queued
        if success_count == len(failed_alerts):
            await self.failed_storage.clear_alerts()

        # Start processing
        if not self._processing:
            asyncio.create_task(self._process_alerts())

        return success_count

    async def stop(self):
        """Stop alert processing"""
        logger.info("Stopping alert system")
        self._stop_event.set()

        # Wait for processing to complete
        timeout = 10
        start_time = time.time()

        while self._processing and time.time() - start_time < timeout:
            await asyncio.sleep(0.1)

        if self._processing:
            logger.warning("Alert processing did not stop cleanly")

# Singleton instance
_robust_alert_system: Optional[RobustAlertSystem] = None

def get_robust_alert_system(bot: Bot) -> RobustAlertSystem:
    """Get or create the robust alert system singleton"""
    global _robust_alert_system

    if _robust_alert_system is None:
        _robust_alert_system = RobustAlertSystem(bot)

    return _robust_alert_system

# Enhanced wrapper function for backward compatibility
async def send_trade_alert_robust(bot: Bot, chat_id: int, alert_type: str,
                                symbol: str, side: str, approach: str,
                                pnl: Decimal, entry_price: Decimal,
                                current_price: Decimal, position_size: Decimal,
                                cancelled_orders: List[str] = None,
                                additional_info: Dict[str, Any] = None) -> bool:
    """Enhanced trade alert with robust delivery"""

    # Determine priority based on alert type
    if alert_type in ["sl_hit", "position_closed"]:
        priority = AlertPriority.CRITICAL
    elif alert_type in ["tp_hit", "tp_early_hit", "tp_with_fills"]:
        priority = AlertPriority.HIGH
    elif alert_type == "limit_filled":
        priority = AlertPriority.MEDIUM
    else:
        priority = AlertPriority.LOW

    # Get robust alert system
    alert_system = get_robust_alert_system(bot)

    # Send alert
    return await alert_system.send_alert(
        alert_type=alert_type,
        chat_id=chat_id,
        symbol=symbol,
        side=side,
        approach=approach,
        priority=priority,
        pnl=pnl,
        entry_price=entry_price,
        current_price=current_price,
        position_size=position_size,
        cancelled_orders=cancelled_orders or [],
        additional_info=additional_info or {}
    )