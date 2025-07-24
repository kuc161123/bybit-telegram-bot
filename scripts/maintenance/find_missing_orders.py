#!/usr/bin/env python3
"""
Find the missing 7 orders by checking all possible order sources.
"""

import os
import sys
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2
from config.settings import ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2


def find_all_orders(client, account_name):
    """Find ALL orders using different methods."""
    
    print(f"\n{'='*80}")
    print(f"{account_name} ACCOUNT - FINDING ALL ORDERS")
    print(f"{'='*80}")
    
    all_found_orders = set()  # Track unique order IDs
    order_details = {}
    
    try:
        # Method 1: Regular open orders
        print("\n1️⃣ Method 1: get_open_orders (settleCoin=USDT):")
        resp1 = client.get_open_orders(category="linear", settleCoin="USDT", limit=200)
        if resp1 and resp1.get('retCode') == 0:
            orders1 = resp1.get('result', {}).get('list', [])
            print(f"   Found: {len(orders1)} orders")
            for o in orders1:
                all_found_orders.add(o['orderId'])
                order_details[o['orderId']] = o
        
        # Method 2: Without settleCoin (might return more)
        print("\n2️⃣ Method 2: get_open_orders (no settleCoin):")
        try:
            resp2 = client.get_open_orders(category="linear", limit=200)
            if resp2 and resp2.get('retCode') == 0:
                orders2 = resp2.get('result', {}).get('list', [])
                new_orders = [o for o in orders2 if o['orderId'] not in all_found_orders]
                print(f"   Found: {len(orders2)} total, {len(new_orders)} new")
                for o in orders2:
                    all_found_orders.add(o['orderId'])
                    order_details[o['orderId']] = o
        except Exception as e:
            print(f"   Error: {e}")
        
        # Method 3: Check with orderFilter
        print("\n3️⃣ Method 3: get_open_orders with StopOrder filter:")
        try:
            resp3 = client.get_open_orders(category="linear", settleCoin="USDT", orderFilter="StopOrder", limit=200)
            if resp3 and resp3.get('retCode') == 0:
                orders3 = resp3.get('result', {}).get('list', [])
                new_orders = [o for o in orders3 if o['orderId'] not in all_found_orders]
                print(f"   Found: {len(orders3)} total, {len(new_orders)} new")
                for o in orders3:
                    all_found_orders.add(o['orderId'])
                    order_details[o['orderId']] = o
        except Exception as e:
            print(f"   Error: {e}")
        
        # Method 4: Check order history (recent orders)
        print("\n4️⃣ Method 4: get_order_history (last 200):")
        try:
            resp4 = client.get_order_history(category="linear", limit=200)
            if resp4 and resp4.get('retCode') == 0:
                orders4 = resp4.get('result', {}).get('list', [])
                # Only count active orders from history
                active_from_history = [o for o in orders4 if o.get('orderStatus') in ['New', 'PartiallyFilled', 'Untriggered']]
                new_orders = [o for o in active_from_history if o['orderId'] not in all_found_orders]
                print(f"   Found: {len(orders4)} in history, {len(active_from_history)} active, {len(new_orders)} new active")
                for o in active_from_history:
                    all_found_orders.add(o['orderId'])
                    order_details[o['orderId']] = o
        except Exception as e:
            print(f"   Error: {e}")
        
        # Method 5: Check by individual positions
        print("\n5️⃣ Method 5: Checking orders for each position:")
        pos_resp = client.get_positions(category="linear", settleCoin="USDT")
        if pos_resp and pos_resp.get('retCode') == 0:
            positions = [p for p in pos_resp.get('result', {}).get('list', []) if float(p.get('size', 0)) > 0]
            
            for pos in positions:
                symbol = pos['symbol']
                try:
                    # Get orders for this specific symbol
                    sym_resp = client.get_open_orders(category="linear", symbol=symbol, limit=50)
                    if sym_resp and sym_resp.get('retCode') == 0:
                        sym_orders = sym_resp.get('result', {}).get('list', [])
                        new_orders = [o for o in sym_orders if o['orderId'] not in all_found_orders]
                        if new_orders:
                            print(f"   {symbol}: Found {len(new_orders)} new orders")
                        for o in sym_orders:
                            all_found_orders.add(o['orderId'])
                            order_details[o['orderId']] = o
                except:
                    pass
        
        # Summary for this account
        print(f"\n📊 {account_name} Account Summary:")
        print(f"   Total unique orders found: {len(all_found_orders)}")
        
        # Analyze order types
        active_orders = []
        for order_id, order in order_details.items():
            if order.get('orderStatus') in ['New', 'PartiallyFilled', 'Untriggered']:
                active_orders.append(order)
        
        print(f"   Active orders: {len(active_orders)}")
        
        # Check for any non-USDT orders
        non_usdt = [o for o in active_orders if o.get('settleCoin') != 'USDT']
        if non_usdt:
            print(f"   ⚠️  Non-USDT orders found: {len(non_usdt)}")
            for o in non_usdt[:5]:  # Show first 5
                print(f"      {o['symbol']}: settleCoin={o.get('settleCoin')}")
        
        return len(active_orders), order_details
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 0, {}


def main():
    """Main function."""
    print("🔍 FINDING ALL ORDERS - COMPREHENSIVE SEARCH")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check main account
    main_count, main_orders = find_all_orders(bybit_client, "MAIN")
    
    # Check mirror account
    mirror_count = 0
    if ENABLE_MIRROR_TRADING and BYBIT_API_KEY_2 and BYBIT_API_SECRET_2 and bybit_client_2:
        mirror_count, mirror_orders = find_all_orders(bybit_client_2, "MIRROR")
    
    # Total summary
    print("\n" + "="*80)
    print("FINAL SUMMARY:")
    print(f"Main account: {main_count} active orders")
    print(f"Mirror account: {mirror_count} active orders")
    print(f"TOTAL: {main_count + mirror_count} active orders")
    
    if main_count + mirror_count != 107:
        print(f"\n⚠️  Discrepancy: Script found {main_count + mirror_count} but exchange shows 107")
        print(f"   Missing: {107 - (main_count + mirror_count)} orders")
        print("\nPossible explanations:")
        print("1. Exchange UI might be showing cancelled/filled orders")
        print("2. You might have orders in Spot market (not Derivatives)")
        print("3. Orders in other settlement coins (not USDT)")
        print("4. Orders placed through web/app that use different categorization")
        print("5. Pending orders that haven't been confirmed yet")


if __name__ == "__main__":
    main()