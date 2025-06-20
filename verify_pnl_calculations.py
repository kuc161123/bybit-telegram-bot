#!/usr/bin/env python3
"""
Verify P&L calculations for the dashboard
"""
import asyncio
import logging
from decimal import Decimal
from clients.bybit_helpers import get_all_positions, get_all_open_orders

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_pnl_calculations():
    """Verify P&L calculations match expected values"""
    
    # Get positions and orders
    positions = await get_all_positions()
    all_orders = await get_all_open_orders()
    
    print("\n" + "="*80)
    print("P&L CALCULATION VERIFICATION")
    print("="*80)
    
    active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
    
    for pos in active_positions:
        symbol = pos.get('symbol', '')
        position_size = float(pos.get('size', 0))
        avg_price = float(pos.get('avgPrice', 0))
        side = pos.get('side', '')
        leverage = float(pos.get('leverage', 1))
        unrealized_pnl = float(pos.get('unrealisedPnl', 0))
        
        print(f"\nPosition: {symbol}")
        print(f"  Side: {side}")
        print(f"  Size (leveraged): {position_size}")
        print(f"  Leverage: {leverage}x")
        print(f"  Size (unleveraged): {position_size/leverage:.4f}")
        print(f"  Entry Price: ${avg_price}")
        print(f"  Current Unrealized P&L: ${unrealized_pnl:.2f}")
        
        # Find TP/SL orders for this position
        position_orders = [o for o in all_orders if o.get('symbol') == symbol]
        
        tp_orders = []
        sl_orders = []
        
        for order in position_orders:
            # Get trigger price (for conditional orders) or regular price
            trigger_price = order.get('triggerPrice', '')
            regular_price = order.get('price', '')
            
            # Determine which price to use
            order_price = float(trigger_price) if trigger_price else float(regular_price) if regular_price else 0
            
            reduce_only = order.get('reduceOnly', False)
            
            if order_price > 0 and reduce_only:
                # Classify as TP or SL based on price relative to entry
                if side == 'Buy':
                    if order_price > avg_price:
                        tp_orders.append((order_price, order))
                    else:
                        sl_orders.append((order_price, order))
                else:  # Sell
                    if order_price < avg_price:
                        tp_orders.append((order_price, order))
                    else:
                        sl_orders.append((order_price, order))
        
        print(f"\n  TP Orders Found: {len(tp_orders)}")
        print(f"  SL Orders Found: {len(sl_orders)}")
        
        # Calculate potential P&L
        if tp_orders:
            print("\n  Take Profit Analysis:")
            total_tp_pnl = 0
            
            for i, (tp_price, order) in enumerate(tp_orders):
                qty = float(order.get('qty', position_size))
                
                # Calculate P&L for this TP
                if side == 'Buy':
                    pnl_leveraged = (tp_price - avg_price) * qty
                else:
                    pnl_leveraged = (avg_price - tp_price) * qty
                
                pnl_unleveraged = pnl_leveraged / leverage
                
                print(f"    TP{i+1}: Price=${tp_price:.4f}, Qty={qty}")
                print(f"          Leveraged P&L: ${pnl_leveraged:.2f}")
                print(f"          Actual P&L: ${pnl_unleveraged:.2f}")
                
                total_tp_pnl += pnl_unleveraged
            
            print(f"\n    Total if all TPs hit: ${total_tp_pnl:.2f}")
        
        if sl_orders:
            print("\n  Stop Loss Analysis:")
            for i, (sl_price, order) in enumerate(sl_orders):
                # Use full position size for SL
                if side == 'Buy':
                    loss_leveraged = abs((avg_price - sl_price) * position_size)
                else:
                    loss_leveraged = abs((sl_price - avg_price) * position_size)
                
                loss_unleveraged = loss_leveraged / leverage
                
                print(f"    SL: Price=${sl_price:.4f}")
                print(f"        Leveraged Loss: ${loss_leveraged:.2f}")
                print(f"        Actual Loss: ${loss_unleveraged:.2f}")
        
        print("-" * 80)

async def main():
    await verify_pnl_calculations()

if __name__ == "__main__":
    asyncio.run(main())