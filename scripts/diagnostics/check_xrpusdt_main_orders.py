#!/usr/bin/env python3
"""Check XRPUSDT orders on main account"""
import asyncio
from clients.bybit_helpers import get_open_orders

async def main():
    print("=== MAIN ACCOUNT XRPUSDT ORDERS ===")
    orders = await get_open_orders("XRPUSDT")
    
    print(f"\nTotal orders: {len(orders)}")
    
    tp_orders = []
    sl_orders = []
    entry_orders = []
    
    for order in orders:
        order_link_id = order.get('orderLinkId', '')
        if order.get('reduceOnly'):
            if 'TP' in order_link_id:
                tp_orders.append(order)
            elif 'SL' in order_link_id:
                sl_orders.append(order)
        else:
            entry_orders.append(order)
    
    print(f"  TP orders: {len(tp_orders)}")
    print(f"  SL orders: {len(sl_orders)}")
    print(f"  Entry orders: {len(entry_orders)}")
    
    # Show details
    if tp_orders:
        print("\nTP Order Details:")
        for i, tp in enumerate(tp_orders):
            print(f"  TP{i+1}:")
            print(f"    OrderType: {tp.get('orderType')}")
            print(f"    StopOrderType: {tp.get('stopOrderType')}")
            print(f"    Qty: {tp.get('qty')}")
            print(f"    Price: {tp.get('price')}")
            print(f"    TriggerPrice: {tp.get('triggerPrice')}")
    
    if sl_orders:
        print("\nSL Order Details:")
        for sl in sl_orders:
            print(f"  SL:")
            print(f"    OrderType: {sl.get('orderType')}")
            print(f"    StopOrderType: {sl.get('stopOrderType')}")
            print(f"    Qty: {sl.get('qty')}")
            print(f"    TriggerPrice: {sl.get('triggerPrice')}")

if __name__ == "__main__":
    asyncio.run(main())