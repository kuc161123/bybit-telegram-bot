#!/usr/bin/env python3
"""
Close all positions and orders on both accounts - fixed version
"""

import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_client import bybit_client
from config.settings import ENABLE_MIRROR_TRADING

async def close_all_main():
    """Close all positions and orders on main account"""
    print("\n📌 MAIN ACCOUNT - Processing...")
    
    try:
        # Cancel all orders
        orders = bybit_client.get_open_orders(category="linear")
        if orders and orders.get("result", {}).get("list"):
            order_list = orders["result"]["list"]
            print(f"Found {len(order_list)} open orders")
            for order in order_list:
                try:
                    result = bybit_client.cancel_order(
                        category="linear",
                        symbol=order["symbol"],
                        orderId=order["orderId"]
                    )
                    print(f"  ✅ Cancelled {order['symbol']} order")
                except Exception as e:
                    print(f"  ❌ Failed to cancel {order['symbol']} order: {e}")
        else:
            print("  No open orders found")
            
        # Close all positions
        positions = bybit_client.get_position_info(category="linear")
        if positions and positions.get("result", {}).get("list"):
            position_list = positions["result"]["list"]
            active_positions = [p for p in position_list if float(p.get("size", 0)) > 0]
            
            if active_positions:
                print(f"Found {len(active_positions)} open positions")
                for pos in active_positions:
                    try:
                        symbol = pos["symbol"]
                        side = pos["side"]
                        size = pos["size"]
                        
                        # Close with market order
                        close_side = "Sell" if side == "Buy" else "Buy"
                        result = bybit_client.place_order(
                            category="linear",
                            symbol=symbol,
                            side=close_side,
                            orderType="Market",
                            qty=str(size),
                            reduceOnly=True
                        )
                        print(f"  ✅ Closed {symbol} {side} position: {size}")
                    except Exception as e:
                        print(f"  ❌ Failed to close {symbol}: {e}")
            else:
                print("  No open positions found")
        else:
            print("  No positions data")
            
    except Exception as e:
        print(f"  ❌ Error processing main account: {e}")

async def close_all_mirror():
    """Close all positions and orders on mirror account"""
    if not ENABLE_MIRROR_TRADING:
        return
        
    print("\n📌 MIRROR ACCOUNT - Processing...")
    
    try:
        from clients.bybit_client import initialize_mirror_client
        mirror_client = initialize_mirror_client()
        
        if not mirror_client:
            print("  ❌ Mirror client not available")
            return
            
        # Cancel all orders
        orders = mirror_client.get_open_orders(category="linear")
        if orders and orders.get("result", {}).get("list"):
            order_list = orders["result"]["list"]
            print(f"Found {len(order_list)} open orders")
            for order in order_list:
                try:
                    result = mirror_client.cancel_order(
                        category="linear",
                        symbol=order["symbol"],
                        orderId=order["orderId"]
                    )
                    print(f"  ✅ Cancelled {order['symbol']} order")
                except Exception as e:
                    print(f"  ❌ Failed to cancel {order['symbol']} order: {e}")
        else:
            print("  No open orders found")
            
        # Close all positions
        positions = mirror_client.get_position_info(category="linear")
        if positions and positions.get("result", {}).get("list"):
            position_list = positions["result"]["list"]
            active_positions = [p for p in position_list if float(p.get("size", 0)) > 0]
            
            if active_positions:
                print(f"Found {len(active_positions)} open positions")
                for pos in active_positions:
                    try:
                        symbol = pos["symbol"]
                        side = pos["side"]
                        size = pos["size"]
                        
                        # Close with market order
                        close_side = "Sell" if side == "Buy" else "Buy"
                        result = mirror_client.place_order(
                            category="linear",
                            symbol=symbol,
                            side=close_side,
                            orderType="Market",
                            qty=str(size),
                            reduceOnly=True
                        )
                        print(f"  ✅ Closed {symbol} {side} position: {size}")
                    except Exception as e:
                        print(f"  ❌ Failed to close {symbol}: {e}")
            else:
                print("  No open positions found")
        else:
            print("  No positions data")
            
    except Exception as e:
        print(f"  ❌ Error processing mirror account: {e}")

async def main():
    """Main execution"""
    print("🧹 CLOSING ALL POSITIONS AND ORDERS")
    print("=" * 60)
    
    await close_all_main()
    await close_all_mirror()
    
    print("\n" + "=" * 60)
    print("✅ COMPLETE!")
    print("=" * 60)
    print("\n📌 Bot memory has already been wiped")
    print("📌 Restart the bot with: python3 main.py")

if __name__ == "__main__":
    asyncio.run(main())