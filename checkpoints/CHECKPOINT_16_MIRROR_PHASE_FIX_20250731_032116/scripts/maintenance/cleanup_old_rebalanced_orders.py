#!/usr/bin/env python3
"""
Clean up old rebalanced orders, keeping only the most recent ones.
"""

import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv
from pybit.unified_trading import HTTP
import re

# Load environment variables
load_dotenv()

def init_clients():
    """Initialize Bybit clients for both accounts."""
    # Main account
    main_client = HTTP(
        testnet=os.getenv('USE_TESTNET', 'false').lower() == 'true',
        api_key=os.getenv('BYBIT_API_KEY'),
        api_secret=os.getenv('BYBIT_API_SECRET')
    )
    
    # Mirror account
    mirror_client = HTTP(
        testnet=os.getenv('USE_TESTNET', 'false').lower() == 'true',
        api_key=os.getenv('BYBIT_API_KEY_2'),
        api_secret=os.getenv('BYBIT_API_SECRET_2')
    )
    
    return main_client, mirror_client

def identify_orders_to_cancel(orders):
    """Identify which orders should be cancelled based on patterns."""
    # Group orders by type (TP1, TP2, TP3, TP4, SL) and approach
    order_groups = {}
    limit_orders = []
    
    for order in orders:
        link_id = order.get('orderLinkId', '')
        
        # Skip if no link ID
        if not link_id:
            continue
            
        # Check if it's a LIMIT order (these should be cancelled)
        if 'LIMIT' in link_id and order.get('triggerPrice', '') == '':
            limit_orders.append(order)
            continue
        
        # Extract order type from link ID (TP1, TP2, TP3, TP4, SL)
        order_type = None
        if '_TP1_' in link_id:
            order_type = 'TP1'
        elif '_TP2_' in link_id:
            order_type = 'TP2'
        elif '_TP3_' in link_id:
            order_type = 'TP3'
        elif '_TP4_' in link_id:
            order_type = 'TP4'
        elif '_SL_' in link_id:
            order_type = 'SL'
        
        if order_type:
            if order_type not in order_groups:
                order_groups[order_type] = []
            order_groups[order_type].append(order)
    
    orders_to_cancel = []
    
    # For each order type, keep only the most recent one
    for order_type, group_orders in order_groups.items():
        if len(group_orders) > 1:
            # Sort by creation time (newest first)
            sorted_orders = sorted(group_orders, key=lambda x: int(x.get('createdTime', 0)), reverse=True)
            
            # Keep the newest, cancel the rest
            orders_to_cancel.extend(sorted_orders[1:])
            
            print(f"\n{order_type} orders found: {len(group_orders)}")
            print(f"  Keeping: {sorted_orders[0]['orderLinkId']} (newest)")
            for old_order in sorted_orders[1:]:
                print(f"  Will cancel: {old_order['orderLinkId']} (older)")
    
    # Add all LIMIT orders to cancel list
    if limit_orders:
        print(f"\nLIMIT orders to cancel: {len(limit_orders)}")
        for order in limit_orders:
            print(f"  Will cancel: {order['orderLinkId']}")
        orders_to_cancel.extend(limit_orders)
    
    return orders_to_cancel

def cleanup_orders_for_symbol(client, symbol, account_name, dry_run=True):
    """Clean up old rebalanced orders for a specific symbol."""
    try:
        # Get all open orders
        response = client.get_open_orders(
            category="linear",
            symbol=symbol,
            limit=50
        )
        
        if response['retCode'] != 0:
            print(f"\nError getting orders for {symbol} on {account_name}: {response.get('retMsg', 'Unknown error')}")
            return
        
        orders = response['result']['list']
        if not orders:
            print(f"\n{account_name} - {symbol}: No open orders found")
            return
            
        print(f"\n{'='*80}")
        print(f"{account_name} - {symbol}: Analyzing {len(orders)} open orders")
        print(f"{'='*80}")
        
        # Identify orders to cancel
        orders_to_cancel = identify_orders_to_cancel(orders)
        
        if not orders_to_cancel:
            print("No duplicate or LIMIT orders found to cancel")
            return
        
        print(f"\nTotal orders to cancel: {len(orders_to_cancel)}")
        
        if dry_run:
            print("\nDRY RUN MODE - No orders will be cancelled")
            print("Run with --execute flag to actually cancel orders")
        else:
            print("\nCancelling orders...")
            cancelled_count = 0
            failed_count = 0
            
            for order in orders_to_cancel:
                try:
                    cancel_response = client.cancel_order(
                        category="linear",
                        symbol=symbol,
                        orderId=order['orderId']
                    )
                    
                    if cancel_response['retCode'] == 0:
                        print(f"  ✓ Cancelled: {order['orderLinkId']}")
                        cancelled_count += 1
                    else:
                        print(f"  ✗ Failed to cancel {order['orderLinkId']}: {cancel_response.get('retMsg', 'Unknown error')}")
                        failed_count += 1
                        
                except Exception as e:
                    print(f"  ✗ Exception cancelling {order['orderLinkId']}: {str(e)}")
                    failed_count += 1
            
            print(f"\nSummary: {cancelled_count} cancelled, {failed_count} failed")
            
    except Exception as e:
        print(f"\nException processing {symbol} on {account_name}: {str(e)}")

def main():
    """Main function to clean up old rebalanced orders."""
    import sys
    
    dry_run = '--execute' not in sys.argv
    
    print("Cleanup Old Rebalanced Orders")
    print("=" * 80)
    
    if dry_run:
        print("\n⚠️  DRY RUN MODE - No orders will be cancelled")
        print("Run with --execute flag to actually cancel orders")
    else:
        print("\n⚠️  EXECUTE MODE - Orders will be cancelled!")
        # Check if running interactively
        if sys.stdin.isatty():
            response = input("\nAre you sure you want to proceed? (yes/no): ")
            if response.lower() != 'yes':
                print("Cancelled by user")
                return
        else:
            print("Running in non-interactive mode, proceeding with cleanup...")
    
    # Initialize clients
    main_client, mirror_client = init_clients()
    
    # Symbols to check
    main_symbols = ['SUIUSDT', 'RUNEUSDT']
    mirror_symbols = ['NKNUSDT', 'WIFUSDT']
    
    # Process main account
    print("\n\nMAIN ACCOUNT")
    print("=" * 80)
    for symbol in main_symbols:
        cleanup_orders_for_symbol(main_client, symbol, "Main", dry_run)
    
    # Process mirror account
    print("\n\nMIRROR ACCOUNT")
    print("=" * 80)
    for symbol in mirror_symbols:
        cleanup_orders_for_symbol(mirror_client, symbol, "Mirror", dry_run)
    
    print("\n\nCleanup complete!")

if __name__ == "__main__":
    main()