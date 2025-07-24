#!/usr/bin/env python3
"""
Clean up active orders on mirror account to reduce order accumulation.
Focuses on actually active orders only.
"""

import asyncio
import os
import sys
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()


async def cleanup_active_orders():
    """Clean up active orders on mirror account."""
    
    print("🧹 Cleaning Up Active Orders on Mirror Account")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    from pybit.unified_trading import HTTP
    from config.settings import BYBIT_API_KEY_2, BYBIT_API_SECRET_2, USE_TESTNET
    
    if not BYBIT_API_KEY_2 or not BYBIT_API_SECRET_2:
        print("❌ Mirror account not configured")
        return
    
    mirror_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY_2,
        api_secret=BYBIT_API_SECRET_2
    )
    
    # Step 1: Get all active positions
    print("\n📊 Step 1: Getting Active Positions")
    print("-" * 40)
    
    active_positions = {}
    pos_response = mirror_client.get_positions(
        category="linear",
        settleCoin="USDT"
    )
    
    if pos_response['retCode'] == 0:
        for pos in pos_response['result']['list']:
            if float(pos['size']) > 0:
                symbol = pos['symbol']
                active_positions[symbol] = pos
    
    print(f"Found {len(active_positions)} active positions")
    
    # Step 2: Check orders for each position
    print("\n\n📋 Step 2: Analyzing Orders by Position")
    print("-" * 40)
    
    total_cancelled = 0
    symbols_processed = 0
    
    for symbol, position in active_positions.items():
        symbols_processed += 1
        
        try:
            # Get orders for this symbol
            response = mirror_client.get_open_orders(
                category="linear",
                symbol=symbol,
                openOnly=1,
                limit=50
            )
            
            if response['retCode'] != 0:
                continue
            
            orders = response['result']['list']
            stop_orders = [o for o in orders if o.get('stopOrderType') == 'Stop']
            
            if len(stop_orders) <= 6:  # Skip if already within reasonable limits
                continue
            
            print(f"\n📍 {symbol}: {len(stop_orders)} stop orders (Position: {position['side']} {float(position['size']):,.0f})")
            
            # Categorize orders
            tp_orders = []
            sl_orders = []
            
            for order in stop_orders:
                link_id = order.get('orderLinkId', '')
                if 'SL' in link_id:
                    sl_orders.append(order)
                else:
                    tp_orders.append(order)
            
            print(f"  - {len(tp_orders)} TP orders")
            print(f"  - {len(sl_orders)} SL orders")
            
            # Keep the newest orders
            tp_orders.sort(key=lambda x: x.get('createdTime', ''), reverse=True)
            sl_orders.sort(key=lambda x: x.get('createdTime', ''), reverse=True)
            
            # Configuration: what to keep
            keep_sl = min(1, len(sl_orders))  # Keep 1 SL
            keep_tp = min(4, len(tp_orders))  # Keep up to 4 TPs
            
            # Cancel old orders
            cancel_list = []
            if len(sl_orders) > keep_sl:
                cancel_list.extend(sl_orders[keep_sl:])
            if len(tp_orders) > keep_tp:
                cancel_list.extend(tp_orders[keep_tp:])
            
            if cancel_list:
                print(f"  Cancelling {len(cancel_list)} old orders...")
                
                cancelled_this_symbol = 0
                for order in cancel_list:
                    try:
                        # Double check it's still active
                        check_response = mirror_client.get_open_orders(
                            category="linear",
                            symbol=symbol,
                            orderId=order['orderId']
                        )
                        
                        if check_response['retCode'] == 0 and check_response['result']['list']:
                            # Order still exists, cancel it
                            cancel_response = mirror_client.cancel_order(
                                category="linear",
                                symbol=symbol,
                                orderId=order['orderId']
                            )
                            
                            if cancel_response['retCode'] == 0:
                                cancelled_this_symbol += 1
                                if cancelled_this_symbol % 5 == 0:
                                    print(f"    Cancelled {cancelled_this_symbol} orders...")
                        
                    except Exception as e:
                        # Order probably already filled/cancelled
                        pass
                
                print(f"  ✅ Cancelled {cancelled_this_symbol} orders")
                total_cancelled += cancelled_this_symbol
                
            # Small delay between symbols
            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"  ❌ Error processing {symbol}: {e}")
    
    # Step 3: Try to add ZILUSDT stop loss
    print("\n\n🛡️ Step 3: Adding Stop Loss for ZILUSDT")
    print("-" * 40)
    
    if 'ZILUSDT' in active_positions:
        pos = active_positions['ZILUSDT']
        
        # Check current orders
        response = mirror_client.get_open_orders(
            category="linear",
            symbol="ZILUSDT",
            openOnly=1
        )
        
        if response['retCode'] == 0:
            orders = response['result']['list']
            stop_orders = [o for o in orders if o.get('stopOrderType') == 'Stop']
            
            # Check if SL exists
            has_sl = any('SL' in o.get('orderLinkId', '') for o in stop_orders)
            
            if not has_sl and len(stop_orders) < 10:
                print(f"Adding SL for {pos['side']} {float(pos['size']):,.0f} units...")
                
                try:
                    sl_response = mirror_client.place_order(
                        category="linear",
                        symbol="ZILUSDT",
                        side="Sell" if pos['side'] == 'Buy' else 'Buy',
                        orderType="Market",
                        qty=str(int(float(pos['size']))),
                        triggerPrice="0.01027",
                        triggerDirection=2 if pos['side'] == 'Buy' else 1,
                        triggerBy="LastPrice",
                        positionIdx=pos.get('positionIdx', 1),
                        reduceOnly=True,
                        orderLinkId=f"BOT_CONS_SL_CLEAN_{datetime.now().strftime('%H%M%S')}"
                    )
                    
                    if sl_response['retCode'] == 0:
                        print("✅ Stop loss added successfully!")
                    else:
                        print(f"❌ Failed: {sl_response['retMsg']}")
                        
                except Exception as e:
                    print(f"❌ Error: {e}")
            else:
                if has_sl:
                    print("✅ Stop loss already exists")
                else:
                    print(f"❌ Cannot add SL - {len(stop_orders)} orders exist")
    
    # Summary
    print("\n\n" + "=" * 60)
    print("📊 CLEANUP SUMMARY")
    print("=" * 60)
    
    print(f"\nPositions processed: {symbols_processed}")
    print(f"Orders cancelled: {total_cancelled}")
    
    print("\n✅ Cleanup complete!")
    print("\n💡 Next steps:")
    print("1. Monitor order counts regularly")
    print("2. Consider implementing automated order management")
    print("3. Reduce position count if hitting limits frequently")
    
    # Create a simple monitor that can run in background
    monitor_code = '''#!/usr/bin/env python3
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
'''
    
    with open('monitor_mirror_orders.py', 'w') as f:
        f.write(monitor_code)
    
    print("\n📝 Created monitor_mirror_orders.py for ongoing monitoring")


async def main():
    """Main function."""
    await cleanup_active_orders()


if __name__ == "__main__":
    asyncio.run(main())