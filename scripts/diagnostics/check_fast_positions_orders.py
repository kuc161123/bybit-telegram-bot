#!/usr/bin/env python3
"""
Check Fast approach positions and their TP/SL orders.
Also investigate INJUSDT conservative position missing limit orders.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any
from pybit.unified_trading import HTTP
from config.settings import BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET

async def check_positions_and_orders():
    """Check all positions and their corresponding orders"""
    
    # Initialize Bybit client
    session = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    # Fast positions to check
    fast_positions = ["ENAUSDT", "TIAUSDT", "JTOUSDT", "WIFUSDT", 
                      "JASMYUSDT", "WLDUSDT", "KAVAUSDT", "BTCUSDT"]
    
    # Also check INJUSDT (conservative)
    all_symbols = fast_positions + ["INJUSDT"]
    
    print("=" * 80)
    print(f"Checking positions and orders at {datetime.now()}")
    print("=" * 80)
    
    # Get all positions
    positions_response = session.get_positions(category="linear", settleCoin="USDT")
    positions = positions_response.get("result", {}).get("list", [])
    
    # Get all orders
    orders_response = session.get_open_orders(category="linear", settleCoin="USDT")
    orders = orders_response.get("result", {}).get("list", [])
    
    # Create a map of orders by symbol
    orders_by_symbol = {}
    for order in orders:
        symbol = order.get("symbol")
        if symbol not in orders_by_symbol:
            orders_by_symbol[symbol] = []
        orders_by_symbol[symbol].append(order)
    
    # Check each position
    for symbol in all_symbols:
        print(f"\n{'='*60}")
        print(f"SYMBOL: {symbol}")
        print(f"{'='*60}")
        
        # Find position for this symbol
        position = None
        for pos in positions:
            if pos.get("symbol") == symbol and float(pos.get("size", 0)) > 0:
                position = pos
                break
        
        if not position:
            print(f"❌ No open position found for {symbol}")
            continue
        
        # Position details
        side = position.get("side")
        size = float(position.get("size", 0))
        avg_price = float(position.get("avgPrice", 0))
        unrealized_pnl = float(position.get("unrealizedPnl", 0))
        
        print(f"\n📊 POSITION:")
        print(f"   Side: {side}")
        print(f"   Size: {size}")
        print(f"   Avg Price: {avg_price}")
        print(f"   Unrealized PnL: ${unrealized_pnl:.2f}")
        
        # Get orders for this symbol
        symbol_orders = orders_by_symbol.get(symbol, [])
        
        if not symbol_orders:
            print(f"\n❌ NO ORDERS FOUND FOR {symbol}!")
            if symbol == "INJUSDT":
                print("   ⚠️  This is a CONSERVATIVE position - should have limit orders!")
            continue
        
        # Analyze orders
        tp_orders = []
        sl_orders = []
        limit_orders = []
        
        for order in symbol_orders:
            order_type = order.get("orderType")
            order_side = order.get("side")
            order_link_id = order.get("orderLinkId", "")
            trigger_price = order.get("triggerPrice", "")
            qty = float(order.get("qty", 0))
            price = order.get("price", "")
            
            # Detect order purpose - OrderLinkID takes precedence
            stop_order_type = order.get("stopOrderType", "")
            trigger_direction = order.get("triggerDirection", 0)
            
            # First check OrderLinkID patterns
            if "TP" in order_link_id:
                tp_orders.append(order)
            elif "SL" in order_link_id:
                sl_orders.append(order)
            # Then check stopOrderType
            elif stop_order_type == "TakeProfit":
                tp_orders.append(order)
            elif stop_order_type in ["Stop", "StopLoss"]:
                sl_orders.append(order)
            elif order_type == "Limit" and not trigger_price:
                limit_orders.append(order)
            # Fallback detection based on trigger price and position side
            elif trigger_price and order_side != side:  # Reduce-only orders
                if side == "Sell":
                    # For sell positions: TP is below entry, SL is above
                    if float(trigger_price) < avg_price:
                        tp_orders.append(order)
                    else:
                        sl_orders.append(order)
                elif side == "Buy":
                    # For buy positions: TP is above entry, SL is below
                    if float(trigger_price) > avg_price:
                        tp_orders.append(order)
                    else:
                        sl_orders.append(order)
        
        # Display TP orders
        if tp_orders:
            print(f"\n✅ TAKE PROFIT ORDERS ({len(tp_orders)}):")
            total_tp_qty = 0
            for order in tp_orders:
                trigger_price = order.get("triggerPrice", "")
                qty = float(order.get("qty", 0))
                total_tp_qty += qty
                order_link_id = order.get("orderLinkId", "")
                print(f"   - Trigger: {trigger_price}, Qty: {qty} ({qty/size*100:.1f}%), LinkID: {order_link_id}")
            
            print(f"   Total TP Quantity: {total_tp_qty} ({total_tp_qty/size*100:.1f}% of position)")
            
            # Check if it's Fast or Conservative
            if len(tp_orders) == 1 and total_tp_qty == size:
                print("   ✅ FAST APPROACH (100% single TP)")
            elif len(tp_orders) > 1:
                print("   📊 CONSERVATIVE APPROACH (multiple TPs)")
            else:
                print(f"   ⚠️  WARNING: TP quantity ({total_tp_qty}) doesn't match position size ({size})")
        else:
            print(f"\n❌ NO TAKE PROFIT ORDERS!")
        
        # Display SL orders
        if sl_orders:
            print(f"\n✅ STOP LOSS ORDERS ({len(sl_orders)}):")
            total_sl_qty = 0
            for order in sl_orders:
                trigger_price = order.get("triggerPrice", "")
                qty = float(order.get("qty", 0))
                total_sl_qty += qty
                order_link_id = order.get("orderLinkId", "")
                print(f"   - Trigger: {trigger_price}, Qty: {qty} ({qty/size*100:.1f}%), LinkID: {order_link_id}")
            
            print(f"   Total SL Quantity: {total_sl_qty} ({total_sl_qty/size*100:.1f}% of position)")
            
            if total_sl_qty != size:
                print(f"   ⚠️  WARNING: SL quantity ({total_sl_qty}) doesn't match position size ({size})")
        else:
            print(f"\n❌ NO STOP LOSS ORDERS!")
        
        # Display limit orders (for INJUSDT)
        if limit_orders:
            print(f"\n📋 LIMIT ORDERS ({len(limit_orders)}):")
            for order in limit_orders:
                order_side = order.get("side")
                price = order.get("price", "")
                qty = float(order.get("qty", 0))
                order_link_id = order.get("orderLinkId", "")
                print(f"   - {order_side} @ {price}, Qty: {qty}, LinkID: {order_link_id}")
        
        # Summary
        print(f"\n📋 SUMMARY:")
        if tp_orders and sl_orders:
            if len(tp_orders) == 1 and total_tp_qty == size and total_sl_qty == size:
                print("   ✅ FAST APPROACH - Properly configured with 100% TP and SL")
            elif len(tp_orders) > 1:
                print("   📊 CONSERVATIVE APPROACH - Multiple TPs detected")
            else:
                print("   ⚠️  CONFIGURATION ISSUE - Check TP/SL quantities")
        else:
            missing = []
            if not tp_orders:
                missing.append("TP")
            if not sl_orders:
                missing.append("SL")
            print(f"   ❌ MISSING ORDERS: {', '.join(missing)}")
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    
    # Special focus on problem positions
    print("\n🔍 POSITIONS REQUIRING ATTENTION:")
    for symbol in all_symbols:
        symbol_orders = orders_by_symbol.get(symbol, [])
        position_exists = any(p.get("symbol") == symbol and float(p.get("size", 0)) > 0 for p in positions)
        
        if position_exists:
            has_tp = any("TP" in order.get("orderLinkId", "") or order.get("triggerPrice") for order in symbol_orders)
            has_sl = any("SL" in order.get("orderLinkId", "") for order in symbol_orders)
            
            if not has_tp or not has_sl:
                print(f"\n❌ {symbol}:")
                if not has_tp:
                    print("   - Missing TP orders")
                if not has_sl:
                    print("   - Missing SL orders")
                if symbol == "INJUSDT":
                    print("   - This is supposed to be a CONSERVATIVE position!")

if __name__ == "__main__":
    asyncio.run(check_positions_and_orders())