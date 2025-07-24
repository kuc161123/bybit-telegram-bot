#!/usr/bin/env python3
"""
Clean up excessive stop orders on mirror account to stay within Bybit limits.
Focus on symbols that have way more than 10 orders.
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


async def clean_excessive_orders():
    """Clean up excessive stop orders."""
    
    print("🧹 Cleaning Excessive Stop Orders on Mirror Account")
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
    
    # Symbols that need cleaning based on previous check
    problem_symbols = {
        'CYBERUSDT': 20,  # Has 20 orders!
        'MEWUSDT': 15,    # Has 15 orders
        'GRTUSDT': 10,    # At limit
        'TONUSDT': 10     # At limit
    }
    
    print(f"\n🎯 Target symbols for cleanup:")
    for symbol, count in problem_symbols.items():
        print(f"  - {symbol}: {count} orders")
    
    total_cancelled = 0
    
    for symbol, current_count in problem_symbols.items():
        print(f"\n\n📍 Processing {symbol} ({current_count} orders)...")
        print("-" * 40)
        
        try:
            # Get all orders for this symbol
            response = mirror_client.get_open_orders(
                category="linear",
                symbol=symbol,
                openOnly=1,
                limit=50
            )
            
            if response['retCode'] != 0:
                print(f"❌ Error fetching orders: {response['retMsg']}")
                continue
            
            orders = response['result']['list']
            stop_orders = [o for o in orders if o.get('stopOrderType') == 'Stop']
            
            print(f"Found {len(stop_orders)} stop orders")
            
            if len(stop_orders) <= 8:
                print("✅ Already within safe limits (<= 8 orders)")
                continue
            
            # Group by type and position
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
            
            # Strategy: Keep newest SL and some TPs, cancel old ones
            # Sort by creation time (newest first)
            tp_orders.sort(key=lambda x: x.get('createdTime', ''), reverse=True)
            sl_orders.sort(key=lambda x: x.get('createdTime', ''), reverse=True)
            
            # Keep configuration
            keep_sl = 1  # Keep 1 SL per position
            keep_tp = 4  # Keep 4 TPs per position
            
            # Determine what to cancel
            cancel_list = []
            
            # Keep newest SLs, cancel extras
            if len(sl_orders) > keep_sl:
                cancel_list.extend(sl_orders[keep_sl:])
                print(f"\n  Will cancel {len(sl_orders) - keep_sl} old SL orders")
            
            # Keep newest TPs, cancel extras
            if len(tp_orders) > keep_tp:
                cancel_list.extend(tp_orders[keep_tp:])
                print(f"  Will cancel {len(tp_orders) - keep_tp} old TP orders")
            
            # Cancel the orders
            if cancel_list:
                print(f"\n  Cancelling {len(cancel_list)} orders...")
                
                cancelled = 0
                for order in cancel_list:
                    try:
                        cancel_response = mirror_client.cancel_order(
                            category="linear",
                            symbol=symbol,
                            orderId=order['orderId']
                        )
                        
                        if cancel_response['retCode'] == 0:
                            print(f"    ✅ Cancelled {order['orderId'][:8]}...")
                            cancelled += 1
                        else:
                            print(f"    ❌ Failed {order['orderId'][:8]}: {cancel_response['retMsg']}")
                    
                    except Exception as e:
                        print(f"    ❌ Error cancelling order: {e}")
                
                print(f"\n  Summary: Cancelled {cancelled}/{len(cancel_list)} orders")
                total_cancelled += cancelled
            else:
                print("  ✅ No orders need cancellation")
            
        except Exception as e:
            print(f"❌ Error processing {symbol}: {e}")
    
    # Now try to add stop loss for ZILUSDT
    print(f"\n\n🛡️ Adding Stop Loss for ZILUSDT...")
    print("-" * 40)
    
    try:
        # Get ZILUSDT position
        pos_response = mirror_client.get_positions(
            category="linear",
            symbol="ZILUSDT"
        )
        
        if pos_response['retCode'] == 0:
            positions = [p for p in pos_response['result']['list'] if float(p['size']) > 0]
            
            for pos in positions:
                if pos['side'] == 'Buy':  # Long position
                    size = float(pos['size'])
                    position_idx = pos.get('positionIdx', 1)
                    
                    print(f"Adding SL for LONG {size:,.0f} units...")
                    
                    sl_response = mirror_client.place_order(
                        category="linear",
                        symbol="ZILUSDT",
                        side="Sell",
                        orderType="Market",
                        qty=str(size),
                        triggerPrice="0.01027",
                        triggerDirection=2,
                        triggerBy="LastPrice",
                        positionIdx=position_idx,
                        reduceOnly=True,
                        orderLinkId=f"BOT_CONS_SL_CLEAN_{datetime.now().strftime('%H%M%S')}"
                    )
                    
                    if sl_response['retCode'] == 0:
                        print(f"✅ Stop loss placed successfully!")
                    else:
                        print(f"❌ Failed: {sl_response['retMsg']}")
    
    except Exception as e:
        print(f"❌ Error adding SL: {e}")
    
    # Summary
    print(f"\n\n" + "=" * 60)
    print("📊 CLEANUP SUMMARY")
    print("=" * 60)
    print(f"\nTotal orders cancelled: {total_cancelled}")
    print("\n💡 Recommendations:")
    print("1. Monitor these positions closely")
    print("2. Consider reducing position count to stay within limits")
    print("3. The bot's rebalancer may need adjustment for high position counts")


async def main():
    """Main function."""
    await clean_excessive_orders()


if __name__ == "__main__":
    asyncio.run(main())