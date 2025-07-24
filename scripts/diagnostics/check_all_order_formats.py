#!/usr/bin/env python3
"""
Comprehensive script to check ALL types of TP/SL orders
- Different order types (Stop, StopMarket, TakeProfit, StopLoss)
- Different naming conventions (not just BOT_ prefix)
- Check triggerPrice field for stop orders
- Check both orderLinkId and orderId fields
- Look for any orders that match position symbols
- Check for partially filled orders
"""

import os
import sys
from pathlib import Path
from decimal import Decimal
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from clients.bybit_client import create_bybit_client
from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET,
    BYBIT_API_KEY_2, BYBIT_API_SECRET_2
)

class OrderFormatChecker:
    def __init__(self, client, account_name: str):
        self.client = client
        self.account_name = account_name
        
    def get_current_price(self, symbol: str) -> Optional[Decimal]:
        """Get current market price for a symbol"""
        try:
            result = self.client.get_tickers(category="linear", symbol=symbol)
            if result['retCode'] == 0 and result['result']['list']:
                ticker = result['result']['list'][0]
                return Decimal(ticker['markPrice'])
        except Exception as e:
            print(f"Error getting price for {symbol}: {e}")
        return None
    
    def analyze_positions_and_orders(self):
        """Analyze all positions and their orders"""
        print(f"\n{'='*80}")
        print(f"ACCOUNT: {self.account_name}")
        print(f"{'='*80}")
        
        # Get all positions
        try:
            positions_result = self.client.get_positions(category="linear", settleCoin="USDT")
            positions = positions_result['result']['list'] if positions_result['retCode'] == 0 else []
        except Exception as e:
            print(f"Error getting positions: {e}")
            positions = []
            
        if not positions:
            print("No open positions")
            return
            
        print(f"\nFound {len(positions)} open positions")
        
        # Get ALL open orders
        try:
            orders_result = self.client.get_open_orders(category="linear", settleCoin="USDT")
            all_orders = orders_result['result']['list'] if orders_result['retCode'] == 0 else []
        except Exception as e:
            print(f"Error getting orders: {e}")
            all_orders = []
            
        print(f"Found {len(all_orders)} total open orders")
        
        # Group orders by symbol
        orders_by_symbol = defaultdict(list)
        for order in all_orders:
            orders_by_symbol[order['symbol']].append(order)
        
        # Analyze each position
        for pos in positions:
            symbol = pos['symbol']
            side = pos['side']
            size = Decimal(pos['size'])
            avg_price = Decimal(pos['avgPrice'])
            unrealized_pnl = Decimal(pos.get('unrealizedPnl', '0'))
            cum_realized_pnl = Decimal(pos.get('cumRealisedPnl', '0'))
            
            # Get current price
            current_price = self.get_current_price(symbol)
            
            print(f"\n{'-'*80}")
            print(f"POSITION: {symbol} {side}")
            print(f"  Size: {size}")
            print(f"  Avg Price: {avg_price}")
            print(f"  Current Price: {current_price}")
            print(f"  Unrealized PnL: ${unrealized_pnl:.2f}")
            print(f"  Cumulative Realized PnL: ${cum_realized_pnl:.2f}")
            
            # Get all orders for this symbol
            symbol_orders = orders_by_symbol.get(symbol, [])
            print(f"\n  ORDERS FOR {symbol}: {len(symbol_orders)} orders")
            
            if not symbol_orders:
                print(f"  ⚠️  NO ORDERS FOUND FOR THIS POSITION!")
                continue
            
            # Categorize orders
            tp_orders = []
            sl_orders = []
            other_orders = []
            
            for order in symbol_orders:
                order_type = order.get('orderType', '')
                order_side = order.get('side', '')
                trigger_price = Decimal(order.get('triggerPrice', '0'))
                price = Decimal(order.get('price', '0'))
                stop_order_type = order.get('stopOrderType', '')
                order_link_id = order.get('orderLinkId', '')
                order_id = order.get('orderId', '')
                qty = Decimal(order.get('qty', '0'))
                leaves_qty = Decimal(order.get('leavesQty', '0'))
                cum_exec_qty = Decimal(order.get('cumExecQty', '0'))
                order_status = order.get('orderStatus', '')
                created_time = order.get('createdTime', '')
                
                # Determine effective price for comparison
                effective_price = trigger_price if trigger_price > 0 else price
                
                # Classify order as TP or SL
                is_tp = False
                is_sl = False
                
                # Check by order type
                if order_type in ['TakeProfit', 'MarketIfTouched']:
                    is_tp = True
                elif order_type in ['StopLoss', 'Stop', 'StopMarket']:
                    is_sl = True
                elif order_type == 'Limit' and effective_price > 0 and current_price:
                    # For limit orders, check price relative to current
                    if side == 'Buy':  # Long position
                        if order_side == 'Sell' and effective_price > current_price:
                            is_tp = True
                        elif order_side == 'Sell' and effective_price < current_price:
                            is_sl = True
                    else:  # Short position
                        if order_side == 'Buy' and effective_price < current_price:
                            is_tp = True
                        elif order_side == 'Buy' and effective_price > current_price:
                            is_sl = True
                
                # Also check by naming convention
                order_link_upper = order_link_id.upper()
                if any(x in order_link_upper for x in ['TP', 'TAKE', 'PROFIT']):
                    is_tp = True
                elif any(x in order_link_upper for x in ['SL', 'STOP', 'LOSS']):
                    is_sl = True
                
                order_info = {
                    'order': order,
                    'order_type': order_type,
                    'order_side': order_side,
                    'trigger_price': trigger_price,
                    'price': price,
                    'effective_price': effective_price,
                    'qty': qty,
                    'leaves_qty': leaves_qty,
                    'cum_exec_qty': cum_exec_qty,
                    'order_status': order_status,
                    'order_link_id': order_link_id,
                    'order_id': order_id,
                    'stop_order_type': stop_order_type,
                    'created_time': created_time
                }
                
                if is_tp:
                    tp_orders.append(order_info)
                elif is_sl:
                    sl_orders.append(order_info)
                else:
                    other_orders.append(order_info)
            
            # Display TP orders
            if tp_orders:
                print(f"\n  TAKE PROFIT ORDERS ({len(tp_orders)}):")
                tp_orders.sort(key=lambda x: x['effective_price'], reverse=(side == 'Buy'))
                for i, tp in enumerate(tp_orders, 1):
                    print(f"    TP{i}:")
                    print(f"      Type: {tp['order_type']}")
                    print(f"      Side: {tp['order_side']}")
                    print(f"      Price: {tp['effective_price']} (trigger: {tp['trigger_price']}, limit: {tp['price']})")
                    print(f"      Quantity: {tp['qty']} (leaves: {tp['leaves_qty']}, filled: {tp['cum_exec_qty']})")
                    print(f"      Status: {tp['order_status']}")
                    print(f"      OrderLinkId: {tp['order_link_id']}")
                    print(f"      OrderId: {tp['order_id']}")
                    if tp['stop_order_type']:
                        print(f"      StopOrderType: {tp['stop_order_type']}")
                    print(f"      Created: {tp['created_time']}")
            else:
                print(f"\n  ⚠️  NO TAKE PROFIT ORDERS FOUND!")
            
            # Display SL orders
            if sl_orders:
                print(f"\n  STOP LOSS ORDERS ({len(sl_orders)}):")
                sl_orders.sort(key=lambda x: x['effective_price'], reverse=(side == 'Sell'))
                for i, sl in enumerate(sl_orders, 1):
                    print(f"    SL{i}:")
                    print(f"      Type: {sl['order_type']}")
                    print(f"      Side: {sl['order_side']}")
                    print(f"      Price: {sl['effective_price']} (trigger: {sl['trigger_price']}, limit: {sl['price']})")
                    print(f"      Quantity: {sl['qty']} (leaves: {sl['leaves_qty']}, filled: {sl['cum_exec_qty']})")
                    print(f"      Status: {sl['order_status']}")
                    print(f"      OrderLinkId: {sl['order_link_id']}")
                    print(f"      OrderId: {sl['order_id']}")
                    if sl['stop_order_type']:
                        print(f"      StopOrderType: {sl['stop_order_type']}")
                    print(f"      Created: {sl['created_time']}")
            else:
                print(f"\n  ⚠️  NO STOP LOSS ORDERS FOUND!")
            
            # Display other orders
            if other_orders:
                print(f"\n  OTHER/UNCLASSIFIED ORDERS ({len(other_orders)}):")
                for i, other in enumerate(other_orders, 1):
                    print(f"    Order {i}:")
                    print(f"      Type: {other['order_type']}")
                    print(f"      Side: {other['order_side']}")
                    print(f"      Price: {other['effective_price']} (trigger: {other['trigger_price']}, limit: {other['price']})")
                    print(f"      Quantity: {other['qty']} (leaves: {other['leaves_qty']}, filled: {other['cum_exec_qty']})")
                    print(f"      Status: {other['order_status']}")
                    print(f"      OrderLinkId: {other['order_link_id']}")
                    print(f"      OrderId: {other['order_id']}")
                    if other['stop_order_type']:
                        print(f"      StopOrderType: {other['stop_order_type']}")
                    print(f"      Created: {other['created_time']}")
            
            # Summary
            print(f"\n  SUMMARY:")
            total_tp_qty = sum(tp['qty'] for tp in tp_orders)
            total_sl_qty = sum(sl['qty'] for sl in sl_orders)
            print(f"    Position Size: {size}")
            print(f"    Total TP Quantity: {total_tp_qty} ({len(tp_orders)} orders)")
            print(f"    Total SL Quantity: {total_sl_qty} ({len(sl_orders)} orders)")
            
            if total_tp_qty != size:
                print(f"    ⚠️  TP quantity mismatch! Expected: {size}, Found: {total_tp_qty}")
            if total_sl_qty != size:
                print(f"    ⚠️  SL quantity mismatch! Expected: {size}, Found: {total_sl_qty}")
        
        print(f"\n{'='*80}")

def main():
    """Main function"""
    print("Comprehensive Order Format Check")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check main account
    if BYBIT_API_KEY and BYBIT_API_SECRET:
        # Use synchronous client directly since we're not using async methods
        from pybit.unified_trading import HTTP
        client = HTTP(
            api_key=BYBIT_API_KEY,
            api_secret=BYBIT_API_SECRET,
            testnet=USE_TESTNET
        )
        checker = OrderFormatChecker(client, "MAIN ACCOUNT")
        checker.analyze_positions_and_orders()
    
    # Check mirror account
    if BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
        from pybit.unified_trading import HTTP
        client2 = HTTP(
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2,
            testnet=USE_TESTNET
        )
        checker2 = OrderFormatChecker(client2, "MIRROR ACCOUNT")
        checker2.analyze_positions_and_orders()
    
    print("\nAnalysis complete!")

if __name__ == "__main__":
    main()