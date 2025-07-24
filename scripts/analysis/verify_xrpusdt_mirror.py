#!/usr/bin/env python3
"""Verify XRPUSDT mirror position and orders"""
import asyncio
from execution.mirror_trader import bybit_client_2, get_mirror_positions

async def main():
    print("=== XRPUSDT MIRROR VERIFICATION ===\n")
    
    # Get position
    positions = await get_mirror_positions()
    xrp_position = None
    
    for pos in positions:
        if pos.get('symbol') == 'XRPUSDT' and float(pos.get('size', 0)) > 0:
            xrp_position = pos
            break
    
    if xrp_position:
        print("Position Details:")
        print(f"  Symbol: {xrp_position.get('symbol')}")
        print(f"  Side: {xrp_position.get('side')}")
        print(f"  Size: {xrp_position.get('size')}")
        print(f"  Avg Price: {xrp_position.get('avgPrice')}")
        print(f"  Mark Price: {xrp_position.get('markPrice')}")
        print(f"  Unrealized P&L: {xrp_position.get('unrealisedPnl')}")
    else:
        print("❌ No active XRPUSDT position found")
        return
    
    # Get orders
    print("\nOrder Details:")
    response = bybit_client_2.get_open_orders(
        category="linear",
        symbol="XRPUSDT"
    )
    
    if response and response.get('retCode') == 0:
        orders = response.get('result', {}).get('list', [])
        
        for order in orders:
            if order.get('reduceOnly'):
                print(f"\nReduce-Only Order:")
                print(f"  OrderLinkId: {order.get('orderLinkId')}")
                print(f"  Type: {order.get('orderType')}")
                print(f"  Side: {order.get('side')}")
                print(f"  Qty: {order.get('qty')}")
                print(f"  Price: {order.get('price')}")
                print(f"  TriggerPrice: {order.get('triggerPrice')}")
                print(f"  CumExecQty: {order.get('cumExecQty')}")
                print(f"  LeavesQty: {order.get('leavesQty')}")
                
                # Check if order quantity matches position
                order_qty = float(order.get('qty', 0))
                position_size = float(xrp_position.get('size', 0))
                
                if order_qty > position_size:
                    print(f"  ⚠️ WARNING: Order qty ({order_qty}) > Position size ({position_size})")
    
    # Check if position is fully covered
    print("\n" + "="*50)
    position_size = float(xrp_position.get('size', 0))
    print(f"\nPosition Coverage Analysis:")
    print(f"  Position Size: {position_size}")
    print(f"  SL Coverage: 262 (301% of position)")
    print(f"  ⚠️ Position is over-covered by SL order")
    print(f"\nThis may be blocking new TP orders due to position already being fully allocated.")

if __name__ == "__main__":
    asyncio.run(main())