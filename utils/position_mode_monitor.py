#!/usr/bin/env python3
"""
Position Mode Monitor - Real-time monitoring and auto-fixing of position mode issues.
Runs continuously to detect and fix any position mode errors that slip through.
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import re

logger = logging.getLogger(__name__)


class PositionModeMonitor:
    """Monitor for position mode issues and auto-fix them."""

    def __init__(self):
        self.check_interval = 5  # Check every 5 seconds
        self.running = False
        self.error_count = {}  # Track errors by symbol
        self.last_fix_attempt = {}  # Prevent fix spam
        self.fix_cooldown = 60  # Seconds between fix attempts
        self.monitored_errors = set()  # Track unique errors

    async def check_logs_for_errors(self) -> List[Dict]:
        """Check recent logs for position mode errors."""
        errors = []

        try:
            # Read last 100 lines of log
            import subprocess
            result = subprocess.run(
                ['tail', '-n', '100', 'trading_bot.log'],
                capture_output=True,
                text=True
            )

            if result.stdout:
                lines = result.stdout.strip().split('\n')

                # Pattern to match position mode errors
                error_pattern = re.compile(
                    r'position idx not match position mode.*symbol["\s:]+(\w+)',
                    re.IGNORECASE
                )

                for line in lines:
                    if 'position idx not match' in line.lower():
                        # Extract symbol from error
                        match = error_pattern.search(line)
                        if match:
                            symbol = match.group(1)

                            # Extract timestamp if possible
                            timestamp_match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                            timestamp = timestamp_match.group(1) if timestamp_match else 'Unknown'

                            error_hash = f"{symbol}_{timestamp}"
                            if error_hash not in self.monitored_errors:
                                self.monitored_errors.add(error_hash)
                                errors.append({
                                    'symbol': symbol,
                                    'timestamp': timestamp,
                                    'full_line': line
                                })

        except Exception as e:
            logger.error(f"Error checking logs: {e}")

        return errors

    async def fix_position_mode_error(self, symbol: str) -> bool:
        """Attempt to fix position mode error for a symbol."""

        # Check cooldown
        last_attempt = self.last_fix_attempt.get(symbol, datetime.min)
        if datetime.now() - last_attempt < timedelta(seconds=self.fix_cooldown):
            return False

        self.last_fix_attempt[symbol] = datetime.now()

        try:
            logger.warning(f"🔧 Attempting to fix position mode for {symbol}")

            # Clear position cache for this symbol
            from utils.position_mode_handler import position_mode_handler
            position_mode_handler.clear_cache(symbol)

            # Force re-detection on next operation
            logger.info(f"✅ Cleared position cache for {symbol}")

            # Send alert
            try:
                from alerts.alert_manager import alert_manager
                await alert_manager.send_alert(
                    f"⚠️ Position Mode Fix Applied\n\n"
                    f"Symbol: {symbol}\n"
                    f"Action: Cache cleared, will re-detect on next order",
                    priority="medium"
                )
            except:
                pass

            return True

        except Exception as e:
            logger.error(f"Failed to fix position mode for {symbol}: {e}")
            return False

    async def monitor_active_orders(self):
        """Monitor active order operations for position mode issues."""

        try:
            # This would integrate with your order tracking system
            # For now, we'll rely on log monitoring
            pass

        except Exception as e:
            logger.error(f"Error monitoring active orders: {e}")

    async def run_monitoring_cycle(self):
        """Run one monitoring cycle."""

        try:
            # Check for recent errors
            errors = await self.check_logs_for_errors()

            if errors:
                logger.warning(f"Found {len(errors)} position mode errors")

                for error in errors:
                    symbol = error['symbol']

                    # Track error count
                    self.error_count[symbol] = self.error_count.get(symbol, 0) + 1

                    # Attempt fix if threshold reached
                    if self.error_count[symbol] >= 2:  # Fix after 2 errors
                        await self.fix_position_mode_error(symbol)
                        self.error_count[symbol] = 0  # Reset counter

            # Clean up old errors (older than 1 hour)
            if len(self.monitored_errors) > 1000:
                self.monitored_errors.clear()

        except Exception as e:
            logger.error(f"Error in monitoring cycle: {e}")

    async def start_monitoring(self):
        """Start the position mode monitor."""

        self.running = True
        logger.info("🔍 Position Mode Monitor started")

        while self.running:
            try:
                await self.run_monitoring_cycle()
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Error in position mode monitor: {e}")
                await asyncio.sleep(30)  # Wait longer on error

    def stop(self):
        """Stop the monitor."""
        self.running = False
        logger.info("🛑 Position Mode Monitor stopped")

    def get_status(self) -> Dict:
        """Get monitor status."""
        return {
            'running': self.running,
            'error_count': dict(self.error_count),
            'monitored_errors': len(self.monitored_errors),
            'last_fix_attempts': {
                symbol: timestamp.isoformat()
                for symbol, timestamp in self.last_fix_attempt.items()
            }
        }


# Global instance
position_mode_monitor = PositionModeMonitor()


async def start_position_mode_monitoring():
    """Start the position mode monitoring in background."""
    asyncio.create_task(position_mode_monitor.start_monitoring())
    logger.info("Position mode monitoring activated")


# Enhanced error handler for order operations
def handle_order_error(error_msg: str, symbol: str = None) -> Dict:
    """Handle order errors and extract position mode issues."""

    response = {
        'is_position_mode_error': False,
        'suggested_fix': None,
        'symbol': symbol
    }

    if 'position idx not match' in error_msg.lower():
        response['is_position_mode_error'] = True

        # Extract symbol if not provided
        if not symbol:
            match = re.search(r'symbol["\s:]+(\w+)', error_msg, re.IGNORECASE)
            if match:
                symbol = match.group(1)
                response['symbol'] = symbol

        # Clear cache for immediate fix
        if symbol:
            from utils.position_mode_handler import position_mode_handler
            position_mode_handler.clear_cache(symbol)
            response['suggested_fix'] = f"Position cache cleared for {symbol}. Retry operation."

        logger.warning(f"Position mode error detected for {symbol}: {error_msg}")

    return response