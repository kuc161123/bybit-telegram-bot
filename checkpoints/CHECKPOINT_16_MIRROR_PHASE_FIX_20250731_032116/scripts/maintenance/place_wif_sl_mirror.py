#!/usr/bin/env python3
"""
Place WIFUSDT SL order on mirror account with correct parameters
"""
from pybit.unified_trading import HTTP
from config.settings import USE_TESTNET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
import time

# Initialize mirror client
mirror_client = HTTP(
    api_key=BYBIT_API_KEY_2,
    api_secret=BYBIT_API_SECRET_2,
    testnet=USE_TESTNET
)

print("Placing WIFUSDT SL order on mirror account...")

# SL parameters
symbol = "WIFUSDT"
side = "Sell"  # Opposite of Buy position
qty = "442"
trigger_price = "0.8354"

try:
    response = mirror_client.place_order(
        category="linear",
        symbol=symbol,
        side=side,
        orderType="Market",
        qty=qty,
        triggerPrice=trigger_price,
        triggerDirection=2,  # 1=rise, 2=fall - for SL on long position, trigger on fall
        reduceOnly=True,
        orderLinkId=f"BOT_MIR_WIFUSDT_SL_{int(time.time())}",
        positionIdx=0,
        stopOrderType="StopLoss",
        triggerBy="MarkPrice"
    )
    
    if response.get("retCode") == 0:
        order_id = response.get("result", {}).get("orderId", "")
        print(f"✅ SL order placed successfully: {order_id}")
        print(f"   Trigger: ${trigger_price}")
        print(f"   Quantity: {qty}")
    else:
        print(f"❌ Failed: {response.get('retMsg', 'Unknown error')}")
        print(f"Full response: {response}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\nRun check_wif_orders.py to verify all orders are in place")