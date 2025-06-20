#!/usr/bin/env python3
"""
Test script for GGShot screenshot analysis validation
Tests both LONG and SHORT trade scenarios with various edge cases
"""
import asyncio
import logging
from decimal import Decimal
from utils.ggshot_validator import validate_ggshot_parameters, ggshot_validator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_long_trades():
    """Test validation for LONG trades"""
    print("\n" + "="*50)
    print("TESTING LONG TRADES (Buy)")
    print("="*50)
    
    # Test 1: Valid long trade
    print("\n1. Valid Long Trade:")
    params = {
        "primary_entry_price": Decimal("65000"),
        "limit_entry_1_price": Decimal("64800"),
        "limit_entry_2_price": Decimal("64600"),
        "tp1_price": Decimal("66000"),
        "tp2_price": Decimal("67000"),
        "sl_price": Decimal("64000"),
        "leverage": 10,
        "margin_amount": Decimal("100")
    }
    success, errors, validated = await validate_ggshot_parameters(params, "BTCUSDT", "Buy", Decimal("65000"))
    print(f"Result: {'✅ PASS' if success else '❌ FAIL'}")
    if errors:
        print(f"Errors: {errors}")
    
    # Test 2: Invalid - TP below entry
    print("\n2. Invalid - TP below entry:")
    params = {
        "primary_entry_price": Decimal("65000"),
        "tp1_price": Decimal("64000"),  # Wrong direction
        "sl_price": Decimal("64000"),
        "leverage": 10,
        "margin_amount": Decimal("100")
    }
    success, errors, validated = await validate_ggshot_parameters(params, "BTCUSDT", "Buy")
    print(f"Result: {'✅ PASS' if not success else '❌ FAIL'}")  # Should fail
    print(f"Errors: {errors}")
    
    # Test 3: Invalid - SL above entry
    print("\n3. Invalid - SL above entry:")
    params = {
        "primary_entry_price": Decimal("65000"),
        "tp1_price": Decimal("66000"),
        "sl_price": Decimal("66000"),  # Wrong direction
        "leverage": 10,
        "margin_amount": Decimal("100")
    }
    success, errors, validated = await validate_ggshot_parameters(params, "BTCUSDT", "Buy")
    print(f"Result: {'✅ PASS' if not success else '❌ FAIL'}")  # Should fail
    print(f"Errors: {errors}")
    
    # Test 4: Invalid - Limit orders above primary entry
    print("\n4. Invalid - Limit orders above primary entry:")
    params = {
        "primary_entry_price": Decimal("65000"),
        "limit_entry_1_price": Decimal("65200"),  # Should be below for long
        "tp1_price": Decimal("66000"),
        "sl_price": Decimal("64000"),
        "leverage": 10,
        "margin_amount": Decimal("100")
    }
    success, errors, validated = await validate_ggshot_parameters(params, "BTCUSDT", "Buy")
    print(f"Result: {'✅ PASS' if not success else '❌ FAIL'}")  # Should fail
    print(f"Errors: {errors}")

async def test_short_trades():
    """Test validation for SHORT trades"""
    print("\n" + "="*50)
    print("TESTING SHORT TRADES (Sell)")
    print("="*50)
    
    # Test 1: Valid short trade
    print("\n1. Valid Short Trade:")
    params = {
        "primary_entry_price": Decimal("65000"),
        "limit_entry_1_price": Decimal("65200"),
        "limit_entry_2_price": Decimal("65400"),
        "tp1_price": Decimal("64000"),
        "tp2_price": Decimal("63000"),
        "sl_price": Decimal("66000"),
        "leverage": 10,
        "margin_amount": Decimal("100")
    }
    success, errors, validated = await validate_ggshot_parameters(params, "BTCUSDT", "Sell", Decimal("65000"))
    print(f"Result: {'✅ PASS' if success else '❌ FAIL'}")
    if errors:
        print(f"Errors: {errors}")
    
    # Test 2: Invalid - TP above entry
    print("\n2. Invalid - TP above entry:")
    params = {
        "primary_entry_price": Decimal("65000"),
        "tp1_price": Decimal("66000"),  # Wrong direction for short
        "sl_price": Decimal("66000"),
        "leverage": 10,
        "margin_amount": Decimal("100")
    }
    success, errors, validated = await validate_ggshot_parameters(params, "BTCUSDT", "Sell")
    print(f"Result: {'✅ PASS' if not success else '❌ FAIL'}")  # Should fail
    print(f"Errors: {errors}")
    
    # Test 3: Invalid - SL below entry
    print("\n3. Invalid - SL below entry:")
    params = {
        "primary_entry_price": Decimal("65000"),
        "tp1_price": Decimal("64000"),
        "sl_price": Decimal("64000"),  # Wrong direction for short
        "leverage": 10,
        "margin_amount": Decimal("100")
    }
    success, errors, validated = await validate_ggshot_parameters(params, "BTCUSDT", "Sell")
    print(f"Result: {'✅ PASS' if not success else '❌ FAIL'}")  # Should fail
    print(f"Errors: {errors}")
    
    # Test 4: Invalid - Limit orders below primary entry
    print("\n4. Invalid - Limit orders below primary entry:")
    params = {
        "primary_entry_price": Decimal("65000"),
        "limit_entry_1_price": Decimal("64800"),  # Should be above for short
        "tp1_price": Decimal("64000"),
        "sl_price": Decimal("66000"),
        "leverage": 10,
        "margin_amount": Decimal("100")
    }
    success, errors, validated = await validate_ggshot_parameters(params, "BTCUSDT", "Sell")
    print(f"Result: {'✅ PASS' if not success else '❌ FAIL'}")  # Should fail
    print(f"Errors: {errors}")

