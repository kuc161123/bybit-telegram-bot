#!/usr/bin/env python3
"""
Verify dashboard P&L calculations by replicating the exact logic
"""
import asyncio
from decimal import Decimal
from clients.bybit_helpers import get_all_positions, get_all_open_orders

async def verify_dashboard_pnl():
    # Replicate exact dashboard logic
    positions = await get_all_positions()
    active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
    all_orders = await get_all_open_orders()
    
    print(f"\nActive positions: {len(active_positions)}")
    print(f"Total orders: {len(all_orders)}")
    
    # Calculate potential P&L from actual TP/SL orders
    potential_profit_tp1 = 0
    potential_profit_all_tp = 0
    potential_loss_sl = 0
    
    positions_with_tps = 0
    positions_with_sls = 0
    
    print("\n" + "="*100)
    print(f"{'Symbol':<12} {'Side':<5} {'Size':<12} {'Leverage':<8} {'TP Orders':<10} {'SL Orders':<10} {'TP1 P&L':<12} {'All TP P&L':<12} {'SL P&L':<12}")
    print("="*100)
    
    for pos in active_positions:
        symbol = pos.get('symbol', '')
        position_size = float(pos.get('size', 0))
        avg_price = float(pos.get('avgPrice', 0))
        side = pos.get('side', '')
        leverage = float(pos.get('leverage', 1))
        
        # Find TP and SL orders for this position
        tp_orders = []
        sl_orders = []
        
        for order in all_orders:
            if order.get('symbol') == symbol:
                trigger_price = order.get('triggerPrice', '')
                reduce_only = order.get('reduceOnly', False)
                
                if trigger_price and reduce_only:
                    try:
                        trigger_price_float = float(trigger_price)
                    except (ValueError, TypeError):
                        continue
                    
                    # TP orders: price is favorable to position
                    if side == 'Buy':
                        if trigger_price_float > avg_price:
                            tp_orders.append(order)
                        else:
                            sl_orders.append(order)
                    else:  # Sell/Short position
                        if trigger_price_float < avg_price:
                            tp_orders.append(order)
                        else:
                            sl_orders.append(order)
                
                # Also check for regular limit orders that might be TPs
                elif order.get('orderType') == 'Limit' and reduce_only:
                    tp_orders.append(order)
        
        pos_tp1_pnl = 0
        pos_all_tp_pnl = 0
        pos_sl_pnl = 0
        
        # Calculate P&L from actual orders
        if tp_orders:
            positions_with_tps += 1
            
            # Sort TPs by price
            def get_order_price(order):
                try:
                    trigger_price = order.get('triggerPrice', '')
                    if trigger_price:
                        return float(trigger_price)
                    price = order.get('price', '')
                    if price:
                        return float(price)
                    return 0
                except:
                    return 0
            
            tp_orders.sort(key=get_order_price, reverse=(side == 'Buy'))
            
            # TP1 profit
            if len(tp_orders) > 0:
                tp1_order = tp_orders[0]
                if tp1_order.get('triggerPrice'):
                    tp1_price = float(tp1_order.get('triggerPrice', avg_price))
                else:
                    tp1_price = float(tp1_order.get('price', avg_price))
                tp1_qty = float(tp1_order.get('qty', position_size))
                tp1_qty_unleveraged = tp1_qty / leverage if leverage > 0 else tp1_qty
                
                if side == 'Buy':
                    pos_tp1_pnl = (tp1_price - avg_price) * tp1_qty_unleveraged
                else:
                    pos_tp1_pnl = (avg_price - tp1_price) * tp1_qty_unleveraged
                
                potential_profit_tp1 += pos_tp1_pnl
            
            # All TPs profit
            for tp_order in tp_orders:
                if tp_order.get('triggerPrice'):
                    tp_price = float(tp_order.get('triggerPrice', avg_price))
                else:
                    tp_price = float(tp_order.get('price', avg_price))
                tp_qty = float(tp_order.get('qty', 0))
                tp_qty_unleveraged = tp_qty / leverage if leverage > 0 else tp_qty
                
                if side == 'Buy':
                    pos_all_tp_pnl += (tp_price - avg_price) * tp_qty_unleveraged
                else:
                    pos_all_tp_pnl += (avg_price - tp_price) * tp_qty_unleveraged
            
            potential_profit_all_tp += pos_all_tp_pnl
        
        if sl_orders and len(sl_orders) > 0:
            positions_with_sls += 1
            sl_order = sl_orders[0]
            sl_price = float(sl_order.get('triggerPrice', 0))
            if sl_price == 0:
                sl_price = float(sl_order.get('price', 0))
            
            if sl_price > 0:
                position_size_unleveraged = position_size / leverage if leverage > 0 else position_size
                
                if side == 'Buy':
                    pos_sl_pnl = abs((avg_price - sl_price) * position_size_unleveraged)
                else:
                    pos_sl_pnl = abs((sl_price - avg_price) * position_size_unleveraged)
                
                potential_loss_sl += pos_sl_pnl
        
        print(f"{symbol:<12} {side:<5} {position_size:<12.4f} {leverage:<8.0f} {len(tp_orders):<10} {len(sl_orders):<10} ${pos_tp1_pnl:<11.2f} ${pos_all_tp_pnl:<11.2f} ${pos_sl_pnl:<11.2f}")
    
    print("="*100)
    print(f"\nSummary:")
    print(f"Positions with TP orders: {positions_with_tps}/{len(active_positions)}")
    print(f"Positions with SL orders: {positions_with_sls}/{len(active_positions)}")
    print(f"\nAggregate P&L:")
    print(f"If All TP1 Hit: ${potential_profit_tp1:.2f}")
    print(f"If All TPs Hit: ${potential_profit_all_tp:.2f}")
    print(f"If All SL Hit: ${potential_loss_sl:.2f}")

if __name__ == "__main__":
    asyncio.run(verify_dashboard_pnl())