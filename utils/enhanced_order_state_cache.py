#!/usr/bin/env python3
"""
Enhanced order state cache with recent attempt tracking
"""

import time
from typing import Dict, Optional
from collections import defaultdict
import asyncio

class EnhancedOrderStateCache:
    def __init__(self):
        self._states = {}
        self._non_cancellable = set()
        self._cancel_attempts = defaultdict(list)  # order_id -> list of timestamps
        self._lock = asyncio.Lock()

    async def get_recent_attempt_count(self, order_id: str, window_seconds: int = 60) -> int:
        """Get count of recent cancellation attempts within time window"""
        async with self._lock:
            if order_id not in self._cancel_attempts:
                return 0

            current_time = time.time()
            cutoff_time = current_time - window_seconds

            # Filter attempts within window
            recent_attempts = [t for t in self._cancel_attempts[order_id] if t > cutoff_time]

            # Update list to only keep recent attempts
            self._cancel_attempts[order_id] = recent_attempts

            return len(recent_attempts)

    async def record_cancel_attempt(self, order_id: str, success: bool = False):
        """Record a cancellation attempt"""
        async with self._lock:
            self._cancel_attempts[order_id].append(time.time())

            # Clean up old entries (older than 5 minutes)
            cutoff = time.time() - 300
            self._cancel_attempts[order_id] = [
                t for t in self._cancel_attempts[order_id] if t > cutoff
            ]

    async def is_order_cancellable(self, order_id: str) -> bool:
        """Check if order can be cancelled"""
        if order_id in self._non_cancellable:
            return False

        # Check recent attempts
        recent_attempts = await self.get_recent_attempt_count(order_id, 30)
        if recent_attempts >= 5:
            # Too many recent attempts, likely not cancellable
            return False

        return order_id not in self._non_cancellable

    async def prevent_cancellation(self, order_id: str):
        """Mark order as non-cancellable"""
        async with self._lock:
            self._non_cancellable.add(order_id)

    async def update_order_state(self, order_id: str, state: str, order_data: Optional[Dict] = None):
        """Update order state"""
        async with self._lock:
            self._states[order_id] = {
                'state': state,
                'data': order_data,
                'updated': time.time()
            }

            # Mark as non-cancellable if in terminal state
            if state in ['Filled', 'Cancelled', 'Rejected']:
                self._non_cancellable.add(order_id)

# Export enhanced instance
enhanced_order_state_cache = EnhancedOrderStateCache()
