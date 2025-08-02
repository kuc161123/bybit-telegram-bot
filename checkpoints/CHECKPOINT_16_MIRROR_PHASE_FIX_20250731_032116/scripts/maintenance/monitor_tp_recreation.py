#!/usr/bin/env python3
"""Monitor Conservative positions for TP recreation issues."""

import asyncio
import json
import logging
from datetime import datetime
from pybit.unified_trading import HTTP
from dotenv import load_dotenv
import os

load_dotenv()

async def monitor_conservative_positions():
    """Monitor Conservative positions and their TP orders."""
    
    client = HTTP(
        api_key=os.getenv("BYBIT_API_KEY"),
        api_secret=os.getenv("BYBIT_API_SECRET"),
        testnet=os.getenv("USE_TESTNET", "false").lower() == "true"
    )
    
    print("\n🔍 Monitoring Conservative positions for TP recreation issues...")
    
    while True:
        try:
            # Get all positions
            positions = client.get_positions(category="linear", settleCoin="USDT")
            if positions.get("retCode") == 0:
                for pos in positions["result"]["list"]:
                    if float(pos.get("size", 0)) > 0:
                        symbol = pos["symbol"]
                        size = float(pos["size"])
                        
                        # Get orders for this position
                        orders = client.get_open_orders(category="linear", symbol=symbol)
                        if orders.get("retCode") == 0:
                            tp_orders = [
                                o for o in orders["result"]["list"]
                                if "TP" in o.get("orderLinkId", "") or o.get("stopOrderType") == "TakeProfit"
                            ]
                            
                            # Check for Conservative positions
                            conservative_orders = [
                                o for o in tp_orders
                                if "CONS" in o.get("orderLinkId", "")
                            ]
                            
                            if conservative_orders:
                                tp_total_qty = sum(float(o["qty"]) for o in conservative_orders)
                                
                                print(f"\n📊 {symbol}:")
                                print(f"   Position size: {size}")
                                print(f"   TP orders: {len(conservative_orders)}")
                                print(f"   TP total qty: {tp_total_qty}")
                                
                                if tp_total_qty > size * 1.05:  # 5% tolerance
                                    print(f"   ⚠️  WARNING: TP quantity ({tp_total_qty}) > Position size ({size})")
                                    print(f"   🔄 This indicates TP recreation issue!")
            
            await asyncio.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(monitor_conservative_positions())
