#!/usr/bin/env python3
"""
Check the stop loss status of all current positions
"""

import asyncio
import pickle
from decimal import Decimal
from typing import Dict, Any
from config import *
from clients.bybit_client import bybit_client, api_error_handler
from utils.helpers import safe_decimal_conversion

async def main():
    try:
        # Load bot data
        persistence_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
        with open(persistence_file, 'rb') as f:
            data = pickle.load(f)
        
        # Get all chats data
        chats_data = data.get("chats_data", {})
        
        print("\n🔍 Checking Stop Loss Status for All Positions\n")
        print("=" * 80)
        
        # Fetch current positions
        positions = await bybit_client.get_position_info()
        open_positions = [p for p in positions if float(p.get("size", 0)) > 0]
        
        if not open_positions:
            print("No open positions found")
            return
            
        print(f"Found {len(open_positions)} open positions:\n")
        
        for pos in open_positions:
            symbol = pos.get("symbol")
            side = pos.get("side")
            size = pos.get("size")
            avg_price = pos.get("avgPrice")
            mark_price = pos.get("markPrice")
            
            print(f"\n📊 {symbol} - {side}")
            print(f"   Size: {size}")
            print(f"   Entry Price: {avg_price}")
            print(f"   Current Price: {mark_price}")
            
            # Find chat data for this position
            position_chat_data = None
            for chat_id, chat_data in chats_data.items():
                monitors = chat_data.get("active_monitor_task_data_v2", {})
                for monitor_id, monitor_data in monitors.items():
                    if monitor_data.get("symbol") == symbol:
                        position_chat_data = monitor_data
                        break
                if position_chat_data:
                    break
            
            if position_chat_data:
                approach = position_chat_data.get("approach", "unknown")
                sl_moved = position_chat_data.get("sl_moved_to_breakeven", False)
                print(f"   Approach: {approach}")
                print(f"   SL Moved to Breakeven: {'✅ Yes' if sl_moved else '❌ No'}")
                
                if sl_moved:
                    breakeven_price = position_chat_data.get("sl_breakeven_price")
                    if breakeven_price:
                        print(f"   Breakeven Price: {breakeven_price}")
            else:
                print("   ⚠️ No monitor data found for this position")
            
            # Fetch active orders for this position
            orders = await bybit_client.get_open_orders(symbol=symbol)
            sl_orders = [o for o in orders if o.get("stopOrderType") == "StopLoss"]
            tp_orders = [o for o in orders if o.get("stopOrderType") == "TakeProfit"]
            
            print(f"   Active Orders: {len(tp_orders)} TPs, {len(sl_orders)} SLs")
            
            if sl_orders:
                for sl in sl_orders:
                    trigger_price = sl.get("triggerPrice")
                    qty = sl.get("qty")
                    print(f"   SL Order: Price={trigger_price}, Qty={qty}")
        
        print("\n" + "=" * 80)
        print("\n✅ Check complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())