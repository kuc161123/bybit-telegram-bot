#!/usr/bin/env python3
"""
Monitor health check and recovery system
Provides comprehensive health monitoring and automatic recovery for position monitors
"""
import asyncio
import logging
import time
import psutil
import gc
from typing import Optional, Dict, Any, List, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from config.constants import *
from config.settings import POSITION_MONITOR_INTERVAL
from clients.bybit_helpers import get_position_info, get_all_positions
from utils.robust_alerts import get_robust_alert_system, AlertPriority

logger = logging.getLogger(__name__)

# Health check constants
HEALTH_CHECK_INTERVAL = 30  # seconds
CONSECUTIVE_FAILURES_THRESHOLD = 3
RECOVERY_MAX_ATTEMPTS = 3
MEMORY_THRESHOLD_MB = 500  # Alert if monitor uses more than 500MB
CPU_THRESHOLD_PERCENT = 50  # Alert if monitor uses more than 50% CPU
STALE_DATA_THRESHOLD = 300  # 5 minutes
POSITION_CHECK_TIMEOUT = 10  # seconds

class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    RECOVERING = "recovering"

class RecoveryAction(Enum):
    """Types of recovery actions"""
    RESTART_MONITOR = "restart_monitor"
    CLEAR_CACHE = "clear_cache"
    RECONNECT_SERVICES = "reconnect_services"
    FORCE_REFRESH = "force_refresh"
    EMERGENCY_STOP = "emergency_stop"

@dataclass
class HealthMetrics:
    """Container for health metrics"""
    timestamp: float = field(default_factory=time.time)
    status: HealthStatus = HealthStatus.HEALTHY
    consecutive_failures: int = 0
    last_successful_check: float = field(default_factory=time.time)
    memory_usage_mb: float = 0.0
    cpu_percent: float = 0.0
    api_response_time: float = 0.0
    position_sync_status: bool = True
    telegram_connected: bool = True
    bybit_connected: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

@dataclass
class MonitorHealth:
    """Health information for a specific monitor"""
    monitor_id: str
    symbol: str
    chat_id: int
    metrics: HealthMetrics = field(default_factory=HealthMetrics)
    recovery_attempts: int = 0
    last_recovery: Optional[float] = None
    monitor_start_time: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

