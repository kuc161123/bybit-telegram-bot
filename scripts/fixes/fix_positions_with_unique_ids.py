#!/usr/bin/env python3
"""
Fix Fast approach positions with unique order IDs
"""

import asyncio
import time
import random
from typing import List, Dict, Any
from pybit.unified_trading import HTTP
from config.settings import BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET

async def fix_positions():
    """Fix positions with missing orders using unique IDs"""
    
    # Initialize Bybit client
    session = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    print("=" * 80)
    print("FIXING POSITION ORDERS WITH UNIQUE IDS")
    print("=" * 80)
    
    # Generate unique suffix
    unique_suffix = str(random.randint(10000, 99999))
    
    # 1. Fix TIAUSDT missing SL
    print("\n🔧 FIXING TIAUSDT MISSING SL...")
    try:
        # First check existing orders
        orders = session.get_open_orders(category="linear", symbol="TIAUSDT").get("result", {}).get("list", [])
        has_sl = any("SL" in order.get("orderLinkId", "") for order in orders)
        
        if has_sl:
            print("✅ SL order already exists for TIAUSDT")
        else:
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
                
                # Create SL order with unique ID
                result = session.place_order(
                    category="linear",
                    symbol="TIAUSDT",
                    side="Buy" if side == "Sell" else "Sell",
                    orderType="Market",
                    qty=str(size),
                    triggerPrice=str(sl_price),
                    triggerBy="LastPrice",
                    triggerDirection=1 if side == "Sell" else 2,  # 1=rise, 2=fall
                    orderLinkId=f"BOT_FAST_TIAUSDT_SL_{unique_suffix}",
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
        # Check existing orders
        orders = session.get_open_orders(category="linear", symbol="BTCUSDT").get("result", {}).get("list", [])
        has_tp = any("TP" in order.get("orderLinkId", "") or order.get("stopOrderType") == "TakeProfit" for order in orders)
        has_sl = any("SL" in order.get("orderLinkId", "") or order.get("stopOrderType") == "Stop" for order in orders)
        
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
            
            if not has_tp:
                print(f"Creating TP at {tp_price}")
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
                    orderLinkId=f"BOT_FAST_BTCUSDT_TP_{unique_suffix}",
                    reduceOnly=True,
                    stopOrderType="TakeProfit",
                    positionIdx=2 if side == "Sell" else 1  # 1=long, 2=short for one-way mode
                )
                print(f"✅ TP order created: {result_tp.get('result', {}).get('orderId')}")
                time.sleep(0.5)
            else:
                print("✅ TP order already exists")
            
            if not has_sl:
                print(f"Creating SL at {sl_price}")
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
                    orderLinkId=f"BOT_FAST_BTCUSDT_SL_{unique_suffix}",
                    reduceOnly=True,
                    stopOrderType="Stop",
                    positionIdx=2 if side == "Sell" else 1  # 1=long, 2=short for one-way mode
                )
                print(f"✅ SL order created: {result_sl.get('result', {}).get('orderId')}")
            else:
                print("✅ SL order already exists")
        else:
            print("❌ No open position for BTCUSDT")
    except Exception as e:
        print(f"❌ Error fixing BTCUSDT: {e}")
    
    print("\n" + "="*80)
    print("FIX COMPLETE - Please run check_fast_positions_orders.py again to verify")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(fix_positions())