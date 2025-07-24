#!/usr/bin/env python3
"""
Delete all orders on mirror account and copy from main account.
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Dict, List
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from config.settings import ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
from execution.mirror_trader import bybit_client_2
from clients.bybit_client import bybit_client
from utils.position_mode_handler import position_mode_handler


async def cancel_all_mirror_orders():
    """Cancel all orders on mirror account."""
    print("\n🗑️  Cancelling all mirror account orders...")
    
    try:
        # Get all open orders
        orders_response = bybit_client_2.get_open_orders(
            category="linear",
            settleCoin="USDT",
            limit=200
        )
        
        if orders_response and orders_response.get('retCode') == 0:
            all_orders = orders_response.get('result', {}).get('list', [])
            active_orders = [
                order for order in all_orders 
                if order.get('orderStatus') in ['New', 'PartiallyFilled', 'Untriggered']
            ]
            
            print(f"   Found {len(active_orders)} orders to cancel")
            
            # Cancel each order
            cancelled = 0
            for order in active_orders:
                try:
                    cancel_response = bybit_client_2.cancel_order(
                        category="linear",
                        symbol=order['symbol'],
                        orderId=order['orderId']
                    )
                    if cancel_response.get('retCode') == 0:
                        cancelled += 1
                except Exception as e:
                    print(f"   ⚠️  Failed to cancel order {order['orderId']}: {e}")
            
            print(f"   ✅ Cancelled {cancelled} orders")
            return True
        
    except Exception as e:
        print(f"   ❌ Error cancelling orders: {e}")
        return False


async def copy_orders_from_main():
    """Copy all orders from main account to mirror account."""
    print("\n📋 Copying orders from main account...")
    
    try:
        # Get all orders from main account
        main_orders_response = bybit_client.get_open_orders(
            category="linear",
            settleCoin="USDT",
            limit=200
        )
        
        if not main_orders_response or main_orders_response.get('retCode') != 0:
            print("   ❌ Failed to fetch main account orders")
            return
        
        all_main_orders = main_orders_response.get('result', {}).get('list', [])
        active_main_orders = [
            order for order in all_main_orders 
            if order.get('orderStatus') in ['New', 'PartiallyFilled', 'Untriggered']
        ]
        
        print(f"   Found {len(active_main_orders)} orders on main account")
        
        # Group orders by type
        limit_orders = []
        tp_orders = []
        sl_orders = []
        
        for order in active_main_orders:
            if order.get('stopOrderType') == 'TakeProfit':
                tp_orders.append(order)
            elif order.get('stopOrderType') == 'StopLoss':
                sl_orders.append(order)
            else:
                limit_orders.append(order)
        
        print(f"   Main account orders: {len(limit_orders)} limit, {len(tp_orders)} TP, {len(sl_orders)} SL")
        
        # Get mirror positions for reference
        positions_response = bybit_client_2.get_positions(
            category="linear",
            settleCoin="USDT"
        )
        
        mirror_positions = {}
        if positions_response and positions_response.get('retCode') == 0:
            for pos in positions_response.get('result', {}).get('list', []):
                if float(pos.get('size', 0)) > 0:
                    key = f"{pos['symbol']}_{pos['side']}"
                    mirror_positions[key] = pos
        
        # Copy orders
        created = 0
        
        # Copy limit orders
        print("\n   📝 Copying limit orders...")
        for order in limit_orders:
            try:
                # Skip if no corresponding position on mirror
                position_key = f"{order['symbol']}_{order['side']}"
                if position_key not in mirror_positions:
                    continue
                
                order_params = {
                    "category": "linear",
                    "symbol": order['symbol'],
                    "side": order['side'],
                    "orderType": order['orderType'],
                    "qty": order['qty'],
                    "price": order['price'],
                    "timeInForce": order.get('timeInForce', 'GTC'),
                    "orderLinkId": order.get('orderLinkId', ''),
                    "reduceOnly": order.get('reduceOnly', False)
                }
                
                # Add position index for hedge mode
                pos_idx = position_mode_handler.get_correct_position_idx(
                    bybit_client_2,
                    order['symbol'],
                    order['side'],
                    is_reduce_only=order.get('reduceOnly', False)
                )
                if pos_idx:
                    order_params['positionIdx'] = pos_idx
                
                response = bybit_client_2.place_order(**order_params)
                if response.get('retCode') == 0:
                    created += 1
                    
            except Exception as e:
                print(f"      ⚠️  Failed to copy limit order: {e}")
        
        # Copy TP orders
        print("\n   📈 Copying TP orders...")
        for order in tp_orders:
            try:
                # Check if position exists on mirror
                position_key = f"{order['symbol']}_{order['side']}"
                # For TP orders, the position side is opposite
                position_side = 'Buy' if order['side'] == 'Sell' else 'Sell'
                position_key = f"{order['symbol']}_{position_side}"
                
                if position_key not in mirror_positions:
                    continue
                
                order_params = {
                    "category": "linear",
                    "symbol": order['symbol'],
                    "side": order['side'],
                    "orderType": order['orderType'],
                    "qty": order['qty'],
                    "triggerPrice": order.get('triggerPrice', order.get('stopPx')),
                    "triggerBy": order.get('triggerBy', 'LastPrice'),
                    "orderLinkId": order.get('orderLinkId', ''),
                    "reduceOnly": True,
                    "stopOrderType": "TakeProfit"
                }
                
                # Add position index for hedge mode
                pos_idx = position_mode_handler.get_correct_position_idx(
                    bybit_client_2,
                    order['symbol'],
                    order['side'],
                    is_reduce_only=True
                )
                if pos_idx:
                    order_params['positionIdx'] = pos_idx
                
                response = bybit_client_2.place_order(**order_params)
                if response.get('retCode') == 0:
                    created += 1
                    
            except Exception as e:
                print(f"      ⚠️  Failed to copy TP order: {e}")
        
        # Copy SL orders
        print("\n   🛡️  Copying SL orders...")
        for order in sl_orders:
            try:
                # Check if position exists on mirror
                position_key = f"{order['symbol']}_{order['side']}"
                # For SL orders, the position side is opposite
                position_side = 'Buy' if order['side'] == 'Sell' else 'Sell'
                position_key = f"{order['symbol']}_{position_side}"
                
                if position_key not in mirror_positions:
                    continue
                
                order_params = {
                    "category": "linear",
                    "symbol": order['symbol'],
                    "side": order['side'],
                    "orderType": order['orderType'],
                    "qty": order['qty'],
                    "triggerPrice": order.get('triggerPrice', order.get('stopPx')),
                    "triggerBy": order.get('triggerBy', 'LastPrice'),
                    "orderLinkId": order.get('orderLinkId', ''),
                    "reduceOnly": True,
                    "stopOrderType": "StopLoss"
                }
                
                # Add position index for hedge mode
                pos_idx = position_mode_handler.get_correct_position_idx(
                    bybit_client_2,
                    order['symbol'],
                    order['side'],
                    is_reduce_only=True
                )
                if pos_idx:
                    order_params['positionIdx'] = pos_idx
                
                response = bybit_client_2.place_order(**order_params)
                if response.get('retCode') == 0:
                    created += 1
                    
            except Exception as e:
                print(f"      ⚠️  Failed to copy SL order: {e}")
        
        print(f"\n   ✅ Created {created} orders on mirror account")
        
    except Exception as e:
        print(f"   ❌ Error copying orders: {e}")
        import traceback
        traceback.print_exc()


async def count_mirror_orders():
    """Count orders on mirror account."""
    print("\n📊 Final order count on mirror account:")
    
    try:
        # Get all open orders
        orders_response = bybit_client_2.get_open_orders(
            category="linear",
            settleCoin="USDT",
            limit=200
        )
        
        if orders_response and orders_response.get('retCode') == 0:
            all_orders = orders_response.get('result', {}).get('list', [])
            
            # Filter active orders
            active_orders = [
                order for order in all_orders 
                if order.get('orderStatus') in ['New', 'PartiallyFilled', 'Untriggered']
            ]
            
            # Count by type
            limit_orders = []
            tp_orders = []
            sl_orders = []
            
            for order in active_orders:
                if order.get('stopOrderType') == 'TakeProfit':
                    tp_orders.append(order)
                elif order.get('stopOrderType') == 'StopLoss':
                    sl_orders.append(order)
                else:
                    limit_orders.append(order)
            
            print(f"\n✅ Total active orders on mirror account: {len(active_orders)}")
            print(f"   Limit orders: {len(limit_orders)}")
            print(f"   Take Profit orders: {len(tp_orders)}")
            print(f"   Stop Loss orders: {len(sl_orders)}")
            
            # Check for issues
            print("\n🔍 Checking for issues:")
            
            # Group by symbol
            symbols = {}
            for order in active_orders:
                symbol = order.get('symbol', 'Unknown')
                if symbol not in symbols:
                    symbols[symbol] = {'limit': 0, 'tp': 0, 'sl': 0}
                
                if order.get('stopOrderType') == 'TakeProfit':
                    symbols[symbol]['tp'] += 1
                elif order.get('stopOrderType') == 'StopLoss':
                    symbols[symbol]['sl'] += 1
                else:
                    symbols[symbol]['limit'] += 1
            
            issues = 0
            for symbol, counts in sorted(symbols.items()):
                has_issue = False
                
                # Check for missing SL
                if counts['tp'] > 0 and counts['sl'] == 0:
                    print(f"   ⚠️  {symbol}: Has TP orders but no SL")
                    has_issue = True
                    issues += 1
                
                # Check for duplicate SL
                if counts['sl'] > 1:
                    print(f"   ⚠️  {symbol}: Multiple SL orders ({counts['sl']})")
                    has_issue = True
                    issues += 1
                
                # Show symbol summary
                if not has_issue:
                    print(f"   ✅ {symbol}: {counts['limit']} limit, {counts['tp']} TP, {counts['sl']} SL")
            
            if issues == 0:
                print("\n   ✅ All positions have proper TP/SL orders!")
            
        else:
            print(f"❌ Error fetching orders: {orders_response}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main function."""
    print("🔄 MIRROR ACCOUNT ORDER SYNC")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Check configuration
    if not ENABLE_MIRROR_TRADING or not BYBIT_API_KEY_2 or not BYBIT_API_SECRET_2:
        print("❌ Mirror trading is not configured")
        return
    
    # Check if mirror client is available
    if not bybit_client_2:
        print("❌ Mirror account client not initialized")
        return
    
    # Step 1: Cancel all mirror orders
    if await cancel_all_mirror_orders():
        # Wait a bit for cancellations to process
        await asyncio.sleep(2)
        
        # Step 2: Copy orders from main account
        await copy_orders_from_main()
        
        # Wait for orders to be placed
        await asyncio.sleep(2)
        
        # Step 3: Count final orders
        await count_mirror_orders()
    
    print("\n✅ Mirror account sync complete!")


if __name__ == "__main__":
    asyncio.run(main())