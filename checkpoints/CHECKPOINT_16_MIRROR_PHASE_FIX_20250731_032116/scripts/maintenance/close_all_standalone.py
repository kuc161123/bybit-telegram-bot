#!/usr/bin/env python3
"""
Standalone script to close all positions and orders without dependencies
"""

import os
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def close_all_positions_and_orders():
    """Close all positions and orders on both accounts"""
    
    print("\n🧹 CLOSING ALL POSITIONS AND ORDERS")
    print("=" * 60)
    
    # Main account
    try:
        print("\n📌 MAIN ACCOUNT:")
        
        # Initialize client
        client = HTTP(
            testnet=False,
            api_key=os.getenv('BYBIT_API_KEY'),
            api_secret=os.getenv('BYBIT_API_SECRET')
        )
        
        # Get positions
        positions = client.get_positions(
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
                        result = client.place_order(
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
        orders = client.get_open_orders(
            category="linear",
            settleCoin="USDT"
        )
        
        if orders and orders.get('retCode') == 0:
            open_orders = orders['result']['list']
            if open_orders:
                print(f"\nFound {len(open_orders)} open orders:")
                for order in open_orders:
                    try:
                        result = client.cancel_order(
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
    if os.getenv('ENABLE_MIRROR_TRADING') == 'true' and os.getenv('BYBIT_API_KEY_2') and os.getenv('BYBIT_API_SECRET_2'):
        try:
            print("\n📌 MIRROR ACCOUNT:")
            mirror_client = HTTP(
                testnet=False,
                api_key=os.getenv('BYBIT_API_KEY_2'),
                api_secret=os.getenv('BYBIT_API_SECRET_2')
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
    else:
        print("\n📌 MIRROR ACCOUNT: Not configured or disabled")
    
    print("\n" + "=" * 60)
    print("✅ COMPLETE!")

if __name__ == "__main__":
    close_all_positions_and_orders()