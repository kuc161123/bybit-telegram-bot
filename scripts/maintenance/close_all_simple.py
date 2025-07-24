#!/usr/bin/env python3
"""
Simple script to close all positions and orders
"""

import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_client import bybit_client
from config.settings import ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2

async def close_all():
    """Close all positions and orders"""
    print("\n🧹 CLOSING ALL POSITIONS AND ORDERS")
    print("=" * 60)
    
    # Main account
    try:
        print("\n📌 MAIN ACCOUNT:")
        
        # Get positions
        positions = bybit_client.get_positions(
            category="linear",
            settleCoin="USDT"
        )
        
        if positions and positions.get('retCode') == 0:
            active_positions = [p for p in positions['result']['list'] if float(p.get('size', 0)) > 0]
            
            if active_positions:
                print(f"Found {len(active_positions)} active positions:")
                for pos in active_positions:
                    symbol = pos['symbol']
                    side = pos['side']
                    size = pos['size']
                    print(f"  - {symbol} {side}: {size}")
                    
                    # Close position
                    try:
                        close_side = "Sell" if side == "Buy" else "Buy"
                        result = bybit_client.place_order(
                            category="linear",
                            symbol=symbol,
                            side=close_side,
                            orderType="Market",
                            qty=str(size),
                            reduceOnly=True
                        )
                        if result.get('retCode') == 0:
                            print(f"    ✅ Closed {symbol}")
                        else:
                            print(f"    ❌ Failed: {result.get('retMsg')}")
                    except Exception as e:
                        print(f"    ❌ Error: {e}")
            else:
                print("  ✅ No active positions")
        
        # Cancel orders
        orders = bybit_client.get_open_orders(
            category="linear",
            settleCoin="USDT"
        )
        
        if orders and orders.get('retCode') == 0:
            open_orders = orders['result']['list']
            if open_orders:
                print(f"\nFound {len(open_orders)} open orders:")
                for order in open_orders:
                    try:
                        result = bybit_client.cancel_order(
                            category="linear",
                            symbol=order['symbol'],
                            orderId=order['orderId']
                        )
                        if result.get('retCode') == 0:
                            print(f"  ✅ Cancelled {order['symbol']} order")
                        else:
                            print(f"  ❌ Failed: {result.get('retMsg')}")
                    except Exception as e:
                        print(f"  ❌ Error: {e}")
            else:
                print("  ✅ No open orders")
                
    except Exception as e:
        print(f"  ❌ Error with main account: {e}")
    
    # Mirror account
    if ENABLE_MIRROR_TRADING and BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
        try:
            print("\n📌 MIRROR ACCOUNT:")
            from pybit.unified_trading import HTTP
            mirror_client = HTTP(
                testnet=False,
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2
            )
            
            # Get positions
            positions = mirror_client.get_positions(
                category="linear",
                settleCoin="USDT"
            )
            
            if positions and positions.get('retCode') == 0:
                active_positions = [p for p in positions['result']['list'] if float(p.get('size', 0)) > 0]
                
                if active_positions:
                    print(f"Found {len(active_positions)} active positions:")
                    for pos in active_positions:
                        symbol = pos['symbol']
                        side = pos['side']
                        size = pos['size']
                        print(f"  - {symbol} {side}: {size}")
                        
                        # Close position
                        try:
                            close_side = "Sell" if side == "Buy" else "Buy"
                            result = mirror_client.place_order(
                                category="linear",
                                symbol=symbol,
                                side=close_side,
                                orderType="Market",
                                qty=str(size),
                                reduceOnly=True
                            )
                            if result.get('retCode') == 0:
                                print(f"    ✅ Closed {symbol}")
                            else:
                                print(f"    ❌ Failed: {result.get('retMsg')}")
                        except Exception as e:
                            print(f"    ❌ Error: {e}")
                else:
                    print("  ✅ No active positions")
            
            # Cancel orders
            orders = mirror_client.get_open_orders(
                category="linear",
                settleCoin="USDT"
            )
            
            if orders and orders.get('retCode') == 0:
                open_orders = orders['result']['list']
                if open_orders:
                    print(f"\nFound {len(open_orders)} open orders:")
                    for order in open_orders:
                        try:
                            result = mirror_client.cancel_order(
                                category="linear",
                                symbol=order['symbol'],
                                orderId=order['orderId']
                            )
                            if result.get('retCode') == 0:
                                print(f"  ✅ Cancelled {order['symbol']} order")
                            else:
                                print(f"  ❌ Failed: {result.get('retMsg')}")
                        except Exception as e:
                            print(f"  ❌ Error: {e}")
                else:
                    print("  ✅ No open orders")
                    
        except Exception as e:
            print(f"  ❌ Error with mirror account: {e}")
    
    print("\n" + "=" * 60)
    print("✅ COMPLETE!")

if __name__ == "__main__":
    asyncio.run(close_all())