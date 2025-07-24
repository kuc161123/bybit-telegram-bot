#!/usr/bin/env python3
"""
Background order protector - prevents order accumulation.
"""

import asyncio
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def protect_orders():
    """Protect against order accumulation."""
    
    from pybit.unified_trading import HTTP
    from config.settings import BYBIT_API_KEY_2, BYBIT_API_SECRET_2, USE_TESTNET
    from datetime import datetime
    
    if not BYBIT_API_KEY_2:
        return
    
    mirror_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY_2,
        api_secret=BYBIT_API_SECRET_2
    )
    
    max_orders = 6
    check_interval = 60  # seconds
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Order protector started")
    print(f"Will maintain max {max_orders} orders per symbol")
    print(f"Checking every {check_interval} seconds")
    
    while True:
        try:
            # Get all positions
            pos_response = mirror_client.get_positions(
                category="linear",
                settleCoin="USDT"
            )
            
            if pos_response['retCode'] == 0:
                active_symbols = []
                for pos in pos_response['result']['list']:
                    if float(pos['size']) > 0:
                        active_symbols.append(pos['symbol'])
                
                # Check each symbol
                for symbol in active_symbols:
                    try:
                        # Get orders
                        order_response = mirror_client.get_open_orders(
                            category="linear",
                            symbol=symbol,
                            openOnly=1
                        )
                        
                        if order_response['retCode'] == 0:
                            orders = order_response['result']['list']
                            stop_orders = [o for o in orders if o.get('stopOrderType') == 'Stop']
                            
                            if len(stop_orders) > max_orders:
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] {symbol} has {len(stop_orders)} orders, cleaning...")
                                
                                # Sort by creation time (keep newest)
                                stop_orders.sort(key=lambda x: x.get('createdTime', ''), reverse=True)
                                
                                # Cancel old ones
                                for order in stop_orders[max_orders:]:
                                    try:
                                        mirror_client.cancel_order(
                                            category="linear",
                                            symbol=symbol,
                                            orderId=order['orderId']
                                        )
                                    except:
                                        pass
                                
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] Cleaned {symbol}")
                    
                    except Exception as e:
                        pass
                    
                    await asyncio.sleep(0.1)  # Rate limit
            
            await asyncio.sleep(check_interval)
            
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    try:
        asyncio.run(protect_orders())
    except KeyboardInterrupt:
        print("\nOrder protector stopped")
