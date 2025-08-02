#!/usr/bin/env python3
import asyncio
from clients.bybit_client import bybit_client

try:
    from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
    MIRROR_AVAILABLE = True
except ImportError:
    MIRROR_AVAILABLE = False
    bybit_client_2 = None

async def main():
    print("Checking position modes...")
    
    # Check main account
    print("\nMain Account:")
    try:
        info = bybit_client.get_account_info()
        if info and info.get('retCode') == 0:
            result = info.get('result', {})
            print(f"  Margin Mode: {result.get('marginMode', 'UNKNOWN')}")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Check mirror account
    if MIRROR_AVAILABLE and bybit_client_2:
        print("\nMirror Account:")
        try:
            info = bybit_client_2.get_account_info()
            if info and info.get('retCode') == 0:
                result = info.get('result', {})
                print(f"  Margin Mode: {result.get('marginMode', 'UNKNOWN')}")
        except Exception as e:
            print(f"  Error: {e}")
    else:
        print("\nMirror Account: Not available")

if __name__ == "__main__":
    asyncio.run(main())