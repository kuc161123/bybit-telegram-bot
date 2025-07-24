#!/usr/bin/env python3
"""Check position modes for both accounts"""
import asyncio
from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2

async def main():
    print("=== POSITION MODE CHECK ===\n")
    
    # Main account
    try:
        response = bybit_client.get_positions(
            category="linear",
            symbol="XRPUSDT"
        )
        if response and response.get('retCode') == 0:
            positions = response.get('result', {}).get('list', [])
            if positions:
                print("Main Account XRPUSDT:")
                print(f"  Position Mode: {'Hedge' if positions[0].get('positionIdx') != 0 else 'One-Way'}")
                print(f"  Position Index: {positions[0].get('positionIdx')}")
    except Exception as e:
        print(f"Error checking main: {e}")
    
    # Mirror account
    if bybit_client_2:
        try:
            response = bybit_client_2.get_positions(
                category="linear",
                symbol="XRPUSDT"
            )
            if response and response.get('retCode') == 0:
                positions = response.get('result', {}).get('list', [])
                if positions:
                    print("\nMirror Account XRPUSDT:")
                    print(f"  Position Mode: {'Hedge' if positions[0].get('positionIdx') != 0 else 'One-Way'}")
                    print(f"  Position Index: {positions[0].get('positionIdx')}")
        except Exception as e:
            print(f"Error checking mirror: {e}")

if __name__ == "__main__":
    asyncio.run(main())