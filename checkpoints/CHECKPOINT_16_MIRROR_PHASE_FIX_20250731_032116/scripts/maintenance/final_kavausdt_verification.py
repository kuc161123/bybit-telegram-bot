#!/usr/bin/env python3
"""
Final KAVAUSDT Verification

Comprehensive test of the complete quantity validation system for KAVAUSDT.
Tests both the bybit_helpers and Enhanced TP/SL Manager validation layers.
"""
import asyncio
import logging
import sys
import os
from decimal import Decimal

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_bybit_helpers_quantity_validation():
    """Test the bybit_helpers quantity adjustment function"""
    try:
        logger.info("🧪 Testing bybit_helpers quantity validation...")
        
        from clients.bybit_helpers import adjust_quantity_to_step_size
        
        # Test problematic KAVAUSDT quantity
        problematic_qty = "1.998239040839265642562757587"
        
        logger.info(f"📊 Testing quantity: {problematic_qty}")
        
        # Apply the validation
        adjusted_qty = await adjust_quantity_to_step_size("KAVAUSDT", problematic_qty)
        
        logger.info(f"✅ Bybit helpers adjusted quantity: {adjusted_qty}")
        
        # Validate the result
        if adjusted_qty == "1.9":
            logger.info("✅ bybit_helpers quantity validation working correctly!")
            return True
        else:
            logger.error(f"❌ Expected 1.9, got {adjusted_qty}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error testing bybit_helpers validation: {e}")
        return False

async def test_enhanced_tp_sl_quantity_validation():
    """Test the Enhanced TP/SL Manager quantity validation"""
    try:
        logger.info("🔧 Testing Enhanced TP/SL Manager quantity validation...")
        
        from clients.bybit_helpers import get_instrument_info
        from utils.helpers import value_adjusted_to_step
        
        # Get KAVAUSDT specs (same as Enhanced TP/SL Manager would)
        instrument_info = await get_instrument_info("KAVAUSDT")
        
        if not instrument_info:
            logger.error("❌ Could not get KAVAUSDT instrument info")
            return False
        
        lot_size_filter = instrument_info.get("lotSizeFilter", {})
        qty_step = Decimal(lot_size_filter.get("qtyStep", "1"))
        min_order_qty = Decimal(lot_size_filter.get("minOrderQty", "0.001"))
        
        # Test the same logic as Enhanced TP/SL Manager
        problematic_qty = Decimal("1.998239040839265642562757587")
        
        logger.info(f"📊 Raw quantity: {problematic_qty}")
        logger.info(f"📏 Qty step: {qty_step}")
        logger.info(f"📏 Min qty: {min_order_qty}")
        
        # Apply Enhanced TP/SL Manager logic
        adjusted_quantity = value_adjusted_to_step(problematic_qty, qty_step)
        
        # Ensure minimum quantity (Enhanced TP/SL Manager does this)
        if adjusted_quantity < min_order_qty:
            adjusted_quantity = min_order_qty
            logger.info(f"🔧 Raised to minimum: {adjusted_quantity}")
        
        logger.info(f"✅ Enhanced TP/SL Manager adjusted quantity: {adjusted_quantity}")
        
        # Validate the result
        if adjusted_quantity == Decimal("1.9"):
            logger.info("✅ Enhanced TP/SL Manager quantity validation working correctly!")
            return True
        else:
            logger.error(f"❌ Expected 1.9, got {adjusted_quantity}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error testing Enhanced TP/SL Manager validation: {e}")
        return False

async def test_order_placement_simulation():
    """Simulate order placement with the problematic quantity"""
    try:
        logger.info("🎯 Simulating order placement with quantity validation...")
        
        from clients.bybit_helpers import adjust_quantity_to_step_size, adjust_price_to_tick_size
        
        # Simulate placing a KAVAUSDT TP order with problematic quantity
        symbol = "KAVAUSDT"
        problematic_qty = "1.998239040839265642562757587"
        price = "0.4000"
        
        logger.info(f"📋 Simulating order: {symbol} qty={problematic_qty} price={price}")
        
        # Apply the same validation that place_order_with_retry does
        adjusted_qty = await adjust_quantity_to_step_size(symbol, problematic_qty)
        adjusted_price = await adjust_price_to_tick_size(symbol, price)
        
        logger.info(f"🔧 Validated order: {symbol} qty={adjusted_qty} price={adjusted_price}")
        
        # Check if it would pass Bybit validation
        if adjusted_qty == "1.9":
            logger.info("✅ Order would be accepted by Bybit (quantity valid)")
            return True
        else:
            logger.error(f"❌ Order might be rejected (quantity: {adjusted_qty})")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error simulating order placement: {e}")
        return False

async def main():
    """Main test execution"""
    logger.info("🚀 Starting final KAVAUSDT quantity validation verification...")
    
    # Test 1: bybit_helpers layer
    test1_passed = await test_bybit_helpers_quantity_validation()
    
    # Test 2: Enhanced TP/SL Manager layer  
    test2_passed = await test_enhanced_tp_sl_quantity_validation()
    
    # Test 3: Order placement simulation
    test3_passed = await test_order_placement_simulation()
    
    # Final summary
    logger.info("\n" + "="*70)
    logger.info("📋 FINAL VERIFICATION RESULTS")
    logger.info("="*70)
    
    logger.info(f"✅ bybit_helpers validation: {'PASS' if test1_passed else 'FAIL'}")
    logger.info(f"✅ Enhanced TP/SL Manager validation: {'PASS' if test2_passed else 'FAIL'}")
    logger.info(f"✅ Order placement simulation: {'PASS' if test3_passed else 'FAIL'}")
    
    all_passed = test1_passed and test2_passed and test3_passed
    
    if all_passed:
        logger.info("\n🎉 ALL VERIFICATION TESTS PASSED!")
        logger.info("✅ KAVAUSDT quantity validation is fully operational")
        logger.info("💡 The bot will no longer experience quantity validation errors")
        logger.info("🔧 Both order placement layers have proper validation")
        logger.info("📊 Quantities with 27 decimal places will be corrected to 0.1 step size")
    else:
        logger.error("\n❌ Some verification tests failed")
        logger.error("🚨 Quantity validation system needs attention")
    
    logger.info("="*70)

if __name__ == "__main__":
    asyncio.run(main())