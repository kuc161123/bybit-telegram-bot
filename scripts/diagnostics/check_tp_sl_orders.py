#!/usr/bin/env python3
"""
Check which positions have TP and SL orders
"""
import asyncio
from clients.bybit_helpers import get_all_positions, get_all_open_orders

async def check_tp_sl():
    # Get all positions
    positions = await get_all_positions()
    active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
    
    # Get all orders
    all_orders = await get_all_open_orders()
    
    print(f"\nActive positions: {len(active_positions)}")
    print(f"Total open orders: {len(all_orders)}")
    print("\n" + "="*100)
    
    # Group orders by symbol
    orders_by_symbol = {}
    for order in all_orders:
        symbol = order.get('symbol')
        if symbol not in orders_by_symbol:
            orders_by_symbol[symbol] = []
        orders_by_symbol[symbol].append(order)
    
    # Check each position for TP/SL
    for pos in active_positions:
        symbol = pos.get('symbol')
        side = pos.get('side')
        size = float(pos.get('size', 0))
        avg_price = float(pos.get('avgPrice', 0))
        
        print(f"\n{symbol} - {side} position:")
        print(f"  Size: {size}, Avg Price: ${avg_price:.4f}")
        
        # Get orders for this symbol
        symbol_orders = orders_by_symbol.get(symbol, [])
        
        # Separate TP and SL orders
        tp_orders = []
        sl_orders = []
        
        for order in symbol_orders:
            order_side = order.get('side')
            stop_order_type = order.get('stopOrderType', '')
            trigger_by = order.get('triggerBy', '')
            
            # For a long position, TP is a sell limit order and SL is a sell stop order
            # For a short position, TP is a buy limit order and SL is a buy stop order
            if side == 'Buy':  # Long position
                if order_side == 'Sell':
                    if stop_order_type in ['TakeProfit', 'PartialTakeProfit']:
                        tp_orders.append(order)
                    elif stop_order_type in ['StopLoss', 'PartialStopLoss']:
                        sl_orders.append(order)
            else:  # Short position
                if order_side == 'Buy':
                    if stop_order_type in ['TakeProfit', 'PartialTakeProfit']:
                        tp_orders.append(order)
                    elif stop_order_type in ['StopLoss', 'PartialStopLoss']:
                        sl_orders.append(order)
        
        # Display TP orders
        if tp_orders:
            print(f"  ✅ Take Profit Orders ({len(tp_orders)}):")
            for tp in tp_orders:
                tp_price = float(tp.get('triggerPrice', 0))
                tp_qty = float(tp.get('qty', 0))
                tp_percent = ((tp_price - avg_price) / avg_price * 100) if side == 'Buy' else ((avg_price - tp_price) / avg_price * 100)
                print(f"    - TP at ${tp_price:.4f} ({tp_percent:+.2f}%) for {tp_qty} units")
        else:
            print(f"  ❌ No Take Profit orders")
        
        # Display SL orders
        if sl_orders:
            print(f"  ✅ Stop Loss Orders ({len(sl_orders)}):")
            for sl in sl_orders:
                sl_price = float(sl.get('triggerPrice', 0))
                sl_qty = float(sl.get('qty', 0))
                sl_percent = ((sl_price - avg_price) / avg_price * 100) if side == 'Buy' else ((avg_price - sl_price) / avg_price * 100)
                print(f"    - SL at ${sl_price:.4f} ({sl_percent:+.2f}%) for {sl_qty} units")
        else:
            print(f"  ❌ No Stop Loss orders")
        
        print(f"  Total orders for {symbol}: {len(symbol_orders)}")

if __name__ == "__main__":
    asyncio.run(check_tp_sl())