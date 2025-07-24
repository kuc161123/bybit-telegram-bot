#!/usr/bin/env python3
"""
Check and close all positions/orders properly
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_client import bybit_client
from config.settings import ENABLE_MIRROR_TRADING

def check_positions():
    """Check all positions on both accounts"""
    print("\n📊 CHECKING POSITIONS...")
    
    # Main account
    try:
        print("\n📌 MAIN ACCOUNT:")
        # Get all positions
        result = bybit_client.get_position_info(
            category="linear",
            settleCoin="USDT"
        )
        
        if result and result.get("result", {}).get("list"):
            positions = result["result"]["list"]
            active = [p for p in positions if float(p.get("size", 0)) > 0]
            
            if active:
                print(f"Found {len(active)} active positions:")
                for pos in active:
                    print(f"  - {pos['symbol']} {pos['side']}: {pos['size']} @ {pos['avgPrice']}")
                    
                    # Close the position
                    try:
                        close_side = "Sell" if pos["side"] == "Buy" else "Buy"
                        close_result = bybit_client.place_order(
                            category="linear",
                            symbol=pos["symbol"],
                            side=close_side,
                            orderType="Market",
                            qty=str(pos["size"]),
                            reduceOnly=True
                        )
                        print(f"    ✅ Closed {pos['symbol']}")
                    except Exception as e:
                        print(f"    ❌ Failed to close: {e}")
            else:
                print("  No active positions")
        else:
            print("  No positions found")
            
    except Exception as e:
        print(f"  ❌ Error checking main positions: {e}")
    
    # Check orders
    try:
        print("\n📋 MAIN ACCOUNT ORDERS:")
        # Get open orders with settleCoin
        orders = bybit_client.get_open_orders(
            category="linear",
            settleCoin="USDT"
        )
        
        if orders and orders.get("result", {}).get("list"):
            order_list = orders["result"]["list"]
            print(f"Found {len(order_list)} open orders:")
            for order in order_list:
                print(f"  - {order['symbol']} {order['side']} {order['orderType']}: {order['qty']} @ {order.get('price', 'Market')}")
                
                # Cancel the order
                try:
                    cancel_result = bybit_client.cancel_order(
                        category="linear",
                        symbol=order["symbol"],
                        orderId=order["orderId"]
                    )
                    print(f"    ✅ Cancelled order")
                except Exception as e:
                    print(f"    ❌ Failed to cancel: {e}")
        else:
            print("  No open orders")
            
    except Exception as e:
        print(f"  ❌ Error checking orders: {e}")
    
    # Mirror account
    if ENABLE_MIRROR_TRADING:
        try:
            print("\n📌 MIRROR ACCOUNT:")
            # Try to get mirror client
            from config.settings import BYBIT_API_KEY_2, BYBIT_API_SECRET_2
            if BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
                from pybit.unified_trading import HTTP
                mirror_client = HTTP(
                    testnet=False,
                    api_key=BYBIT_API_KEY_2,
                    api_secret=BYBIT_API_SECRET_2
                )
                
                # Check positions
                result = mirror_client.get_position_info(
                    category="linear",
                    settleCoin="USDT"
                )
                
                if result and result.get("result", {}).get("list"):
                    positions = result["result"]["list"]
                    active = [p for p in positions if float(p.get("size", 0)) > 0]
                    
                    if active:
                        print(f"Found {len(active)} active positions:")
                        for pos in active:
                            print(f"  - {pos['symbol']} {pos['side']}: {pos['size']} @ {pos['avgPrice']}")
                            
                            # Close the position
                            try:
                                close_side = "Sell" if pos["side"] == "Buy" else "Buy"
                                close_result = mirror_client.place_order(
                                    category="linear",
                                    symbol=pos["symbol"],
                                    side=close_side,
                                    orderType="Market",
                                    qty=str(pos["size"]),
                                    reduceOnly=True
                                )
                                print(f"    ✅ Closed {pos['symbol']}")
                            except Exception as e:
                                print(f"    ❌ Failed to close: {e}")
                    else:
                        print("  No active positions")
                        
                # Check orders
                print("\n📋 MIRROR ACCOUNT ORDERS:")
                orders = mirror_client.get_open_orders(
                    category="linear",
                    settleCoin="USDT"
                )
                
                if orders and orders.get("result", {}).get("list"):
                    order_list = orders["result"]["list"]
                    print(f"Found {len(order_list)} open orders:")
                    for order in order_list:
                        print(f"  - {order['symbol']} {order['side']} {order['orderType']}: {order['qty']} @ {order.get('price', 'Market')}")
                        
                        # Cancel the order
                        try:
                            cancel_result = mirror_client.cancel_order(
                                category="linear",
                                symbol=order["symbol"],
                                orderId=order["orderId"]
                            )
                            print(f"    ✅ Cancelled order")
                        except Exception as e:
                            print(f"    ❌ Failed to cancel: {e}")
                else:
                    print("  No open orders")
                    
            else:
                print("  Mirror trading not configured")
                
        except Exception as e:
            print(f"  ❌ Error checking mirror account: {e}")

if __name__ == "__main__":
    print("🧹 CHECKING AND CLOSING ALL POSITIONS/ORDERS")
    print("=" * 60)
    check_positions()
    print("\n" + "=" * 60)
    print("✅ DONE!")
    print("\n📌 Bot memory has been wiped")
    print("📌 Restart the bot with: python3 main.py")