#!/usr/bin/env python3
"""
Quick check to verify position count and P&L totals
"""
import asyncio
from clients.bybit_helpers import get_all_positions, get_all_open_orders

async def check_positions():
    # Get all positions
    positions = await get_all_positions()
    active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
    
    print(f"\nTotal positions: {len(positions)}")
    print(f"Active positions (size > 0): {len(active_positions)}")
    
    # Get all orders to find TP/SL
    all_orders = await get_all_open_orders()
    print(f"Total open orders: {len(all_orders)}")
    
    # Calculate simple P&L assuming 1% TP and 1% SL
    total_position_value = 0
    total_margin = 0
    
    print("\nPosition details:")
    print("-" * 80)
    for p in active_positions[:10]:  # Show first 10
        symbol = p.get('symbol')
        size = float(p.get('size', 0))
        avg_price = float(p.get('avgPrice', 0))
        leverage = float(p.get('leverage', 1))
        position_value = size * avg_price
        margin = position_value / leverage
        
        total_position_value += position_value
        total_margin += margin
        
        print(f"{symbol}: Size={size}, Price=${avg_price:.4f}, Value=${position_value:.2f}, Margin=${margin:.2f}")
    
    if len(active_positions) > 10:
        print(f"... and {len(active_positions) - 10} more positions")
    
    print("-" * 80)
    print(f"\nTotal position value: ${total_position_value:,.2f}")
    print(f"Total margin used: ${total_margin:,.2f}")
    
    # Simple P&L calculation (1% profit/loss)
    print(f"\nSimple P&L estimates (assuming 1% moves):")
    print(f"If all positions gain 1%: ${total_margin * 0.01:,.2f}")
    print(f"If all positions lose 1%: ${total_margin * 0.01:,.2f}")

if __name__ == "__main__":
    asyncio.run(check_positions())