#!/usr/bin/env python3
"""
Debug script to examine all TP orders in detail
"""
import asyncio
import logging
from clients.bybit_helpers import get_all_positions, get_all_open_orders

logging.basicConfig(level=logging.INFO)

async def debug_tp_orders():
    """Examine all TP orders to understand the discrepancy"""
    
    print("\n=== DEBUGGING TP ORDERS ===\n")
    
    # Get positions
    positions = await get_all_positions()
    print(f"Found {len(positions)} positions:")
    for pos in positions:
        print(f"  - {pos.get('symbol')}: {pos.get('size')} @ ${pos.get('avgPrice')} ({pos.get('side')})")
    
    # Get all orders
    orders = await get_all_open_orders()
    print(f"\nFound {len(orders)} total orders")
    
    # Analyze each order
    print("\nOrder Details:")
    for i, order in enumerate(orders):
        symbol = order.get('symbol', '')
        side = order.get('side', '')
        order_type = order.get('orderType', '')
        qty = order.get('qty', '')
        price = order.get('price', '')
        trigger_price = order.get('triggerPrice', '')
        reduce_only = order.get('reduceOnly', False)
        trigger_by = order.get('triggerBy', '')
        
        print(f"\n{i+1}. {symbol} {side} {order_type}")
        print(f"   Qty: {qty}")
        print(f"   Price: {price}")
        print(f"   Trigger Price: {trigger_price}")
        print(f"   Trigger By: {trigger_by}")
        print(f"   Reduce Only: {reduce_only}")
        
        # Determine if it's a TP or SL
        if trigger_price and reduce_only:
            # Find matching position
            pos = next((p for p in positions if p.get('symbol') == symbol), None)
            if pos:
                pos_side = pos.get('side', '')
                avg_price = float(pos.get('avgPrice', 0))
                trigger_price_float = float(trigger_price)
                
                if pos_side == 'Buy':
                    if trigger_price_float > avg_price:
                        print(f"   -> This is a TP order (Long position, trigger > avg)")
                    else:
                        print(f"   -> This is a SL order (Long position, trigger < avg)")
                else:
                    if trigger_price_float < avg_price:
                        print(f"   -> This is a TP order (Short position, trigger < avg)")
                    else:
                        print(f"   -> This is a SL order (Short position, trigger > avg)")
                
                # Calculate profit/loss
                if pos_side == 'Buy':
                    pnl = (trigger_price_float - avg_price) * float(qty)
                else:
                    pnl = (avg_price - trigger_price_float) * float(qty)
                print(f"   -> P&L if executed: ${pnl:.2f}")
    
    # Now specifically look for TP1 orders
    print("\n\n=== TP1 ORDERS SUMMARY ===")
    tp1_total = 0
    
    for pos in positions:
        symbol = pos.get('symbol', '')
        pos_side = pos.get('side', '')
        avg_price = float(pos.get('avgPrice', 0))
        
        # Find all TP orders for this position
        tp_orders = []
        for order in orders:
            if order.get('symbol') != symbol:
                continue
            
            trigger_price = order.get('triggerPrice', '')
            if not trigger_price or not order.get('reduceOnly', False):
                continue
            
            trigger_price_float = float(trigger_price)
            
            # Check if it's a TP
            is_tp = False
            if pos_side == 'Buy' and trigger_price_float > avg_price:
                is_tp = True
            elif pos_side == 'Sell' and trigger_price_float < avg_price:
                is_tp = True
            
            if is_tp:
                tp_orders.append({
                    'price': trigger_price_float,
                    'qty': float(order.get('qty', 0))
                })
        
        if tp_orders:
            # Sort by price to find TP1
            tp_orders.sort(key=lambda x: x['price'], reverse=(pos_side == 'Buy'))
            tp1 = tp_orders[0]
            
            # Calculate TP1 profit
            if pos_side == 'Buy':
                profit = (tp1['price'] - avg_price) * tp1['qty']
            else:
                profit = (avg_price - tp1['price']) * tp1['qty']
            
            tp1_total += profit
            print(f"\n{symbol} TP1: {tp1['qty']} @ ${tp1['price']} = ${profit:.2f}")
    
    print(f"\nTOTAL TP1 PROFIT: ${tp1_total:.2f}")
    
    if abs(tp1_total - 337.3) < 1:
        print("\n✅ This matches the $337.3 the user is seeing!")
    elif abs(tp1_total - 177.15) < 1:
        print("\n✅ This matches the correct calculation of $177.15")
    else:
        print(f"\n❌ This doesn't match either value (User: $337.3, Expected: $177.15)")

if __name__ == "__main__":
    asyncio.run(debug_tp_orders())