#!/usr/bin/env python3
"""
Fix IOTXUSDT conservative position limit order alerts
"""

import pickle
import os
from datetime import datetime
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

load_dotenv()

def main():
    # Load the bot data
    persistence_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    
    try:
        with open(persistence_file, 'rb') as f:
            bot_data = pickle.load(f)
        print("✅ Loaded bot data")
    except Exception as e:
        print(f"❌ Error loading bot data: {e}")
        return
    
    # Initialize Bybit client
    api_key = os.getenv('BYBIT_API_KEY')
    api_secret = os.getenv('BYBIT_API_SECRET')
    testnet = os.getenv('USE_TESTNET', 'false').lower() == 'true'
    
    session = HTTP(
        testnet=testnet,
        api_key=api_key,
        api_secret=api_secret
    )
    
    # Check IOTXUSDT position
    print("\n🔍 Checking IOTXUSDT position...")
    try:
        pos_response = session.get_positions(
            category="linear",
            symbol="IOTXUSDT"
        )
        
        if pos_response['retCode'] == 0:
            positions = pos_response['result']['list']
            if positions and float(positions[0].get('size', 0)) > 0:
                pos = positions[0]
                print(f"✅ Found IOTXUSDT position: {pos['side']} {pos['size']} @ {pos['avgPrice']}")
            else:
                print("❌ No active IOTXUSDT position found")
                return
        else:
            print(f"❌ Error fetching position: {pos_response}")
            return
    except Exception as e:
        print(f"❌ Exception fetching position: {e}")
        return
    
    # Fetch all orders for IOTXUSDT
    print("\n🔍 Fetching IOTXUSDT orders...")
    try:
        order_response = session.get_open_orders(
            category="linear",
            symbol="IOTXUSDT",
            limit=50
        )
        
        if order_response['retCode'] == 0:
            orders = order_response['result']['list']
            print(f"✅ Found {len(orders)} orders for IOTXUSDT")
        else:
            print(f"❌ Error fetching orders: {order_response}")
            return
    except Exception as e:
        print(f"❌ Exception fetching orders: {e}")
        return
    
    # Categorize orders
    limit_orders = []
    tp_orders = []
    sl_order = None
    
    for order in orders:
        order_type = order.get('orderType', '')
        order_link_id = order.get('orderLinkId', '')
        stop_order_type = order.get('stopOrderType', '')
        reduce_only = order.get('reduceOnly', False)
        
        # Check for limit orders (entry orders, not reduce-only)
        if order_type == 'Limit' and not reduce_only:
            limit_orders.append(order)
        # Check for TP orders
        elif stop_order_type == 'TakeProfit' or 'TP' in order_link_id or 'CONS_TP' in order_link_id:
            tp_orders.append(order)
        # Check for SL orders
        elif stop_order_type == 'StopLoss' or 'SL' in order_link_id or 'CONS_SL' in order_link_id:
            sl_order = order
    
    print(f"\n📋 Order breakdown:")
    print(f"  Limit orders (entry): {len(limit_orders)}")
    for i, order in enumerate(limit_orders):
        print(f"    {i+1}. {order['side']} {order['qty']} @ ${order['price']}")
    
    print(f"  TP orders: {len(tp_orders)}")
    tp_orders_sorted = sorted(tp_orders, key=lambda x: float(x.get('triggerPrice', 0)), reverse=True)  # Descending for buy
    for i, order in enumerate(tp_orders_sorted):
        print(f"    TP{i+1}: {order['side']} {order['qty']} @ ${order.get('triggerPrice', 'N/A')}")
    
    print(f"  SL order: {'Yes' if sl_order else 'No'}")
    if sl_order:
        print(f"    {sl_order['side']} {sl_order['qty']} @ ${sl_order.get('triggerPrice', 'N/A')}")
    
    # Setup monitoring data
    chat_id = 5634913742
    chat_data_all = bot_data.get('chat_data', {})
    chat_data = chat_data_all.get(chat_id, {})
    
    # Get or create active_monitor_task_data_v2
    active_monitors = chat_data.get('active_monitor_task_data_v2', {})
    
    # Find the correct monitor key for IOTXUSDT
    monitor_key = None
    for key, monitor_data in active_monitors.items():
        if isinstance(monitor_data, dict) and monitor_data.get('symbol') == 'IOTXUSDT':
            monitor_key = key
            print(f"\n✅ Found existing monitor: {key}")
            break
    
    # If no monitor found, create one
    if not monitor_key:
        monitor_key = f"{chat_id}_IOTXUSDT_conservative"
        print(f"\n📝 Creating new monitor: {monitor_key}")
    
    # Get or create monitor data
    monitor_data = active_monitors.get(monitor_key, {})
    monitor_data.update({
        'symbol': 'IOTXUSDT',
        'side': 'Buy',  # Based on bot logs showing Buy position
        'approach': 'conservative',
        '_chat_id': chat_id
    })
    
    # Update order tracking
    if limit_orders:
        limit_ids = [order['orderId'] for order in limit_orders]
        monitor_data['conservative_limit_order_ids'] = limit_ids
        print(f"\n✅ Updated limit order tracking: {len(limit_ids)} orders")
        for i, order_id in enumerate(limit_ids):
            print(f"   {i+1}. {order_id[:8]}...")
    else:
        print(f"\n⚠️  No limit orders found for IOTXUSDT")
    
    if tp_orders:
        tp_ids = [order['orderId'] for order in tp_orders_sorted]
        monitor_data['conservative_tp_order_ids'] = tp_ids
        print(f"\n✅ Updated TP order tracking: {len(tp_ids)} orders")
        for i, order_id in enumerate(tp_ids):
            print(f"   TP{i+1}: {order_id[:8]}...")
    
    if sl_order:
        sl_id = sl_order['orderId']
        monitor_data['conservative_sl_order_id'] = sl_id
        print(f"\n✅ Updated SL order tracking: {sl_id[:8]}...")
    
    # Update the data structures
    active_monitors[monitor_key] = monitor_data
    chat_data['active_monitor_task_data_v2'] = active_monitors
    
    # Update bot data
    chat_data_all[chat_id] = chat_data
    bot_data['chat_data'] = chat_data_all
    
    # Create backup
    backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{persistence_file}"
    os.rename(persistence_file, backup_file)
    print(f"\n📦 Created backup: {backup_file}")
    
    # Save updated data
    with open(persistence_file, 'wb') as f:
        pickle.dump(bot_data, f)
    print(f"✅ Saved updated bot data")
    
    print("\n" + "="*60)
    print("✨ IOTXUSDT LIMIT ORDER ALERTS FIXED!")
    print("="*60)
    
    print("\n🔔 Alert Status:")
    if limit_orders:
        print(f"  ✅ Limit fill alerts: ENABLED ({len(limit_orders)} orders)")
    else:
        print(f"  ⚠️  Limit fill alerts: No limit orders found")
    
    if tp_orders:
        print(f"  ✅ TP hit alerts: ENABLED ({len(tp_orders)} orders)")
    else:
        print(f"  ⚠️  TP hit alerts: No TP orders found")
    
    if sl_order:
        print(f"  ✅ SL hit alerts: ENABLED")
    else:
        print(f"  ⚠️  SL hit alerts: No SL order found")
    
    print("\n📌 IMPORTANT:")
    print("  • The bot must be running for alerts to work")
    print("  • Start with: ./run_main.sh or python main.py")
    print("  • Alerts will trigger when orders are filled")
    
    if limit_orders:
        print("\n💡 Limit Order Alert Info:")
        print("  • You'll receive alerts when limit orders fill")
        print("  • This increases your position size")
        print("  • Auto-rebalancer may adjust TP/SL quantities")
    else:
        print("\n💡 No Limit Orders Found:")
        print("  • This position may not have any pending limit orders")
        print("  • If you add limit orders later, run this script again")
        print("  • Or restart the bot to detect new orders")

if __name__ == "__main__":
    main()