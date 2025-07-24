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
    print("🔍 Detailed Position Mode Analysis")
    
    # Test both accounts
    for name, client in [("Main", bybit_client), ("Mirror", bybit_client_2)]:
        if client is None:
            continue
            
        print(f"\n📍 {name} Account:")
        
        # Get account info
        try:
            info = client.get_account_info()
            if info and info.get('retCode') == 0:
                result = info.get('result', {})
                print(f"   Margin Mode: {result.get('marginMode', 'UNKNOWN')}")
                print(f"   Margin Type: {result.get('marginType', 'UNKNOWN')}")
                
                # Additional details
                for key, value in result.items():
                    if key not in ['marginMode', 'marginType']:
                        print(f"   {key}: {value}")
        except Exception as e:
            print(f"   Account info error: {e}")
        
        # Check positions to understand mode
        try:
            positions = client.get_positions(category="linear")
            if positions and positions.get('retCode') == 0:
                pos_list = positions.get('result', {}).get('list', [])
                print(f"   Total positions: {len(pos_list)}")
                
                # Analyze position structure
                for pos in pos_list[:3]:  # Show first 3
                    symbol = pos.get('symbol', '')
                    side = pos.get('side', '')
                    size = pos.get('size', '0')
                    pos_idx = pos.get('positionIdx', 'N/A')
                    print(f"     {symbol}: {side} {size} (idx: {pos_idx})")
                    
        except Exception as e:
            print(f"   Positions error: {e}")

if __name__ == "__main__":
    asyncio.run(main())