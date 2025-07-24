#!/usr/bin/env python3
"""
Check all open orders on mirror account organized by symbol
"""
import asyncio
import os
import sys
from collections import defaultdict

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_helpers import api_call_with_retry
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled

async def check_mirror_orders():
    """Check and display all open orders on mirror account"""
    
    if not is_mirror_trading_enabled() or not bybit_client_2:
        print("❌ Mirror trading is not enabled")
        return
    
    print("🔍 Fetching mirror account orders...\n")
    
    try:
        # Get all open orders
        response = await api_call_with_retry(
            lambda: bybit_client_2.get_open_orders(
                category="linear",
                settleCoin="USDT"
            ),
            timeout=30
        )
        
        if response and response.get("retCode") == 0:
            orders = response.get("result", {}).get("list", [])
            
            if not orders:
                print("✅ No open orders on mirror account")
                return
            
            # Group orders by symbol
            orders_by_symbol = defaultdict(list)
            for order in orders:
                symbol = order.get("symbol", "Unknown")
                orders_by_symbol[symbol].append(order)
            
            # Display orders by symbol
            print(f"📋 Found {len(orders)} open orders on mirror account:\n")
            print("=" * 80)
            
            for symbol, symbol_orders in sorted(orders_by_symbol.items()):
                print(f"\n🪙 {symbol} - {len(symbol_orders)} orders")
                print("-" * 40)
                
                # Separate by order type
                tp_orders = []
                sl_orders = []
                limit_orders = []
                other_orders = []
                
                for order in symbol_orders:
                    order_type = order.get("orderType", "")
                    stop_order_type = order.get("stopOrderType", "")
                    
                    if stop_order_type == "TakeProfit":
                        tp_orders.append(order)
                    elif stop_order_type == "StopLoss":
                        sl_orders.append(order)
                    elif order_type == "Limit":
                        limit_orders.append(order)
                    else:
                        other_orders.append(order)
                
                # Display Take Profits
                if tp_orders:
                    print(f"\n  📈 Take Profit Orders ({len(tp_orders)}):")
                    for i, order in enumerate(tp_orders, 1):
                        order_id = order.get("orderId", "")[:8]
                        trigger_price = order.get("triggerPrice", "N/A")
                        qty = order.get("qty", "N/A")
                        side = order.get("side", "")
                        print(f"    {i}. TP {side} {qty} @ ${trigger_price} (ID: {order_id}...)")
                
                # Display Stop Losses
                if sl_orders:
                    print(f"\n  🛑 Stop Loss Orders ({len(sl_orders)}):")
                    for i, order in enumerate(sl_orders, 1):
                        order_id = order.get("orderId", "")[:8]
                        trigger_price = order.get("triggerPrice", "N/A")
                        qty = order.get("qty", "N/A")
                        side = order.get("side", "")
                        print(f"    {i}. SL {side} {qty} @ ${trigger_price} (ID: {order_id}...)")
                
                # Display Limit Orders
                if limit_orders:
                    print(f"\n  📊 Limit Orders ({len(limit_orders)}):")
                    for i, order in enumerate(limit_orders, 1):
                        order_id = order.get("orderId", "")[:8]
                        price = order.get("price", "N/A")
                        qty = order.get("qty", "N/A")
                        side = order.get("side", "")
                        print(f"    {i}. Limit {side} {qty} @ ${price} (ID: {order_id}...)")
                
                # Display Other Orders
                if other_orders:
                    print(f"\n  📋 Other Orders ({len(other_orders)}):")
                    for i, order in enumerate(other_orders, 1):
                        order_id = order.get("orderId", "")[:8]
                        order_type = order.get("orderType", "Unknown")
                        qty = order.get("qty", "N/A")
                        side = order.get("side", "")
                        print(f"    {i}. {order_type} {side} {qty} (ID: {order_id}...)")
            
            print("\n" + "=" * 80)
            
            # Summary
            print(f"\n📊 Summary:")
            print(f"  • Total Symbols: {len(orders_by_symbol)}")
            print(f"  • Total Orders: {len(orders)}")
            
            # Count by type
            tp_count = sum(1 for o in orders if o.get("stopOrderType") == "TakeProfit")
            sl_count = sum(1 for o in orders if o.get("stopOrderType") == "StopLoss")
            limit_count = sum(1 for o in orders if o.get("orderType") == "Limit" and not o.get("stopOrderType"))
            
            print(f"  • Take Profits: {tp_count}")
            print(f"  • Stop Losses: {sl_count}")
            print(f"  • Limit Orders: {limit_count}")
            print(f"  • Others: {len(orders) - tp_count - sl_count - limit_count}")
            
        else:
            print(f"❌ Error fetching orders: {response}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_mirror_orders())