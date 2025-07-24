#!/usr/bin/env python3
"""
Check position details including positionIdx
"""
import asyncio
from clients.bybit_helpers import get_all_positions

async def check_positions():
    positions = await get_all_positions()
    
    print(f"\nTotal positions: {len(positions)}")
    print("\nPosition Details:")
    print("-" * 80)
    
    for pos in positions:
        if float(pos.get('size', 0)) > 0:
            symbol = pos.get('symbol')
            side = pos.get('side')
            size = float(pos.get('size', 0))
            avg_price = float(pos.get('avgPrice', 0))
            position_idx = pos.get('positionIdx', 'N/A')
            
            print(f"{symbol}:")
            print(f"  Side: {side}")
            print(f"  Size: {size}")
            print(f"  Avg Price: ${avg_price:.4f}")
            print(f"  Position Index: {position_idx}")
            print(f"  Raw positionIdx: {repr(position_idx)}")
            print()

if __name__ == "__main__":
    asyncio.run(check_positions())