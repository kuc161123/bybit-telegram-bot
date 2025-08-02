#!/usr/bin/env python3
"""
Order State Cache - Prevents unnecessary order operations on already processed orders
Tracks order states to avoid "order not exists or too late to cancel" errors
"""
import asyncio
import logging
import time
from typing import Dict, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

class OrderStateCache:
    """
    Caches order states to prevent unnecessary API calls and errors
    """

    def __init__(self):
        # Order state cache: order_id -> state_info
        self._order_states: Dict[str, Dict] = {}

        # Track orders that are definitely gone (filled/cancelled)
        self._completed_orders: Set[str] = set()

        # Track orders we recently tried to cancel
        self._recent_cancel_attempts: Dict[str, float] = {}

        # Cache expiry times
        self._state_cache_ttl = 300  # 5 minutes
        self._completed_cache_ttl = 3600  # 1 hour
        self._cancel_attempt_cooldown = 60  # 1 minute

        # Lock for thread safety
        self._lock = asyncio.Lock()

        # Stats
        self._stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "prevented_cancellations": 0,
            "successful_cancellations": 0,
            "failed_cancellations": 0
        }

    async def is_order_cancellable(self, order_id: str) -> bool:
        """
        Check if an order is likely cancellable without making an API call

        Returns:
            True if order might be cancellable, False if definitely not
        """
        async with self._lock:
            # Check if order is in completed set
            if order_id in self._completed_orders:
                self._stats["cache_hits"] += 1
                logger.debug(f"📋 Order {order_id[:8]}... is in completed cache - not cancellable")
                return False

            # Check if we recently tried to cancel this order
            if order_id in self._recent_cancel_attempts:
                last_attempt = self._recent_cancel_attempts[order_id]
                if time.time() - last_attempt < self._cancel_attempt_cooldown:
                    self._stats["cache_hits"] += 1
                    logger.debug(f"📋 Order {order_id[:8]}... was recently cancelled - cooldown active")
                    return False

            # Check cached state
            if order_id in self._order_states:
                state_info = self._order_states[order_id]
                if time.time() - state_info["timestamp"] < self._state_cache_ttl:
                    status = state_info["status"]
                    if status in ["Filled", "Cancelled", "Rejected"]:
                        self._stats["cache_hits"] += 1
                        logger.debug(f"📋 Order {order_id[:8]}... has status {status} - not cancellable")
                        return False

            self._stats["cache_misses"] += 1
            return True

    async def update_order_state(self, order_id: str, status: str, order_info: Optional[Dict] = None):
        """
        Update the cached state of an order

        Args:
            order_id: Order ID
            status: Order status (New, PartiallyFilled, Filled, Cancelled, etc.)
            order_info: Full order information if available
        """
        async with self._lock:
            self._order_states[order_id] = {
                "status": status,
                "timestamp": time.time(),
                "info": order_info
            }

            # If order is completed, add to completed set
            if status in ["Filled", "Cancelled", "Rejected"]:
                self._completed_orders.add(order_id)
                logger.debug(f"📋 Added order {order_id[:8]}... to completed cache (status: {status})")

    async def record_cancel_attempt(self, order_id: str, success: bool):
        """
        Record a cancellation attempt for an order

        Args:
            order_id: Order ID
            success: Whether the cancellation was successful
        """
        async with self._lock:
            self._recent_cancel_attempts[order_id] = time.time()

            if success:
                self._completed_orders.add(order_id)
                self._stats["successful_cancellations"] += 1
            else:
                self._stats["failed_cancellations"] += 1

    async def prevent_cancellation(self, order_id: str):
        """
        Record that a cancellation was prevented due to cache
        """
        async with self._lock:
            self._stats["prevented_cancellations"] += 1
            logger.info(f"🛡️ Prevented unnecessary cancellation of order {order_id[:8]}...")

    async def cleanup_expired_entries(self):
        """
        Remove expired entries from caches
        """
        async with self._lock:
            current_time = time.time()

            # Clean up order states
            expired_states = []
            for order_id, state_info in self._order_states.items():
                if current_time - state_info["timestamp"] > self._state_cache_ttl:
                    expired_states.append(order_id)

            for order_id in expired_states:
                del self._order_states[order_id]

            # Clean up recent cancel attempts
            expired_attempts = []
            for order_id, timestamp in self._recent_cancel_attempts.items():
                if current_time - timestamp > self._cancel_attempt_cooldown:
                    expired_attempts.append(order_id)

            for order_id in expired_attempts:
                del self._recent_cancel_attempts[order_id]

            # Note: We keep completed_orders longer as they're definitely not cancellable
            # Could implement a separate cleanup for very old completed orders if needed

            if expired_states or expired_attempts:
                logger.debug(f"🧹 Cleaned up {len(expired_states)} expired states, {len(expired_attempts)} cancel attempts")

    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total_requests = self._stats["cache_hits"] + self._stats["cache_misses"]
        hit_rate = (self._stats["cache_hits"] / total_requests * 100) if total_requests > 0 else 0

        return {
            **self._stats,
            "hit_rate": f"{hit_rate:.1f}%",
            "cached_orders": len(self._order_states),
            "completed_orders": len(self._completed_orders),
            "recent_cancellations": len(self._recent_cancel_attempts)
        }

# Global instance
order_state_cache = OrderStateCache()

# Periodic cleanup task
async def periodic_cache_cleanup():
    """Run periodic cleanup of expired cache entries"""
    while True:
        try:
            await asyncio.sleep(300)  # Run every 5 minutes
            await order_state_cache.cleanup_expired_entries()

            # Log stats periodically
            stats = order_state_cache.get_stats()
            if stats["cached_orders"] > 0:
                logger.info(f"📊 Order cache stats: {stats}")

        except Exception as e:
            logger.error(f"Error in cache cleanup: {e}")
            await asyncio.sleep(60)  # Wait before retrying