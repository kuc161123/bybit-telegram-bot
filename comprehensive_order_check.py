#!/usr/bin/env python3
"""
Comprehensive check of ALL orders on Bybit - including all states and types
"""

import asyncio
import sys
import os
from decimal import Decimal
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pybit.unified_trading import HTTP
from config.settings import BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2

async def comprehensive_order_check(account="main"):
    """Check ALL orders including different states and types"""
    
    try:
        # Create Bybit client
        if account == "main":
            api_key = BYBIT_API_KEY
            api_secret = BYBIT_API_SECRET
        else:
            api_key = BYBIT_API_KEY_2
            api_secret = BYBIT_API_SECRET_2
            
        if USE_TESTNET:
            client = HTTP(
                testnet=True,
                api_key=api_key,
                api_secret=api_secret
            )
        else:
            client = HTTP(
                testnet=False,
                api_key=api_key,
                api_secret=api_secret
            )
        
        print(f"\n{'=' * 80}")
        print(f"{account.upper()} ACCOUNT - COMPREHENSIVE ORDER CHECK")
        print("=" * 80)
        
        # Get active positions first
        print("\n📊 Active Positions:")
        try:
            response = client.get_positions(category="linear", settleCoin="USDT")
            positions = response.get('result', {}).get('list', [])
            
            active_positions = {}
            for pos in positions:
                if float(pos.get('size', 0)) > 0:
                    symbol = pos.get('symbol')
                    side = pos.get('side')
                    size = pos.get('size')
                    active_positions[symbol] = {
                        'side': side,
                        'size': size,
                        'avgPrice': pos.get('avgPrice'),
                        'tp_orders': [],
                        'sl_orders': [],
                        'limit_orders': []
                    }
                    print(f"  {symbol} {side}: {size}")
                    
        except Exception as e:
            print(f"Error fetching positions: {e}")
            active_positions = {}
        
        # Method 1: Get ALL open orders (no filter)
        print("\n📋 Checking ALL Open Orders (Method 1):")
        try:
            response = client.get_open_orders(category="linear")
            orders = response.get('result', {}).get('list', [])
            print(f"  Found {len(orders)} orders")
            
            # Categorize these orders
            for order in orders:
                symbol = order.get('symbol')
                if symbol in active_positions:
                    order_type = order.get('orderType', '')
                    reduce_only = order.get('reduceOnly', False)
                    trigger_price = order.get('triggerPrice', '0')
                    
                    if trigger_price != '0' and trigger_price != '':
                        # This is a conditional order (SL or TP with trigger)
                        active_positions[symbol]['sl_orders'].append(order)
                    elif reduce_only:
                        # This is a TP order
                        active_positions[symbol]['tp_orders'].append(order)
                    else:
                        # This is a limit entry order
                        active_positions[symbol]['limit_orders'].append(order)
                        
        except Exception as e:
            print(f"  Error: {e}")
        
        # Method 2: Check Stop Orders specifically
        print("\n🛑 Checking Stop Orders (Method 2):")
        try:
            response = client.get_open_orders(category="linear", orderFilter="StopOrder")
            orders = response.get('result', {}).get('list', [])
            print(f"  Found {len(orders)} stop orders")
            
            # These are definitely stop orders
            for order in orders:
                symbol = order.get('symbol')
                if symbol in active_positions:
                    # Check if we already have this order
                    order_id = order.get('orderId')
                    existing_ids = [o.get('orderId') for o in active_positions[symbol]['sl_orders']]
                    if order_id not in existing_ids:
                        active_positions[symbol]['sl_orders'].append(order)
                        
        except Exception as e:
            print(f"  Error: {e}")
        
        # Method 3: Check each position's orders individually
        print("\n🔍 Checking Orders by Position (Method 3):")
        for symbol in active_positions.keys():
            try:
                response = client.get_open_orders(category="linear", symbol=symbol)
                orders = response.get('result', {}).get('list', [])
                if orders:
                    print(f"  {symbol}: Found {len(orders)} orders")
            except Exception as e:
                print(f"  {symbol}: Error - {e}")
        
        # Now analyze and display results
        print("\n" + "=" * 80)
        print("DETAILED POSITION ANALYSIS")
        print("=" * 80)
        
        for symbol, pos_data in sorted(active_positions.items()):
            print(f"\n{symbol} {pos_data['side']}: {pos_data['size']} @ avg {pos_data['avgPrice']}")
            
            # Analyze TP orders
            tp_orders = pos_data['tp_orders']
            print(f"\n  📈 Take Profit Orders ({len(tp_orders)}):")
            total_tp_qty = Decimal('0')
            if tp_orders:
                for order in tp_orders:
                    qty = order.get('qty', '0')
                    price = order.get('price', '0')
                    order_type = order.get('orderType', '')
                    link_id = order.get('orderLinkId', '')
                    total_tp_qty += Decimal(qty)
                    print(f"     - {qty} @ {price} ({order_type}) [{link_id}]")
                print(f"     Total TP Coverage: {total_tp_qty} ({float(total_tp_qty)/float(pos_data['size'])*100:.1f}%)")
            else:
                print("     None found")
            
            # Analyze SL orders
            sl_orders = pos_data['sl_orders']
            print(f"\n  🛑 Stop Loss Orders ({len(sl_orders)}):")
            total_sl_qty = Decimal('0')
            if sl_orders:
                for order in sl_orders:
                    qty = order.get('qty', '0')
                    trigger_price = order.get('triggerPrice', '0')
                    order_type = order.get('orderType', '')
                    link_id = order.get('orderLinkId', '')
                    total_sl_qty += Decimal(qty)
                    print(f"     - {qty} @ trigger {trigger_price} ({order_type}) [{link_id}]")
                print(f"     Total SL Coverage: {total_sl_qty} ({float(total_sl_qty)/float(pos_data['size'])*100:.1f}%)")
            else:
                print("     None found")
            
            # Analyze limit orders
            limit_orders = pos_data['limit_orders']
            if limit_orders:
                print(f"\n  📥 Limit Entry Orders ({len(limit_orders)}):")
                for order in limit_orders:
                    side = order.get('side', '')
                    qty = order.get('qty', '0')
                    price = order.get('price', '0')
                    link_id = order.get('orderLinkId', '')
                    print(f"     - {side} {qty} @ {price} [{link_id}]")
            
            # Summary
            print(f"\n  📊 Summary:")
            if tp_orders and sl_orders:
                print(f"     ✅ Position protected with TP and SL")
            elif sl_orders and not tp_orders:
                print(f"     ⚠️  Has SL but missing TP orders")
            elif tp_orders and not sl_orders:
                print(f"     ⚠️  Has TP but missing SL order")
            else:
                print(f"     ❌ NO PROTECTION - Missing both TP and SL")
        
        # Final summary
        print("\n" + "=" * 80)
        print("ACCOUNT SUMMARY")
        print("=" * 80)
        
        fully_protected = 0
        sl_only = 0
        tp_only = 0
        unprotected = 0
        
        for symbol, pos_data in active_positions.items():
            has_tp = len(pos_data['tp_orders']) > 0
            has_sl = len(pos_data['sl_orders']) > 0
            
            if has_tp and has_sl:
                fully_protected += 1
            elif has_sl and not has_tp:
                sl_only += 1
            elif has_tp and not has_sl:
                tp_only += 1
            else:
                unprotected += 1
        
        print(f"\n✅ Fully Protected: {fully_protected}")
        print(f"⚠️  SL Only: {sl_only}")
        print(f"⚠️  TP Only: {tp_only}")
        print(f"❌ Unprotected: {unprotected}")
        print(f"📊 Total Positions: {len(active_positions)}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

async def main():
    print("🔍 Running Comprehensive Order Check...")
    
    # Check main account
    await comprehensive_order_check("main")
    
    # Check mirror account if enabled
    if BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
        await comprehensive_order_check("mirror")
    else:
        print("\n⚠️  Mirror account not configured")

if __name__ == "__main__":
    asyncio.run(main())