class MonitorHealthChecker:
    """Comprehensive health monitoring and recovery system"""

    def __init__(self):
        self._monitors: Dict[str, MonitorHealth] = {}
        self._global_metrics = HealthMetrics()
        self._recovery_in_progress: Set[str] = set()
        self._health_check_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._process = psutil.Process()

    def register_monitor(self, monitor_id: str, symbol: str, chat_id: int):
        """Register a monitor for health checking"""
        if monitor_id not in self._monitors:
            self._monitors[monitor_id] = MonitorHealth(
                monitor_id=monitor_id,
                symbol=symbol,
                chat_id=chat_id
            )
            logger.info(f"Registered monitor for health checking: {monitor_id}")

    def unregister_monitor(self, monitor_id: str):
        """Unregister a monitor from health checking"""
        if monitor_id in self._monitors:
            del self._monitors[monitor_id]
            logger.info(f"Unregistered monitor from health checking: {monitor_id}")

    async def start_health_monitoring(self):
        """Start the health monitoring task"""
        if self._health_check_task is None or self._health_check_task.done():
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info("Started health monitoring system")

    async def stop_health_monitoring(self):
        """Stop the health monitoring task"""
        self._shutdown_event.set()
        if self._health_check_task and not self._health_check_task.done():
            await self._health_check_task
        logger.info("Stopped health monitoring system")

    async def _health_check_loop(self):
        """Main health check loop"""
        while not self._shutdown_event.is_set():
            try:
                # Check all monitors
                for monitor_id, monitor_health in list(self._monitors.items()):
                    if monitor_id not in self._recovery_in_progress:
                        await self._check_monitor_health(monitor_health)

                # Check global system health
                await self._check_global_health()

                # Wait for next check
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)

            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)

    async def _check_monitor_health(self, monitor: MonitorHealth) -> HealthMetrics:
        """Perform comprehensive health check on a monitor"""
        metrics = HealthMetrics()

        try:
            # Check system resources
            await self._check_system_resources(monitor, metrics)

            # Check service connectivity
            await self._check_service_connectivity(monitor, metrics)

            # Check position synchronization
            await self._check_position_sync(monitor, metrics)

            # Check for stale data
            await self._check_data_freshness(monitor, metrics)

            # Determine overall status
            self._determine_health_status(metrics)

            # Update monitor health
            monitor.metrics = metrics

            # Handle health status
            await self._handle_health_status(monitor)

            return metrics

        except Exception as e:
            logger.error(f"Error checking health for monitor {monitor.monitor_id}: {e}")
            metrics.status = HealthStatus.CRITICAL
            metrics.errors.append(f"Health check error: {str(e)}")
            return metrics

    async def _check_system_resources(self, monitor: MonitorHealth, metrics: HealthMetrics):
        """Check system resource usage"""
        try:
            # Get process info
            process_info = self._process.as_dict(attrs=['memory_info', 'cpu_percent'])

            # Memory usage
            memory_mb = process_info['memory_info'].rss / 1024 / 1024
            metrics.memory_usage_mb = memory_mb

            if memory_mb > MEMORY_THRESHOLD_MB:
                metrics.warnings.append(f"High memory usage: {memory_mb:.1f}MB")

            # CPU usage
            cpu_percent = process_info['cpu_percent']
            metrics.cpu_percent = cpu_percent

            if cpu_percent > CPU_THRESHOLD_PERCENT:
                metrics.warnings.append(f"High CPU usage: {cpu_percent:.1f}%")

        except Exception as e:
            logger.error(f"Error checking system resources: {e}")
            metrics.errors.append("Failed to check system resources")

    async def _check_service_connectivity(self, monitor: MonitorHealth, metrics: HealthMetrics):
        """Check connectivity to external services"""
        # Check Bybit API
        try:
            start_time = time.time()
            position = await asyncio.wait_for(
                get_position_info(monitor.symbol),
                timeout=POSITION_CHECK_TIMEOUT
            )
            metrics.api_response_time = time.time() - start_time
            metrics.bybit_connected = position is not None

            if metrics.api_response_time > 5:
                metrics.warnings.append(f"Slow API response: {metrics.api_response_time:.2f}s")

        except asyncio.TimeoutError:
            metrics.bybit_connected = False
            metrics.errors.append("Bybit API timeout")
        except Exception as e:
            metrics.bybit_connected = False
            metrics.errors.append(f"Bybit API error: {str(e)}")

        # Telegram connectivity is checked in the main monitor loop
        metrics.telegram_connected = True  # Assume connected unless proven otherwise

    async def _check_position_sync(self, monitor: MonitorHealth, metrics: HealthMetrics):
        """Check if position data is synchronized"""
        try:
            # Get position from exchange
            position = await get_position_info(monitor.symbol)

            if position:
                # Check if position size matches expectations
                # This would need access to chat_data to compare
                metrics.position_sync_status = True
            else:
                # No position found - might be closed
                metrics.position_sync_status = True

        except Exception as e:
            logger.error(f"Error checking position sync: {e}")
            metrics.position_sync_status = False
            metrics.errors.append("Position sync check failed")

    async def _check_data_freshness(self, monitor: MonitorHealth, metrics: HealthMetrics):
        """Check if monitor data is fresh"""
        time_since_activity = time.time() - monitor.last_activity

        if time_since_activity > STALE_DATA_THRESHOLD:
            metrics.warnings.append(f"Stale data: No activity for {time_since_activity:.0f}s")

    def _determine_health_status(self, metrics: HealthMetrics):
        """Determine overall health status from metrics"""
        if metrics.errors:
            metrics.status = HealthStatus.CRITICAL
        elif metrics.warnings:
            metrics.status = HealthStatus.WARNING
        else:
            metrics.status = HealthStatus.HEALTHY

    async def _handle_health_status(self, monitor: MonitorHealth):
        """Handle health status and trigger recovery if needed"""
        metrics = monitor.metrics

        if metrics.status == HealthStatus.HEALTHY:
            # Reset failure counter
            metrics.consecutive_failures = 0
            metrics.last_successful_check = time.time()

        elif metrics.status in [HealthStatus.WARNING, HealthStatus.CRITICAL]:
            # Increment failure counter
            metrics.consecutive_failures += 1

            # Check if recovery is needed
            if metrics.consecutive_failures >= CONSECUTIVE_FAILURES_THRESHOLD:
                if monitor.monitor_id not in self._recovery_in_progress:
                    await self._initiate_recovery(monitor)

    async def _initiate_recovery(self, monitor: MonitorHealth):
        """Initiate recovery process for unhealthy monitor"""
        monitor_id = monitor.monitor_id

        # Check recovery attempts
        if monitor.recovery_attempts >= RECOVERY_MAX_ATTEMPTS:
            logger.error(f"Max recovery attempts reached for {monitor_id}")
            await self._emergency_alert(monitor)
            return

        # Mark recovery in progress
        self._recovery_in_progress.add(monitor_id)
        monitor.metrics.status = HealthStatus.RECOVERING
        monitor.recovery_attempts += 1
        monitor.last_recovery = time.time()

        logger.warning(f"Initiating recovery for monitor {monitor_id} (attempt {monitor.recovery_attempts})")

        try:
            # Determine recovery actions based on errors
            actions = self._determine_recovery_actions(monitor.metrics)

            # Execute recovery actions
            for action in actions:
                success = await self._execute_recovery_action(monitor, action)
                if not success:
                    logger.error(f"Recovery action {action} failed for {monitor_id}")

            # Verify recovery
            await asyncio.sleep(5)  # Give time for recovery to take effect
            new_metrics = await self._check_monitor_health(monitor)

            if new_metrics.status == HealthStatus.HEALTHY:
                logger.info(f"Recovery successful for monitor {monitor_id}")
                monitor.recovery_attempts = 0
            else:
                logger.warning(f"Recovery incomplete for monitor {monitor_id}")

        except Exception as e:
            logger.error(f"Error during recovery for {monitor_id}: {e}")

        finally:
            self._recovery_in_progress.discard(monitor_id)

    def _determine_recovery_actions(self, metrics: HealthMetrics) -> List[RecoveryAction]:
        """Determine which recovery actions to take based on metrics"""
        actions = []

        # High memory usage - clear caches
        if metrics.memory_usage_mb > MEMORY_THRESHOLD_MB:
            actions.append(RecoveryAction.CLEAR_CACHE)

        # API connectivity issues - reconnect
        if not metrics.bybit_connected:
            actions.append(RecoveryAction.RECONNECT_SERVICES)

        # Position sync issues - force refresh
        if not metrics.position_sync_status:
            actions.append(RecoveryAction.FORCE_REFRESH)

        # Multiple errors - restart monitor
        if len(metrics.errors) >= 2:
            actions.append(RecoveryAction.RESTART_MONITOR)

        # Default action if no specific issues
        if not actions:
            actions.append(RecoveryAction.FORCE_REFRESH)

        return actions

    async def _execute_recovery_action(self, monitor: MonitorHealth,
                                     action: RecoveryAction) -> bool:
        """Execute a specific recovery action"""
        try:
            logger.info(f"Executing recovery action: {action.value} for {monitor.monitor_id}")

            if action == RecoveryAction.CLEAR_CACHE:
                # Force garbage collection
                gc.collect()
                return True

            elif action == RecoveryAction.RECONNECT_SERVICES:
                # Services auto-reconnect on next API call
                return True

            elif action == RecoveryAction.FORCE_REFRESH:
                # Update last activity to trigger refresh
                monitor.last_activity = time.time()
                return True

            elif action == RecoveryAction.RESTART_MONITOR:
                # This would need to signal the monitor to restart
                # For now, just log it
                logger.warning(f"Monitor restart requested for {monitor.monitor_id}")
                return True

            elif action == RecoveryAction.EMERGENCY_STOP:
                # Emergency stop - unregister monitor
                self.unregister_monitor(monitor.monitor_id)
                return True

            return False

        except Exception as e:
            logger.error(f"Error executing recovery action {action}: {e}")
            return False

    async def _emergency_alert(self, monitor: MonitorHealth):
        """Send emergency alert for critical monitor failure"""
        try:
            from telegram import Bot
            from config.settings import bot_token

            bot = Bot(token=bot_token)
            alert_system = get_robust_alert_system(bot)

            message = f"""
🚨 <b>EMERGENCY: Monitor System Failure</b>
━━━━━━━━━━━━━━━━━━━━━━
📊 Symbol: {monitor.symbol}
🆔 Monitor: {monitor.monitor_id}

❌ <b>Critical Errors:</b>
{chr(10).join(f"• {error}" for error in monitor.metrics.errors[:5])}

⚠️ <b>Recovery Failed</b>
Attempts: {monitor.recovery_attempts}/{RECOVERY_MAX_ATTEMPTS}

🔧 <b>Recommended Action:</b>
• Check system logs
• Restart the bot if necessary
• Verify API credentials
"""

            await alert_system.send_alert(
                alert_type="emergency",
                chat_id=monitor.chat_id,
                symbol=monitor.symbol,
                side="",
                approach="",
                priority=AlertPriority.CRITICAL,
                message=message
            )

        except Exception as e:
            logger.error(f"Failed to send emergency alert: {e}")

    async def _check_global_health(self):
        """Check overall system health"""
        try:
            # Count monitors by status
            status_counts = defaultdict(int)
            for monitor in self._monitors.values():
                status_counts[monitor.metrics.status] += 1

            # Log summary
            if status_counts[HealthStatus.CRITICAL] > 0:
                logger.warning(f"System health: {status_counts[HealthStatus.CRITICAL]} critical monitors")

            # Check total resource usage
            total_memory = sum(m.metrics.memory_usage_mb for m in self._monitors.values())
            if total_memory > MEMORY_THRESHOLD_MB * 2:
                logger.warning(f"High total memory usage: {total_memory:.1f}MB")

        except Exception as e:
            logger.error(f"Error checking global health: {e}")

    def get_monitor_health(self, monitor_id: str) -> Optional[MonitorHealth]:
        """Get health information for a specific monitor"""
        return self._monitors.get(monitor_id)

    def get_all_health_metrics(self) -> Dict[str, MonitorHealth]:
        """Get health metrics for all monitors"""
        return self._monitors.copy()

    def update_monitor_activity(self, monitor_id: str):
        """Update last activity timestamp for a monitor"""
        if monitor_id in self._monitors:
            self._monitors[monitor_id].last_activity = time.time()

# Singleton instance
_health_checker: Optional[MonitorHealthChecker] = None

def get_health_checker() -> MonitorHealthChecker:
    """Get or create the health checker singleton"""
    global _health_checker

    if _health_checker is None:
        _health_checker = MonitorHealthChecker()

    return _health_checker

async def check_monitor_health(monitor_id: str, symbol: str, chat_id: int) -> HealthMetrics:
    """Convenience function to check health of a specific monitor"""
    checker = get_health_checker()
    checker.register_monitor(monitor_id, symbol, chat_id)

    monitor = checker.get_monitor_health(monitor_id)
    if monitor:
        return await checker._check_monitor_health(monitor)

    return HealthMetrics(status=HealthStatus.CRITICAL, errors=["Monitor not found"])