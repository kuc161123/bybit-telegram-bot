#!/usr/bin/env python3
"""
Mirror position synchronization monitor.
Ensures mirror positions stay in sync with main positions.
"""

import asyncio
import logging
from datetime import datetime
from typing import Set, Dict

logger = logging.getLogger(__name__)

class MirrorSyncMonitor:
    """Monitor to ensure mirror account stays synchronized with main account."""

    def __init__(self):
        self.check_interval = 300  # Check every 5 minutes
        self.last_check = None
        self.running = False

    async def check_sync_status(self):
        """Check if mirror positions are in sync with main positions."""
        try:
            from clients.bybit_helpers import get_all_positions
            from execution.mirror_trader import get_mirror_positions

            # Get positions from both accounts
            main_positions = await get_all_positions()
            mirror_positions = await get_mirror_positions()

            # Create sets for comparison
            main_active = {
                f"{p['symbol']}-{p['side']}"
                for p in main_positions
                if float(p.get('size', 0)) > 0
            }

            mirror_active = {
                f"{p['symbol']}-{p['side']}"
                for p in mirror_positions
                if float(p.get('size', 0)) > 0
            }

            # Find discrepancies
            mirror_only = mirror_active - main_active
            main_only = main_active - mirror_active

            if mirror_only:
                logger.warning(f"⚠️ Found {len(mirror_only)} orphaned mirror positions: {mirror_only}")
                # Could trigger automatic closure here if desired

            if main_only:
                logger.warning(f"⚠️ Found {len(main_only)} positions not mirrored: {main_only}")

            return len(mirror_only) == 0 and len(main_only) == 0

        except Exception as e:
            logger.error(f"Error checking sync status: {e}")
            return None

    async def start_monitoring(self):
        """Start the synchronization monitor."""
        self.running = True
        logger.info("🔄 Mirror sync monitor started")

        while self.running:
            try:
                is_synced = await self.check_sync_status()

                if is_synced is True:
                    logger.debug("✅ Mirror account is synchronized")
                elif is_synced is False:
                    logger.warning("⚠️ Mirror account is out of sync!")

                await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Error in sync monitor: {e}")
                await asyncio.sleep(60)  # Wait before retry

    def stop(self):
        """Stop the monitor."""
        self.running = False
        logger.info("🛑 Mirror sync monitor stopped")

# Global instance
mirror_sync_monitor = MirrorSyncMonitor()
