#!/usr/bin/env python3
"""
Simple script to show all unique stopOrderType values and orderLinkId patterns
"""

import os
import sys
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_client import bybit_client
from config.settings import USE_TESTNET

def main():
    """Show all unique order types and patterns"""
    print(f"\nAnalyzing Bybit Order Types on {'TESTNET' if USE_TESTNET else 'MAINNET'}")
    print("=" * 60)
    
    # Get all open orders
    response = bybit_client.get_open_orders(
        category="linear",
        settleCoin="USDT",
        limit=200
    )
    
    if response.get("retCode") != 0:
        print(f"Error: {response.get('retMsg')}")
        return
        
    orders = response.get("result", {}).get("list", [])
    print(f"\nTotal orders found: {len(orders)}")
    
    # Collect unique values
    stop_order_types = set()
    order_types = set()
    trigger_directions = set()
    order_patterns = defaultdict(list)
    
    for order in orders:
        # Collect unique stopOrderType values
        stop_type = order.get("stopOrderType", "EMPTY")
        stop_order_types.add(stop_type)
        
        # Collect orderType values
        order_type = order.get("orderType", "EMPTY")
        order_types.add(order_type)
        
        # Collect triggerDirection values
        trigger_dir = order.get("triggerDirection", "EMPTY")
        trigger_directions.add(trigger_dir)
        
        # Analyze orderLinkId patterns
        order_link_id = order.get("orderLinkId", "")
        if order_link_id:
            # Categorize by suffix
            if "_TP" in order_link_id:
                key = "Take Profit Orders"
            elif "_SL" in order_link_id:
                key = "Stop Loss Orders"
            elif "_LIMIT" in order_link_id:
                key = "Limit Orders"
            else:
                key = "Other Orders"
                
            order_patterns[key].append({
                'orderLinkId': order_link_id,
                'stopOrderType': stop_type,
                'orderType': order_type,
                'triggerDirection': trigger_dir,
                'triggerPrice': order.get('triggerPrice', 'None'),
                'reduceOnly': order.get('reduceOnly', False),
                'symbol': order.get('symbol', 'Unknown')
            })
    
    # Display results
    print("\n" + "=" * 60)
    print("UNIQUE stopOrderType VALUES:")
    print("=" * 60)
    for stop_type in sorted(stop_order_types):
        if stop_type == "":
            print("  - '' (empty string)")
        else:
            print(f"  - '{stop_type}'")
    
    print("\n" + "=" * 60)
    print("UNIQUE orderType VALUES:")
    print("=" * 60)
    for order_type in sorted(order_types):
        print(f"  - '{order_type}'")
    
    print("\n" + "=" * 60)
    print("UNIQUE triggerDirection VALUES:")
    print("=" * 60)
    for trigger_dir in sorted(trigger_directions):
        print(f"  - {trigger_dir}")
    
    print("\n" + "=" * 60)
    print("ORDER PATTERNS BY TYPE:")
    print("=" * 60)
    
    for pattern_type, orders_list in order_patterns.items():
        print(f"\n{pattern_type} ({len(orders_list)} orders):")
        print("-" * 40)
        
        # Show first example of each type
        if orders_list:
            example = orders_list[0]
            print(f"  Example: {example['symbol']}")
            print(f"  - orderLinkId: {example['orderLinkId']}")
            print(f"  - stopOrderType: '{example['stopOrderType']}'")
            print(f"  - orderType: '{example['orderType']}'")
            print(f"  - triggerDirection: {example['triggerDirection']}")
            print(f"  - triggerPrice: {example['triggerPrice']}")
            print(f"  - reduceOnly: {example['reduceOnly']}")
    
    # Summary of how to identify TP/SL
    print("\n" + "=" * 60)
    print("SUMMARY: How Bybit Identifies TP/SL Orders")
    print("=" * 60)
    print("1. stopOrderType = 'Stop' for BOTH TP and SL")
    print("2. triggerDirection = 1 for TP (price rises)")
    print("3. triggerDirection = 2 for SL (price falls)")
    print("4. orderType = 'Market' for triggered orders")
    print("5. reduceOnly = True for closing positions")
    print("6. Bot uses orderLinkId suffixes (_TP, _SL) for identification")

if __name__ == "__main__":
    main()