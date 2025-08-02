#!/usr/bin/env python3
"""
Cancel ALL DOTUSDT orders on both main and mirror accounts.
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()


async def cancel_all_dot_orders():
    """Cancel all DOTUSDT orders."""
    
    print("🔨 Cancelling ALL DOTUSDT Orders")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    from pybit.unified_trading import HTTP
    from config.settings import (
        BYBIT_API_KEY, BYBIT_API_SECRET,
        BYBIT_API_KEY_2, BYBIT_API_SECRET_2,
        USE_TESTNET
    )
    
    if not all([BYBIT_API_KEY, BYBIT_API_SECRET]):
        print("❌ API credentials not configured")
        return
    
    # Initialize clients
    main_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    mirror_client = None
    if BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
        mirror_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2
        )
    
    total_cancelled = {'MAIN': 0, 'MIRROR': 0}
    
    for account_name, client in [("MAIN", main_client), ("MIRROR", mirror_client)]:
        if not client:
            continue
            
        print(f"\n\n{'='*40} {account_name} ACCOUNT {'='*40}")
        
        # Multiple attempts to ensure all orders are cancelled
        for attempt in range(3):
            print(f"\n📤 Attempt {attempt + 1} - Checking for DOTUSDT orders...")
            
            try:
                # Get all open orders for DOTUSDT
                response = client.get_open_orders(
                    category="linear",
                    symbol="DOTUSDT",
                    openOnly=1,
                    limit=50
                )
                
                if response['retCode'] == 0:
                    orders = response['result']['list']
                    
                    if not orders:
                        print("✅ No orders found")
                        break
                    
                    print(f"Found {len(orders)} orders to cancel:")
                    
                    cancelled_this_round = 0
                    for i, order in enumerate(orders, 1):
                        order_type = order.get('orderType', '')
                        stop_type = order.get('stopOrderType', '')
                        side = order['side']
                        qty = float(order['qty'])
                        price = order.get('triggerPrice', order.get('price', 'N/A'))
                        order_id = order['orderId']
                        link_id = order.get('orderLinkId', 'N/A')
                        
                        print(f"\n  Order {i}:")
                        print(f"    Type: {order_type} {stop_type}")
                        print(f"    Side: {side}")
                        print(f"    Quantity: {qty:,.0f}")
                        print(f"    Price/Trigger: ${price}")
                        print(f"    Order ID: {order_id[:8]}...")
                        print(f"    Link ID: {link_id}")
                        
                        # Try to cancel
                        print("    Cancelling...", end='')
                        try:
                            cancel_resp = client.cancel_order(
                                category="linear",
                                symbol="DOTUSDT",
                                orderId=order_id
                            )
                            
                            if cancel_resp['retCode'] == 0:
                                print(" ✅ Success!")
                                cancelled_this_round += 1
                            else:
                                print(f" ❌ Failed: {cancel_resp['retMsg']}")
                                
                        except Exception as e:
                            print(f" ❌ Error: {e}")
                    
                    total_cancelled[account_name] += cancelled_this_round
                    
                    if cancelled_this_round > 0:
                        print(f"\n✅ Cancelled {cancelled_this_round} orders this round")
                        # Wait before next attempt
                        await asyncio.sleep(1)
                    else:
                        break
                        
                else:
                    print(f"❌ Error fetching orders: {response['retMsg']}")
                    break
                    
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
                break
        
        # Also try batch cancel as a backup
        print("\n📤 Attempting batch cancel...")
        try:
            batch_response = client.cancel_all_orders(
                category="linear",
                symbol="DOTUSDT"
            )
            
            if batch_response['retCode'] == 0:
                result = batch_response.get('result', {})
                batch_cancelled = len(result.get('list', []))
                if batch_cancelled > 0:
                    print(f"✅ Batch cancelled {batch_cancelled} additional orders")
                    total_cancelled[account_name] += batch_cancelled
            else:
                print(f"Batch cancel response: {batch_response['retMsg']}")
                
        except Exception as e:
            print(f"Batch cancel not available or error: {e}")
    
    # Final verification
    print("\n\n" + "=" * 80)
    print("📊 FINAL VERIFICATION")
    print("=" * 80)
    
    for account_name, client in [("MAIN", main_client), ("MIRROR", mirror_client)]:
        if not client:
            continue
            
        print(f"\n{account_name} Account:")
        
        try:
            response = client.get_open_orders(
                category="linear",
                symbol="DOTUSDT",
                openOnly=1
            )
            
            if response['retCode'] == 0:
                remaining = len(response['result']['list'])
                if remaining == 0:
                    print("✅ No DOTUSDT orders remaining")
                else:
                    print(f"⚠️  Still {remaining} DOTUSDT orders remaining")
                    
        except Exception as e:
            print(f"❌ Error checking: {e}")
    
    # Summary
    print("\n\n" + "=" * 80)
    print("📊 CANCELLATION SUMMARY")
    print("=" * 80)
    
    print(f"\nTotal Orders Cancelled:")
    print(f"  Main Account: {total_cancelled['MAIN']}")
    print(f"  Mirror Account: {total_cancelled['MIRROR']}")
    print(f"  Grand Total: {sum(total_cancelled.values())}")
    
    print("\n✅ DOTUSDT order cancellation complete!")


async def main():
    """Main function."""
    await cancel_all_dot_orders()


if __name__ == "__main__":
    asyncio.run(main())