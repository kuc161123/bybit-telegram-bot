#!/usr/bin/env python3
"""
Mirror Account Status Report

Shows all positions and orders on the mirror trading account.
"""
import asyncio
import logging
import sys
import os
from decimal import Decimal

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_helpers import get_all_positions, get_open_orders_with_client

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def show_mirror_account_status():
    """Show comprehensive mirror account status"""
    try:
        from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
        
        if not is_mirror_trading_enabled():
            print("❌ Mirror trading not enabled")
            return
        
        print("\n" + "="*80)
        print("🪞 MIRROR ACCOUNT STATUS REPORT")
        print("="*80)
        
        # Get all positions
        print("\n📊 POSITIONS:")
        print("-" * 50)
        
        positions = await get_all_positions(client=bybit_client_2)
        if not positions:
            print("No positions found")
        else:
            total_unrealized_pnl = 0
            for i, pos in enumerate(positions, 1):
                symbol = pos.get('symbol', 'Unknown')
                side = pos.get('side', 'Unknown')
                size = pos.get('size', '0')
                entry_price = pos.get('avgPrice', '0')
                mark_price = pos.get('markPrice', '0')
                unrealized_pnl = pos.get('unrealisedPnl', '0')
                position_idx = pos.get('positionIdx', '0')
                
                try:
                    unrealized_pnl_float = float(unrealized_pnl)
                    total_unrealized_pnl += unrealized_pnl_float
                except:
                    unrealized_pnl_float = 0
                
                pnl_emoji = "🟢" if unrealized_pnl_float >= 0 else "🔴"
                
                print(f"{i:2d}. {symbol:<12} {side:<4} | Size: {size:<12} | Entry: ${entry_price:<10} | Mark: ${mark_price:<10} | P&L: {pnl_emoji} ${unrealized_pnl:<10} | Idx: {position_idx}")
            
            print("-" * 50)
            total_pnl_emoji = "🟢" if total_unrealized_pnl >= 0 else "🔴"
            print(f"Total Unrealized P&L: {total_pnl_emoji} ${total_unrealized_pnl:.2f}")
        
        # Get all orders
        print(f"\n📋 ORDERS:")
        print("-" * 50)
        
        response = await get_open_orders_with_client(bybit_client_2, category="linear", settleCoin="USDT")
        if response and hasattr(response, 'get') and response.get('retCode') == 0:
            orders = response.get('result', {}).get('list', [])
        else:
            orders = []
        
        if not orders:
            print("No orders found")
        else:
            # Group orders by symbol
            orders_by_symbol = {}
            for order in orders:
                symbol = order.get('symbol', 'Unknown')
                if symbol not in orders_by_symbol:
                    orders_by_symbol[symbol] = []
                orders_by_symbol[symbol].append(order)
            
            total_orders = len(orders)
            print(f"Total Orders: {total_orders}")
            print()
            
            for symbol, symbol_orders in orders_by_symbol.items():
                print(f"🔸 {symbol} ({len(symbol_orders)} orders):")
                
                # Separate order types
                tp_orders = []
                sl_orders = []
                limit_orders = []
                other_orders = []
                
                for order in symbol_orders:
                    order_link_id = order.get('orderLinkId', '')
                    order_type = order.get('orderType', '')
                    stop_order_type = order.get('stopOrderType', '')
                    
                    if 'TP' in order_link_id or stop_order_type == 'TakeProfit':
                        tp_orders.append(order)
                    elif 'SL' in order_link_id or stop_order_type == 'StopLoss':
                        sl_orders.append(order)
                    elif order_type == 'Limit' and not order.get('triggerPrice'):
                        limit_orders.append(order)
                    else:
                        other_orders.append(order)
                
                # Show limit orders first
                if limit_orders:
                    print("  📥 Limit Orders:")
                    for order in limit_orders:
                        side = order.get('side', 'Unknown')
                        qty = order.get('qty', '0')
                        price = order.get('price', '0')
                        order_id = order.get('orderId', 'Unknown')[:8]
                        status = order.get('orderStatus', 'Unknown')
                        
                        print(f"    {side:<4} {qty:<10} @ ${price:<10} | {status:<12} | ID: {order_id}...")
                
                # Show TP orders
                if tp_orders:
                    print("  🎯 Take Profit Orders:")
                    for order in sorted(tp_orders, key=lambda x: float(x.get('price', 0) if x.get('price') else x.get('triggerPrice', 0))):
                        side = order.get('side', 'Unknown')
                        qty = order.get('qty', '0')
                        price = order.get('price') or order.get('triggerPrice', '0')
                        order_id = order.get('orderId', 'Unknown')[:8]
                        status = order.get('orderStatus', 'Unknown')
                        order_link_id = order.get('orderLinkId', '')
                        
                        # Extract TP number from order link ID
                        tp_num = ""
                        if 'TP1' in order_link_id:
                            tp_num = "TP1"
                        elif 'TP2' in order_link_id:
                            tp_num = "TP2"
                        elif 'TP3' in order_link_id:
                            tp_num = "TP3"
                        elif 'TP4' in order_link_id:
                            tp_num = "TP4"
                        elif 'TP' in order_link_id:
                            tp_num = "TP"
                        
                        print(f"    {tp_num:<3} {side:<4} {qty:<10} @ ${price:<10} | {status:<12} | ID: {order_id}...")
                
                # Show SL orders
                if sl_orders:
                    print("  🛡️ Stop Loss Orders:")
                    for order in sl_orders:
                        side = order.get('side', 'Unknown')
                        qty = order.get('qty', '0')
                        trigger_price = order.get('triggerPrice', '0')
                        order_id = order.get('orderId', 'Unknown')[:8]
                        status = order.get('orderStatus', 'Unknown')
                        
                        print(f"    SL  {side:<4} {qty:<10} @ ${trigger_price:<10} | {status:<12} | ID: {order_id}...")
                
                # Show other orders
                if other_orders:
                    print("  📌 Other Orders:")
                    for order in other_orders:
                        side = order.get('side', 'Unknown')
                        qty = order.get('qty', '0')
                        price = order.get('price') or order.get('triggerPrice', '0')
                        order_type = order.get('orderType', 'Unknown')
                        order_id = order.get('orderId', 'Unknown')[:8]
                        status = order.get('orderStatus', 'Unknown')
                        
                        print(f"    {order_type:<7} {side:<4} {qty:<10} @ ${price:<10} | {status:<12} | ID: {order_id}...")
                
                print()  # Space between symbols
        
        print("="*80)
        print("✅ Mirror account status report completed")
        
    except ImportError:
        print("❌ Mirror trading not available")
    except Exception as e:
        print(f"❌ Error getting mirror account status: {e}")

if __name__ == "__main__":
    asyncio.run(show_mirror_account_status())