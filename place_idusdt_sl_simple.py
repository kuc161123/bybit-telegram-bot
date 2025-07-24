#!/usr/bin/env python3
"""
Simple script to place SL for IDUSDT mirror position
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from execution.mirror_trader import bybit_client_2
from config.constants import BOT_PREFIX
from datetime import datetime

def main():
    print("📍 Placing SL order for IDUSDT mirror position...")
    
    # Position parameters (from previous check)
    symbol = "IDUSDT"
    size = "77"  # Position size
    entry_price = 0.1765  # Approximate entry price
    sl_percentage = 0.08  # 8% below entry
    sl_price = round(entry_price * (1 - sl_percentage), 4)
    
    print(f"   Symbol: {symbol}")
    print(f"   Size: {size}")
    print(f"   Entry Price: {entry_price}")
    print(f"   SL Price: {sl_price}")
    
    try:
        order_link_id = f"{BOT_PREFIX}SL_IDUSDT_mirror_{int(datetime.now().timestamp())}"
        
        result = bybit_client_2.place_order(
            category="linear",
            symbol=symbol,
            side="Sell",
            orderType="Market",
            qty=size,
            triggerPrice=str(sl_price),
            triggerDirection="2",  # Falling
            triggerBy="LastPrice",
            reduceOnly=True,
            orderLinkId=order_link_id
        )
        
        if result and result.get("retCode") == 0:
            order_id = result.get("result", {}).get("orderId")
            print(f"✅ SL order placed successfully!")
            print(f"   Order ID: {order_id}")
            print(f"   Order Link ID: {order_link_id}")
        else:
            print(f"❌ Failed to place SL order: {result}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()