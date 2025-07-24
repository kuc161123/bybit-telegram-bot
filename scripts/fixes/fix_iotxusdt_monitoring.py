#!/usr/bin/env python3
"""
Fix IOTXUSDT monitoring by reconstructing the chat data with order IDs
"""

import asyncio
import pickle
import os
from datetime import datetime
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

load_dotenv()

async def fix_iotxusdt_monitoring():
    """Reconstruct IOTXUSDT monitoring data"""
    
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
    chat_id = "5634913742"
    chat_data_all = bot_data.get('chat_data', {})
    chat_data = chat_data_all.get(int(chat_id), {})
    
    print(f"\n📊 Current IOTXUSDT monitoring status:")
    
    # Check for IOTXUSDT monitor
    monitor_key = f"{chat_id}_IOTXUSDT_conservative"
    monitor_tasks = bot_data.get('monitor_tasks', {})
    
    if monitor_key in monitor_tasks:
        print(f"✅ Monitor found: {monitor_key}")
        
        # Get current chat data for this position
        conservative_limit_ids = chat_data.get('conservative_limit_order_ids', [])
        conservative_tp_ids = chat_data.get('conservative_tp_order_ids', [])
        conservative_sl_id = chat_data.get('conservative_sl_order_id')
        
        print(f"\nCurrent order tracking:")
        print(f"  Limit orders: {len(conservative_limit_ids)} IDs")
        print(f"  TP orders: {len(conservative_tp_ids)} IDs")
        print(f"  SL order: {'Yes' if conservative_sl_id else 'No'}")
    else:
        print(f"❌ No monitor found for IOTXUSDT conservative")
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
        else:
            print(f"❌ Error fetching orders: {response}")
            return
    except Exception as e:
        print(f"❌ Exception fetching orders: {e}")
        return
    
    if not orders:
        print("❌ No orders found for IOTXUSDT")
        return
    
    print(f"✅ Found {len(orders)} orders for IOTXUSDT")
    
    # Separate orders by type
    limit_orders = []
    tp_orders = []
    sl_order = None
    
    for order in orders:
        order_type = order.get('orderType', '')
        order_link_id = order.get('orderLinkId', '')
        
        if order_type == 'Limit' and not order.get('reduceOnly'):
            limit_orders.append(order)
        elif 'TP' in order_link_id or (order.get('stopOrderType') == 'TakeProfit'):
            tp_orders.append(order)
        elif 'SL' in order_link_id or (order.get('stopOrderType') == 'StopLoss'):
            sl_order = order
    
    print(f"\n📋 Order breakdown:")
    print(f"  Limit orders: {len(limit_orders)}")
    print(f"  TP orders: {len(tp_orders)}")
    print(f"  SL order: {'Yes' if sl_order else 'No'}")
    
    # Update chat data with order IDs
    if limit_orders:
        limit_ids = [order['orderId'] for order in limit_orders]
        chat_data['conservative_limit_order_ids'] = limit_ids
        print(f"\n✅ Updated limit order IDs: {len(limit_ids)} orders")
        for i, order_id in enumerate(limit_ids):
            print(f"   {i+1}. {order_id[:8]}...")
    
    if tp_orders:
        # Sort TP orders by price
        tp_orders.sort(key=lambda x: float(x.get('triggerPrice', 0)), reverse=True)
        tp_ids = [order['orderId'] for order in tp_orders]
        chat_data['conservative_tp_order_ids'] = tp_ids
        print(f"\n✅ Updated TP order IDs: {len(tp_ids)} orders")
        for i, order_id in enumerate(tp_ids):
            print(f"   TP{i+1}: {order_id[:8]}...")
    
    if sl_order:
        sl_id = sl_order['orderId']
        chat_data['conservative_sl_order_id'] = sl_id
        print(f"\n✅ Updated SL order ID: {sl_id[:8]}...")
    
    # Add other required fields if missing
    if 'symbol' not in chat_data:
        chat_data['symbol'] = 'IOTXUSDT'
    if 'side' not in chat_data:
        chat_data['side'] = 'Sell'
    if 'approach' not in chat_data:
        chat_data['approach'] = 'conservative'
    
    # Update the bot data
    chat_data_all[int(chat_id)] = chat_data
    bot_data['chat_data'] = chat_data_all
    
    # Create backup
    backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{persistence_file}"
    os.rename(persistence_file, backup_file)
    print(f"\n📦 Created backup: {backup_file}")
    
    # Save updated data
    with open(persistence_file, 'wb') as f:
        pickle.dump(bot_data, f)
    print(f"✅ Saved updated bot data")
    
    print("\n✅ IOTXUSDT monitoring fixed!")
    print("🔄 Please restart the bot for changes to take effect")
    print("\nAfter restart, you will receive alerts for:")
    print("  • Limit order fills")
    print("  • TP hits")
    print("  • SL hits")

if __name__ == "__main__":
    asyncio.run(fix_iotxusdt_monitoring())