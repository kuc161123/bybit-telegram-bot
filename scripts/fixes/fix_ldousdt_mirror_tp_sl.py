#!/usr/bin/env python3
"""Fix missing TP/SL orders for LDOUSDT mirror position"""

import asyncio
import sys
import os
from datetime import datetime
from decimal import Decimal
from pybit.unified_trading import HTTP

# Add parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import USE_TESTNET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2


async def fix_ldousdt_mirror_tp_sl():
    """Place missing TP/SL orders for LDOUSDT mirror position"""
    print(f"\n{'='*60}")
    print(f"Fixing LDOUSDT Mirror Position TP/SL - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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
    
    # Get symbol info for tick size and qty step
    instrument_response = mirror_client.get_instruments_info(
        category="linear",
        symbol="LDOUSDT"
    )
    
    if instrument_response.get("retCode") != 0:
        print(f"❌ Error fetching instrument info: {instrument_response.get('retMsg')}")
        return
        
    instrument = instrument_response.get("result", {}).get("list", [])[0]
    tick_size = float(instrument.get("priceFilter", {}).get("tickSize", 0.0001))
    qty_step = float(instrument.get("lotSizeFilter", {}).get("qtyStep", 0.1))
    
    print(f"\nInstrument info:")
    print(f"  Tick size: {tick_size}")
    print(f"  Qty step: {qty_step}")
    
    # Calculate TP and SL prices based on position side
    if position_side == "Sell":
        # For short position: TP is below entry, SL is above entry
        tp1_price = entry_price * 0.98  # 2% profit
        tp2_price = entry_price * 0.97  # 3% profit
        tp3_price = entry_price * 0.96  # 4% profit
        tp4_price = entry_price * 0.95  # 5% profit
        sl_price = entry_price * 1.02   # 2% loss
        
        # For sell position: TP orders are Buy orders
        tp_side = "Buy"
        sl_side = "Buy"
    else:
        # For long position: TP is above entry, SL is below entry
        tp1_price = entry_price * 1.02  # 2% profit
        tp2_price = entry_price * 1.03  # 3% profit
        tp3_price = entry_price * 1.04  # 4% profit
        tp4_price = entry_price * 1.05  # 5% profit
        sl_price = entry_price * 0.98   # 2% loss
        
        # For buy position: TP orders are Sell orders
        tp_side = "Sell"
        sl_side = "Sell"
    
    # Round prices to tick size
    def round_to_tick(price, tick):
        return round(price / tick) * tick
        
    tp1_price = round_to_tick(tp1_price, tick_size)
    tp2_price = round_to_tick(tp2_price, tick_size)
    tp3_price = round_to_tick(tp3_price, tick_size)
    tp4_price = round_to_tick(tp4_price, tick_size)
    sl_price = round_to_tick(sl_price, tick_size)
    
    # Calculate quantities (85%, 5%, 5%, 5% distribution)
    def round_qty(qty, step):
        return round(qty / step) * step
        
    tp1_qty = round_qty(position_size * 0.85, qty_step)
    tp2_qty = round_qty(position_size * 0.05, qty_step)
    tp3_qty = round_qty(position_size * 0.05, qty_step)
    tp4_qty = round_qty(position_size * 0.05, qty_step)
    
    # Adjust for rounding errors
    total_tp_qty = tp1_qty + tp2_qty + tp3_qty + tp4_qty
    if total_tp_qty < position_size:
        tp1_qty += round_qty(position_size - total_tp_qty, qty_step)
    
    sl_qty = position_size  # SL covers full position
    
    print(f"\n{'='*40}")
    print("Placing TP orders...")
    print(f"{'='*40}")
    
    # Place TP orders
    tp_orders = [
        {"qty": tp1_qty, "price": tp1_price, "label": "TP1 (85%)"},
        {"qty": tp2_qty, "price": tp2_price, "label": "TP2 (5%)"},
        {"qty": tp3_qty, "price": tp3_price, "label": "TP3 (5%)"},
        {"qty": tp4_qty, "price": tp4_price, "label": "TP4 (5%)"},
    ]
    
    successful_tps = 0
    for tp in tp_orders:
        if tp["qty"] <= 0:
            continue
            
        print(f"\nPlacing {tp['label']}: {tp['qty']} @ ${tp['price']:.4f}")
        
        try:
            result = mirror_client.place_order(
                category="linear",
                symbol="LDOUSDT",
                side=tp_side,
                orderType="Limit",
                qty=str(tp["qty"]),
                price=str(tp["price"]),
                reduceOnly=True,
                stopOrderType="TakeProfit",
                triggerPrice=str(tp["price"]),
                triggerDirection=1 if position_side == "Buy" else 2,
                orderLinkId=f"TP_{datetime.now().timestamp():.0f}_{tp['label'].replace(' ', '_')}"
            )
            
            if result.get("retCode") == 0:
                print(f"✅ {tp['label']} placed successfully!")
                successful_tps += 1
            else:
                print(f"❌ Failed to place {tp['label']}: {result.get('retMsg')}")
                
        except Exception as e:
            print(f"❌ Error placing {tp['label']}: {e}")
    
    print(f"\n{'='*40}")
    print("Placing SL order...")
    print(f"{'='*40}")
    
    # Place SL order
    print(f"\nPlacing SL: {sl_qty} @ ${sl_price:.4f}")
    
    try:
        result = mirror_client.place_order(
            category="linear",
            symbol="LDOUSDT",
            side=sl_side,
            orderType="Market",
            qty=str(sl_qty),
            reduceOnly=True,
            stopOrderType="StopLoss",
            triggerPrice=str(sl_price),
            triggerDirection=1 if position_side == "Sell" else 2,
            orderLinkId=f"SL_{datetime.now().timestamp():.0f}"
        )
        
        if result.get("retCode") == 0:
            print("✅ SL placed successfully!")
            sl_success = True
        else:
            print(f"❌ Failed to place SL: {result.get('retMsg')}")
            sl_success = False
            
    except Exception as e:
        print(f"❌ Error placing SL: {e}")
        sl_success = False
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY:")
    print(f"{'='*60}")
    print(f"✅ Successfully placed {successful_tps} TP orders")
    if sl_success:
        print("✅ Successfully placed SL order")
    else:
        print("❌ Failed to place SL order")
        
    print(f"\nPosition is now protected with:")
    print(f"  - {successful_tps} Take Profit orders")
    print(f"  - {'1' if sl_success else '0'} Stop Loss order")
    
    # Verify orders were placed
    print(f"\n{'='*40}")
    print("Verifying orders...")
    print(f"{'='*40}")
    
    orders = mirror_client.get_open_orders(
        category="linear",
        symbol="LDOUSDT",
        limit=50
    )
    
    if orders['retCode'] == 0:
        order_list = orders['result']['list']
        tp_count = 0
        sl_count = 0
        
        for order in order_list:
            stop_order_type = order.get('stopOrderType', '')
            if stop_order_type == 'TakeProfit':
                tp_count += 1
            elif stop_order_type == 'StopLoss':
                sl_count += 1
                
        print(f"\n✅ Verification complete:")
        print(f"  - {tp_count} TP orders found")
        print(f"  - {sl_count} SL orders found")
    else:
        print(f"❌ Could not verify orders: {orders['retMsg']}")


if __name__ == "__main__":
    asyncio.run(fix_ldousdt_mirror_tp_sl())