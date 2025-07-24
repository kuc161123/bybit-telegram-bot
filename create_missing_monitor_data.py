#!/usr/bin/env python3
"""
Create Missing Monitor Data
Gathers complete information for missing monitors including TP/SL orders
"""

import asyncio
import logging
import json
import sys
import os
from decimal import Decimal
from datetime import datetime
import time
import pickle
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2
from clients.bybit_helpers import get_open_orders_with_client

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def get_position_orders(symbol: str, client) -> Dict:
    """Get all orders for a specific position"""
    try:
        # Get all active orders for the symbol
        orders = await get_open_orders_with_client(client, symbol=symbol)
        
        # Categorize orders
        tp_orders = []
        sl_orders = []
        limit_orders = []
        
        for order in orders:
            order_type = order.get('orderType', '').lower()
            stop_order_type = order.get('stopOrderType', '')
            reduce_only = order.get('reduceOnly', False)
            
            if stop_order_type == 'TakeProfit' or 'tp' in order.get('orderLinkId', '').lower():
                tp_orders.append(order)
            elif stop_order_type == 'StopLoss' or 'sl' in order.get('orderLinkId', '').lower():
                sl_orders.append(order)
            elif order_type == 'limit' and not reduce_only:
                limit_orders.append(order)
        
        return {
            'tp_orders': tp_orders,
            'sl_orders': sl_orders,
            'limit_orders': limit_orders,
            'total_orders': len(orders)
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting orders for {symbol}: {e}")
        return {'tp_orders': [], 'sl_orders': [], 'limit_orders': [], 'total_orders': 0}

async def create_monitor_data_for_position(position_info: dict, orders_info: dict) -> dict:
    """Create complete monitor data structure for a position"""
    
    symbol = position_info['symbol']
    side = position_info['side']
    account = position_info['account']
    size = Decimal(str(position_info['size']))
    avg_price = Decimal(str(position_info['avgPrice']))
    
    # Create monitor key
    monitor_key = f"{symbol}_{side}_{account}"
    
    # Extract TP information
    tp_orders_data = {}
    for i, tp_order in enumerate(orders_info['tp_orders']):
        tp_key = f"tp{i+1}"
        tp_orders_data[tp_key] = {
            'order_id': tp_order.get('orderId'),
            'order_link_id': tp_order.get('orderLinkId'),
            'price': Decimal(str(tp_order.get('triggerPrice', 0))),
            'quantity': Decimal(str(tp_order.get('qty', 0))),
            'status': tp_order.get('orderStatus')
        }
    
    # Extract SL information
    sl_order_data = None
    if orders_info['sl_orders']:
        sl_order = orders_info['sl_orders'][0]  # Should only be one SL
        sl_order_data = {
            'order_id': sl_order.get('orderId'),
            'order_link_id': sl_order.get('orderLinkId'),
            'price': Decimal(str(sl_order.get('triggerPrice', 0))),
            'quantity': Decimal(str(sl_order.get('qty', 0))),
            'status': sl_order.get('orderStatus')
        }
    
    # Get chat_id from pickle file
    chat_id = None
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        # Find chat_id from user_data
        for uid, user_data in data.get('user_data', {}).items():
            if user_data.get('positions'):
                chat_id = uid
                break
    except Exception as e:
        logger.warning(f"⚠️ Could not get chat_id: {e}")
    
    # Create monitor data structure matching enhanced_tp_sl_manager format
    monitor_data = {
        'symbol': symbol,
        'side': side,
        'size': size,
        'position_size': size,  # Current position size
        'initial_size': size,   # Original position size
        'remaining_size': size, # Remaining size to manage
        'filled_size': Decimal('0'),
        'account': account,
        'account_type': account,
        'avg_entry_price': avg_price,
        'entry_price': avg_price,  # Alias for compatibility
        'weighted_avg_entry': avg_price,
        'actual_entry_prices': [(avg_price, size)],  # Track actual fills
        'tp_orders': tp_orders_data,
        'sl_order': sl_order_data,
        'approach': 'conservative',  # Default approach
        'status': 'active',
        'created_at': datetime.now().isoformat(),
        'last_check': time.time(),
        'monitoring_active': True,
        'tp1_hit': False,
        'tp2_hit': False, 
        'tp3_hit': False,
        'tp4_hit': False,
        'breakeven_moved': False,
        'sl_moved_to_breakeven': False,
        'limit_orders_cancelled': False,
        'chat_id': chat_id,
        'position_idx': 0,  # Mirror uses One-Way mode
        'dashboard_key': monitor_key,  # For monitor_tasks compatibility
        'stop_loss': sl_order_data['price'] if sl_order_data else None,
        'take_profits': [tp['price'] for tp in tp_orders_data.values()]
    }
    
    return monitor_key, monitor_data

async def main():
    """Main function to create missing monitor data"""
    logger.info("🔧 Creating Missing Monitor Data")
    logger.info("=" * 80)
    
    try:
        # Load analysis results
        with open('monitor_analysis.json', 'r') as f:
            analysis = json.load(f)
        
        missing_details = analysis['missing_details']
        logger.info(f"📊 Processing {len(missing_details)} missing monitors")
        
        # Prepare monitor data for all missing positions
        all_monitor_data = {}
        
        for position_info in missing_details:
            symbol = position_info['symbol']
            account = position_info['account']
            
            logger.info(f"\n📍 Processing {symbol} ({account} account)")
            
            # Get orders for this position
            client = bybit_client_2 if account == 'mirror' else bybit_client
            orders_info = await get_position_orders(symbol, client)
            
            logger.info(f"   Found {orders_info['total_orders']} orders")
            logger.info(f"   TP orders: {len(orders_info['tp_orders'])}")
            logger.info(f"   SL orders: {len(orders_info['sl_orders'])}")
            logger.info(f"   Limit orders: {len(orders_info['limit_orders'])}")
            
            # Create monitor data
            monitor_key, monitor_data = await create_monitor_data_for_position(
                position_info, orders_info
            )
            
            all_monitor_data[monitor_key] = monitor_data
            
            logger.info(f"   ✅ Created monitor data for {monitor_key}")
            logger.info(f"   Size: {monitor_data['size']}")
            logger.info(f"   Entry: {monitor_data['avg_entry_price']}")
            logger.info(f"   TPs: {len(monitor_data['tp_orders'])}")
            logger.info(f"   SL: {'Yes' if monitor_data['sl_order'] else 'No'}")
        
        # Save monitor data for next phase
        output_file = 'missing_monitors_data.json'
        with open(output_file, 'w') as f:
            # Convert Decimal to string for JSON serialization
            json_data = {}
            for key, data in all_monitor_data.items():
                json_data[key] = {
                    k: str(v) if isinstance(v, Decimal) else v
                    for k, v in data.items()
                }
            json.dump(json_data, f, indent=2)
        
        logger.info(f"\n💾 Monitor data saved to {output_file}")
        logger.info(f"✅ Created data for {len(all_monitor_data)} monitors")
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("📊 SUMMARY:")
        for monitor_key in all_monitor_data:
            logger.info(f"   ✅ {monitor_key}")
        
        return all_monitor_data
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {}

if __name__ == "__main__":
    asyncio.run(main())