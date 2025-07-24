#!/usr/bin/env python3
"""Check detailed JUPUSDT orders on both accounts"""
import asyncio
from clients.bybit_helpers import get_open_orders
from execution.mirror_trader import bybit_client_2

async def main():
    # Check main account
    print("=== MAIN ACCOUNT ORDERS ===")
    main_orders = await get_open_orders("JUPUSDT")
    
    print(f"Total orders: {len(main_orders)}")
    for i, order in enumerate(main_orders):
        print(f"\nOrder {i+1}:")
        print(f"  OrderLinkId: {order.get('orderLinkId')}")
        print(f"  OrderType: {order.get('orderType')}")
        print(f"  StopOrderType: {order.get('stopOrderType')}")
        print(f"  Side: {order.get('side')}")
        print(f"  Qty: {order.get('qty')}")
        print(f"  Price: {order.get('price')}")
        print(f"  TriggerPrice: {order.get('triggerPrice')}")
        print(f"  ReduceOnly: {order.get('reduceOnly')}")
        print(f"  OrderStatus: {order.get('orderStatus')}")
    
    # Check mirror account
    if bybit_client_2:
        print("\n\n=== MIRROR ACCOUNT ORDERS ===")
        response = bybit_client_2.get_open_orders(
            category="linear",
            symbol="JUPUSDT"
        )
        
        if response and response.get('retCode') == 0:
            mirror_orders = response.get('result', {}).get('list', [])
            print(f"Total orders: {len(mirror_orders)}")
            
            for i, order in enumerate(mirror_orders):
                print(f"\nOrder {i+1}:")
                print(f"  OrderLinkId: {order.get('orderLinkId')}")
                print(f"  OrderType: {order.get('orderType')}")
                print(f"  StopOrderType: {order.get('stopOrderType')}")
                print(f"  Side: {order.get('side')}")
                print(f"  Qty: {order.get('qty')}")
                print(f"  Price: {order.get('price')}")
                print(f"  TriggerPrice: {order.get('triggerPrice')}")
                print(f"  ReduceOnly: {order.get('reduceOnly')}")
                print(f"  OrderStatus: {order.get('orderStatus')}")

if __name__ == "__main__":
    asyncio.run(main())