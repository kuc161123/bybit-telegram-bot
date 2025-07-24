#!/usr/bin/env python3
"""Check LDOUSDT mirror position TP/SL orders"""

import asyncio
import sys
import os
from datetime import datetime
from decimal import Decimal
from pybit.unified_trading import HTTP

# Add parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import USE_TESTNET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2


async def check_ldousdt_mirror_orders():
    """Check all orders for LDOUSDT on mirror account"""
    print(f"\n{'='*60}")
    print(f"LDOUSDT Mirror Position Order Check - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # Initialize mirror account client
    api_key = BYBIT_API_KEY_2
    api_secret = BYBIT_API_SECRET_2
    use_testnet = USE_TESTNET
    
    if not api_key or not api_secret:
        print("❌ Mirror account credentials not configured!")
        return
        
    mirror_client = HTTP(
        api_key=api_key,
        api_secret=api_secret,
        testnet=use_testnet
    )
    
    # Check position first
    print("Checking LDOUSDT position on mirror account...")
    
    position_response = mirror_client.get_positions(
        category="linear",
        symbol="LDOUSDT"
    )
    
    if position_response.get("retCode") != 0:
        print(f"❌ Error fetching position: {position_response.get('retMsg')}")
        return
        
    positions = position_response.get("result", {}).get("list", [])
    if not positions or float(positions[0].get("size", 0)) == 0:
        print("❌ No open LDOUSDT position found on mirror account")
        return
        
    position_info = positions[0]
    
    # Display position details
    position_size = float(position_info.get('size', 0))
    position_side = position_info.get('side', 'None')
    entry_price = float(position_info.get('avgPrice', 0))
    mark_price = float(position_info.get('markPrice', 0))
    unrealized_pnl = float(position_info.get('unrealisedPnl', 0))
    
    print(f"\n✅ LDOUSDT Position Found:")
    print(f"  Side: {position_side}")
    print(f"  Size: {position_size}")
    print(f"  Entry Price: ${entry_price:.4f}")
    print(f"  Mark Price: ${mark_price:.4f}")
    print(f"  Unrealized PnL: ${unrealized_pnl:.2f}")
    
    # Get all open orders
    print(f"\n{'='*40}")
    print("Checking open orders for LDOUSDT...")
    print(f"{'='*40}\n")
    
    try:
        # Get open orders for LDOUSDT
        orders = mirror_client.get_open_orders(
            category="linear",
            symbol="LDOUSDT",
            limit=50
        )
        
        if orders['retCode'] != 0:
            print(f"❌ Error fetching orders: {orders['retMsg']}")
            return
            
        order_list = orders['result']['list']
        
        if not order_list:
            print("⚠️  NO OPEN ORDERS FOUND FOR LDOUSDT!")
            print("   This position has no TP or SL protection!")
            return
            
        # Analyze orders
        tp_orders = []
        sl_orders = []
        other_orders = []
        
        print(f"Found {len(order_list)} open orders:\n")
        
        for i, order in enumerate(order_list):
            # Debug: print first order's full details
            if i == 0:
                print("DEBUG - First order full details:")
                for key, value in order.items():
                    print(f"  {key}: {value}")
                print()
                
            order_id = order.get('orderId', '')
            order_type = order.get('orderType', '')
            side = order.get('side', '')
            qty = float(order.get('qty', 0) or 0)
            price = float(order.get('price', 0) or 0)
            stop_order_type = order.get('stopOrderType', '')
            trigger_price = float(order.get('triggerPrice', 0) or 0)
            reduce_only = order.get('reduceOnly', False)
            created_time = order.get('createdTime', '')
            
            # Determine order category
            # Check if it's a conditional order (has triggerPrice)
            if reduce_only and trigger_price > 0:
                # For Sell position:
                # - TP: Buy orders with trigger price < entry price
                # - SL: Buy orders with trigger price > entry price
                if position_side == "Sell" and side == "Buy":
                    if trigger_price < entry_price:
                        tp_orders.append(order)
                    else:
                        sl_orders.append(order)
                # For Buy position:
                # - TP: Sell orders with trigger price > entry price
                # - SL: Sell orders with trigger price < entry price
                elif position_side == "Buy" and side == "Sell":
                    if trigger_price > entry_price:
                        tp_orders.append(order)
                    else:
                        sl_orders.append(order)
                else:
                    other_orders.append(order)
            else:
                other_orders.append(order)
                
        # Display TP orders
        if tp_orders:
            print(f"✅ Take Profit Orders ({len(tp_orders)}):")
            total_tp_qty = 0
            for order in tp_orders:
                qty = float(order.get('qty', 0) or 0)
                trigger_price = float(order.get('triggerPrice', 0) or 0)
                total_tp_qty += qty
                tp_percentage = (qty / position_size) * 100
                print(f"   - TP Order: {qty} ({tp_percentage:.1f}%) @ ${trigger_price:.4f}")
            
            tp_coverage = (total_tp_qty / position_size) * 100
            print(f"   Total TP Coverage: {total_tp_qty} ({tp_coverage:.1f}%)")
        else:
            print("❌ NO TAKE PROFIT ORDERS FOUND!")
            
        # Display SL orders
        if sl_orders:
            print(f"\n✅ Stop Loss Orders ({len(sl_orders)}):")
            total_sl_qty = 0
            for order in sl_orders:
                qty = float(order.get('qty', 0) or 0)
                trigger_price = float(order.get('triggerPrice', 0) or 0)
                total_sl_qty += qty
                sl_percentage = (qty / position_size) * 100
                print(f"   - SL Order: {qty} ({sl_percentage:.1f}%) @ ${trigger_price:.4f}")
                
            sl_coverage = (total_sl_qty / position_size) * 100
            print(f"   Total SL Coverage: {total_sl_qty} ({sl_coverage:.1f}%)")
        else:
            print("\n❌ NO STOP LOSS ORDERS FOUND!")
            
        # Display other orders
        if other_orders:
            print(f"\n⚠️  Other Orders ({len(other_orders)}):")
            for order in other_orders:
                order_type = order.get('orderType', '')
                side = order.get('side', '')
                qty = float(order.get('qty', 0) or 0)
                price = float(order.get('price', 0) or 0)
                reduce_only = order.get('reduceOnly', False)
                print(f"   - {order_type} {side}: {qty} @ ${price:.4f} (reduceOnly: {reduce_only}, stopOrderType: {stop_order_type}, triggerPrice: ${trigger_price:.4f})")
                
        # Summary
        print(f"\n{'='*40}")
        print("SUMMARY:")
        print(f"{'='*40}")
        
        if not tp_orders and not sl_orders:
            print("⚠️  CRITICAL: This position has NO risk management orders!")
            print("   No TP orders and No SL orders found!")
            print("   Position is completely unprotected!")
        elif not tp_orders:
            print("⚠️  WARNING: Position has no Take Profit orders!")
        elif not sl_orders:
            print("⚠️  WARNING: Position has no Stop Loss orders!")
        else:
            tp_coverage = (sum(float(o.get('qty', 0)) for o in tp_orders) / position_size) * 100
            sl_coverage = (sum(float(o.get('qty', 0)) for o in sl_orders) / position_size) * 100
            print(f"✅ Position protected with:")
            print(f"   - {len(tp_orders)} TP orders ({tp_coverage:.1f}% coverage)")
            print(f"   - {len(sl_orders)} SL orders ({sl_coverage:.1f}% coverage)")
            
    except Exception as e:
        print(f"❌ Error checking orders: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_ldousdt_mirror_orders())