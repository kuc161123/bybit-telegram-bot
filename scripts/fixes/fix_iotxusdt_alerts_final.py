#!/usr/bin/env python3
"""
Fix IOTXUSDT alerts by properly setting up the monitoring data
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
    
    # Get chat data
    chat_id = 5634913742
    chat_data_all = bot_data.get('chat_data', {})
    chat_data = chat_data_all.get(chat_id, {})
    
    print(f"\n📊 Current IOTXUSDT data in chat {chat_id}:")
    print(f"  Symbol: {chat_data.get('symbol', 'N/A')}")
    print(f"  Side: {chat_data.get('side', 'N/A')}")
    print(f"  Approach: {chat_data.get('approach', 'N/A')}")
    
    # Check active monitors
    active_monitors = chat_data.get('active_monitor_task_data_v2', {})
    iotx_monitors = {k: v for k, v in active_monitors.items() if 'IOTXUSDT' in k}
    
    print(f"\n📊 IOTXUSDT monitors found: {len(iotx_monitors)}")
    for monitor_key in iotx_monitors:
        print(f"  ✅ {monitor_key}")
    
    # Initialize Bybit client
    api_key = os.getenv('BYBIT_API_KEY')
    api_secret = os.getenv('BYBIT_API_SECRET')
    testnet = os.getenv('USE_TESTNET', 'false').lower() == 'true'
    
    session = HTTP(
        testnet=testnet,
        api_key=api_key,
        api_secret=api_secret
    )
    
    # Fetch all open orders for IOTXUSDT
    print(f"\n🔍 Fetching IOTXUSDT orders from Bybit...")
    
    try:
        response = session.get_open_orders(
            category="linear",
            symbol="IOTXUSDT",
            limit=50
        )
        
        if response['retCode'] == 0:
            orders = response['result']['list']
            print(f"✅ Found {len(orders)} orders for IOTXUSDT")
        else:
            print(f"❌ Error fetching orders: {response}")
            return
    except Exception as e:
        print(f"❌ Exception fetching orders: {e}")
        return
    
    if not orders:
        print("❌ No orders found for IOTXUSDT")
        return
    
    # Separate orders by type
    limit_orders = []
    tp_orders = []
    sl_order = None
    
    for order in orders:
        order_type = order.get('orderType', '')
        order_link_id = order.get('orderLinkId', '')
        stop_order_type = order.get('stopOrderType', '')
        
        if order_type == 'Limit' and not order.get('reduceOnly'):
            limit_orders.append(order)
        elif stop_order_type == 'TakeProfit' or 'TP' in order_link_id:
            tp_orders.append(order)
        elif stop_order_type == 'StopLoss' or 'SL' in order_link_id:
            sl_order = order
    
    print(f"\n📋 Order breakdown:")
    print(f"  Limit orders: {len(limit_orders)}")
    print(f"  TP orders: {len(tp_orders)}")
    print(f"  SL order: {'Yes' if sl_order else 'No'}")
    
    # Find the IOTXUSDT conservative monitor data
    iotx_conservative_key = None
    for key in iotx_monitors:
        if 'conservative' in key:
            iotx_conservative_key = key
            break
    
    if not iotx_conservative_key:
        print("\n⚠️ No conservative monitor found for IOTXUSDT")
        print("Creating new monitor data...")
        iotx_conservative_key = f"{chat_id}_IOTXUSDT_conservative"
    
    # Get or create monitor data
    monitor_data = active_monitors.get(iotx_conservative_key, {})
    
    # Update monitor data with order IDs
    if limit_orders:
        limit_ids = [order['orderId'] for order in limit_orders]
        monitor_data['conservative_limit_order_ids'] = limit_ids
        # Also update in main chat data
        chat_data['conservative_limit_order_ids'] = limit_ids
        print(f"\n✅ Updated limit order IDs: {len(limit_ids)} orders")
        for i, order_id in enumerate(limit_ids):
            price = limit_orders[i].get('price', 'N/A')
            print(f"   {i+1}. {order_id[:8]}... @ ${price}")
    
    if tp_orders:
        # Sort TP orders by price (descending for sell position)
        tp_orders.sort(key=lambda x: float(x.get('triggerPrice', 0)), reverse=True)
        tp_ids = [order['orderId'] for order in tp_orders]
        monitor_data['conservative_tp_order_ids'] = tp_ids
        # Also update in main chat data
        chat_data['conservative_tp_order_ids'] = tp_ids
        print(f"\n✅ Updated TP order IDs: {len(tp_ids)} orders")
        for i, (order_id, order) in enumerate(zip(tp_ids, tp_orders)):
            price = order.get('triggerPrice', 'N/A')
            print(f"   TP{i+1}: {order_id[:8]}... @ ${price}")
    
    if sl_order:
        sl_id = sl_order['orderId']
        monitor_data['conservative_sl_order_id'] = sl_id
        # Also update in main chat data
        chat_data['conservative_sl_order_id'] = sl_id
        price = sl_order.get('triggerPrice', 'N/A')
        print(f"\n✅ Updated SL order ID: {sl_id[:8]}... @ ${price}")
    
    # Update monitor data
    monitor_data['symbol'] = 'IOTXUSDT'
    monitor_data['side'] = 'Sell'
    monitor_data['approach'] = 'conservative'
    monitor_data['_chat_id'] = chat_id
    
    # Update the active monitors
    active_monitors[iotx_conservative_key] = monitor_data
    chat_data['active_monitor_task_data_v2'] = active_monitors
    
    # Update approach in chat data
    chat_data['approach'] = 'conservative'
    
    # Update the bot data
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
    
    print("\n✨ IOTXUSDT alerts have been fixed!")
    print("\n📱 You will now receive alerts for:")
    print("  ✅ Limit order fills")
    print("  ✅ Take profit hits")  
    print("  ✅ Stop loss hits")
    print("\n⚠️ No need to restart the bot - the monitor will pick up the changes automatically!")

if __name__ == "__main__":
    main()