#!/usr/bin/env python3
"""
Test suite for the robust trading bot systems
Tests alert delivery, order management, and health monitoring
"""
import asyncio
import logging
import time
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.robust_alerts import (
    RobustAlertSystem, AlertMessage, AlertPriority, CircuitBreaker,
    AlertDeduplicator, send_trade_alert_robust
)
from utils.robust_orders import (
    RobustOrderManager, AtomicOrderOperation, OrderOperationLock,
    IdempotencyManager, OrderValidation
)
from utils.monitor_health import (
    MonitorHealthChecker, HealthStatus, RecoveryAction,
    get_health_checker
)

class TestRobustAlerts:
    """Test robust alert system"""
    
    def __init__(self):
        self.mock_bot = Mock()
        self.mock_bot.send_message = AsyncMock()
        self.alert_system = RobustAlertSystem(self.mock_bot)
    
    async def test_alert_retry(self):
        """Test alert retry mechanism"""
        logger.info("Testing alert retry mechanism...")
        
        # Configure bot to fail twice then succeed
        self.mock_bot.send_message.side_effect = [
            Exception("Network error"),
            Exception("Timeout"),
            None  # Success on third try
        ]
        
        # Send alert
        success = await self.alert_system.send_alert(
            alert_type="tp_hit",
            chat_id=123456,
            symbol="BTCUSDT",
            side="Buy",
            approach="fast",
            priority=AlertPriority.HIGH,
            pnl=Decimal("100"),
            entry_price=Decimal("50000"),
            current_price=Decimal("51000"),
            position_size=Decimal("0.1")
        )
        
        # Allow processing time
        await asyncio.sleep(3)
        
        # Verify retry happened
        assert self.mock_bot.send_message.call_count >= 3
        logger.info("✅ Alert retry test passed")
    
    async def test_circuit_breaker(self):
        """Test circuit breaker functionality"""
        logger.info("Testing circuit breaker...")
        
        breaker = CircuitBreaker(failure_threshold=3, timeout=2)
        
        # Mock function that fails
        async def failing_func():
            raise Exception("Service unavailable")
        
        # Trigger failures
        for i in range(3):
            try:
                await breaker.call(failing_func)
            except Exception:
                pass
        
        # Circuit should be open now
        try:
            await breaker.call(failing_func)
            assert False, "Circuit breaker should be open"
        except Exception as e:
            assert "Circuit breaker is open" in str(e)
        
        logger.info("✅ Circuit breaker test passed")
    
    async def test_deduplication(self):
        """Test alert deduplication"""
        logger.info("Testing alert deduplication...")
        
        dedup = AlertDeduplicator(ttl=5)
        
        alert1 = AlertMessage(
            chat_id=123,
            alert_type="tp_hit",
            symbol="BTCUSDT",
            side="Buy",
            approach="fast",
            priority=AlertPriority.HIGH,
            data={}
        )
        
        # First alert should not be duplicate
        is_dup1 = await dedup.is_duplicate(alert1)
        assert not is_dup1
        
        # Same alert should be duplicate
        is_dup2 = await dedup.is_duplicate(alert1)
        assert is_dup2
        
        logger.info("✅ Deduplication test passed")
    
    async def test_priority_queue(self):
        """Test priority queue processing"""
        logger.info("Testing priority queue...")
        
        # Clear any existing alerts
        while not self.alert_system._queue.empty():
            self.alert_system._queue.get_nowait()
        
        # Add alerts with different priorities
        await self.alert_system.send_alert(
            alert_type="limit_filled",
            chat_id=123,
            symbol="BTCUSDT",
            side="Buy",
            approach="conservative",
            priority=AlertPriority.LOW,
            additional_info={"limit_number": 1}
        )
        
        await self.alert_system.send_alert(
            alert_type="sl_hit",
            chat_id=123,
            symbol="BTCUSDT",
            side="Buy",
            approach="fast",
            priority=AlertPriority.CRITICAL,
            pnl=Decimal("-50"),
            entry_price=Decimal("50000"),
            current_price=Decimal("49000"),
            position_size=Decimal("0.1")
        )
        
        # Critical alert should be processed first
        priority, _, alert = await self.alert_system._queue.get()
        assert alert.priority == AlertPriority.CRITICAL
        
        logger.info("✅ Priority queue test passed")

