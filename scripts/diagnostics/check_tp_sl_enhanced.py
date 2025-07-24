#!/usr/bin/env python3
"""
Enhanced check for TP/SL orders with multiple detection methods
"""
import asyncio
import json
from clients.bybit_helpers import get_all_positions, get_all_open_orders, bybit_client

async def check_tp_sl_enhanced():
    # Get all positions
    positions = await get_all_positions()
    active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
    
    # Get all orders
    all_orders = await get_all_open_orders()
    
    print(f"\nActive positions: {len(active_positions)}")
    print(f"Total open orders: {len(all_orders)}")
    print("\n" + "="*120)
    
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
        
        # Separate TP and SL orders using multiple detection methods
        tp_orders = []
        sl_orders = []
        other_orders = []
        
        for order in symbol_orders:
            order_side = order.get('side')
            stop_order_type = order.get('stopOrderType', '')
            trigger_price_str = order.get('triggerPrice', '')
            trigger_price = float(trigger_price_str) if trigger_price_str else 0
            reduce_only = order.get('reduceOnly', False)
            order_link_id = order.get('orderLinkId', '')
            
            # Method 1: Check stopOrderType field (most reliable)
            if stop_order_type:
                if 'TakeProfit' in stop_order_type:
                    tp_orders.append(order)
                    print(f"    ✓ Found TP via stopOrderType: {stop_order_type}")
                elif 'StopLoss' in stop_order_type:
                    sl_orders.append(order)
                    print(f"    ✓ Found SL via stopOrderType: {stop_order_type}")
                else:
                    other_orders.append(order)
                continue
            
            # Method 2: Check orderLinkId patterns
            if 'TP' in order_link_id.upper() or 'TAKE_PROFIT' in order_link_id.upper():
                tp_orders.append(order)
                print(f"    ✓ Found TP via orderLinkId pattern: {order_link_id}")
                continue
            elif 'SL' in order_link_id.upper() or 'STOP_LOSS' in order_link_id.upper():
                sl_orders.append(order)
                print(f"    ✓ Found SL via orderLinkId pattern: {order_link_id}")
                continue
            
            # Method 3: Infer from price and position (if trigger price exists and reduce only)
            if trigger_price > 0 and reduce_only:
                # For long positions: TP is sell above entry, SL is sell below entry
                # For short positions: TP is buy below entry, SL is buy above entry
                if side == 'Buy':  # Long position
                    if order_side == 'Sell':
                        if trigger_price > avg_price:
                            tp_orders.append(order)
                            print(f"    ✓ Found TP via price inference (sell @ ${trigger_price:.4f} > entry @ ${avg_price:.4f})")
                        else:
                            sl_orders.append(order)
                            print(f"    ✓ Found SL via price inference (sell @ ${trigger_price:.4f} < entry @ ${avg_price:.4f})")
                else:  # Short position
                    if order_side == 'Buy':
                        if trigger_price < avg_price:
                            tp_orders.append(order)
                            print(f"    ✓ Found TP via price inference (buy @ ${trigger_price:.4f} < entry @ ${avg_price:.4f})")
                        else:
                            sl_orders.append(order)
                            print(f"    ✓ Found SL via price inference (buy @ ${trigger_price:.4f} > entry @ ${avg_price:.4f})")
            else:
                other_orders.append(order)
        
        # Display TP orders
        if tp_orders:
            print(f"  ✅ Take Profit Orders ({len(tp_orders)}):")
            for tp in tp_orders:
                tp_price_str = tp.get('triggerPrice', '')
                tp_price = float(tp_price_str) if tp_price_str else 0
                tp_qty = float(tp.get('qty', 0))
                tp_percent = ((tp_price - avg_price) / avg_price * 100) if side == 'Buy' else ((avg_price - tp_price) / avg_price * 100)
                order_id = tp.get('orderId', 'N/A')
                print(f"    - TP at ${tp_price:.4f} ({tp_percent:+.2f}%) for {tp_qty} units [ID: {order_id[:8]}...]")
        else:
            print(f"  ❌ No Take Profit orders detected")
        
        # Display SL orders
        if sl_orders:
            print(f"  ✅ Stop Loss Orders ({len(sl_orders)}):")
            for sl in sl_orders:
                sl_price_str = sl.get('triggerPrice', '')
                sl_price = float(sl_price_str) if sl_price_str else 0
                sl_qty = float(sl.get('qty', 0))
                sl_percent = ((sl_price - avg_price) / avg_price * 100) if side == 'Buy' else ((avg_price - sl_price) / avg_price * 100)
                order_id = sl.get('orderId', 'N/A')
                print(f"    - SL at ${sl_price:.4f} ({sl_percent:+.2f}%) for {sl_qty} units [ID: {order_id[:8]}...]")
        else:
            print(f"  ❌ No Stop Loss orders detected")
        
        # Show other orders
        if other_orders:
            print(f"  ℹ️  Other orders ({len(other_orders)}):")
            for order in other_orders[:3]:  # Show first 3
                order_type = order.get('orderType', 'Unknown')
                qty = float(order.get('qty', 0))
                price = float(order.get('price', 0))
                print(f"    - {order_type} order for {qty} units @ ${price:.4f}")
        
        print(f"  Total orders for {symbol}: {len(symbol_orders)}")
    
    # Show sample raw order data for debugging
    print("\n" + "="*120)
    print("Sample raw order data (first order):")
    if all_orders:
        print(json.dumps(all_orders[0], indent=2))

if __name__ == "__main__":
    asyncio.run(check_tp_sl_enhanced())