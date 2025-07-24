#!/usr/bin/env python3
"""
Test script to verify leverage warning has been silenced
"""

import asyncio
import logging
from dotenv import load_dotenv
from clients.bybit_helpers import set_symbol_leverage

# Load environment variables
load_dotenv()

# Set up logging to see debug messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_leverage_setting():
    """Test setting leverage twice to see if warning is silenced"""
    symbol = "BTCUSDT"
    leverage = 10
    
    print(f"\n🧪 Testing leverage setting for {symbol} at {leverage}x")
    print("="*60)
    
    # First attempt - might actually set leverage
    print("\n1️⃣ First attempt (may set leverage):")
    result1 = await set_symbol_leverage(symbol, leverage)
    print(f"   Result: {result1}")
    
    # Wait a moment
    await asyncio.sleep(1)
    
    # Second attempt - should be already set
    print("\n2️⃣ Second attempt (should be already set):")
    result2 = await set_symbol_leverage(symbol, leverage)
    print(f"   Result: {result2}")
    
    print("\n" + "="*60)
    print("✅ Test complete!")
    print("\nExpected behavior:")
    print("- First attempt: May show 'Successfully set' or 'already at' message")
    print("- Second attempt: Should show debug message, NOT error")
    print("- No 'API call error' messages with 110043 should appear")

if __name__ == "__main__":
    asyncio.run(test_leverage_setting())