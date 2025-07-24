#!/usr/bin/env python3
"""
Check why INJUSDT is not detecting limit orders
"""

import pickle
from pybit.unified_trading import HTTP
import os
from dotenv import load_dotenv

load_dotenv()

# Load bot data
with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
    bot_data = pickle.load(f)

# Check INJUSDT monitor data
chat_id = 5634913742
chat_data = bot_data.get('chat_data', {}).get(chat_id, {})
monitors = chat_data.get('active_monitor_task_data_v2', {})

print('=' * 80)
print('INJUSDT MONITOR DATA CHECK')
print('=' * 80)

for key, data in monitors.items():
    if 'INJUSDT' in key:
        print(f'\nMonitor Key: {key}')
        print(f'Symbol: {data.get("symbol")}')
        print(f'Approach: {data.get("approach")}')
        print(f'Limit IDs stored: {data.get("conservative_limit_order_ids", [])}')
        print(f'TP IDs stored: {data.get("conservative_tp_order_ids", [])}')
        print(f'SL ID stored: {data.get("conservative_sl_order_id")}')

# Check actual orders on Bybit
session = HTTP(
    testnet=os.getenv('USE_TESTNET', 'false').lower() == 'true',
    api_key=os.getenv('BYBIT_API_KEY'),
    api_secret=os.getenv('BYBIT_API_SECRET')
)

print('\n\n' + '=' * 80)
print('ACTUAL INJUSDT ORDERS ON BYBIT')
print('=' * 80)

response = session.get_open_orders(category='linear', symbol='INJUSDT', limit=50)
if response['retCode'] == 0:
    orders = response['result']['list']
    
    # Categorize orders
    limit_orders = []
    tp_orders = []
    sl_orders = []
    
    for order in orders:
        order_type = order.get('orderType', '')
        stop_order_type = order.get('stopOrderType', '')
        reduce_only = order.get('reduceOnly', False)
        order_link_id = order.get('orderLinkId', '')
        
        if order_type == 'Limit' and not reduce_only:
            limit_orders.append(order)
        elif stop_order_type == 'TakeProfit' or 'TP' in order_link_id:
            tp_orders.append(order)
        elif stop_order_type == 'StopLoss' or 'SL' in order_link_id:
            sl_orders.append(order)
    
    print(f'\nLimit Orders (entry): {len(limit_orders)}')
    for i, o in enumerate(limit_orders):
        print(f'  {i+1}. ID: {o["orderId"]}')
        print(f'     Price: ${o["price"]}')
        print(f'     Qty: {o["qty"]}')
        print(f'     Status: {o["orderStatus"]}')
        print(f'     LinkID: {o.get("orderLinkId", "N/A")}')
    
    print(f'\nTP Orders: {len(tp_orders)}')
    for i, o in enumerate(tp_orders):
        print(f'  TP{i+1}: {o["orderId"][:8]}... @ ${o.get("triggerPrice", o.get("price"))}')
    
    print(f'\nSL Orders: {len(sl_orders)}')
    for o in sl_orders:
        print(f'  SL: {o["orderId"][:8]}... @ ${o.get("triggerPrice", o.get("price"))}')

# Check main chat_data for LIMIT_ORDER_IDS
print('\n\n' + '=' * 80)
print('CHAT DATA CHECK')
print('=' * 80)

from config.constants import LIMIT_ORDER_IDS, CONSERVATIVE_TP_ORDER_IDS, CONSERVATIVE_SL_ORDER_ID

limit_ids_in_chat = chat_data.get(LIMIT_ORDER_IDS, [])
tp_ids_in_chat = chat_data.get(CONSERVATIVE_TP_ORDER_IDS, [])
sl_id_in_chat = chat_data.get(CONSERVATIVE_SL_ORDER_ID)

print(f'LIMIT_ORDER_IDS in chat_data: {limit_ids_in_chat}')
print(f'CONSERVATIVE_TP_ORDER_IDS in chat_data: {len(tp_ids_in_chat)} orders')
print(f'CONSERVATIVE_SL_ORDER_ID in chat_data: {sl_id_in_chat}')

print('\n\n' + '=' * 80)
print('DIAGNOSIS')
print('=' * 80)

if limit_orders and not limit_ids_in_chat:
    print('❌ PROBLEM: Limit orders exist on Bybit but not in chat_data!')
    print('   The monitor is checking chat_data[LIMIT_ORDER_IDS] which is empty')
    print('   But the actual limit order IDs are stored in active_monitor_task_data_v2')
    print('\n   SOLUTION: The monitor needs to check its own monitor data, not chat_data')
elif not limit_orders:
    print('✅ No limit orders found on Bybit - they may have been filled')
else:
    print('✅ Limit orders are properly tracked')