#!/usr/bin/env python3
"""
Check mirror account positions and their corresponding orders
"""
import asyncio
import os
import sys
from collections import defaultdict

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_helpers import api_call_with_retry
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled

async def check_mirror_positions_and_orders():
    """Check mirror positions and their orders"""
    
    if not is_mirror_trading_enabled() or not bybit_client_2:
        print("❌ Mirror trading is not enabled")
        return
    
    print("🔍 Fetching mirror account positions and orders...\n")
    
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
        
        if pos_response and pos_response.get("retCode") == 0:
            positions = pos_response.get("result", {}).get("list", [])
            active_positions = [p for p in positions if float(p.get("size", 0)) > 0]
            
            print(f"📊 MIRROR ACCOUNT STATUS\n{'='*80}\n")
            
            # Display positions
            if active_positions:
                print(f"💰 Active Positions ({len(active_positions)}):")
                for pos in active_positions:
                    symbol = pos.get("symbol")
                    side = pos.get("side")
                    size = float(pos.get("size", 0))
                    avg_price = float(pos.get("avgPrice", 0))
                    mark_price = float(pos.get("markPrice", 0))
                    pnl = float(pos.get("unrealisedPnl", 0))
                    
                    pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                    print(f"\n  {pnl_emoji} {symbol} {side}")
                    print(f"     Size: {size} @ ${avg_price:.6f}")
                    print(f"     Mark: ${mark_price:.6f}")
                    print(f"     P&L: ${pnl:.2f}")
            else:
                print("  No active positions")
            
            # Get and display orders
            if order_response and order_response.get("retCode") == 0:
                orders = order_response.get("result", {}).get("list", [])
                
                if orders:
                    # Group by symbol
                    orders_by_symbol = defaultdict(list)
                    for order in orders:
                        symbol = order.get("symbol")
                        orders_by_symbol[symbol].append(order)
                    
                    print(f"\n\n📋 Open Orders ({len(orders)} total):")
                    print("-" * 80)
                    
                    # Check each position's orders
                    for pos in active_positions:
                        symbol = pos.get("symbol")
                        symbol_orders = orders_by_symbol.get(symbol, [])
                        
                        if symbol_orders:
                            print(f"\n🪙 {symbol} - {len(symbol_orders)} orders:")
                            
                            # Analyze order types
                            for order in symbol_orders:
                                order_id = order.get("orderId", "")[:8]
                                order_type = order.get("orderType", "")
                                side = order.get("side", "")
                                qty = float(order.get("qty", 0))
                                price = order.get("price", "")
                                trigger_price = order.get("triggerPrice", "")
                                stop_order_type = order.get("stopOrderType", "")
                                trigger_direction = order.get("triggerDirection", "")
                                
                                # Determine order purpose
                                pos_side = pos.get("side")
                                
                                if order_type == "Market" and side != pos_side:
                                    # Market order opposite to position = likely TP/SL
                                    if trigger_price:
                                        mark_price = float(pos.get("markPrice", 0))
                                        trigger_float = float(trigger_price)
                                        
                                        if pos_side == "Buy":
                                            if trigger_float > mark_price:
                                                order_desc = f"TP (Take Profit)"
                                            else:
                                                order_desc = f"SL (Stop Loss)"
                                        else:  # Sell position
                                            if trigger_float < mark_price:
                                                order_desc = f"TP (Take Profit)"
                                            else:
                                                order_desc = f"SL (Stop Loss)"
                                    else:
                                        order_desc = "Conditional"
                                    
                                    print(f"    • {order_desc}: {side} {qty} @ trigger ${trigger_price} (ID: {order_id}...)")
                                
                                elif order_type == "Limit":
                                    print(f"    • Limit: {side} {qty} @ ${price} (ID: {order_id}...)")
                                
                                else:
                                    print(f"    • {order_type}: {side} {qty} (ID: {order_id}...)")
                    
                    # Check for orders without positions
                    position_symbols = {p.get("symbol") for p in active_positions}
                    orphaned_symbols = set(orders_by_symbol.keys()) - position_symbols
                    
                    if orphaned_symbols:
                        print(f"\n\n⚠️ Orders without active positions:")
                        for symbol in orphaned_symbols:
                            print(f"\n🪙 {symbol} - {len(orders_by_symbol[symbol])} orphaned orders")
                            for order in orders_by_symbol[symbol]:
                                order_id = order.get("orderId", "")[:8]
                                order_type = order.get("orderType", "")
                                side = order.get("side", "")
                                qty = order.get("qty", "")
                                print(f"    • {order_type} {side} {qty} (ID: {order_id}...)")
            
            print("\n" + "="*80)
            
        else:
            print(f"❌ Error fetching data: {pos_response}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_mirror_positions_and_orders())