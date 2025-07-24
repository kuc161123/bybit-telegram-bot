#!/usr/bin/env python3
"""
Fix Fast approach positions missing orders and INJUSDT duplicate TP issues
"""

import asyncio
import time
from typing import List, Dict, Any
from pybit.unified_trading import HTTP
from config.settings import BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET

async def fix_positions():
    """Fix positions with missing or duplicate orders"""
    
    # Initialize Bybit client
    session = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    print("=" * 80)
    print("FIXING POSITION ORDERS")
    print("=" * 80)
    
    # 1. Fix TIAUSDT missing SL
    print("\n🔧 FIXING TIAUSDT MISSING SL...")
    try:
        positions = session.get_positions(category="linear", symbol="TIAUSDT").get("result", {}).get("list", [])
        if positions and float(positions[0].get("size", 0)) > 0:
            position = positions[0]
            size = float(position.get("size"))
            avg_price = float(position.get("avgPrice"))
            side = position.get("side")
            
            # For Sell position, SL should be above entry
            sl_price = round(avg_price * 1.025, 3)  # 2.5% above entry
            
            print(f"Position: {side} {size} @ {avg_price}")
            print(f"Creating SL at {sl_price}")
            
            # Create SL order
            result = session.place_order(
                category="linear",
                symbol="TIAUSDT",
                side="Buy" if side == "Sell" else "Sell",
                orderType="Market",
                qty=str(size),
                triggerPrice=str(sl_price),
                triggerBy="LastPrice",
                triggerDirection=1 if side == "Sell" else 2,  # 1=rise, 2=fall
                orderLinkId=f"BOT_FAST_FIX_TIAUSDT_SL",
                reduceOnly=True,
                stopOrderType="Stop",
                positionIdx=2 if side == "Sell" else 1  # 1=long, 2=short for one-way mode
            )
            print(f"✅ SL order created: {result.get('result', {}).get('orderId')}")
        else:
            print("❌ No open position for TIAUSDT")
    except Exception as e:
        print(f"❌ Error fixing TIAUSDT: {e}")
    
    # 2. Fix BTCUSDT missing TP and SL
    print("\n🔧 FIXING BTCUSDT MISSING TP AND SL...")
    try:
        positions = session.get_positions(category="linear", symbol="BTCUSDT").get("result", {}).get("list", [])
        if positions and float(positions[0].get("size", 0)) > 0:
            position = positions[0]
            size = float(position.get("size"))
            avg_price = float(position.get("avgPrice"))
            side = position.get("side")
            
            print(f"Position: {side} {size} @ {avg_price}")
            
            # For Sell position
            tp_price = round(avg_price * 0.93, 0)  # 7% below entry
            sl_price = round(avg_price * 1.025, 0)  # 2.5% above entry
            
            print(f"Creating TP at {tp_price}")
            print(f"Creating SL at {sl_price}")
            
            # Create TP order
            result_tp = session.place_order(
                category="linear",
                symbol="BTCUSDT",
                side="Buy" if side == "Sell" else "Sell",
                orderType="Market",
                qty=str(size),
                triggerPrice=str(tp_price),
                triggerBy="LastPrice",
                triggerDirection=2 if side == "Sell" else 1,  # TP: 2=fall for sell, 1=rise for buy
                orderLinkId=f"BOT_FAST_FIX_BTCUSDT_TP",
                reduceOnly=True,
                stopOrderType="TakeProfit",
                positionIdx=2 if side == "Sell" else 1  # 1=long, 2=short for one-way mode
            )
            print(f"✅ TP order created: {result_tp.get('result', {}).get('orderId')}")
            
            # Small delay between orders
            time.sleep(0.5)
            
            # Create SL order
            result_sl = session.place_order(
                category="linear",
                symbol="BTCUSDT",
                side="Buy" if side == "Sell" else "Sell",
                orderType="Market",
                qty=str(size),
                triggerPrice=str(sl_price),
                triggerBy="LastPrice",
                triggerDirection=1 if side == "Sell" else 2,  # SL: 1=rise for sell, 2=fall for buy
                orderLinkId=f"BOT_FAST_FIX_BTCUSDT_SL",
                reduceOnly=True,
                stopOrderType="Stop",
                positionIdx=2 if side == "Sell" else 1  # 1=long, 2=short for one-way mode
            )
            print(f"✅ SL order created: {result_sl.get('result', {}).get('orderId')}")
        else:
            print("❌ No open position for BTCUSDT")
    except Exception as e:
        print(f"❌ Error fixing BTCUSDT: {e}")
    
    # 3. Fix INJUSDT duplicate TP orders
    print("\n🔧 FIXING INJUSDT DUPLICATE TP ORDERS...")
    try:
        # Get all orders for INJUSDT
        orders = session.get_open_orders(category="linear", symbol="INJUSDT").get("result", {}).get("list", [])
        
        # Find duplicate TP1 orders
        tp1_orders = [o for o in orders if 'TP1' in o.get('orderLinkId', '')]
        
        if len(tp1_orders) > 1:
            print(f"Found {len(tp1_orders)} TP1 orders, need to clean up duplicates")
            
            # Group by trigger price
            price_groups = {}
            for order in tp1_orders:
                trigger_price = order.get('triggerPrice')
                if trigger_price not in price_groups:
                    price_groups[trigger_price] = []
                price_groups[trigger_price].append(order)
            
            # Cancel duplicates, keep one from each price group
            for price, orders_at_price in price_groups.items():
                if len(orders_at_price) > 1:
                    print(f"\nFound {len(orders_at_price)} TP1 orders at price {price}")
                    # Keep the most recent one (last in list)
                    for order_to_cancel in orders_at_price[:-1]:
                        try:
                            result = session.cancel_order(
                                category="linear",
                                symbol="INJUSDT",
                                orderId=order_to_cancel.get('orderId')
                            )
                            print(f"✅ Cancelled duplicate: {order_to_cancel.get('orderLinkId')}")
                            time.sleep(0.5)
                        except Exception as e:
                            print(f"❌ Error cancelling order: {e}")
            
            # Also check for orders with extremely low trigger prices (likely errors)
            error_orders = []
            for o in orders:
                try:
                    trigger_price = o.get('triggerPrice', '')
                    if trigger_price and float(trigger_price) < 1.0 and 'TP' in o.get('orderLinkId', ''):
                        error_orders.append(o)
                except (ValueError, TypeError):
                    pass
            if error_orders:
                print(f"\n⚠️ Found {len(error_orders)} TP orders with suspiciously low trigger prices")
                for order in error_orders:
                    print(f"   {order.get('orderLinkId')}: Trigger={order.get('triggerPrice')}")
                    try:
                        result = session.cancel_order(
                            category="linear",
                            symbol="INJUSDT",
                            orderId=order.get('orderId')
                        )
                        print(f"   ✅ Cancelled erroneous order")
                        time.sleep(0.5)
                    except Exception as e:
                        print(f"   ❌ Error cancelling: {e}")
        
        # Verify position and check if we need to recreate proper conservative orders
        positions = session.get_positions(category="linear", symbol="INJUSDT").get("result", {}).get("list", [])
        if positions and float(positions[0].get("size", 0)) > 0:
            position = positions[0]
            size = float(position.get("size"))
            avg_price = float(position.get("avgPrice"))
            side = position.get("side")
            
            print(f"\n📊 Current position: {side} {size} @ {avg_price}")
            
            # Check remaining orders
            orders = session.get_open_orders(category="linear", symbol="INJUSDT").get("result", {}).get("list", [])
            tp_orders = [o for o in orders if 'TP' in o.get('orderLinkId', '')]
            valid_tp_orders = []
            for o in tp_orders:
                try:
                    trigger_price = o.get('triggerPrice', '')
                    if trigger_price and float(trigger_price) > 1.0:
                        valid_tp_orders.append(o)
                except (ValueError, TypeError):
                    pass
            
            print(f"Valid TP orders remaining: {len(valid_tp_orders)}")
            
            if len(valid_tp_orders) < 4:
                print("⚠️ Less than 4 TP orders - conservative position needs proper structure")
                # You may want to implement full conservative order recreation here
            
    except Exception as e:
        print(f"❌ Error fixing INJUSDT: {e}")
    
    print("\n" + "="*80)
    print("FIX COMPLETE - Please run check_fast_positions_orders.py again to verify")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(fix_positions())