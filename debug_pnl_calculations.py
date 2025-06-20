#!/usr/bin/env python3
"""
Debug script to analyze P&L calculations
"""
import asyncio
import logging
from decimal import Decimal
from clients.bybit_helpers import get_all_positions, get_all_open_orders
from utils.cache import get_usdt_wallet_balance_cached

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def debug_pnl_calculations():
    """Debug P&L calculations to find issues"""
    
    print("\n=== DEBUGGING P&L CALCULATIONS ===\n")
    
    # Get wallet balance
    try:
        wallet_info = await get_usdt_wallet_balance_cached()
        if isinstance(wallet_info, tuple) and len(wallet_info) >= 2:
            total_balance = wallet_info[0]
            available_balance = wallet_info[1]
        else:
            total_balance = 0
            available_balance = 0
        print(f"💰 Total Balance: ${total_balance}")
        print(f"🔓 Available Balance: ${available_balance}")
    except Exception as e:
        print(f"❌ Error getting wallet balance: {e}")
        total_balance = 0
        available_balance = 0
    
    # Get all positions
    positions = await get_all_positions()
    active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
    
    print(f"\n📊 Total Positions Found: {len(positions)}")
    print(f"📈 Active Positions (size > 0): {len(active_positions)}")
    
    # Get all orders
    all_orders = await get_all_open_orders()
    print(f"\n📋 Total Open Orders: {len(all_orders)}")
    
    # Calculate potential P&L
    potential_profit_tp1 = 0
    potential_profit_all_tp = 0
    potential_loss_sl = 0
    
    print("\n=== POSITION-BY-POSITION ANALYSIS ===\n")
    
    for idx, pos in enumerate(active_positions):
        symbol = pos.get('symbol', '')
        position_size = float(pos.get('size', 0))
        avg_price = float(pos.get('avgPrice', 0))
        side = pos.get('side', '')
        leverage = float(pos.get('leverage', 1))
        unrealized_pnl = float(pos.get('unrealisedPnl', 0))
        position_value = float(pos.get('positionValue', 0))
        position_im = float(pos.get('positionIM', 0))
        
        print(f"\n--- Position {idx + 1}: {symbol} ---")
        print(f"Side: {side} | Size: {position_size} | Avg Price: ${avg_price}")
        print(f"Leverage: {leverage}x | Position Value: ${position_value:.2f}")
        print(f"Initial Margin (actual USDT used): ${position_im:.2f}")
        print(f"Current Unrealized P&L: ${unrealized_pnl:.2f}")
        
        # Calculate unleveraged size (actual quantity, not leveraged)
        unleveraged_size = position_size / leverage if leverage > 0 else position_size
        print(f"Unleveraged Size: {unleveraged_size:.6f}")
        
        # Find TP and SL orders for this position
        tp_orders = []
        sl_orders = []
        
        for order in all_orders:
            if order.get('symbol') == symbol:
                order_side = order.get('side', '')
                trigger_price = order.get('triggerPrice', '')
                reduce_only = order.get('reduceOnly', False)
                order_type = order.get('orderType', '')
                
                # Debug order info
                if trigger_price or order_type == 'Limit':
                    print(f"\n  Order: {order_type} {order_side}")
                    print(f"  Trigger Price: {trigger_price}")
                    print(f"  Price: {order.get('price', '')}")
                    print(f"  Qty: {order.get('qty', '')}")
                    print(f"  Reduce Only: {reduce_only}")
                
                # For positions, we need to identify TP and SL based on trigger price
                if trigger_price and reduce_only:
                    try:
                        trigger_price_float = float(trigger_price)
                    except (ValueError, TypeError):
                        continue
                    
                    # TP orders: price is favorable to position
                    if side == 'Buy':
                        # Long position: TP if trigger > avg_price, SL if trigger < avg_price
                        if trigger_price_float > avg_price:
                            tp_orders.append(order)
                            print(f"  → Identified as TP (trigger ${trigger_price_float} > avg ${avg_price})")
                        else:
                            sl_orders.append(order)
                            print(f"  → Identified as SL (trigger ${trigger_price_float} < avg ${avg_price})")
                    else:  # Sell/Short position
                        # Short position: TP if trigger < avg_price, SL if trigger > avg_price
                        if trigger_price_float < avg_price:
                            tp_orders.append(order)
                            print(f"  → Identified as TP (trigger ${trigger_price_float} < avg ${avg_price})")
                        else:
                            sl_orders.append(order)
                            print(f"  → Identified as SL (trigger ${trigger_price_float} > avg ${avg_price})")
                
                # Also check for regular limit orders that might be TPs
                elif order_type == 'Limit' and reduce_only:
                    # These are likely TP orders
                    tp_orders.append(order)
                    print(f"  → Identified as TP (Limit order, reduce only)")
        
        print(f"\nTP Orders found: {len(tp_orders)}")
        print(f"SL Orders found: {len(sl_orders)}")
        
        # Calculate P&L from actual orders
        position_tp1_profit = 0
        position_all_tp_profit = 0
        position_sl_loss = 0
        
        if tp_orders:
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
                except (ValueError, TypeError):
                    return 0
            
            tp_orders.sort(key=get_order_price, reverse=(side == 'Buy'))
            
            print(f"\nTP Order Details:")
            for i, tp_order in enumerate(tp_orders):
                tp_price = get_order_price(tp_order)
                tp_qty = float(tp_order.get('qty', 0))
                tp_qty_unleveraged = tp_qty / leverage if leverage > 0 else tp_qty
                
                if side == 'Buy':
                    profit = (tp_price - avg_price) * tp_qty_unleveraged
                else:
                    profit = (avg_price - tp_price) * tp_qty_unleveraged
                
                print(f"  TP{i+1}: Price ${tp_price}, Qty {tp_qty} (unleveraged: {tp_qty_unleveraged:.6f})")
                print(f"  → Profit: ${profit:.2f}")
                
                if i == 0:
                    position_tp1_profit = profit
                position_all_tp_profit += profit
        
        if sl_orders and len(sl_orders) > 0:
            sl_order = sl_orders[0]
            sl_price = float(sl_order.get('triggerPrice', 0))
            if sl_price == 0:
                sl_price = float(sl_order.get('price', 0))
            
            if sl_price > 0:
                position_size_unleveraged = position_size / leverage if leverage > 0 else position_size
                
                if side == 'Buy':
                    loss = abs((avg_price - sl_price) * position_size_unleveraged)
                else:
                    loss = abs((sl_price - avg_price) * position_size_unleveraged)
                
                position_sl_loss = loss
                print(f"\nSL Order: Price ${sl_price}")
                print(f"→ Loss: ${loss:.2f}")
        
        # Add to totals
        potential_profit_tp1 += position_tp1_profit
        potential_profit_all_tp += position_all_tp_profit
        potential_loss_sl += position_sl_loss
        
        print(f"\nPosition Summary:")
        print(f"  Potential TP1 Profit: ${position_tp1_profit:.2f}")
        print(f"  Potential All TP Profit: ${position_all_tp_profit:.2f}")
        print(f"  Potential SL Loss: ${position_sl_loss:.2f}")
    
    print("\n=== FINAL TOTALS ===\n")
    print(f"📊 Active Positions: {len(active_positions)}")
    print(f"💰 Current Account P&L: $39 (as reported by user)")
    print(f"\n🎯 Potential P&L Analysis:")
    print(f"  If All TP1 Hit: +${potential_profit_tp1:.2f}")
    print(f"  If All TPs Hit: +${potential_profit_all_tp:.2f}")
    print(f"  If All SL Hit: -${potential_loss_sl:.2f}")
    print(f"  Risk:Reward = 1:{(potential_profit_tp1/potential_loss_sl if potential_loss_sl > 0 else 0):.1f}")
    
    # Check for potential issues
    print("\n=== POTENTIAL ISSUES CHECK ===\n")
    
    # Check 1: Are we missing positions?
    print(f"1. Position Count Check:")
    print(f"   - User reports: 24 positions")
    print(f"   - We found: {len(active_positions)} active positions")
    if len(active_positions) < 24:
        print("   ⚠️ ISSUE: We're finding fewer positions than the user reports!")
    
    # Check 2: Are calculations reasonable?
    print(f"\n2. Calculation Reasonableness:")
    total_margin = sum(float(p.get('positionIM', 0)) for p in active_positions)
    print(f"   - Total margin used: ${total_margin:.2f}")
    print(f"   - Average margin per position: ${total_margin/len(active_positions) if active_positions else 0:.2f}")
    
    # Check 3: Missing orders?
    positions_with_tp = sum(1 for pos in active_positions if any(
        o.get('symbol') == pos.get('symbol') and o.get('reduceOnly', False) 
        for o in all_orders
    ))
    print(f"\n3. Order Coverage:")
    print(f"   - Positions with any reduce-only orders: {positions_with_tp}/{len(active_positions)}")
    
    return {
        'active_positions': len(active_positions),
        'potential_profit_tp1': potential_profit_tp1,
        'potential_profit_all_tp': potential_profit_all_tp,
        'potential_loss_sl': potential_loss_sl,
        'total_orders': len(all_orders)
    }

if __name__ == "__main__":
    asyncio.run(debug_pnl_calculations())