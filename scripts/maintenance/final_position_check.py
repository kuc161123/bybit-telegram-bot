#!/usr/bin/env python3
"""
Final check for DOTUSDT, ZENUSDT, ONEUSDT, and ZILUSDT positions.
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()


async def final_check():
    """Final check of problem positions."""
    
    print("🔍 Final Position Check")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    from pybit.unified_trading import HTTP
    from config.settings import (
        BYBIT_API_KEY, BYBIT_API_SECRET,
        BYBIT_API_KEY_2, BYBIT_API_SECRET_2,
        USE_TESTNET
    )
    
    # Initialize clients
    main_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    mirror_client = None
    if BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
        mirror_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2
        )
    
    symbols_to_check = ['DOTUSDT', 'ZENUSDT', 'ONEUSDT', 'ZILUSDT']
    
    print(f"\n📋 Checking: {', '.join(symbols_to_check)}")
    
    for account_name, client in [("MAIN", main_client), ("MIRROR", mirror_client)]:
        if not client:
            continue
            
        print(f"\n\n{'='*40} {account_name} ACCOUNT {'='*40}")
        
        has_positions = False
        
        try:
            response = client.get_positions(
                category="linear",
                settleCoin="USDT"
            )
            
            if response['retCode'] == 0:
                for pos in response['result']['list']:
                    if pos['symbol'] in symbols_to_check and float(pos.get('size', 0)) > 0:
                        has_positions = True
                        
                        print(f"\n📍 {pos['symbol']}:")
                        print(f"  Side: {pos['side']}")
                        print(f"  Size: {float(pos['size']):,.0f}")
                        print(f"  Position Index: {pos.get('positionIdx', 'N/A')}")
                        
                        if pos['side'] == 'Buy' and pos.get('positionIdx') == 1:
                            print("  ⚠️ This is a LONG position that should have been closed!")
                        elif pos['side'] == 'Sell' and pos['symbol'] == 'ZILUSDT':
                            print("  ✅ This is a SHORT position (correctly kept)")
                
                if not has_positions:
                    print("\n✅ No positions found for the target symbols (or only allowed positions)")
                    
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n\n" + "=" * 80)
    print("📊 FINAL STATUS")
    print("=" * 80)
    print("\n✅ Positions that should be closed:")
    print("- DOTUSDT: Buy positions")
    print("- ZENUSDT: Buy positions")
    print("- ONEUSDT: All positions")
    print("- ZILUSDT: Buy positions only")
    print("\n✅ Positions that should remain:")
    print("- ZILUSDT: Sell/Short positions")


async def main():
    """Main function."""
    await final_check()


if __name__ == "__main__":
    asyncio.run(main())