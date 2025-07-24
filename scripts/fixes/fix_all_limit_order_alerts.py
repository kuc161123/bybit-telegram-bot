#!/usr/bin/env python3
"""
Fix limit order alerts for ALL conservative positions
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

# Import the API call function from bybit_helpers
from clients.bybit_helpers import api_call_with_retry
from clients.bybit_client import bybit_client

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
                # Get chat data for this monitor
                chat_data = chat_data_dict.get(chat_id, {})
                
                # Find the monitor data
                monitor_data_found = False
                monitor_data = chat_data.get('monitor_data', {})
                
                # Try different key formats
                possible_keys = [
                    f"{symbol}_conservative_{chat_id}",
                    f"{symbol}_conservative",
                    symbol
                ]
                
                target_data = None
                target_key = None
                
                for key in possible_keys:
                    if key in monitor_data:
                        target_data = monitor_data[key]
                        target_key = key
                        monitor_data_found = True
                        break
                
                # If not in monitor_data, check ACTIVE_MONITOR_TASK
                if not monitor_data_found:
                    active_monitors = chat_data.get('ACTIVE_MONITOR_TASK', {})
                    if isinstance(active_monitors, dict):
                        for key, data in active_monitors.items():
                            if isinstance(data, dict) and data.get('symbol') == symbol and data.get('approach') == 'conservative':
                                # Create proper monitor data
                                if 'monitor_data' not in chat_data:
                                    chat_data['monitor_data'] = {}
                                
                                target_key = f"{symbol}_conservative_{chat_id}"
                                target_data = {
                                    'SYMBOL': symbol,
                                    'TRADING_APPROACH': 'conservative',
                                    'chat_id': chat_id,
                                    '_chat_id': chat_id
                                }
                                chat_data['monitor_data'][target_key] = target_data
                                monitor_data_found = True
                                logger.info(f"  Created monitor data for {symbol}")
                                break
                
                if target_data:
                    # Add limit order IDs
                    limit_order_ids = [order.get('orderId') for order in limit_orders]
                    target_data['LIMIT_ORDER_IDS'] = limit_order_ids
                    target_data['CONSERVATIVE_LIMITS_FILLED'] = target_data.get('CONSERVATIVE_LIMITS_FILLED', [])
                    
                    # Ensure chat_id is set
                    target_data['chat_id'] = chat_id
                    target_data['_chat_id'] = chat_id
                    
                    logger.info(f"  ✅ Added {len(limit_order_ids)} limit order IDs to {symbol}")
                    fixed_count += 1
                else:
                    logger.warning(f"  ⚠️ Could not find monitor data for {symbol}")
            else:
                logger.info(f"  No limit orders found for {symbol}")
                
        except Exception as e:
            logger.error(f"  ❌ Error processing {symbol}: {e}")
    
    # Save updated persistence
    if fixed_count > 0:
        try:
            with open(pickle_file, 'wb') as f:
                pickle.dump(persistence_data, f)
            logger.info(f"\n✅ Fixed {fixed_count} conservative monitors and saved persistence")
        except Exception as e:
            logger.error(f"Error saving persistence: {e}")
    else:
        logger.info(f"\n✅ No fixes needed - all conservative monitors already have limit order tracking")

if __name__ == "__main__":
    asyncio.run(fix_all_limit_order_alerts())