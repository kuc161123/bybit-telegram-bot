#!/usr/bin/env python3
"""
Fix POPCAT chat data to ensure it has limit order IDs for monitoring
"""
import asyncio
import logging
import pickle
import os
from decimal import Decimal

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import Bybit client
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_client import get_open_orders

async def fix_popcat_chat_data():
    """Fix POPCAT chat data to include limit order IDs"""
    
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
    
    chat_id = 5634913742  # Your chat ID
    chat_data = chat_data_dict.get(chat_id, {})
    
    # Get open orders for POPCAT
    symbol = "POPCATUSDT"
    logger.info(f"Fetching open orders for {symbol}...")
    
    try:
        orders = await get_open_orders(symbol)
        logger.info(f"Found {len(orders)} open orders for {symbol}")
        
        # Find limit orders
        limit_orders = []
        for order in orders:
            if order.get('orderType') == 'Limit' and not order.get('reduceOnly', False):
                limit_orders.append(order)
                logger.info(f"Found limit order: {order.get('orderId')[:8]}... at price {order.get('price')}")
        
        # Find specific POPCAT chat data or create it
        popcat_chat_data = None
        popcat_key = None
        
        # Look through active monitors
        active_monitors = chat_data.get('ACTIVE_MONITOR_TASK', {})
        for key, monitor_info in active_monitors.items():
            if isinstance(monitor_info, dict) and monitor_info.get('symbol') == symbol:
                if monitor_info.get('approach') == 'conservative':
                    popcat_key = key
                    logger.info(f"Found POPCAT conservative monitor: {key}")
                    break
        
        # If not found in active monitors, check monitor_data
        if not popcat_key:
            monitor_data = chat_data.get('monitor_data', {})
            for key, data in monitor_data.items():
                if symbol in key and 'conservative' in key:
                    popcat_key = key
                    popcat_chat_data = data
                    logger.info(f"Found POPCAT in monitor_data: {key}")
                    break
        
        # Create chat data for POPCAT if not exists
        if not popcat_chat_data:
            popcat_chat_data = {
                'SYMBOL': symbol,
                'SIDE': 'Buy',  # Based on logs showing Buy position
                'TRADING_APPROACH': 'conservative',
                'CONSERVATIVE_MODE_ENABLED': True,
                'chat_id': chat_id,
                '_chat_id': chat_id
            }
            
            # Store it
            if 'monitor_data' not in chat_data:
                chat_data['monitor_data'] = {}
            
            monitor_key = f"{symbol}_conservative_{chat_id}"
            chat_data['monitor_data'][monitor_key] = popcat_chat_data
            logger.info(f"Created new chat data for POPCAT conservative")
        
        # Add limit order IDs - use known IDs if no orders found
        if limit_orders:
            limit_order_ids = [order.get('orderId') for order in limit_orders]
        else:
            # Use the known limit order IDs from logs
            limit_order_ids = [
                'cdc906cc-fea4-45e2-b573-807fc598d518',
                'b8abd178-5d6e-4d69-9c38-c7ccb5e1c77a'
            ]
            logger.info("Using known limit order IDs from logs")
        
        popcat_chat_data['LIMIT_ORDER_IDS'] = limit_order_ids
        popcat_chat_data['CONSERVATIVE_LIMITS_FILLED'] = []  # Reset filled list
        
        logger.info(f"Added {len(limit_order_ids)} limit order IDs to POPCAT chat data: {[id[:8] + '...' for id in limit_order_ids]}")
            
            # Also update in the main chat data if we have active monitor
            if popcat_key and popcat_key in active_monitors:
                active_monitors[popcat_key]['limit_order_ids'] = limit_order_ids
        
        # Save updated persistence
        try:
            with open(pickle_file, 'wb') as f:
                pickle.dump(persistence_data, f)
            logger.info(f"\n✅ Updated POPCAT chat data with limit order IDs and saved persistence")
        except Exception as e:
            logger.error(f"Error saving persistence: {e}")
            
    except Exception as e:
        logger.error(f"Error fetching orders: {e}")

if __name__ == "__main__":
    asyncio.run(fix_popcat_chat_data())