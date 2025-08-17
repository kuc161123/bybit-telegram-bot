#!/usr/bin/env python3
"""
Circuit Breaker Pattern Implementation
Prevents cascade failures by stopping requests to failing services
"""
import time
import logging
from typing import Any, Callable, Optional, Dict
from enum import Enum
from threading import RLock
import asyncio

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"      # Failures exceeded threshold, blocking requests
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered

class CircuitBreaker:
    """
    Circuit breaker implementation for fault tolerance
    """
    
    def __init__(self, 
                 name: str,
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60,
                 expected_exception: type = Exception):
        """
        Initialize circuit breaker
        
        Args:
            name: Name of the circuit breaker (for logging)
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type to catch (others will pass through)
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self._lock = RLock()
        
        # Statistics
        self.call_count = 0
        self.success_count = 0
        self.failure_total = 0
        self.circuit_opened_count = 0
        
    def _reset(self) -> None:
        """Reset the circuit breaker to closed state"""
        with self._lock:
            self.failure_count = 0
            self.last_failure_time = None
            self.state = CircuitState.CLOSED
            logger.info(f"Circuit breaker '{self.name}' reset to CLOSED state")
    
    def _trip(self) -> None:
        """Trip the circuit breaker to open state"""
        with self._lock:
            self.state = CircuitState.OPEN
            self.last_failure_time = time.time()
            self.circuit_opened_count += 1
            logger.warning(f"Circuit breaker '{self.name}' tripped to OPEN state after {self.failure_count} failures")
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        return (self.last_failure_time and 
                time.time() - self.last_failure_time >= self.recovery_timeout)
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        with self._lock:
            self.call_count += 1
            
            # Check circuit state
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    logger.info(f"Circuit breaker '{self.name}' attempting recovery (HALF_OPEN)")
                else:
                    time_remaining = self.recovery_timeout - (time.time() - self.last_failure_time)
                    raise Exception(f"Circuit breaker '{self.name}' is OPEN. Retry in {time_remaining:.0f} seconds")
        
        # Try to execute the function
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    async def async_call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute async function with circuit breaker protection
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        with self._lock:
            self.call_count += 1
            
            # Check circuit state
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    logger.info(f"Circuit breaker '{self.name}' attempting recovery (HALF_OPEN)")
                else:
                    time_remaining = self.recovery_timeout - (time.time() - self.last_failure_time)
                    raise Exception(f"Circuit breaker '{self.name}' is OPEN. Retry in {time_remaining:.0f} seconds")
        
        # Try to execute the function
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self) -> None:
        """Handle successful function execution"""
        with self._lock:
            self.success_count += 1
            
            if self.state == CircuitState.HALF_OPEN:
                self._reset()
                logger.info(f"Circuit breaker '{self.name}' recovered successfully")
            else:
                self.failure_count = 0  # Reset failure count on success
    
    def _on_failure(self) -> None:
        """Handle function execution failure"""
        with self._lock:
            self.failure_count += 1
            self.failure_total += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                self._trip()
                logger.warning(f"Circuit breaker '{self.name}' recovery failed, returning to OPEN")
            elif self.failure_count >= self.failure_threshold:
                self._trip()
    
    def get_state(self) -> str:
        """Get current circuit breaker state"""
        return self.state.value
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        success_rate = (self.success_count / self.call_count * 100) if self.call_count > 0 else 0
        
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'failure_threshold': self.failure_threshold,
            'total_calls': self.call_count,
            'total_successes': self.success_count,
            'total_failures': self.failure_total,
            'success_rate': success_rate,
            'circuit_opened_count': self.circuit_opened_count,
            'last_failure_time': self.last_failure_time
        }
    
    def reset(self) -> None:
        """Manually reset the circuit breaker"""
        self._reset()
    
    def is_open(self) -> bool:
        """Check if circuit is open"""
        return self.state == CircuitState.OPEN
    
    def is_closed(self) -> bool:
        """Check if circuit is closed"""
        return self.state == CircuitState.CLOSED


class CircuitBreakerManager:
    """Manages multiple circuit breakers"""
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
        self._lock = RLock()
    
    def get_or_create(self, 
                      name: str,
                      failure_threshold: int = 5,
                      recovery_timeout: int = 60,
                      expected_exception: type = Exception) -> CircuitBreaker:
        """
        Get existing circuit breaker or create new one
        
        Args:
            name: Circuit breaker name
            failure_threshold: Failure threshold
            recovery_timeout: Recovery timeout in seconds
            expected_exception: Expected exception type
            
        Returns:
            Circuit breaker instance
        """
        with self._lock:
            if name not in self.breakers:
                self.breakers[name] = CircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout,
                    expected_exception=expected_exception
                )
                logger.info(f"Created new circuit breaker: {name}")
            
            return self.breakers[name]
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers"""
        with self._lock:
            return {name: breaker.get_stats() for name, breaker in self.breakers.items()}
    
    def reset_all(self) -> None:
        """Reset all circuit breakers"""
        with self._lock:
            for breaker in self.breakers.values():
                breaker.reset()
            logger.info(f"Reset all {len(self.breakers)} circuit breakers")
    
    def get_open_circuits(self) -> List[str]:
        """Get list of open circuit breakers"""
        with self._lock:
            return [name for name, breaker in self.breakers.items() if breaker.is_open()]


# Global circuit breaker manager
circuit_manager = CircuitBreakerManager()

# Pre-configured circuit breakers for common operations
api_circuit_breaker = circuit_manager.get_or_create(
    "bybit_api",
    failure_threshold=5,
    recovery_timeout=60
)

position_circuit_breaker = circuit_manager.get_or_create(
    "position_fetch",
    failure_threshold=3,
    recovery_timeout=30
)

order_circuit_breaker = circuit_manager.get_or_create(
    "order_placement",
    failure_threshold=3,
    recovery_timeout=45
)


def with_circuit_breaker(breaker_name: str, 
                         failure_threshold: int = 5,
                         recovery_timeout: int = 60):
    """
    Decorator to add circuit breaker protection to functions
    
    Args:
        breaker_name: Name of the circuit breaker
        failure_threshold: Number of failures before opening
        recovery_timeout: Recovery timeout in seconds
    """
    def decorator(func):
        breaker = circuit_manager.get_or_create(
            breaker_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )
        
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                return await breaker.async_call(func, *args, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                return breaker.call(func, *args, **kwargs)
            return sync_wrapper
    
    return decorator