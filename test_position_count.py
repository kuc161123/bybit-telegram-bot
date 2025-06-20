#!/usr/bin/env python3
"""
Simple test to count positions
"""
import asyncio
from clients.bybit_helpers import get_all_positions

async def test_position_count():
    print("Fetching all positions...")
    positions = await get_all_positions()
    
    # Show all positions with size
    print(f"\nTotal positions returned: {len(positions)}")
    
    active_count = 0
    for i, pos in enumerate(positions):
        size = float(pos.get('size', 0))
        if size > 0:
            active_count += 1
            symbol = pos.get('symbol', 'UNKNOWN')
            side = pos.get('side', '')
            unrealized_pnl = float(pos.get('unrealisedPnl', 0))
            print(f"{active_count}. {symbol} {side} - Size: {size} - P&L: ${unrealized_pnl:.2f}")
    
    print(f"\nActive positions (size > 0): {active_count}")
    
    # Check if pagination might be an issue
    if len(positions) == 200:
        print("\n⚠️ WARNING: Exactly 200 positions returned - might be hitting pagination limit!")

if __name__ == "__main__":
    asyncio.run(test_position_count())