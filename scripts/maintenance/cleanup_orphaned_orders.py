#!/usr/bin/env python3
"""
Clean up orphaned orders (orders without active positions) on mirror account
"""
import asyncio
import os
import sys
from collections import defaultdict

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_helpers import api_call_with_retry
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled

async def cleanup_orphaned_orders():
    """Clean up orphaned orders on mirror account"""
    
    if not is_mirror_trading_enabled() or not bybit_client_2:
        print("❌ Mirror trading is not enabled")
        return
    
    print("🧹 Cleaning up orphaned orders on mirror account...\n")
    
    try:
        # Get positions
        pos_response = await api_call_with_retry(
            lambda: bybit_client_2.get_positions(
                category="linear",
                settleCoin="USDT"
            ),
            timeout=30
        )
        
        # Get orders
        order_response = await api_call_with_retry(
            lambda: bybit_client_2.get_open_orders(
                category="linear",
                settleCoin="USDT",
                limit=200
            ),
            timeout=30
        )
        
        if pos_response and pos_response.get("retCode") == 0 and order_response and order_response.get("retCode") == 0:
            positions = pos_response.get("result", {}).get("list", [])
            active_positions = [p for p in positions if float(p.get("size", 0)) > 0]
            orders = order_response.get("result", {}).get("list", [])
            
            # Get active position symbols
            position_symbols = {p.get("symbol") for p in active_positions}
            
            # Group orders by symbol
            orders_by_symbol = defaultdict(list)
            for order in orders:
                symbol = order.get("symbol")
                orders_by_symbol[symbol].append(order)
            
            # Find orphaned symbols
            orphaned_symbols = set(orders_by_symbol.keys()) - position_symbols
            
            if not orphaned_symbols:
                print("✅ No orphaned orders found!")
                return
            
            print(f"Found orphaned orders for symbols: {', '.join(orphaned_symbols)}\n")
            
            # Cancel orphaned orders
            total_cancelled = 0
            
            for symbol in orphaned_symbols:
                symbol_orders = orders_by_symbol[symbol]
                print(f"🪙 Cancelling {len(symbol_orders)} orders for {symbol}:")
                
                for order in symbol_orders:
                    order_id = order.get("orderId", "")
                    order_type = order.get("orderType", "")
                    side = order.get("side", "")
                    qty = order.get("qty", "")
                    
                    try:
                        # Cancel the order
                        cancel_response = await api_call_with_retry(
                            lambda: bybit_client_2.cancel_order(
                                category="linear",
                                symbol=symbol,
                                orderId=order_id
                            ),
                            timeout=20
                        )
                        
                        if cancel_response and cancel_response.get("retCode") == 0:
                            print(f"  ✅ Cancelled: {order_type} {side} {qty} (ID: {order_id[:8]}...)")
                            total_cancelled += 1
                        else:
                            error_msg = cancel_response.get("retMsg", "Unknown error") if cancel_response else "No response"
                            print(f"  ❌ Failed: {order_type} {side} {qty} - {error_msg}")
                            
                    except Exception as e:
                        print(f"  ❌ Error cancelling order {order_id[:8]}...: {e}")
                    
                    # Small delay between cancellations
                    await asyncio.sleep(0.2)
                
                print()  # Empty line between symbols
            
            print(f"\n✅ Cleanup complete! Cancelled {total_cancelled} orphaned orders.")
            
            # Now show remaining orders
            print("\n" + "="*80)
            print("\n🔍 Checking remaining orders...\n")
            
            # Fetch orders again
            order_response = await api_call_with_retry(
                lambda: bybit_client_2.get_open_orders(
                    category="linear",
                    settleCoin="USDT",
                    limit=200
                ),
                timeout=30
            )
            
            if order_response and order_response.get("retCode") == 0:
                orders = order_response.get("result", {}).get("list", [])
                
                if not orders:
                    print("✅ No open orders remaining on mirror account")
                else:
                    # Group by symbol
                    orders_by_symbol = defaultdict(list)
                    for order in orders:
                        symbol = order.get("symbol")
                        orders_by_symbol[symbol].append(order)
                    
                    print(f"📋 Remaining orders ({len(orders)} total):\n")
                    
                    for symbol, symbol_orders in sorted(orders_by_symbol.items()):
                        is_orphaned = symbol not in position_symbols
                        status = " (⚠️ ORPHANED)" if is_orphaned else ""
                        print(f"🪙 {symbol}{status} - {len(symbol_orders)} orders")
                        
                        for order in symbol_orders:
                            order_id = order.get("orderId", "")[:8]
                            order_type = order.get("orderType", "")
                            side = order.get("side", "")
                            qty = order.get("qty", "")
                            trigger_price = order.get("triggerPrice", "")
                            
                            if trigger_price:
                                print(f"    • {order_type} {side} {qty} @ trigger ${trigger_price} (ID: {order_id}...)")
                            else:
                                price = order.get("price", "")
                                print(f"    • {order_type} {side} {qty} @ ${price} (ID: {order_id}...)")
                        print()
            
        else:
            print(f"❌ Error fetching data")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(cleanup_orphaned_orders())