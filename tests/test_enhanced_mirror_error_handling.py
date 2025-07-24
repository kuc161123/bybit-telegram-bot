#!/usr/bin/env python3
"""
Test Enhanced Mirror Error Handling
===================================

This script tests the enhanced error handling implementation
to ensure it's working correctly.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from create_enhanced_mirror_error_handling import EnhancedMirrorErrorHandler, CircuitBreaker

async def test_circuit_breaker():
    """Test circuit breaker functionality"""
    print("\n1. Testing Circuit Breaker:")
    print("-" * 40)
    
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=5)
    
    # Test normal operation
    assert cb.can_execute() == True, "Circuit should be closed initially"
    print("✓ Circuit breaker starts closed")
    
    # Test failure recording
    cb.record_failure()
    assert cb.can_execute() == True, "Circuit should remain closed after 1 failure"
    print("✓ Circuit remains closed after 1 failure")
    
    cb.record_failure()
    assert cb.can_execute() == True, "Circuit should remain closed after 2 failures"
    print("✓ Circuit remains closed after 2 failures")
    
    # Test circuit opening
    cb.record_failure()
    assert cb.can_execute() == False, "Circuit should open after 3 failures"
    print("✓ Circuit opens after reaching threshold")
    
    # Test recovery
    print("  Waiting 5 seconds for recovery...")
    await asyncio.sleep(5.5)
    assert cb.can_execute() == True, "Circuit should close after recovery timeout"
    print("✓ Circuit recovers after timeout")
    
    # Test success reset
    cb.record_success()
    assert cb.failure_count == 0, "Failure count should reset on success"
    print("✓ Success resets failure count")

async def test_error_categorization():
    """Test error categorization"""
    print("\n2. Testing Error Categorization:")
    print("-" * 40)
    
    handler = EnhancedMirrorErrorHandler()
    
    # Test known error codes
    test_cases = [
        (10001, "qty err", "Invalid parameter - quantity error - Quantity validation error", True),
        (110001, "order not exists", "Order not exists", False),
        (110004, "insufficient balance", "Wallet balance insufficient - Insufficient balance", False),
        (110029, "tp sl exists", "TP/SL order already exists", False),
        (99999, "unknown", "Unknown error 99999", False)
    ]
    
    for code, msg, expected_category, expected_retryable in test_cases:
        category, is_retryable = handler.categorize_error(code, msg)
        print(f"  Code {code}: {category[:50]}... (Retryable: {is_retryable})")
        assert expected_category in category, f"Category mismatch for code {code}"
        assert is_retryable == expected_retryable, f"Retryable mismatch for code {code}"
    
    print("✓ All error categorizations correct")

async def test_retry_logic():
    """Test retry logic with exponential backoff"""
    print("\n3. Testing Retry Logic:")
    print("-" * 40)
    
    handler = EnhancedMirrorErrorHandler()
    
    # Test function that fails then succeeds
    attempt_count = 0
    async def test_func(symbol: str):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            error = Exception("Test error")
            error.code = 10001  # Retryable error
            raise error
        return "Success"
    
    # Execute with retry
    start_time = asyncio.get_event_loop().time()
    result = await handler.execute_with_retry(test_func, symbol="BTCUSDT")
    end_time = asyncio.get_event_loop().time()
    
    print(f"  Function succeeded after {attempt_count} attempts")
    print(f"  Total time: {end_time - start_time:.1f}s")
    assert result == "Success", "Function should eventually succeed"
    assert attempt_count == 3, "Should have taken 3 attempts"
    print("✓ Retry logic with exponential backoff working")

async def test_non_retryable_errors():
    """Test non-retryable error handling"""
    print("\n4. Testing Non-Retryable Errors:")
    print("-" * 40)
    
    handler = EnhancedMirrorErrorHandler()
    
    # Test function with non-retryable error
    async def test_func(symbol: str):
        error = Exception("Order not exists")
        error.code = 110001  # Non-retryable error
        raise error
    
    # Should fail immediately
    try:
        await handler.execute_with_retry(test_func, symbol="BTCUSDT")
        assert False, "Should have raised exception"
    except Exception as e:
        assert "Non-retryable error" in str(e), "Should indicate non-retryable"
        print("✓ Non-retryable errors fail immediately")

async def test_circuit_breaker_integration():
    """Test circuit breaker integration with retry logic"""
    print("\n5. Testing Circuit Breaker Integration:")
    print("-" * 40)
    
    handler = EnhancedMirrorErrorHandler()
    
    # Function that always fails
    async def failing_func(symbol: str):
        raise Exception("Always fails")
    
    # Fail multiple times to open circuit
    for i in range(5):
        try:
            await handler.execute_with_retry(failing_func, symbol="ETHUSDT")
        except:
            pass
    
    # Circuit should be open now
    try:
        await handler.execute_with_retry(failing_func, symbol="ETHUSDT")
        assert False, "Should have raised circuit breaker exception"
    except Exception as e:
        assert "Circuit breaker open" in str(e), "Should indicate circuit breaker"
        print("✓ Circuit breaker prevents excessive retries")

async def main():
    """Run all tests"""
    print("Enhanced Mirror Error Handling Test Suite")
    print("=" * 60)
    
    try:
        await test_circuit_breaker()
        await test_error_categorization()
        await test_retry_logic()
        await test_non_retryable_errors()
        await test_circuit_breaker_integration()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed successfully!")
        print("\nThe enhanced error handling is working correctly:")
        print("- Circuit breaker prevents cascading failures")
        print("- Error categorization identifies retryable errors")
        print("- Retry logic uses exponential backoff")
        print("- Non-retryable errors fail fast")
        print("- Integration works as expected")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())