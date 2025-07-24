#!/usr/bin/env python3
"""Check detailed mirror account orders"""
import asyncio
from execution.mirror_trader import bybit_client_2

async def main():
    print("=== CHECKING MIRROR ACCOUNT ORDERS ===\n")
    
    if not bybit_client_2:
        print("❌ Mirror client not available")
        return
    
    # Check each symbol
    symbols = ["JUPUSDT", "TIAUSDT", "LINKUSDT", "XRPUSDT"]
    
    for symbol in symbols:
        print(f"\n{symbol}:")
        print("-" * 40)
        
        try:
            response = bybit_client_2.get_open_orders(
                category="linear",
                symbol=symbol
            )
            
            if response and response.get('retCode') == 0:
                orders = response.get('result', {}).get('list', [])
                print(f"Total orders: {len(orders)}")
                
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
                
                # Show TP/SL details
                if tp_orders:
                    print("\n  TP Order Details:")
                    for i, tp in enumerate(tp_orders):
                        print(f"    TP{i+1}: {tp.get('qty')} @ {tp.get('price')} ({tp.get('orderLinkId')})")
                
                if sl_orders:
                    print("\n  SL Order Details:")
                    for sl in sl_orders:
                        print(f"    SL: {sl.get('qty')} @ trigger {sl.get('triggerPrice')} ({sl.get('orderLinkId')})")
                        
            else:
                print(f"Error: {response}")
                
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())