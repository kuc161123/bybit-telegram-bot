
import asyncio
from decimal import Decimal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock the required functions
async def check_tp_hit_and_cancel_sl(chat_data, symbol, current_price, side, ctx_app):
    """Mock TP check function"""
    logger.info(f"Mock: Checking TP hit for {symbol} at {current_price}")
    # Simulate TP hit
    if current_price >= Decimal("50000"):  # Example for BTC
        logger.info(f"Mock: TP would be hit!")
        return True
    return False

async def check_sl_hit_and_cancel_tp(chat_data, symbol, current_price, side, ctx_app):
    """Mock SL check function"""
    logger.info(f"Mock: Checking SL hit for {symbol} at {current_price}")
    # Simulate SL hit
    if current_price <= Decimal("45000"):  # Example for BTC
        logger.info(f"Mock: SL would be hit!")
        return True
    return False

# Test the logic
async def test_mirror_fast_logic():
    """Test mirror fast approach logic"""
    
    # Test data
    chat_data = {
        "symbol": "BTCUSDT",
        "trading_approach": "fast",
        "tp_order_id": "test-tp-123",
        "sl_order_id": "test-sl-456"
    }
    
    symbol = "BTCUSDT"
    side = "Buy"
    approach = "fast"
    current_size = Decimal("0.001")
    fast_tp_hit = False
    fast_sl_hit = False
    
    print("\n📊 Testing MIRROR fast approach monitoring...")
    
    # Test TP hit scenario
    current_price = Decimal("50100")  # Above TP
    
    if approach == "fast" and current_size > 0:
        
        # Check for TP hit and cancel SL using same function as main account
        if not fast_tp_hit:
            # Pass None for ctx_app to prevent alerts (mirror accounts don't send alerts)
            tp_hit = await check_tp_hit_and_cancel_sl(chat_data, symbol, current_price, side, None)
            if tp_hit:
                fast_tp_hit = True
                logger.info(f"🎯 MIRROR Fast approach TP hit for {symbol} - SL cancelled")
                
                # Log the TP hit details
                tp_order_id = chat_data.get("tp_order_id") or (chat_data.get("tp_order_ids", []) or [None])[0]
                if tp_order_id:
                    logger.info(f"📊 MIRROR TP order {tp_order_id[:8]}... was triggered/filled")
    
    print(f"\n✅ Test completed. TP hit detected: {fast_tp_hit}")

if __name__ == "__main__":
    asyncio.run(test_mirror_fast_logic())
