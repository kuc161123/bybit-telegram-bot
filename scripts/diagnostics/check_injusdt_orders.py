#!/usr/bin/env python3
"""
Check INJUSDT orders to diagnose why startup rebalancer can't find TP orders.
"""
import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import required modules
from clients.bybit_helpers import bybit_client


async def check_injusdt_orders():
    """Check all open orders for INJUSDT and analyze them."""
    try:
        # Get open orders for INJUSDT
        response = bybit_client.get_open_orders(
            category="linear",
            symbol="INJUSDT",
            limit=50
        )
        
        if response['retCode'] != 0:
            logger.error(f"Failed to get orders: {response['retMsg']}")
            return
            
        orders = response['result']['list']
        
        print(f"\n{'='*80}")
        print(f"INJUSDT OPEN ORDERS ANALYSIS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")
        print(f"Total orders found: {len(orders)}")
        print(f"{'='*80}\n")
        
        # Categorize orders
        tp_orders = []
        sl_orders = []
        limit_orders = []
        other_orders = []
        
        for order in orders:
            # Print detailed order information
            print(f"Order ID: {order.get('orderId')}")
            print(f"  OrderLinkId: {order.get('orderLinkId', 'N/A')}")
            print(f"  Side: {order.get('side')}")
            print(f"  OrderType: {order.get('orderType')}")
            print(f"  StopOrderType: {order.get('stopOrderType', 'N/A')}")
            print(f"  ReduceOnly: {order.get('reduceOnly', False)}")
            print(f"  Quantity: {order.get('qty')}")
            print(f"  Price: {order.get('price', 'N/A')}")
            print(f"  TriggerPrice: {order.get('triggerPrice', 'N/A')}")
            print(f"  TriggerBy: {order.get('triggerBy', 'N/A')}")
            print(f"  OrderStatus: {order.get('orderStatus')}")
            print(f"  CreatedTime: {order.get('createdTime')}")
            
            # Analyze order type
            order_link_id = order.get('orderLinkId', '')
            stop_order_type = order.get('stopOrderType', '')
            reduce_only = order.get('reduceOnly', False)
            order_type = order.get('orderType', '')
            
            # Check for Conservative markers
            has_cons_marker = any(marker in order_link_id for marker in ['BOT_CONS', 'CONS_', '_CONS'])
            has_fast_marker = any(marker in order_link_id for marker in ['BOT_FAST', 'FAST_', '_FAST'])
            
            print(f"  Has Conservative marker: {has_cons_marker}")
            print(f"  Has Fast marker: {has_fast_marker}")
            
            # Identify order category
            if stop_order_type == 'TakeProfit' or (reduce_only and 'TP' in order_link_id):
                tp_orders.append(order)
                print(f"  → Identified as: TAKE PROFIT order")
            elif stop_order_type == 'StopLoss' or (reduce_only and 'SL' in order_link_id):
                sl_orders.append(order)
                print(f"  → Identified as: STOP LOSS order")
            elif order_type == 'Limit' and not reduce_only:
                limit_orders.append(order)
                print(f"  → Identified as: LIMIT ENTRY order")
            else:
                other_orders.append(order)
                print(f"  → Identified as: OTHER order type")
            
            print("-" * 40)
        
        # Summary
        print(f"\n{'='*80}")
        print("ORDER SUMMARY:")
        print(f"{'='*80}")
        print(f"Take Profit orders: {len(tp_orders)}")
        print(f"Stop Loss orders: {len(sl_orders)}")
        print(f"Limit Entry orders: {len(limit_orders)}")
        print(f"Other orders: {len(other_orders)}")
        
        # Analyze TP orders for Conservative pattern
        if tp_orders:
            print(f"\n{'='*80}")
            print("TAKE PROFIT ORDERS ANALYSIS:")
            print(f"{'='*80}")
            
            tp_quantities = []
            for tp in tp_orders:
                qty = Decimal(tp.get('qty', '0'))
                tp_quantities.append(qty)
                print(f"TP Order: {tp.get('orderId')}")
                print(f"  Quantity: {qty}")
                print(f"  TriggerPrice: {tp.get('triggerPrice')}")
                print(f"  OrderLinkId: {tp.get('orderLinkId')}")
            
            # Check if quantities match Conservative pattern (85%, 5%, 5%, 5%)
            if len(tp_quantities) == 4:
                total_qty = sum(tp_quantities)
                percentages = [(qty / total_qty * 100) for qty in sorted(tp_quantities, reverse=True)]
                print(f"\nTP Distribution: {[f'{p:.1f}%' for p in percentages]}")
                
                # Check if it matches Conservative pattern
                expected = [85, 5, 5, 5]
                matches_conservative = all(abs(p - e) < 1 for p, e in zip(percentages, expected))
                print(f"Matches Conservative pattern (85%, 5%, 5%, 5%): {matches_conservative}")
            else:
                print(f"\nNumber of TP orders ({len(tp_quantities)}) doesn't match Conservative pattern (expected 4)")
        
        # Check for startup rebalancer detection issues
        print(f"\n{'='*80}")
        print("STARTUP REBALANCER DETECTION ANALYSIS:")
        print(f"{'='*80}")
        
        # Look for orders that should be detected as Conservative
        conservative_orders = [o for o in orders if any(marker in o.get('orderLinkId', '') for marker in ['BOT_CONS', 'CONS_'])]
        print(f"Orders with Conservative markers: {len(conservative_orders)}")
        
        if conservative_orders:
            print("\nConservative orders found:")
            for order in conservative_orders:
                print(f"  - {order.get('orderId')}: {order.get('orderLinkId')} (Type: {order.get('stopOrderType', order.get('orderType'))})")
        
        # Check what the rebalancer might be looking for
        print(f"\n{'='*80}")
        print("REBALANCER DETECTION CRITERIA:")
        print(f"{'='*80}")
        print("The startup rebalancer looks for:")
        print("1. Orders with reduceOnly=True")
        print("2. Orders with stopOrderType='TakeProfit'")
        print("3. Orders with Conservative markers in orderLinkId")
        print("\nOrders matching criteria 1 & 2:")
        
        rebalancer_detected = [
            o for o in orders 
            if o.get('reduceOnly') and o.get('stopOrderType') == 'TakeProfit'
        ]
        print(f"Found: {len(rebalancer_detected)} orders")
        
        if not rebalancer_detected:
            print("\n⚠️  No orders found matching rebalancer detection criteria!")
            print("This explains why the startup rebalancer can't find TP orders.")
            
            # Check what might be wrong
            print("\nPossible issues:")
            if not any(o.get('reduceOnly') for o in tp_orders):
                print("- TP orders don't have reduceOnly=True")
            if not any(o.get('stopOrderType') == 'TakeProfit' for o in tp_orders):
                print("- TP orders don't have stopOrderType='TakeProfit'")
            if not any('CONS' in o.get('orderLinkId', '') for o in tp_orders):
                print("- TP orders don't have Conservative markers in orderLinkId")
        
        # Also check position status
        print(f"\n{'='*80}")
        print("CHECKING POSITION STATUS:")
        print(f"{'='*80}")
        
        position_response = bybit_client.get_positions(
            category="linear",
            symbol="INJUSDT"
        )
        
        if position_response['retCode'] == 0:
            positions = position_response['result']['list']
            if positions:
                for pos in positions:
                    if float(pos.get('size', '0')) > 0:
                        print(f"Position found:")
                        print(f"  Symbol: {pos.get('symbol')}")
                        print(f"  Side: {pos.get('side')}")
                        print(f"  Size: {pos.get('size')}")
                        print(f"  Avg Price: {pos.get('avgPrice')}")
                        print(f"  P&L: {pos.get('unrealisedPnl')}")
            else:
                print("No active position found for INJUSDT")
        
    except Exception as e:
        logger.error(f"Error checking orders: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(check_injusdt_orders())