#!/usr/bin/env python3
"""
Cancel ALL orders for DOTUSDT, ZENUSDT, ONEUSDT, and ZILUSDT on both accounts.
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()


async def cancel_all_problem_orders():
    """Cancel all orders for problem symbols."""
    
    print("🔨 Cancelling ALL Orders for Problem Symbols")
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
    
    # Symbols to check
    symbols_to_check = ['DOTUSDT', 'ZENUSDT', 'ONEUSDT', 'ZILUSDT']
    
    print(f"\n📋 Checking symbols: {', '.join(symbols_to_check)}")
    
    total_cancelled = {'MAIN': 0, 'MIRROR': 0}
    
    for account_name, client in [("MAIN", main_client), ("MIRROR", mirror_client)]:
        if not client:
            continue
            
        print(f"\n\n{'='*40} {account_name} ACCOUNT {'='*40}")
        
        for symbol in symbols_to_check:
            print(f"\n📍 {symbol}:")
            
            # Multiple attempts to ensure all orders are cancelled
            for attempt in range(2):
                try:
                    # Get all open orders
                    response = client.get_open_orders(
                        category="linear",
                        symbol=symbol,
                        openOnly=1,
                        limit=50
                    )
                    
                    if response['retCode'] == 0:
                        orders = response['result']['list']
                        
                        if not orders:
                            if attempt == 0:
                                print("  ✅ No orders found")
                            break
                        
                        print(f"  Found {len(orders)} orders (Attempt {attempt + 1}):")
                        
                        cancelled_this_round = 0
                        for order in orders:
                            order_type = order.get('orderType', '')
                            stop_type = order.get('stopOrderType', '')
                            side = order['side']
                            qty = float(order['qty'])
                            price = order.get('triggerPrice', order.get('price', 'N/A'))
                            order_id = order['orderId']
                            link_id = order.get('orderLinkId', 'N/A')
                            position_idx = order.get('positionIdx', 'N/A')
                            
                            print(f"\n    - {side} {qty:,.0f} @ ${price}")
                            print(f"      Type: {order_type} {stop_type}")
                            print(f"      Position Index: {position_idx}")
                            print(f"      Link ID: {link_id[:30]}...")
                            
                            # Try to cancel
                            try:
                                cancel_resp = client.cancel_order(
                                    category="linear",
                                    symbol=symbol,
                                    orderId=order_id
                                )
                                
                                if cancel_resp['retCode'] == 0:
                                    print("      ✅ Cancelled!")
                                    cancelled_this_round += 1
                                else:
                                    print(f"      ❌ Failed: {cancel_resp['retMsg']}")
                                    
                            except Exception as e:
                                print(f"      ❌ Error: {e}")
                        
                        total_cancelled[account_name] += cancelled_this_round
                        
                        if cancelled_this_round > 0:
                            print(f"\n  ✅ Cancelled {cancelled_this_round} orders this round")
                            # Wait before next attempt
                            await asyncio.sleep(0.5)
                        else:
                            break
                            
                    else:
                        print(f"  ❌ Error fetching orders: {response['retMsg']}")
                        break
                        
                except Exception as e:
                    print(f"  ❌ Error: {e}")
                    break
        
        # Also try batch cancel for all symbols
        print("\n\n📤 Attempting batch cancel for all symbols...")
        batch_cancelled = 0
        for symbol in symbols_to_check:
            try:
                batch_response = client.cancel_all_orders(
                    category="linear",
                    symbol=symbol
                )
                
                if batch_response['retCode'] == 0:
                    result = batch_response.get('result', {})
                    cancelled = len(result.get('list', []))
                    if cancelled > 0:
                        print(f"  {symbol}: Batch cancelled {cancelled} orders")
                        batch_cancelled += cancelled
                        
            except Exception as e:
                pass
        
        if batch_cancelled > 0:
            total_cancelled[account_name] += batch_cancelled
            print(f"\n✅ Total batch cancelled: {batch_cancelled}")
    
    # Final verification
    print("\n\n" + "=" * 80)
    print("📊 FINAL VERIFICATION")
    print("=" * 80)
    
    remaining_orders = {'MAIN': {}, 'MIRROR': {}}
    
    for account_name, client in [("MAIN", main_client), ("MIRROR", mirror_client)]:
        if not client:
            continue
            
        print(f"\n{account_name} Account:")
        
        for symbol in symbols_to_check:
            try:
                response = client.get_open_orders(
                    category="linear",
                    symbol=symbol,
                    openOnly=1
                )
                
                if response['retCode'] == 0:
                    orders = response['result']['list']
                    if orders:
                        remaining_orders[account_name][symbol] = len(orders)
                        print(f"  {symbol}: ⚠️ {len(orders)} orders still remaining")
                    else:
                        print(f"  {symbol}: ✅ No orders")
                        
            except Exception as e:
                print(f"  {symbol}: ❌ Error checking: {e}")
    
    # Summary
    print("\n\n" + "=" * 80)
    print("📊 CANCELLATION SUMMARY")
    print("=" * 80)
    
    print(f"\nTotal Orders Cancelled:")
    print(f"  Main Account: {total_cancelled['MAIN']}")
    print(f"  Mirror Account: {total_cancelled['MIRROR']}")
    print(f"  Grand Total: {sum(total_cancelled.values())}")
    
    if any(remaining_orders['MAIN'].values()) or any(remaining_orders.get('MIRROR', {}).values()):
        print("\n⚠️  Some orders could not be cancelled:")
        for account, symbols in remaining_orders.items():
            if symbols:
                print(f"\n{account} Account:")
                for symbol, count in symbols.items():
                    print(f"  {symbol}: {count} orders")
    else:
        print("\n✅ All orders successfully cancelled!")
    
    print("\n✅ Order cancellation process complete!")


async def main():
    """Main function."""
    await cancel_all_problem_orders()


if __name__ == "__main__":
    asyncio.run(main())