async def test_edge_cases():
    """Test edge cases and extreme values"""
    print("\n" + "="*50)
    print("TESTING EDGE CASES")
    print("="*50)
    
    # Test 1: Extreme price deviation
    print("\n1. Extreme price deviation:")
    params = {
        "primary_entry_price": Decimal("65000"),
        "tp1_price": Decimal("130000"),  # 100% above entry
        "sl_price": Decimal("32500"),   # 50% below entry
        "leverage": 10,
        "margin_amount": Decimal("100")
    }
    success, errors, validated = await validate_ggshot_parameters(params, "BTCUSDT", "Buy")
    print(f"Result: {'✅ PASS' if not success else '❌ FAIL'}")  # Should fail
    print(f"Errors: {errors}")
    
    # Test 2: Invalid leverage
    print("\n2. Invalid leverage:")
    params = {
        "primary_entry_price": Decimal("65000"),
        "tp1_price": Decimal("66000"),
        "sl_price": Decimal("64000"),
        "leverage": 200,  # Too high
        "margin_amount": Decimal("100")
    }
    success, errors, validated = await validate_ggshot_parameters(params, "BTCUSDT", "Buy")
    print(f"Result: {'✅ PASS' if not success else '❌ FAIL'}")  # Should fail
    print(f"Errors: {errors}")
    
    # Test 3: Invalid margin
    print("\n3. Invalid margin:")
    params = {
        "primary_entry_price": Decimal("65000"),
        "tp1_price": Decimal("66000"),
        "sl_price": Decimal("64000"),
        "leverage": 10,
        "margin_amount": Decimal("5")  # Too small
    }
    success, errors, validated = await validate_ggshot_parameters(params, "BTCUSDT", "Buy")
    print(f"Result: {'✅ PASS' if not success else '❌ FAIL'}")  # Should fail
    print(f"Errors: {errors}")
    
    # Test 4: Poor risk/reward ratio
    print("\n4. Poor risk/reward ratio:")
    params = {
        "primary_entry_price": Decimal("65000"),
        "tp1_price": Decimal("65100"),  # Only 0.15% reward
        "sl_price": Decimal("64500"),   # 0.77% risk
        "leverage": 10,
        "margin_amount": Decimal("100")
    }
    success, errors, validated = await validate_ggshot_parameters(params, "BTCUSDT", "Buy")
    print(f"Result: {'✅ PASS' if not success else '❌ FAIL'}")  # Should fail
    print(f"Errors: {errors}")
    
    # Test 5: Missing required parameters
    print("\n5. Missing required parameters:")
    params = {
        "primary_entry_price": Decimal("65000"),
        # Missing TP and SL
        "leverage": 10,
        "margin_amount": Decimal("100")
    }
    success, errors, validated = await validate_ggshot_parameters(params, "BTCUSDT", "Buy")
    print(f"Result: {'✅ PASS' if not success else '❌ FAIL'}")  # Should fail
    print(f"Errors: {errors}")

async def test_validation_report():
    """Test validation report formatting"""
    print("\n" + "="*50)
    print("TESTING VALIDATION REPORT")
    print("="*50)
    
    # Create params with multiple errors
    params = {
        "primary_entry_price": Decimal("65000"),
        "tp1_price": Decimal("64000"),    # Wrong direction
        "sl_price": Decimal("66000"),     # Wrong direction
        "leverage": 200,                  # Too high
        "margin_amount": Decimal("5")     # Too small
    }
    
    success, errors, validated = await validate_ggshot_parameters(params, "BTCUSDT", "Buy")
    
    # Format report
    report = ggshot_validator.format_validation_report(errors, params, "Buy")
    print("\nValidation Report:")
    print(report)

async def main():
    """Run all tests"""
    print("🧪 GGShot Validation Test Suite")
    print("Testing robustness for both LONG and SHORT trades")
    
    await test_long_trades()
    await test_short_trades()
    await test_edge_cases()
    await test_validation_report()
    
    print("\n" + "="*50)
    print("✅ All tests completed!")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())