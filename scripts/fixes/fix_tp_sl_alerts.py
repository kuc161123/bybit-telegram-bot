#!/usr/bin/env python3
"""
Fix TP/SL alerts by adding missing order IDs to chat data
This script queries all open orders and updates persistence with proper order tracking
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

from clients.bybit_helpers import api_call_with_retry
from clients.bybit_client import bybit_client
from config.constants import (
    LIMIT_ORDER_IDS, CONSERVATIVE_LIMITS_FILLED,
    CONSERVATIVE_TP_ORDER_IDS, CONSERVATIVE_SL_ORDER_ID,
    SL_ORDER_ID, TP_ORDER_IDS, LAST_KNOWN_POSITION_SIZE,
    PRIMARY_ENTRY_PRICE
)

async def get_position_orders(symbol: str) -> list:
    """Get all open orders for a symbol"""
    try:
        response = await api_call_with_retry(
            lambda: bybit_client.get_open_orders(
                category="linear",
                symbol=symbol
            ),
            timeout=20
        )
        
        if response and response.get("retCode") == 0:
            return response.get("result", {}).get("list", [])
        return []
    except Exception as e:
        logger.error(f"Error getting orders for {symbol}: {e}")
        return []

async def fix_all_tp_sl_alerts():
    """Fix TP/SL alerts for all positions"""
    
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
    
    # Find all active monitors
    monitor_tasks = bot_data.get('monitor_tasks', {})
    active_monitors = []
    
    for key, monitor in monitor_tasks.items():
        if monitor.get('active'):
            # Skip mirror monitors
            if 'mirror' not in key and monitor.get('account_type', 'primary') == 'primary':
                active_monitors.append({
                    'key': key,
                    'monitor': monitor,
                    'symbol': monitor.get('symbol'),
                    'chat_id': monitor.get('chat_id'),
                    'approach': monitor.get('approach', 'fast')
                })
                logger.info(f"Found active monitor: {key}")
    
    logger.info(f"\nFound {len(active_monitors)} active monitors to fix")
    
    # Fix each monitor
    fixed_count = 0
    for monitor_info in active_monitors:
        symbol = monitor_info['symbol']
        chat_id = monitor_info['chat_id']
        approach = monitor_info['approach']
        
        logger.info(f"\nProcessing {symbol} ({approach})...")
        
        try:
            # Get open orders for this symbol
            orders = await get_position_orders(symbol)
            logger.info(f"Found {len(orders)} open orders for {symbol}")
            
            # Get chat data for this chat_id
            if chat_id not in chat_data_dict:
                chat_data_dict[chat_id] = {}
            
            chat_data = chat_data_dict[chat_id]
            
            if approach == 'conservative':
                # Find limit orders (not reduce-only)
                limit_orders = []
                tp_orders = []
                sl_order = None
                
                for order in orders:
                    order_type = order.get('orderType')
                    reduce_only = order.get('reduceOnly', False)
                    order_link_id = order.get('orderLinkId', '')
                    stop_order_type = order.get('stopOrderType', '')
                    
                    # Limit entry orders
                    if order_type == 'Limit' and not reduce_only:
                        limit_orders.append(order)
                        logger.info(f"  - Limit order: {order.get('orderId')[:8]}... at price {order.get('price')}")
                    
                    # TP orders (either has TP in orderLinkId or stopOrderType is TakeProfit)
                    elif 'TP' in order_link_id or stop_order_type == 'TakeProfit':
                        tp_orders.append(order)
                        logger.info(f"  - TP order: {order.get('orderId')[:8]}... at price {order.get('triggerPrice', order.get('price'))}")
                    
                    # SL orders (either has SL in orderLinkId or stopOrderType is StopLoss)
                    elif 'SL' in order_link_id or stop_order_type == 'StopLoss':
                        sl_order = order
                        logger.info(f"  - SL order: {order.get('orderId')[:8]}... at price {order.get('triggerPrice', order.get('price'))}")
                
                # Update chat data with order IDs
                updated = False
                
                if limit_orders:
                    limit_order_ids = [order.get('orderId') for order in sorted(limit_orders, key=lambda x: float(x.get('price', 0)))]
                    chat_data[LIMIT_ORDER_IDS] = limit_order_ids
                    chat_data[CONSERVATIVE_LIMITS_FILLED] = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])
                    logger.info(f"  ✅ Added {len(limit_order_ids)} limit order IDs")
                    updated = True
                
                if tp_orders:
                    # Sort TP orders by price (ascending for Buy, descending for Sell)
                    side = "Buy"  # Default, should get from position
                    tp_orders_sorted = sorted(tp_orders, key=lambda x: float(x.get('triggerPrice', x.get('price', 0))), 
                                            reverse=(side == "Sell"))
                    tp_order_ids = [order.get('orderId') for order in tp_orders_sorted]
                    chat_data[CONSERVATIVE_TP_ORDER_IDS] = tp_order_ids
                    logger.info(f"  ✅ Added {len(tp_order_ids)} TP order IDs")
                    updated = True
                
                if sl_order:
                    chat_data[CONSERVATIVE_SL_ORDER_ID] = sl_order.get('orderId')
                    logger.info(f"  ✅ Added SL order ID")
                    updated = True
                
                # Also update position-specific data
                position_key = f"position_{symbol}_Buy_conservative"
                position_key2 = f"position_{symbol}_Sell_conservative"
                
                for pkey in [position_key, position_key2]:
                    if pkey in chat_data:
                        position_data = chat_data[pkey]
                        if isinstance(position_data, dict):
                            if limit_orders:
                                position_data[LIMIT_ORDER_IDS] = limit_order_ids
                                position_data[CONSERVATIVE_LIMITS_FILLED] = position_data.get(CONSERVATIVE_LIMITS_FILLED, [])
                            if tp_orders:
                                position_data[CONSERVATIVE_TP_ORDER_IDS] = tp_order_ids
                            if sl_order:
                                position_data[CONSERVATIVE_SL_ORDER_ID] = sl_order.get('orderId')
                            logger.info(f"  ✅ Also updated {pkey} with order IDs")
                
                if updated:
                    fixed_count += 1
                    
            elif approach == 'fast':
                # Find TP and SL orders for fast approach
                tp_order = None
                sl_order = None
                
                for order in orders:
                    order_link_id = order.get('orderLinkId', '')
                    stop_order_type = order.get('stopOrderType', '')
                    
                    # TP order (has FAST_TP in linkId or is TakeProfit type)
                    if '_FAST_TP' in order_link_id or (stop_order_type == 'TakeProfit' and not tp_order):
                        tp_order = order
                        logger.info(f"  - Fast TP order: {order.get('orderId')[:8]}... at price {order.get('triggerPrice', order.get('price'))}")
                    
                    # SL order (has FAST_SL in linkId or is StopLoss type)
                    elif '_FAST_SL' in order_link_id or (stop_order_type == 'StopLoss' and not sl_order):
                        sl_order = order
                        logger.info(f"  - Fast SL order: {order.get('orderId')[:8]}... at price {order.get('triggerPrice', order.get('price'))}")
                
                # Update chat data with order IDs
                updated = False
                
                if tp_order:
                    chat_data["tp_order_id"] = tp_order.get('orderId')
                    chat_data[TP_ORDER_IDS] = [tp_order.get('orderId')]
                    logger.info(f"  ✅ Added fast TP order ID")
                    updated = True
                
                if sl_order:
                    chat_data["sl_order_id"] = sl_order.get('orderId')
                    chat_data[SL_ORDER_ID] = sl_order.get('orderId')
                    logger.info(f"  ✅ Added fast SL order ID")
                    updated = True
                
                # Also update position-specific data
                position_key = f"position_{symbol}_Buy_fast"
                position_key2 = f"position_{symbol}_Sell_fast"
                
                for pkey in [position_key, position_key2]:
                    if pkey in chat_data:
                        position_data = chat_data[pkey]
                        if isinstance(position_data, dict):
                            if tp_order:
                                position_data["tp_order_id"] = tp_order.get('orderId')
                                position_data[TP_ORDER_IDS] = [tp_order.get('orderId')]
                            if sl_order:
                                position_data["sl_order_id"] = sl_order.get('orderId')
                                position_data[SL_ORDER_ID] = sl_order.get('orderId')
                            logger.info(f"  ✅ Also updated {pkey} with order IDs")
                
                if updated:
                    fixed_count += 1
                    
        except Exception as e:
            logger.error(f"  ❌ Error processing {symbol}: {e}")
    
    # Save updated persistence
    if fixed_count > 0:
        try:
            # Create backup first
            backup_file = f"{pickle_file}.backup_tp_sl"
            with open(backup_file, 'wb') as f:
                with open(pickle_file, 'rb') as original:
                    f.write(original.read())
            logger.info(f"Created backup: {backup_file}")
            
            # Save updated data
            with open(pickle_file, 'wb') as f:
                pickle.dump(persistence_data, f)
            logger.info(f"\n✅ Fixed {fixed_count} monitors and saved persistence")
            logger.info("The bot will now properly send alerts when TP/SL orders are filled")
        except Exception as e:
            logger.error(f"Error saving persistence: {e}")
    else:
        logger.info(f"\n✅ No fixes needed - all monitors already have proper order tracking")

if __name__ == "__main__":
    asyncio.run(fix_all_tp_sl_alerts())