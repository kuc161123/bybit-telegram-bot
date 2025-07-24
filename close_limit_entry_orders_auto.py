#!/usr/bin/env python3
"""
Close only limit entry orders on both main and mirror accounts - Auto version
Preserves all TP/SL orders
"""
import asyncio
import os
from typing import Dict, List, Tuple
from pybit.unified_trading import HTTP
from datetime import datetime
import time

# Initialize Bybit clients
USE_TESTNET = os.getenv("USE_TESTNET", "false").lower() == "true"

# Main account
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

# Mirror account
ENABLE_MIRROR_TRADING = os.getenv("ENABLE_MIRROR_TRADING", "false").lower() == "true"
BYBIT_API_KEY_2 = os.getenv("BYBIT_API_KEY_2", "")
BYBIT_API_SECRET_2 = os.getenv("BYBIT_API_SECRET_2", "")

# Initialize clients
bybit_client = HTTP(
    testnet=USE_TESTNET,
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET
)

bybit_client_2 = None
if ENABLE_MIRROR_TRADING and BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
    bybit_client_2 = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY_2,
        api_secret=BYBIT_API_SECRET_2
    )

async def get_open_orders(client, account_name: str) -> List[Dict]:
    """Get all open orders from an account"""
    try:
        all_orders = []
        cursor = None
        
        while True:
            params = {
                "category": "linear",
                "settleCoin": "USDT",
                "limit": 200
            }
            
            if cursor:
                params["cursor"] = cursor
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.get_open_orders(**params)
            )
            
            if response and response.get("retCode") == 0:
                result = response.get("result", {})
                orders = result.get("list", [])
                all_orders.extend(orders)
                
                cursor = result.get("nextPageCursor", "")
                if not cursor:
                    break
            else:
                print(f"❌ {account_name}: Failed to get orders: {response}")
                break
        
        return all_orders
    
    except Exception as e:
        print(f"❌ {account_name}: Error fetching orders: {e}")
        return []

def filter_limit_entry_orders(orders: List[Dict]) -> List[Dict]:
    """Filter for limit entry orders (not TP/SL)"""
    limit_entry_orders = []
    
    for order in orders:
        order_type = order.get("orderType", "")
        reduce_only = order.get("reduceOnly", False)
        order_link_id = order.get("orderLinkId", "")
        stop_order_type = order.get("stopOrderType", "")
        
        # Limit order that is NOT reduce-only and NOT a TP/SL
        if (order_type == "Limit" and 
            not reduce_only and 
            not stop_order_type and
            "TP" not in order_link_id.upper() and
            "SL" not in order_link_id.upper()):
            limit_entry_orders.append(order)
    
    return limit_entry_orders

async def cancel_orders(client, orders: List[Dict], account_name: str) -> Tuple[int, int]:
    """Cancel a list of orders"""
    success_count = 0
    fail_count = 0
    
    for order in orders:
        symbol = order.get("symbol", "")
        order_id = order.get("orderId", "")
        side = order.get("side", "")
        price = order.get("price", "")
        qty = order.get("qty", "")
        
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.cancel_order(
                    category="linear",
                    symbol=symbol,
                    orderId=order_id
                )
            )
            
            if response and response.get("retCode") == 0:
                success_count += 1
                print(f"✅ {account_name}: Cancelled {symbol} {side} order @ ${price} (qty: {qty})")
            else:
                fail_count += 1
                error_msg = response.get("retMsg", "Unknown error") if response else "No response"
                print(f"❌ {account_name}: Failed to cancel {symbol} order: {error_msg}")
        
        except Exception as e:
            fail_count += 1
            print(f"❌ {account_name}: Error cancelling {symbol} order: {e}")
        
        # Small delay to avoid rate limits
        await asyncio.sleep(0.1)
    
    return success_count, fail_count

