#!/usr/bin/env python3
"""
Test TP/SL detection in monitoring system
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_helpers import get_order_info, get_all_open_orders
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_order_detection():
    """Test how the monitoring system would detect TP/SL orders"""
    
    # Get all open orders
    all_orders = await get_all_open_orders()
    
    print(f"\nTotal open orders: {len(all_orders)}")
    print("\nAnalyzing order detection for monitoring:")
    print("="*80)
    
    # Group by symbol
    orders_by_symbol = {}
    for order in all_orders:
        symbol = order.get('symbol')
        if symbol not in orders_by_symbol:
            orders_by_symbol[symbol] = {
                'tp_orders': [],
                'sl_orders': [],
                'other_orders': []
            }
        
        # Analyze order
        order_side = order.get('side')
        stop_order_type = order.get('stopOrderType', '')
        trigger_direction = order.get('triggerDirection', 0)
        trigger_price = order.get('triggerPrice', '')
        reduce_only = order.get('reduceOnly', False)
        order_link_id = order.get('orderLinkId', '')
        order_status = order.get('orderStatus', '')
        
        # Detection logic (mimics what monitor should do)
        is_tp = False
        is_sl = False
        detection_method = ""
        
        # Method 1: stopOrderType (Bybit uses "Stop" for both TP and SL)
        if stop_order_type == 'Stop' and trigger_price and reduce_only:
            if trigger_direction == 1:
                is_tp = True
                detection_method = "stopOrderType='Stop' + triggerDirection=1"
            elif trigger_direction == 2:
                is_sl = True
                detection_method = "stopOrderType='Stop' + triggerDirection=2"
        
        # Method 2: orderLinkId patterns (fallback)
        elif '_TP' in order_link_id.upper():
            is_tp = True
            detection_method = "orderLinkId pattern '_TP'"
        elif '_SL' in order_link_id.upper():
            is_sl = True
            detection_method = "orderLinkId pattern '_SL'"
        
        # Store categorized order
        order_info = {
            'orderId': order.get('orderId', '')[:8] + '...',
            'orderLinkId': order_link_id,
            'triggerPrice': trigger_price,
            'qty': order.get('qty', ''),
            'status': order_status,
            'detection': detection_method
        }
        
        if is_tp:
            orders_by_symbol[symbol]['tp_orders'].append(order_info)
        elif is_sl:
            orders_by_symbol[symbol]['sl_orders'].append(order_info)
        else:
            orders_by_symbol[symbol]['other_orders'].append(order_info)
    
    # Display results
    for symbol, orders in orders_by_symbol.items():
        tp_count = len(orders['tp_orders'])
        sl_count = len(orders['sl_orders'])
        other_count = len(orders['other_orders'])
        
        if tp_count > 0 or sl_count > 0:
            print(f"\n{symbol}:")
            print(f"  ✅ TP Orders: {tp_count}")
            for tp in orders['tp_orders'][:2]:  # Show first 2
                print(f"    - {tp['orderLinkId']}: {tp['qty']} @ {tp['triggerPrice']}")
                print(f"      Detection: {tp['detection']}")
            if tp_count > 2:
                print(f"    ... and {tp_count - 2} more")
            
            print(f"  ✅ SL Orders: {sl_count}")
            for sl in orders['sl_orders'][:2]:
                print(f"    - {sl['orderLinkId']}: {sl['qty']} @ {sl['triggerPrice']}")
                print(f"      Detection: {sl['detection']}")
            
            if other_count > 0:
                print(f"  ℹ️  Other Orders: {other_count}")
    
    # Summary
    print("\n" + "="*80)
    print("Detection Summary:")
    print(f"  - Orders using stopOrderType='Stop': Most common for TP/SL")
    print(f"  - triggerDirection=1: Take Profit (price rises)")
    print(f"  - triggerDirection=2: Stop Loss (price falls)")
    print(f"  - orderLinkId patterns: Backup detection method")
    
    # Test specific order lookup
    print("\n" + "="*80)
    print("Testing individual order lookup (as monitor would do):")
    
    # Find a TP order to test
    test_order_id = None
    for order in all_orders:
        if order.get('stopOrderType') == 'Stop' and order.get('triggerDirection') == 1:
            test_order_id = order.get('orderId')
            break
    
    if test_order_id:
        print(f"\nTesting get_order_info for TP order: {test_order_id[:8]}...")
        order_info = await get_order_info(order.get('symbol'), test_order_id)
        if order_info:
            print(f"  ✅ Order found:")
            print(f"    Status: {order_info.get('orderStatus')}")
            print(f"    Type: {order_info.get('orderType')}")
            print(f"    StopOrderType: {order_info.get('stopOrderType')}")
            print(f"    TriggerDirection: {order_info.get('triggerDirection')}")
        else:
            print(f"  ❌ Order not found")

if __name__ == "__main__":
    asyncio.run(test_order_detection())