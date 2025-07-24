#!/usr/bin/env python3
"""
Fix missing order IDs for SANDUSDT position.
This script queries Bybit to find all open orders for SANDUSDT and updates the persistence.
"""

import asyncio
import pickle
import logging
from decimal import Decimal
from typing import Dict, List, Any

# Import required modules
from clients.bybit_helpers import api_call_with_retry
from clients.bybit_client import bybit_client
from config.constants import (
    LIMIT_ORDER_IDS, CONSERVATIVE_TP_ORDER_IDS, CONSERVATIVE_SL_ORDER_ID,
    TP_ORDER_IDS, SL_ORDER_ID
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def get_open_orders(symbol: str) -> List[Dict[str, Any]]:
    """Get all open orders for a symbol"""
    try:
        orders = await api_call_with_retry(
            lambda: bybit_client.get_open_orders(
                category="linear",
                symbol=symbol,
                limit=50
            ),
            timeout=20
        )
        
        result = orders.get('result', {})
        order_list = result.get('list', [])
        
        logger.info(f"Found {len(order_list)} open orders for {symbol}")
        return order_list
        
    except Exception as e:
        logger.error(f"Error fetching orders: {e}")
        return []

async def fix_sandusdt_orders():
    """Main function to fix SANDUSDT order IDs"""
    
    # Load persistence file
    persistence_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    
    try:
        with open(persistence_file, 'rb') as f:
            data = pickle.load(f)
        logger.info("✅ Loaded persistence file")
    except Exception as e:
        logger.error(f"❌ Error loading persistence file: {e}")
        return
    
    # Get chat data
    chat_data_dict = data.get('chat_data', {})
    
    # Find SANDUSDT positions
    fixed_count = 0
    
    for chat_id, chat_data in chat_data_dict.items():
        # Look for SANDUSDT conservative position data
        position_key = "position_SANDUSDT_Buy_conservative"
        if position_key in chat_data:
            position_data = chat_data[position_key]
            logger.info(f"\n📊 Found SANDUSDT conservative position in chat {chat_id}")
            logger.info(f"   Current limit orders: {position_data.get('limit_order_ids', [])}")
            logger.info(f"   Current TP orders: {position_data.get('conservative_tp_order_ids', [])}")
            logger.info(f"   Current SL order: {position_data.get('conservative_sl_order_id', None)}")
            
            # Get open orders from Bybit
            orders = await get_open_orders("SANDUSDT")
            
            if orders:
                # Categorize orders
                limit_orders = []
                tp_orders = []
                sl_orders = []
                
                for order in orders:
                    order_type = order.get('orderType', '')
                    side = order.get('side', '')
                    reduce_only = order.get('reduceOnly', False)
                    stop_order_type = order.get('stopOrderType', '')
                    
                    # Log order details
                    logger.info(f"\n   📋 Order: {order.get('orderId', '')[:8]}...")
                    logger.info(f"      Type: {order_type}, Side: {side}")
                    logger.info(f"      Price: {order.get('price', 'N/A')}")
                    logger.info(f"      Qty: {order.get('qty', 'N/A')}")
                    logger.info(f"      ReduceOnly: {reduce_only}")
                    logger.info(f"      StopOrderType: {stop_order_type}")
                    
                    # Categorize the order
                    if order_type == 'Limit' and not reduce_only:
                        # Entry limit order
                        limit_orders.append(order)
                    elif reduce_only and side == 'Sell' and stop_order_type == 'TakeProfit':
                        # Take profit order
                        tp_orders.append(order)
                    elif reduce_only and side == 'Buy' and stop_order_type == 'StopLoss':
                        # Stop loss order
                        sl_orders.append(order)
                
                # Sort orders by price
                limit_orders.sort(key=lambda x: float(x.get('price', 0)))
                tp_orders.sort(key=lambda x: float(x.get('price', 0)))
                
                # Update position data
                update_needed = False
                
                if limit_orders and not position_data.get('limit_order_ids'):
                    limit_order_ids = [order.get('orderId') for order in limit_orders]
                    position_data['limit_order_ids'] = limit_order_ids
                    logger.info(f"\n✅ Added {len(limit_order_ids)} limit order IDs")
                    update_needed = True
                
                if tp_orders and not position_data.get('conservative_tp_order_ids'):
                    tp_order_ids = [order.get('orderId') for order in tp_orders]
                    position_data['conservative_tp_order_ids'] = tp_order_ids
                    logger.info(f"✅ Added {len(tp_order_ids)} TP order IDs")
                    update_needed = True
                
                if sl_orders and not position_data.get('conservative_sl_order_id'):
                    sl_order_id = sl_orders[0].get('orderId')
                    position_data['conservative_sl_order_id'] = sl_order_id
                    logger.info(f"✅ Added SL order ID: {sl_order_id[:8]}...")
                    update_needed = True
                
                if update_needed:
                    fixed_count += 1
            else:
                logger.warning(f"⚠️ No open orders found for SANDUSDT")
    
    # Save updated persistence
    if fixed_count > 0:
        try:
            with open(persistence_file, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"\n✅ Successfully updated persistence file")
            logger.info(f"📊 Fixed {fixed_count} SANDUSDT positions")
        except Exception as e:
            logger.error(f"❌ Error saving persistence file: {e}")
    else:
        logger.info("\n✅ No updates needed - SANDUSDT orders already properly stored or no open orders found")

if __name__ == "__main__":
    asyncio.run(fix_sandusdt_orders())