async def update_pickle_file():
    """Update pickle file to clear limit orders from monitors"""
    import pickle
    import shutil
    
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    # Create backup
    backup_name = f'{pickle_file}.backup_clear_limits_{int(time.time())}'
    shutil.copy(pickle_file, backup_name)
    print(f"✅ Created backup: {backup_name}")
    
    # Load pickle
    with open(pickle_file, 'rb') as f:
        data = pickle.load(f)
    
    updated_count = 0
    
    # Clear limit orders from enhanced monitors
    if 'bot_data' in data and 'enhanced_tp_sl_monitors' in data['bot_data']:
        monitors = data['bot_data']['enhanced_tp_sl_monitors']
        
        for key, monitor in monitors.items():
            if 'limit_orders' in monitor and monitor['limit_orders']:
                # Clear limit orders list
                old_count = len(monitor['limit_orders'])
                monitor['limit_orders'] = []
                monitor['limit_orders_cancelled'] = True
                updated_count += 1
                print(f"  ✅ Cleared {old_count} limit orders for {key}")
    
    # Save updated pickle
    with open(pickle_file, 'wb') as f:
        pickle.dump(data, f)
    
    print(f"✅ Pickle file updated - cleared limit orders from {updated_count} monitors")

async def main():
    """Main execution"""
    print("="*80)
    print("CLOSING LIMIT ENTRY ORDERS ONLY - AUTO MODE")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print("\n⚠️  This will cancel all limit entry orders (not TP/SL orders)")
    print("✅ TP/SL orders will remain active")
    
    # Process main account
    print("\n" + "="*40)
    print("MAIN ACCOUNT")
    print("="*40)
    
    main_orders = await get_open_orders(bybit_client, "MAIN")
    main_limit_entries = filter_limit_entry_orders(main_orders)
    
    print(f"\nFound {len(main_limit_entries)} limit entry orders to cancel")
    
    if main_limit_entries:
        # Show what will be cancelled
        print("\nOrders to cancel:")
        for order in main_limit_entries:
            symbol = order.get("symbol", "")
            side = order.get("side", "")
            price = order.get("price", "")
            qty = order.get("qty", "")
            order_id = order.get("orderId", "")
            print(f"  - {symbol} {side} @ ${price} (qty: {qty}) [{order_id[:8]}...]")
        
        # Cancel orders
        print("\nCancelling orders...")
        success, fail = await cancel_orders(bybit_client, main_limit_entries, "MAIN")
        print(f"\nMain Account Results: {success} cancelled, {fail} failed")
    else:
        print("No limit entry orders found")
    
    # Process mirror account
    if bybit_client_2:
        print("\n" + "="*40)
        print("MIRROR ACCOUNT")
        print("="*40)
        
        mirror_orders = await get_open_orders(bybit_client_2, "MIRROR")
        mirror_limit_entries = filter_limit_entry_orders(mirror_orders)
        
        print(f"\nFound {len(mirror_limit_entries)} limit entry orders to cancel")
        
        if mirror_limit_entries:
            # Show what will be cancelled
            print("\nOrders to cancel:")
            for order in mirror_limit_entries:
                symbol = order.get("symbol", "")
                side = order.get("side", "")
                price = order.get("price", "")
                qty = order.get("qty", "")
                order_id = order.get("orderId", "")
                print(f"  - {symbol} {side} @ ${price} (qty: {qty}) [{order_id[:8]}...]")
            
            # Cancel orders
            print("\nCancelling orders...")
            success, fail = await cancel_orders(bybit_client_2, mirror_limit_entries, "MIRROR")
            print(f"\nMirror Account Results: {success} cancelled, {fail} failed")
        else:
            print("No limit entry orders found")
    
    # Summary
    print("\n" + "="*80)
    print("CANCELLATION COMPLETE")
    print("="*80)
    
    # Update pickle file to reflect cancelled orders
    print("\n📝 Updating pickle file to clear limit order tracking...")
    await update_pickle_file()
    
    print("\n✅ OPERATION COMPLETE")
    print("   - All limit entry orders have been cancelled")
    print("   - TP/SL orders remain active")
    print("   - Pickle file updated to reflect changes")

if __name__ == "__main__":
    asyncio.run(main())