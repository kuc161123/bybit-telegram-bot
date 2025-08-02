#!/usr/bin/env python3
"""
Persistence optimization module to reduce disk I/O overhead.
Implements batched and debounced persistence updates.
"""
import asyncio
import logging
import time
from typing import Optional, Set
from contextlib import suppress

logger = logging.getLogger(__name__)


class PersistenceOptimizer:
    """Optimizes persistence updates by batching and debouncing"""

    def __init__(self, update_interval: float = 5.0):
        """
        Initialize the persistence optimizer.

        Args:
            update_interval: Minimum seconds between persistence updates
        """
        self.update_interval = update_interval
        self.last_update_time = 0
        self.pending_update = False
        self.update_lock = asyncio.Lock()
        self.update_task: Optional[asyncio.Task] = None
        self.app_ref = None
        self._running = True

    def set_app(self, app):
        """Set the application reference for persistence updates"""
        self.app_ref = app

    async def request_update(self, force: bool = False):
        """
        Request a persistence update. Updates are debounced and batched.

        Args:
            force: Force immediate update regardless of debouncing
        """
        if not self.app_ref:
            logger.warning("No app reference set for persistence optimizer")
            return

        current_time = time.time()

        # If forcing or enough time has passed, update immediately
        if force or (current_time - self.last_update_time) >= self.update_interval:
            await self._do_update()
            return

        # Otherwise, schedule a debounced update
        async with self.update_lock:
            self.pending_update = True

            # Cancel existing scheduled update
            if self.update_task and not self.update_task.done():
                self.update_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self.update_task

            # Schedule new update
            self.update_task = asyncio.create_task(self._scheduled_update())

    async def _scheduled_update(self):
        """Execute a scheduled update after the debounce interval"""
        try:
            # Wait for the remaining time in the interval
            time_since_last = time.time() - self.last_update_time
            wait_time = max(0, self.update_interval - time_since_last)

            if wait_time > 0:
                await asyncio.sleep(wait_time)

            # Perform the update if still pending
            async with self.update_lock:
                if self.pending_update and self._running:
                    await self._do_update()

        except asyncio.CancelledError:
            logger.debug("Scheduled persistence update cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in scheduled persistence update: {e}")

    async def _do_update(self):
        """Actually perform the persistence update"""
        try:
            if self.app_ref and hasattr(self.app_ref, 'update_persistence'):
                logger.debug("Performing persistence update")
                await self.app_ref.update_persistence()
                self.last_update_time = time.time()
                self.pending_update = False
                logger.debug("Persistence update completed")
            else:
                logger.warning("App reference missing update_persistence method")

        except Exception as e:
            logger.error(f"Error updating persistence: {e}")

    async def flush(self):
        """Force immediate persistence update and wait for completion"""
        await self.request_update(force=True)

    async def shutdown(self):
        """Shutdown the optimizer and perform final update"""
        logger.info("Shutting down persistence optimizer")
        self._running = False

        # Cancel any pending update task
        if self.update_task and not self.update_task.done():
            self.update_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.update_task

        # Perform final update
        await self.flush()
        logger.info("Persistence optimizer shutdown complete")


# Global instance
persistence_optimizer = PersistenceOptimizer(update_interval=5.0)


# Convenience functions
async def optimize_persistence_update(app, force: bool = False):
    """
    Request an optimized persistence update.

    Args:
        app: The application instance
        force: Force immediate update
    """
    if not persistence_optimizer.app_ref:
        persistence_optimizer.set_app(app)
    await persistence_optimizer.request_update(force)


async def flush_persistence():
    """Force immediate persistence update"""
    await persistence_optimizer.flush()


async def shutdown_persistence_optimizer():
    """Shutdown the persistence optimizer"""
    await persistence_optimizer.shutdown()