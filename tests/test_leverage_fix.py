#!/usr/bin/env python3
"""
Test script to verify leverage setting functionality
"""
import asyncio
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_leverage_setting():
    """Test leverage setting on both main and mirror accounts"""
    print("=" * 60)
    print("Testing Leverage Setting Fix")
    print("=" * 60)
    
    # Import required modules
    from clients.bybit_helpers import set_symbol_leverage
    from clients.bybit_client import bybit_client
    
    # Test symbol and leverage
    test_symbol = "BTCUSDT"
    test_leverage = 15
    
    print(f"\n1. Testing leverage setting for {test_symbol} to {test_leverage}x on main account...")
    
    # Test main account leverage setting
    success = await set_symbol_leverage(test_symbol, test_leverage)
    
    if success:
        print(f"✅ Successfully set leverage to {test_leverage}x on main account")
        
        # Check current leverage
        try:
            positions = await bybit_client.get_positions(category="linear", symbol=test_symbol)
            if positions and positions.get('result'):
                position_list = positions['result'].get('list', [])
                if position_list:
                    current_leverage = position_list[0].get('leverage', 'Unknown')
                    print(f"   Current position leverage: {current_leverage}")
        except Exception as e:
            print(f"   Could not verify leverage: {e}")
    else:
        print(f"❌ Failed to set leverage on main account")
    
    # Test mirror account if enabled
    mirror_enabled = os.getenv("ENABLE_MIRROR_TRADING", "false").lower() == "true"
    if mirror_enabled:
        print(f"\n2. Testing leverage setting for {test_symbol} to {test_leverage}x on mirror account...")
        
        try:
            from execution.mirror_trader import set_mirror_leverage, bybit_client_2
            
            success = await set_mirror_leverage(test_symbol, test_leverage)
            
            if success:
                print(f"✅ Successfully set leverage to {test_leverage}x on mirror account")
                
                # Check current leverage on mirror
                if bybit_client_2:
                    try:
                        positions = bybit_client_2.get_positions(category="linear", symbol=test_symbol)
                        if positions and positions.get('result'):
                            position_list = positions['result'].get('list', [])
                            if position_list:
                                current_leverage = position_list[0].get('leverage', 'Unknown')
                                print(f"   Current position leverage: {current_leverage}")
                    except Exception as e:
                        print(f"   Could not verify mirror leverage: {e}")
            else:
                print(f"❌ Failed to set leverage on mirror account")
                
        except ImportError:
            print("   Mirror trading module not available")
    else:
        print("\n2. Mirror trading is disabled - skipping mirror leverage test")
    
    print("\n" + "=" * 60)
    print("Leverage Setting Test Complete")
    print("=" * 60)
    print("\nThe fix ensures that when users select leverage in the bot,")
    print("it will be applied to both main and mirror accounts before placing orders.")

async def main():
    """Run the test"""
    await test_leverage_setting()

if __name__ == "__main__":
    asyncio.run(main())