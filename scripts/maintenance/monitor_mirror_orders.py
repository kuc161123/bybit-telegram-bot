#!/usr/bin/env python3
"""
Simple background monitor to prevent order accumulation.
Run this separately to keep orders under control.
"""

import asyncio
import time
from datetime import datetime

async def monitor_orders():
    """Monitor and manage orders periodically."""
    
    from pybit.unified_trading import HTTP
    from config.settings import BYBIT_API_KEY_2, BYBIT_API_SECRET_2, USE_TESTNET
    
    if not BYBIT_API_KEY_2:
        return
    
    mirror_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY_2,
        api_secret=BYBIT_API_SECRET_2
    )
    
    while True:
        try:
            # Get positions
            response = mirror_client.get_positions(
                category="linear",
                settleCoin="USDT"
            )
            
            if response['retCode'] == 0:
                for pos in response['result']['list']:
                    if float(pos['size']) > 0:
                        symbol = pos['symbol']
                        
                        # Check orders
                        order_response = mirror_client.get_open_orders(
                            category="linear",
                            symbol=symbol,
                            openOnly=1
                        )
                        
                        if order_response['retCode'] == 0:
                            stop_orders = [o for o in order_response['result']['list'] 
                                         if o.get('stopOrderType') == 'Stop']
                            
                            if len(stop_orders) > 8:
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] {symbol} has {len(stop_orders)} orders - needs cleanup")
            
            # Check every 5 minutes
            await asyncio.sleep(300)
            
        except Exception as e:
            print(f"Monitor error: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    print("Starting order monitor...")
    asyncio.run(monitor_orders())
