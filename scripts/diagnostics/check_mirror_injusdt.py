#!/usr/bin/env python3
"""
Check INJUSDT position and orders on mirror account.
"""

import asyncio
import os
from dotenv import load_dotenv
from pybit.unified_trading import HTTP
from tabulate import tabulate
from decimal import Decimal

# Load environment variables
load_dotenv()

async def check_mirror_injusdt():
    """Check INJUSDT position and orders on mirror account."""
    
    # Check if mirror trading is enabled
    api_key_2 = os.getenv('BYBIT_API_KEY_2')
    api_secret_2 = os.getenv('BYBIT_API_SECRET_2')
    
    if not api_key_2 or not api_secret_2:
        print("❌ Mirror trading is NOT enabled (BYBIT_API_KEY_2 or BYBIT_API_SECRET_2 not set)")
        return
    
    print("✅ Mirror trading is ENABLED")
    print("=" * 80)
    
    # Initialize mirror client
    testnet = os.getenv('USE_TESTNET', 'false').lower() == 'true'
    session = HTTP(
        testnet=testnet,
        api_key=api_key_2,
        api_secret=api_secret_2
    )
    
    symbol = "INJUSDT"
    
    # Get position info
    print(f"\n📊 MIRROR ACCOUNT - {symbol} POSITION:")
    print("-" * 60)
    
    try:
        response = session.get_positions(category="linear", symbol=symbol)
        if response['retCode'] == 0 and response['result']['list']:
            position = response['result']['list'][0]
            
            # Position details
            side = position.get('side', 'N/A')
            size = float(position.get('size', 0) or 0)
            avg_price = float(position.get('avgPrice', 0) or 0)
            unrealized_pnl = float(position.get('unrealisedPnl', 0) or 0)  # Note: British spelling
            mark_price = float(position.get('markPrice', 0) or 0)
            
            print(f"Side: {side}")
            print(f"Size: {size}")
            print(f"Avg Price: ${avg_price:.4f}")
            print(f"Mark Price: ${mark_price:.4f}")
            print(f"Unrealized P&L: ${unrealized_pnl:.2f}")
            
            # Calculate P&L percentage
            if avg_price > 0:
                if side == "Buy":
                    pnl_pct = ((mark_price - avg_price) / avg_price) * 100
                else:
                    pnl_pct = ((avg_price - mark_price) / avg_price) * 100
                print(f"P&L %: {pnl_pct:.2f}%")
        else:
            print("No position found")
            size = 0
    except Exception as e:
        print(f"Error fetching position: {e}")
        size = 0
    
    # Get open orders
    print(f"\n📋 MIRROR ACCOUNT - {symbol} OPEN ORDERS:")
    print("-" * 60)
    
    try:
        response = session.get_open_orders(category="linear", symbol=symbol)
        if response['retCode'] == 0 and response['result']['list']:
            orders = response['result']['list']
            
            # Separate TP and SL orders
            tp_orders = []
            sl_orders = []
            other_orders = []
            
            for order in orders:
                order_type = order.get('orderType', '')
                order_side = order['side']
                qty = float(order['qty'])
                price = float(order['price']) if order['price'] else 0
                order_link_id = order.get('orderLinkId', '')
                order_id = order['orderId']
                
                order_info = {
                    'Order ID': order_id[:8] + '...',
                    'Type': order_type,
                    'Side': order_side,
                    'Qty': qty,
                    'Price': f"${price:.4f}" if price else "Market",
                    'LinkID': order_link_id[:20] + '...' if len(order_link_id) > 20 else order_link_id
                }
                
                if 'tp' in order_type.lower() or 'take' in order_type.lower():
                    tp_orders.append(order_info)
                elif 'sl' in order_type.lower() or 'stop' in order_type.lower():
                    sl_orders.append(order_info)
                else:
                    other_orders.append(order_info)
            
            # Display TP orders
            if tp_orders:
                print("\n🎯 Take Profit Orders:")
                print(tabulate(tp_orders, headers="keys", tablefmt="grid"))
                
                # Check Conservative approach distribution
                if len(tp_orders) >= 4 and size > 0:
                    print("\n📊 Conservative Approach Analysis:")
                    expected_percentages = [85, 5, 5, 5]
                    actual_percentages = []
                    
                    for i, order in enumerate(tp_orders[:4]):
                        qty = float(order['Qty'])
                        pct = (qty / size) * 100
                        actual_percentages.append(pct)
                        expected = expected_percentages[i] if i < len(expected_percentages) else 0
                        status = "✅" if abs(pct - expected) < 1 else "⚠️"
                        print(f"  TP{i+1}: {pct:.1f}% (expected {expected}%) {status}")
                    
                    # Check if it matches Conservative approach
                    matches_conservative = all(
                        abs(actual - expected) < 1 
                        for actual, expected in zip(actual_percentages[:4], expected_percentages)
                    )
                    
                    if matches_conservative:
                        print("\n✅ Orders match Conservative approach distribution!")
                    else:
                        print("\n⚠️ Orders DO NOT match Conservative approach distribution!")
                else:
                    print(f"\n⚠️ Found {len(tp_orders)} TP orders - Conservative approach expects 4")
            
            # Display SL orders
            if sl_orders:
                print("\n🛡️ Stop Loss Orders:")
                print(tabulate(sl_orders, headers="keys", tablefmt="grid"))
                
                if len(sl_orders) == 1 and size > 0:
                    sl_qty = float(sl_orders[0]['Qty'])
                    sl_pct = (sl_qty / size) * 100
                    print(f"\nSL covers {sl_pct:.1f}% of position")
                    if abs(sl_pct - 100) < 1:
                        print("✅ SL covers full position")
                    else:
                        print("⚠️ SL does NOT cover full position")
            
            # Display other orders
            if other_orders:
                print("\n📝 Other Orders:")
                print(tabulate(other_orders, headers="keys", tablefmt="grid"))
            
            # Summary
            print(f"\n📊 Order Summary:")
            print(f"  Total Orders: {len(orders)}")
            print(f"  TP Orders: {len(tp_orders)}")
            print(f"  SL Orders: {len(sl_orders)}")
            print(f"  Other Orders: {len(other_orders)}")
            
        else:
            print("No open orders found")
    except Exception as e:
        print(f"Error fetching orders: {e}")

if __name__ == "__main__":
    asyncio.run(check_mirror_injusdt())