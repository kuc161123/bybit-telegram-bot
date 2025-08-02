#!/usr/bin/env python3
"""
Thoroughly cancel ALL NKNUSDT orders on main account.
This script checks multiple times and uses different methods to ensure no orders are missed.
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()


async def cancel_all_nkn_orders():
    """Cancel ALL NKNUSDT orders thoroughly."""
    
    print("🔨 Thoroughly Cancelling ALL NKNUSDT Orders")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    from pybit.unified_trading import HTTP
    from config.settings import (
        BYBIT_API_KEY, BYBIT_API_SECRET,
        USE_TESTNET
    )
    
    if not all([BYBIT_API_KEY, BYBIT_API_SECRET]):
        print("❌ API credentials not configured")
        return
    
    # Initialize main client
    main_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    total_cancelled = 0
    all_orders_found = []
    
    # Method 1: Check with openOnly=1 (active orders)
    print("\n📋 Method 1: Checking active orders (openOnly=1)...")
    try:
        response = main_client.get_open_orders(
            category="linear",
            symbol="NKNUSDT",
            openOnly=1,
            limit=50
        )
        
        if response['retCode'] == 0:
            orders = response['result']['list']
            print(f"Found {len(orders)} active orders")
            all_orders_found.extend(orders)
    except Exception as e:
        print(f"Error: {e}")
    
    # Method 2: Check with openOnly=0 (all orders including filled/cancelled)
    print("\n📋 Method 2: Checking ALL orders (openOnly=0)...")
    try:
        response = main_client.get_open_orders(
            category="linear",
            symbol="NKNUSDT",
            openOnly=0,
            limit=50
        )
        
        if response['retCode'] == 0:
            orders = response['result']['list']
            print(f"Found {len(orders)} total orders")
            
            # Show status breakdown
            status_count = {}
            for order in orders:
                status = order.get('orderStatus', 'Unknown')
                status_count[status] = status_count.get(status, 0) + 1
                
                # Add to list if not already there
                order_id = order['orderId']
                if not any(o['orderId'] == order_id for o in all_orders_found):
                    all_orders_found.append(order)
            
            print("\nOrder statuses:")
            for status, count in status_count.items():
                print(f"  {status}: {count}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Method 3: Try batch cancel
    print("\n📋 Method 3: Attempting batch cancel...")
    try:
        batch_response = main_client.cancel_all_orders(
            category="linear",
            symbol="NKNUSDT"
        )
        
        if batch_response['retCode'] == 0:
            result = batch_response.get('result', {})
            batch_list = result.get('list', [])
            if batch_list:
                print(f"Batch cancelled {len(batch_list)} orders")
                total_cancelled += len(batch_list)
                for item in batch_list:
                    print(f"  - Order {item.get('orderId', 'Unknown')[:12]}...")
            else:
                print("No orders cancelled in batch")
        else:
            print(f"Batch cancel response: {batch_response['retMsg']}")
    except Exception as e:
        print(f"Batch cancel error: {e}")
    
    # Method 4: Try to cancel each order individually
    print("\n📋 Method 4: Cancelling orders individually...")
    
    if all_orders_found:
        print(f"\nAttempting to cancel {len(all_orders_found)} orders individually:")
        
        for i, order in enumerate(all_orders_found, 1):
            order_id = order['orderId']
            status = order.get('orderStatus', 'Unknown')
            order_type = order.get('orderType', '')
            stop_type = order.get('stopOrderType', '')
            side = order['side']
            qty = float(order.get('qty', 0))
            price = order.get('triggerPrice', order.get('price', 'N/A'))
            
            print(f"\nOrder {i}:")
            print(f"  Status: {status}")
            print(f"  Type: {order_type} {stop_type}")
            print(f"  Side: {side} {qty:,.0f} @ ${price}")
            print(f"  Order ID: {order_id[:12]}...")
            
            # Only try to cancel if it's potentially cancellable
            if status in ['New', 'PartiallyFilled', 'Untriggered', 'Created']:
                print("  Attempting to cancel...", end='')
                try:
                    cancel_resp = main_client.cancel_order(
                        category="linear",
                        symbol="NKNUSDT",
                        orderId=order_id
                    )
                    
                    if cancel_resp['retCode'] == 0:
                        print(" ✅ Success!")
                        total_cancelled += 1
                    else:
                        print(f" ❌ Failed: {cancel_resp['retMsg']}")
                except Exception as e:
                    print(f" ❌ Error: {e}")
            else:
                print(f"  Skipping - Status is {status}")
    else:
        print("No orders found to cancel")
    
    # Method 5: Final check
    await asyncio.sleep(1)
    print("\n\n📋 Final Verification...")
    
    try:
        response = main_client.get_open_orders(
            category="linear",
            symbol="NKNUSDT",
            openOnly=1,
            limit=50
        )
        
        if response['retCode'] == 0:
            remaining = len(response['result']['list'])
            if remaining > 0:
                print(f"⚠️  WARNING: Still {remaining} active orders remaining!")
                print("These might be in a state that prevents cancellation.")
                
                # Show details of remaining orders
                for order in response['result']['list']:
                    print(f"\nRemaining order:")
                    print(f"  Order ID: {order['orderId']}")
                    print(f"  Status: {order.get('orderStatus')}")
                    print(f"  Type: {order.get('orderType')} {order.get('stopOrderType', '')}")
                    print(f"  Created: {order.get('createdTime')}")
                    print(f"  Updated: {order.get('updatedTime')}")
            else:
                print("✅ No active orders remaining!")
    except Exception as e:
        print(f"Error in final check: {e}")
    
    # Summary
    print("\n\n" + "=" * 80)
    print("📊 CANCELLATION SUMMARY")
    print("=" * 80)
    
    print(f"\nTotal orders cancelled: {total_cancelled}")
    print(f"Total orders found: {len(all_orders_found)}")
    
    if all_orders_found:
        print("\n💡 Note: Orders with status 'Filled', 'Cancelled', or 'Deactivated'")
        print("cannot be cancelled as they're already processed.")
        print("These may still show in order history but are not active.")
    
    print("\n✅ Thorough cancellation process complete!")


async def main():
    """Main function."""
    await cancel_all_nkn_orders()


if __name__ == "__main__":
    asyncio.run(main())