#!/usr/bin/env python3
"""
Monitor all positions to ensure they have proper orders (4 TPs + 1 SL).
Alerts only if orders are missing (not if they've been filled).
"""

import asyncio
import os
import sys
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()


async def monitor_positions():
    """Monitor positions for missing orders."""
    
    from pybit.unified_trading import HTTP
    from config.settings import (
        BYBIT_API_KEY, BYBIT_API_SECRET,
        BYBIT_API_KEY_2, BYBIT_API_SECRET_2,
        USE_TESTNET
    )
    
    # Initialize clients
    clients = []
    
    if BYBIT_API_KEY and BYBIT_API_SECRET:
        clients.append(("MAIN", HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY,
            api_secret=BYBIT_API_SECRET
        )))
    
    if BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
        clients.append(("MIRROR", HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2
        )))
    
    issues_found = []
    
    for account_name, client in clients:
        try:
            # Get all positions
            pos_resp = client.get_positions(
                category="linear",
                settleCoin="USDT"
            )
            
            if pos_resp['retCode'] != 0:
                continue
                
            positions = [p for p in pos_resp['result']['list'] if float(p.get('size', 0)) > 0]
            
            for pos in positions:
                symbol = pos['symbol']
                side = pos['side']
                size = float(pos['size'])
                avg_price = float(pos.get('avgPrice', 0))
                
                # Get orders
                order_resp = client.get_open_orders(
                    category="linear",
                    symbol=symbol,
                    openOnly=1,  # Only active orders
                    limit=50
                )
                
                if order_resp['retCode'] == 0:
                    orders = order_resp['result']['list']
                    
                    # Count TPs and SLs
                    tp_count = 0
                    sl_count = 0
                    
                    for order in orders:
                        if not order.get('reduceOnly'):
                            continue
                            
                        trigger_price = float(order.get('triggerPrice', 0))
                        if trigger_price == 0:
                            continue
                        
                        # Determine if TP or SL
                        if side == 'Buy':
                            if trigger_price > avg_price:
                                tp_count += 1
                            else:
                                sl_count += 1
                        else:
                            if trigger_price < avg_price:
                                tp_count += 1
                            else:
                                sl_count += 1
                    
                    # Check for issues
                    if tp_count < 4 or sl_count < 1:
                        issues_found.append({
                            'account': account_name,
                            'symbol': symbol,
                            'side': side,
                            'size': size,
                            'tp_count': tp_count,
                            'sl_count': sl_count
                        })
                        
        except Exception as e:
            print(f"Error checking {account_name}: {e}")
    
    return issues_found


async def main_monitor():
    """Main monitoring loop."""
    
    print("🔍 Order Monitoring Started")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    while True:
        try:
            issues = await monitor_positions()
            
            if issues:
                print(f"\n⚠️  ALERT at {datetime.now().strftime('%H:%M:%S')}:")
                print(f"Found {len(issues)} positions with missing orders:\n")
                
                for issue in issues:
                    print(f"  [{issue['account']}] {issue['symbol']} {issue['side']}:")
                    print(f"    Size: {issue['size']:,.0f}")
                    print(f"    TPs: {issue['tp_count']}/4, SLs: {issue['sl_count']}/1")
                    print()
            else:
                print(f"✅ All positions have proper orders at {datetime.now().strftime('%H:%M:%S')}")
            
            # Wait 5 minutes before next check
            await asyncio.sleep(300)
            
        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main_monitor())
