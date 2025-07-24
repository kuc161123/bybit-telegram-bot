#!/usr/bin/env python3
"""
Clean up duplicate orders on mirror account more aggressively.
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from pybit.unified_trading import HTTP
from collections import defaultdict

# Load environment variables
load_dotenv()

def init_mirror_client():
    """Initialize Bybit mirror client."""
    return HTTP(
        testnet=os.getenv('USE_TESTNET', 'false').lower() == 'true',
        api_key=os.getenv('BYBIT_API_KEY_2'),
        api_secret=os.getenv('BYBIT_API_SECRET_2')
    )

def analyze_position_orders(client, symbol):
    """Analyze orders for a specific position to identify duplicates."""
    try:
        # Get position info
        pos_response = client.get_positions(
            category="linear",
            symbol=symbol
        )
        
        if pos_response['retCode'] != 0:
            print(f"Error getting position for {symbol}: {pos_response.get('retMsg', 'Unknown error')}")
            return None
            
        positions = pos_response['result']['list']
        active_position = next((p for p in positions if float(p.get('size', 0)) > 0), None)
        
        if not active_position:
            print(f"No active position found for {symbol}")
            return None
        
        position_size = float(active_position['size'])
        
        # Get all orders
        response = client.get_open_orders(
            category="linear",
            symbol=symbol,
            limit=50
        )
        
        if response['retCode'] != 0:
            print(f"Error getting orders for {symbol}: {response.get('retMsg', 'Unknown error')}")
            return None
        
        orders = response['result']['list']
        
        # Group orders by type and approach
        order_groups = defaultdict(list)
        
        for order in orders:
            link_id = order.get('orderLinkId', '')
            
            # Determine order type and key
            if '_TP1_' in link_id:
                key = 'TP1'
            elif '_TP2_' in link_id:
                key = 'TP2'
            elif '_TP3_' in link_id:
                key = 'TP3'
            elif '_TP4_' in link_id:
                key = 'TP4'
            elif '_SL_' in link_id:
                key = 'SL'
            elif 'LIMIT' in link_id:
                key = 'LIMIT'
            else:
                key = 'OTHER'
            
            order_groups[key].append(order)
        
        # Analyze duplicates
        duplicates_to_remove = []
        orders_to_keep = []
        
        # For each order type, keep only the most recent one
        for order_type, type_orders in order_groups.items():
            if order_type == 'LIMIT':
                # Remove all LIMIT orders
                duplicates_to_remove.extend(type_orders)
            elif len(type_orders) > 1:
                # Sort by creation time (newest first)
                sorted_orders = sorted(type_orders, key=lambda x: int(x.get('createdTime', 0)), reverse=True)
                
                # Keep the newest
                orders_to_keep.append(sorted_orders[0])
                
                # Remove the rest
                duplicates_to_remove.extend(sorted_orders[1:])
            elif len(type_orders) == 1:
                orders_to_keep.append(type_orders[0])
        
        # Calculate expected conservative distribution
        expected_tp1 = position_size * 0.85
        expected_tp234 = position_size * 0.05
        
        return {
            'symbol': symbol,
            'position_size': position_size,
            'total_orders': len(orders),
            'order_groups': dict(order_groups),
            'duplicates_to_remove': duplicates_to_remove,
            'orders_to_keep': orders_to_keep,
            'expected_quantities': {
                'TP1': expected_tp1,
                'TP2': expected_tp234,
                'TP3': expected_tp234,
                'TP4': expected_tp234,
                'SL': position_size
            }
        }
        
    except Exception as e:
        print(f"Exception analyzing {symbol}: {str(e)}")
        return None

def cleanup_duplicates(client, analysis, dry_run=True):
    """Clean up duplicate orders based on analysis."""
    symbol = analysis['symbol']
    duplicates = analysis['duplicates_to_remove']
    
    if not duplicates:
        print(f"{symbol}: No duplicates to remove")
        return
    
    print(f"\n{symbol}: Found {len(duplicates)} duplicate orders to remove")
    
    # Show what will be removed
    for order in duplicates[:5]:  # Show first 5
        created_time = datetime.fromtimestamp(int(order['createdTime']) / 1000)
        print(f"  - {order['orderLinkId']} | Qty: {order['qty']} | Created: {created_time.strftime('%H:%M:%S')}")
    
    if len(duplicates) > 5:
        print(f"  ... and {len(duplicates) - 5} more")
    
    if dry_run:
        print("  DRY RUN - No orders cancelled")
    else:
        # Cancel orders
        cancelled = 0
        failed = 0
        
        for order in duplicates:
            try:
                response = client.cancel_order(
                    category="linear",
                    symbol=symbol,
                    orderId=order['orderId']
                )
                
                if response['retCode'] == 0:
                    cancelled += 1
                else:
                    failed += 1
                    print(f"  Failed to cancel {order['orderLinkId']}: {response.get('retMsg', 'Unknown error')}")
                    
            except Exception as e:
                failed += 1
                print(f"  Exception cancelling {order['orderLinkId']}: {str(e)}")
        
        print(f"  Cancelled: {cancelled}, Failed: {failed}")

def main():
    """Main function to clean up mirror account duplicates."""
    import sys
    
    dry_run = '--execute' not in sys.argv
    
    print("Mirror Account Duplicate Order Cleanup")
    print("=" * 80)
    
    if dry_run:
        print("\n⚠️  DRY RUN MODE - No orders will be cancelled")
        print("Run with --execute flag to actually cancel orders")
    else:
        print("\n⚠️  EXECUTE MODE - Orders will be cancelled!")
        if sys.stdin.isatty():
            response = input("\nAre you sure you want to proceed? (yes/no): ")
            if response.lower() != 'yes':
                print("Cancelled by user")
                return
        else:
            print("Running in non-interactive mode, proceeding...")
    
    # Initialize client
    client = init_mirror_client()
    
    # Get all positions
    try:
        response = client.get_positions(
            category="linear",
            settleCoin="USDT"
        )
        
        if response['retCode'] != 0:
            print(f"Error getting positions: {response.get('retMsg', 'Unknown error')}")
            return
        
        positions = response['result']['list']
        active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
        
        print(f"\nFound {len(active_positions)} active positions")
        
        # Analyze each position
        total_duplicates = 0
        
        for position in active_positions:
            symbol = position['symbol']
            analysis = analyze_position_orders(client, symbol)
            
            if analysis:
                duplicate_count = len(analysis['duplicates_to_remove'])
                total_duplicates += duplicate_count
                
                if duplicate_count > 0:
                    print(f"\n{'='*60}")
                    print(f"{symbol}:")
                    print(f"  Position Size: {analysis['position_size']}")
                    print(f"  Total Orders: {analysis['total_orders']}")
                    print(f"  Order Distribution:")
                    for order_type, type_orders in analysis['order_groups'].items():
                        if type_orders:
                            print(f"    {order_type}: {len(type_orders)} orders")
                    
                    cleanup_duplicates(client, analysis, dry_run)
        
        print(f"\n\nTotal duplicate orders found: {total_duplicates}")
        
        if dry_run and total_duplicates > 0:
            print("\nRun with --execute flag to clean up these duplicates")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()