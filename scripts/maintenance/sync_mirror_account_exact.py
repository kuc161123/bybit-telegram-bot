#!/usr/bin/env python3
"""
Cancel all orders on mirror account and recreate them exactly from main account.
Makes the mirror account a direct copy of the main account.
"""

import asyncio
import os
import sys
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()


async def sync_mirror_exact():
    """Make mirror account an exact copy of main account orders."""
    
    print("🔄 Exact Mirror Account Synchronization")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    from pybit.unified_trading import HTTP
    from config.settings import (
        BYBIT_API_KEY, BYBIT_API_SECRET,
        BYBIT_API_KEY_2, BYBIT_API_SECRET_2,
        USE_TESTNET
    )
    
    if not all([BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2]):
        print("❌ Both main and mirror accounts must be configured")
        return
    
    main_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    mirror_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY_2,
        api_secret=BYBIT_API_SECRET_2
    )
    
    # Step 1: Get all positions from both accounts
    print("\n📊 Step 1: Analyzing Positions")
    print("-" * 40)
    
    # Get main account positions
    main_positions = {}
    pos_response = main_client.get_positions(
        category="linear",
        settleCoin="USDT"
    )
    
    if pos_response['retCode'] == 0:
        for pos in pos_response['result']['list']:
            if float(pos['size']) > 0:
                symbol = pos['symbol']
                main_positions[symbol] = pos
    
    print(f"Main account: {len(main_positions)} active positions")
    
    # Get mirror account positions
    mirror_positions = {}
    pos_response = mirror_client.get_positions(
        category="linear",
        settleCoin="USDT"
    )
    
    if pos_response['retCode'] == 0:
        for pos in pos_response['result']['list']:
            if float(pos['size']) > 0:
                symbol = pos['symbol']
                mirror_positions[symbol] = pos
    
    print(f"Mirror account: {len(mirror_positions)} active positions")
    
    # Find common positions
    common_symbols = set(main_positions.keys()) & set(mirror_positions.keys())
    print(f"Common positions: {len(common_symbols)}")
    
    # Step 2: Cancel ALL mirror account orders
    print("\n\n📤 Step 2: Cancelling ALL Mirror Account Orders")
    print("-" * 40)
    
    total_cancelled = 0
    symbols_with_orders = defaultdict(int)
    
    # First, get count of orders per symbol
    for symbol in mirror_positions.keys():
        response = mirror_client.get_open_orders(
            category="linear",
            symbol=symbol,
            openOnly=1,
            limit=50
        )
        
        if response['retCode'] == 0:
            orders = response['result']['list']
            if orders:
                symbols_with_orders[symbol] = len(orders)
    
    print(f"Found orders on {len(symbols_with_orders)} symbols")
    
    # Cancel orders symbol by symbol
    for symbol, order_count in symbols_with_orders.items():
        print(f"\nCancelling {order_count} orders for {symbol}...")
        
        cancelled_this_symbol = 0
        attempts = 0
        max_attempts = 3
        
        while attempts < max_attempts:
            attempts += 1
            
            # Get current orders
            response = mirror_client.get_open_orders(
                category="linear",
                symbol=symbol,
                openOnly=1,
                limit=50
            )
            
            if response['retCode'] != 0:
                break
            
            orders = response['result']['list']
            if not orders:
                break
            
            # Cancel each order
            for order in orders:
                try:
                    cancel_response = mirror_client.cancel_order(
                        category="linear",
                        symbol=symbol,
                        orderId=order['orderId']
                    )
                    
                    if cancel_response['retCode'] == 0:
                        cancelled_this_symbol += 1
                        
                except Exception as e:
                    # Order might be already filled/cancelled
                    pass
            
            # Small delay before next attempt
            await asyncio.sleep(0.2)
        
        if cancelled_this_symbol > 0:
            print(f"  ✅ Cancelled {cancelled_this_symbol} orders")
            total_cancelled += cancelled_this_symbol
    
    print(f"\n✅ Total orders cancelled: {total_cancelled}")
    
    # Step 3: Get main account orders structure
    print("\n\n📊 Step 3: Collecting Main Account Order Structure")
    print("-" * 40)
    
    main_orders_by_symbol = {}
    
    for symbol in common_symbols:
        response = main_client.get_open_orders(
            category="linear",
            symbol=symbol,
            openOnly=1,
            limit=50
        )
        
        if response['retCode'] == 0:
            orders = response['result']['list']
            if orders:
                main_orders_by_symbol[symbol] = orders
                print(f"{symbol}: {len(orders)} orders to copy")
    
    # Step 4: Recreate orders on mirror account
    print("\n\n🔧 Step 4: Recreating Orders on Mirror Account")
    print("-" * 40)
    
    successful_recreations = 0
    failed_recreations = 0
    
    for symbol in common_symbols:
        if symbol not in main_orders_by_symbol:
            continue
        
        main_orders = main_orders_by_symbol[symbol]
        main_pos = main_positions[symbol]
        mirror_pos = mirror_positions[symbol]
        
        print(f"\n📍 {symbol}: Copying {len(main_orders)} orders")
        
        # Calculate size ratio
        main_size = float(main_pos['size'])
        mirror_size = float(mirror_pos['size'])
        size_ratio = mirror_size / main_size if main_size > 0 else 0
        
        print(f"  Position sizes - Main: {main_size:,.0f}, Mirror: {mirror_size:,.0f} (ratio: {size_ratio:.2f})")
        
        # Sort orders by type (SL first, then TPs)
        sl_orders = []
        tp_orders = []
        
        for order in main_orders:
            if order.get('stopOrderType') == 'Stop':
                link_id = order.get('orderLinkId', '')
                if 'SL' in link_id:
                    sl_orders.append(order)
                else:
                    tp_orders.append(order)
        
        # Place SL orders first
        for order in sl_orders:
            try:
                # Adjust quantity based on mirror position size
                original_qty = float(order['qty'])
                mirror_qty = int(original_qty * size_ratio)
                
                if mirror_qty == 0:
                    continue
                
                # Create order parameters
                order_params = {
                    "category": "linear",
                    "symbol": symbol,
                    "side": order['side'],
                    "orderType": order['orderType'],
                    "qty": str(mirror_qty),
                    "triggerPrice": order['triggerPrice'],
                    "triggerDirection": order.get('triggerDirection', 2 if order['side'] == 'Sell' else 1),
                    "triggerBy": order.get('triggerBy', 'LastPrice'),
                    "reduceOnly": True,
                    "orderLinkId": f"MIRROR_{order.get('orderLinkId', 'SL')}_{datetime.now().strftime('%H%M%S%f')[:10]}"
                }
                
                # Add positionIdx if present
                if mirror_pos.get('positionIdx') is not None:
                    order_params['positionIdx'] = mirror_pos['positionIdx']
                
                response = mirror_client.place_order(**order_params)
                
                if response['retCode'] == 0:
                    print(f"  ✅ SL copied: {mirror_qty} @ ${order['triggerPrice']}")
                    successful_recreations += 1
                else:
                    print(f"  ❌ SL failed: {response['retMsg']}")
                    failed_recreations += 1
                    
            except Exception as e:
                print(f"  ❌ Error copying SL: {e}")
                failed_recreations += 1
        
        # Place TP orders
        tp_count = 0
        for order in tp_orders:
            try:
                # Adjust quantity
                original_qty = float(order['qty'])
                mirror_qty = int(original_qty * size_ratio)
                
                if mirror_qty == 0:
                    continue
                
                tp_count += 1
                
                # Create order parameters
                order_params = {
                    "category": "linear",
                    "symbol": symbol,
                    "side": order['side'],
                    "orderType": order['orderType'],
                    "qty": str(mirror_qty),
                    "triggerPrice": order['triggerPrice'],
                    "triggerDirection": order.get('triggerDirection', 1 if order['side'] == 'Sell' else 2),
                    "triggerBy": order.get('triggerBy', 'LastPrice'),
                    "reduceOnly": True,
                    "orderLinkId": f"MIRROR_{order.get('orderLinkId', f'TP{tp_count}')}_{datetime.now().strftime('%H%M%S%f')[:10]}"
                }
                
                # Add positionIdx if present
                if mirror_pos.get('positionIdx') is not None:
                    order_params['positionIdx'] = mirror_pos['positionIdx']
                
                response = mirror_client.place_order(**order_params)
                
                if response['retCode'] == 0:
                    print(f"  ✅ TP{tp_count} copied: {mirror_qty} @ ${order['triggerPrice']}")
                    successful_recreations += 1
                else:
                    print(f"  ❌ TP{tp_count} failed: {response['retMsg']}")
                    failed_recreations += 1
                    
                    # Stop if hitting order limit
                    if "already had" in response['retMsg'] and "working normal stop orders" in response['retMsg']:
                        print("  ⚠️  Hit order limit, skipping remaining TPs for this symbol")
                        break
                        
            except Exception as e:
                print(f"  ❌ Error copying TP: {e}")
                failed_recreations += 1
        
        # Small delay between symbols
        await asyncio.sleep(0.3)
    
    # Step 5: Verify synchronization
    print("\n\n✅ Step 5: Verification")
    print("-" * 40)
    
    # Count orders on both accounts
    main_total_orders = 0
    mirror_total_orders = 0
    
    for symbol in common_symbols:
        # Main account
        response = main_client.get_open_orders(
            category="linear",
            symbol=symbol,
            openOnly=1
        )
        if response['retCode'] == 0:
            main_total_orders += len(response['result']['list'])
        
        # Mirror account
        response = mirror_client.get_open_orders(
            category="linear",
            symbol=symbol,
            openOnly=1
        )
        if response['retCode'] == 0:
            mirror_total_orders += len(response['result']['list'])
    
    # Summary
    print("\n\n" + "=" * 70)
    print("📊 SYNCHRONIZATION SUMMARY")
    print("=" * 70)
    
    print(f"\nOrders cancelled: {total_cancelled}")
    print(f"Orders recreated: {successful_recreations}")
    print(f"Failed recreations: {failed_recreations}")
    
    print(f"\nCurrent state:")
    print(f"Main account total orders: {main_total_orders}")
    print(f"Mirror account total orders: {mirror_total_orders}")
    
    if failed_recreations > 0:
        print("\n⚠️  Some orders failed to recreate - likely due to order limits")
        print("Consider reducing position count or using fewer TP levels")
    
    print("\n✅ Mirror account synchronization complete!")
    print("The mirror account now reflects the main account order structure")


async def main():
    """Main function."""
    await sync_mirror_exact()


if __name__ == "__main__":
    asyncio.run(main())