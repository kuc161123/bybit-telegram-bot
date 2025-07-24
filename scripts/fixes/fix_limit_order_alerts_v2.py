#!/usr/bin/env python3
"""
Fix limit order alerts for ALL conservative positions - Version 2
This version directly updates the persistence data with limit order IDs
"""
import asyncio
import logging
import pickle
import os
from decimal import Decimal
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import Bybit client
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the API call function from bybit_helpers
from clients.bybit_helpers import api_call_with_retry
from clients.bybit_client import bybit_client
from config.constants import LIMIT_ORDER_IDS, CONSERVATIVE_LIMITS_FILLED

async def fix_all_limit_order_alerts():
    """Fix limit order alerts for all conservative positions"""
    
    # Load persistence
    pickle_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    
    if not os.path.exists(pickle_file):
        logger.error(f"Persistence file not found: {pickle_file}")
        return
    
    try:
        with open(pickle_file, 'rb') as f:
            persistence_data = pickle.load(f)
            logger.info(f"Loaded persistence data")
    except Exception as e:
        logger.error(f"Error loading persistence: {e}")
        return
    
    # Get bot data and chat data
    bot_data = persistence_data.get('bot_data', {})
    chat_data_dict = persistence_data.get('chat_data', {})
    
    # Find all conservative monitors
    monitor_tasks = bot_data.get('monitor_tasks', {})
    conservative_monitors = []
    
    for key, monitor in monitor_tasks.items():
        if monitor.get('approach') == 'conservative' and monitor.get('active'):
            # Skip mirror monitors
            if 'mirror' not in key and monitor.get('account_type', 'primary') == 'primary':
                conservative_monitors.append({
                    'key': key,
                    'monitor': monitor,
                    'symbol': monitor.get('symbol'),
                    'chat_id': monitor.get('chat_id')
                })
                logger.info(f"Found conservative monitor: {key}")
    
    logger.info(f"\nFound {len(conservative_monitors)} conservative monitors to fix")
    
    # Fix each monitor
    fixed_count = 0
    for monitor_info in conservative_monitors:
        symbol = monitor_info['symbol']
        chat_id = monitor_info['chat_id']
        
        logger.info(f"\nProcessing {symbol}...")
        
        try:
            # Get open orders for this symbol
            response = await api_call_with_retry(
                lambda: bybit_client.get_open_orders(
                    category="linear",
                    symbol=symbol
                ),
                timeout=20
            )
            
            orders = []
            if response and response.get("retCode") == 0:
                orders = response.get("result", {}).get("list", [])
            
            logger.info(f"Found {len(orders)} open orders for {symbol}")
            
            # Find limit orders (not reduce-only)
            limit_orders = []
            for order in orders:
                if order.get('orderType') == 'Limit' and not order.get('reduceOnly', False):
                    limit_orders.append(order)
                    logger.info(f"  - Limit order: {order.get('orderId')[:8]}... at price {order.get('price')}")
            
            if limit_orders:
                # Get chat data for this chat_id
                if chat_id not in chat_data_dict:
                    chat_data_dict[chat_id] = {}
                
                chat_data = chat_data_dict[chat_id]
                
                # Add limit order IDs to chat data
                limit_order_ids = [order.get('orderId') for order in sorted(limit_orders, key=lambda x: float(x.get('price', 0)))]
                
                # Update the main chat data
                if LIMIT_ORDER_IDS not in chat_data or chat_data.get(LIMIT_ORDER_IDS) != limit_order_ids:
                    chat_data[LIMIT_ORDER_IDS] = limit_order_ids
                    chat_data[CONSERVATIVE_LIMITS_FILLED] = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])
                    
                    logger.info(f"  ✅ Added {len(limit_order_ids)} limit order IDs to chat data")
                    fixed_count += 1
                
                # Also check for position-specific data
                position_key = f"position_{symbol}_Buy_conservative"
                position_key2 = f"position_{symbol}_Sell_conservative"
                
                for pkey in [position_key, position_key2]:
                    if pkey in chat_data:
                        position_data = chat_data[pkey]
                        if isinstance(position_data, dict):
                            position_data[LIMIT_ORDER_IDS] = limit_order_ids
                            position_data[CONSERVATIVE_LIMITS_FILLED] = position_data.get(CONSERVATIVE_LIMITS_FILLED, [])
                            logger.info(f"  ✅ Also updated {pkey} with limit order IDs")
            else:
                logger.info(f"  No limit orders found for {symbol}")
                
        except Exception as e:
            logger.error(f"  ❌ Error processing {symbol}: {e}")
    
    # Save updated persistence
    if fixed_count > 0:
        try:
            # Create backup first
            backup_file = f"{pickle_file}.backup"
            with open(backup_file, 'wb') as f:
                with open(pickle_file, 'rb') as original:
                    f.write(original.read())
            logger.info(f"Created backup: {backup_file}")
            
            # Save updated data
            with open(pickle_file, 'wb') as f:
                pickle.dump(persistence_data, f)
            logger.info(f"\n✅ Fixed {fixed_count} conservative monitors and saved persistence")
        except Exception as e:
            logger.error(f"Error saving persistence: {e}")
    else:
        logger.info(f"\n✅ No fixes needed - all conservative monitors already have limit order tracking")

if __name__ == "__main__":
    asyncio.run(fix_all_limit_order_alerts())