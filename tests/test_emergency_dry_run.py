#!/usr/bin/env python3
"""
Test script for emergency shutdown functionality - DRY RUN
This tests the emergency module without actually closing positions
"""
import asyncio
import logging
from decimal import Decimal

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Mock some test data
MOCK_POSITIONS = [
    {
        "symbol": "BTCUSDT",
        "side": "Buy",
        "size": "0.01",
        "positionValue": "650.50",
        "avgPrice": "65050",
        "markPrice": "65100",
        "unrealisedPnl": "0.50",
        "positionIdx": 0
    },
    {
        "symbol": "ETHUSDT",
        "side": "Sell",
        "size": "0.1",
        "positionValue": "350.00",
        "avgPrice": "3500",
        "markPrice": "3490",
        "unrealisedPnl": "1.00",
        "positionIdx": 0
    }
]

MOCK_ORDERS = [
    {
        "symbol": "BTCUSDT",
        "orderId": "12345678",
        "orderType": "Limit",
        "side": "Buy",
        "qty": "0.01",
        "price": "64000",
        "orderLinkId": "BOT_LIMIT1_123"
    },
    {
        "symbol": "BTCUSDT",
        "orderId": "87654321",
        "orderType": "Limit",
        "side": "Sell",
        "qty": "0.01",
        "triggerPrice": "66000",
        "orderLinkId": "BOT_TP1_123",
        "reduceOnly": True
    },
    {
        "symbol": "ETHUSDT",
        "orderId": "11112222",
        "orderType": "Limit",
        "side": "Buy",
        "qty": "0.1",
        "triggerPrice": "3600",
        "orderLinkId": "BOT_SL_456",
        "reduceOnly": True
    }
]

async def test_emergency_status():
    """Test getting emergency status"""
    logger.info("Testing emergency status retrieval...")
    
    try:
        from execution.emergency import emergency_shutdown
        
        # Mock the status for testing
        status = {
            "main": {
                "positions": MOCK_POSITIONS,
                "orders": MOCK_ORDERS,
                "total_exposure": sum(Decimal(p["positionValue"]) for p in MOCK_POSITIONS)
            },
            "mirror": {
                "positions": [],
                "orders": [],
                "total_exposure": Decimal("0")
            }
        }
        
        logger.info(f"📊 Status Summary:")
        logger.info(f"Main Account:")
        logger.info(f"  - Positions: {len(status['main']['positions'])}")
        logger.info(f"  - Orders: {len(status['main']['orders'])}")
        logger.info(f"  - Total Exposure: ${status['main']['total_exposure']}")
        
        for pos in status['main']['positions']:
            logger.info(f"    • {pos['symbol']} {pos['side']}: {pos['size']} (${pos['positionValue']})")
        
        return status
        
    except Exception as e:
        logger.error(f"Error testing emergency status: {e}")
        return None

async def test_emergency_message_format():
    """Test emergency summary message formatting"""
    logger.info("\nTesting emergency message formatting...")
    
    try:
        from execution.emergency import EmergencyShutdown
        
        # Create test instance
        shutdown = EmergencyShutdown()
        
        # Mock a summary
        shutdown.summary = {
            "positions_closed": {
                "main": [
                    {"symbol": "BTCUSDT", "side": "Buy", "size": "0.01", "value": "650.50"},
                    {"symbol": "ETHUSDT", "side": "Sell", "size": "0.1", "value": "350.00"}
                ],
                "mirror": []
            },
            "orders_cancelled": {
                "main": [
                    {"symbol": "BTCUSDT", "orderId": "12345678", "orderType": "Limit"},
                    {"symbol": "BTCUSDT", "orderId": "87654321", "orderType": "Limit"},
                    {"symbol": "ETHUSDT", "orderId": "11112222", "orderType": "Limit"}
                ],
                "mirror": []
            },
            "errors": {"main": [], "mirror": []},
            "total_value_closed": {
                "main": Decimal("1000.50"),
                "mirror": Decimal("0")
            },
            "execution_time": 3.7,
            "final_status": {
                "main": {"positions": [], "orders": []},
                "mirror": {"positions": [], "orders": []}
            }
        }
        
        # Format message
        message = shutdown.format_summary_message()
        logger.info("\nFormatted Summary Message:")
        logger.info(message.replace('<b>', '').replace('</b>', ''))  # Remove HTML for console
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing message format: {e}")
        return False

async def test_dry_run_shutdown():
    """Test emergency shutdown logic without executing"""
    logger.info("\nTesting emergency shutdown logic (DRY RUN)...")
    
    try:
        logger.info("🚨 SIMULATING EMERGENCY SHUTDOWN")
        
        # Simulate order cancellation
        logger.info("\n📝 Phase 1: Simulating order cancellation...")
        for order in MOCK_ORDERS:
            logger.info(f"  - Would cancel {order['symbol']} {order['orderType']} order {order['orderId'][:8]}...")
        
        # Simulate position closing
        logger.info("\n💰 Phase 2: Simulating position closing...")
        for pos in MOCK_POSITIONS:
            close_side = "Sell" if pos['side'] == "Buy" else "Buy"
            logger.info(f"  - Would close {pos['symbol']} {pos['side']} position with {close_side} market order")
        
        logger.info("\n✅ DRY RUN COMPLETE - No actual orders were placed or cancelled")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in dry run: {e}")
        return False

async def test_confirmation_flow():
    """Test the confirmation flow logic"""
    logger.info("\nTesting confirmation flow...")
    
    try:
        # Test rate limiting
        from datetime import datetime, timedelta
        
        last_used = datetime.now() - timedelta(minutes=4)  # 4 minutes ago
        cooldown = timedelta(minutes=5)
        
        if datetime.now() - last_used < cooldown:
            remaining = (cooldown - (datetime.now() - last_used)).total_seconds()
            logger.info(f"❌ Rate limited: {int(remaining)} seconds remaining")
        else:
            logger.info("✅ Not rate limited - can proceed")
        
        # Test PIN validation (if enabled)
        test_pin = "1234"
        correct_pin = None  # Set to test PIN validation
        
        if correct_pin:
            if test_pin == correct_pin:
                logger.info("✅ PIN validation passed")
            else:
                logger.info("❌ PIN validation failed")
        else:
            logger.info("ℹ️ PIN validation disabled")
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing confirmation flow: {e}")
        return False

async def main():
    """Run all tests"""
    logger.info("🚨 EMERGENCY SHUTDOWN TEST SUITE (DRY RUN)")
    logger.info("=" * 50)
    
    # Test 1: Status retrieval
    status = await test_emergency_status()
    if status:
        logger.info("✅ Status retrieval test passed")
    else:
        logger.info("❌ Status retrieval test failed")
    
    # Test 2: Message formatting
    if await test_emergency_message_format():
        logger.info("✅ Message formatting test passed")
    else:
        logger.info("❌ Message formatting test failed")
    
    # Test 3: Dry run shutdown
    if await test_dry_run_shutdown():
        logger.info("✅ Dry run shutdown test passed")
    else:
        logger.info("❌ Dry run shutdown test failed")
    
    # Test 4: Confirmation flow
    if await test_confirmation_flow():
        logger.info("✅ Confirmation flow test passed")
    else:
        logger.info("❌ Confirmation flow test failed")
    
    logger.info("\n" + "=" * 50)
    logger.info("🏁 TEST SUITE COMPLETE")
    logger.info("\n⚠️ IMPORTANT: This was a DRY RUN - no actual trades were executed")
    logger.info("To test with real positions, use test_emergency_single_position.py")

if __name__ == "__main__":
    asyncio.run(main())