class TestRobustOrders:
    """Test robust order management"""
    
    def __init__(self):
        self.order_manager = RobustOrderManager()
    
    async def test_atomic_operation(self):
        """Test atomic order operation with rollback"""
        logger.info("Testing atomic order operations...")
        
        chat_data = {
            "sl_order_id": "original_sl_123",
            "tp_order_ids": ["tp1", "tp2", "tp3"],
            "position_status": "active"
        }
        
        try:
            async with AtomicOrderOperation(chat_data, "test_operation") as atomic_op:
                # Modify state
                chat_data["sl_order_id"] = None
                chat_data["tp_order_ids"].remove("tp1")
                
                # Simulate error
                raise Exception("Test error")
        except Exception:
            pass
        
        # State should be rolled back
        assert chat_data["sl_order_id"] == "original_sl_123"
        assert "tp1" in chat_data["tp_order_ids"]
        
        logger.info("✅ Atomic operation test passed")
    
    async def test_idempotency(self):
        """Test idempotent operations"""
        logger.info("Testing idempotency...")
        
        idempotency = IdempotencyManager(ttl=10)
        
        call_count = 0
        async def test_func(value):
            nonlocal call_count
            call_count += 1
            return f"result_{value}"
        
        # First call
        result1, cached1 = await idempotency.execute_once("test_op", test_func, "test")
        assert result1 == "result_test"
        assert not cached1
        assert call_count == 1
        
        # Second call should be cached
        result2, cached2 = await idempotency.execute_once("test_op", test_func, "test")
        assert result2 == "result_test"
        assert cached2
        assert call_count == 1  # Function not called again
        
        logger.info("✅ Idempotency test passed")
    
    async def test_order_lock(self):
        """Test order operation locking"""
        logger.info("Testing order locks...")
        
        lock1 = await OrderOperationLock.get_lock("BTCUSDT", "cancel_tp")
        lock2 = await OrderOperationLock.get_lock("BTCUSDT", "cancel_tp")
        
        # Should be the same lock
        assert lock1 is lock2
        
        # Different operation should have different lock
        lock3 = await OrderOperationLock.get_lock("BTCUSDT", "cancel_sl")
        assert lock3 is not lock1
        
        logger.info("✅ Order lock test passed")
    
    def test_order_validation(self):
        """Test order parameter validation"""
        logger.info("Testing order validation...")
        
        # Valid order
        valid, error = OrderValidation.validate_order_params(
            symbol="BTCUSDT",
            side="Buy",
            order_type="Limit",
            qty=Decimal("0.1"),
            price=Decimal("50000")
        )
        assert valid
        assert error is None
        
        # Invalid side
        valid, error = OrderValidation.validate_order_params(
            symbol="BTCUSDT",
            side="Invalid",
            order_type="Market",
            qty=Decimal("0.1")
        )
        assert not valid
        assert "Invalid side" in error
        
        # Missing price for limit order
        valid, error = OrderValidation.validate_order_params(
            symbol="BTCUSDT",
            side="Buy",
            order_type="Limit",
            qty=Decimal("0.1")
        )
        assert not valid
        assert "requires price" in error
        
        logger.info("✅ Order validation test passed")

class TestMonitorHealth:
    """Test monitor health system"""
    
    def __init__(self):
        self.health_checker = MonitorHealthChecker()
    
    async def test_health_registration(self):
        """Test monitor registration and health check"""
        logger.info("Testing health registration...")
        
        # Register monitor
        self.health_checker.register_monitor(
            monitor_id="test_monitor_1",
            symbol="BTCUSDT",
            chat_id=123456
        )
        
        # Get health
        monitor = self.health_checker.get_monitor_health("test_monitor_1")
        assert monitor is not None
        assert monitor.symbol == "BTCUSDT"
        assert monitor.chat_id == 123456
        
        # Unregister
        self.health_checker.unregister_monitor("test_monitor_1")
        monitor = self.health_checker.get_monitor_health("test_monitor_1")
        assert monitor is None
        
        logger.info("✅ Health registration test passed")
    
    async def test_health_metrics(self):
        """Test health metrics collection"""
        logger.info("Testing health metrics...")
        
        # Register monitor
        self.health_checker.register_monitor(
            monitor_id="test_monitor_2",
            symbol="ETHUSDT",
            chat_id=789012
        )
        
        # Update activity
        self.health_checker.update_monitor_activity("test_monitor_2")
        
        monitor = self.health_checker.get_monitor_health("test_monitor_2")
        assert monitor.last_activity > monitor.monitor_start_time
        
        logger.info("✅ Health metrics test passed")
    
    async def test_recovery_actions(self):
        """Test recovery action determination"""
        logger.info("Testing recovery actions...")
        
        from utils.monitor_health import HealthMetrics
        
        # High memory usage
        metrics1 = HealthMetrics()
        metrics1.memory_usage_mb = 600
        actions1 = self.health_checker._determine_recovery_actions(metrics1)
        assert RecoveryAction.CLEAR_CACHE in actions1
        
        # API connectivity issues
        metrics2 = HealthMetrics()
        metrics2.bybit_connected = False
        actions2 = self.health_checker._determine_recovery_actions(metrics2)
        assert RecoveryAction.RECONNECT_SERVICES in actions2
        
        # Multiple errors
        metrics3 = HealthMetrics()
        metrics3.errors = ["Error 1", "Error 2", "Error 3"]
        actions3 = self.health_checker._determine_recovery_actions(metrics3)
        assert RecoveryAction.RESTART_MONITOR in actions3
        
        logger.info("✅ Recovery actions test passed")

async def run_all_tests():
    """Run all test suites"""
    logger.info("Starting robust systems test suite...")
    
    # Test robust alerts
    alert_tests = TestRobustAlerts()
    await alert_tests.test_alert_retry()
    await alert_tests.test_circuit_breaker()
    await alert_tests.test_deduplication()
    await alert_tests.test_priority_queue()
    
    # Test robust orders
    order_tests = TestRobustOrders()
    await order_tests.test_atomic_operation()
    await order_tests.test_idempotency()
    await order_tests.test_order_lock()
    order_tests.test_order_validation()
    
    # Test monitor health
    health_tests = TestMonitorHealth()
    await health_tests.test_health_registration()
    await health_tests.test_health_metrics()
    await health_tests.test_recovery_actions()
    
    logger.info("\n✅ All tests passed successfully!")
    logger.info("\nRobust systems are ready for integration.")

if __name__ == "__main__":
    asyncio.run(run_all_tests())