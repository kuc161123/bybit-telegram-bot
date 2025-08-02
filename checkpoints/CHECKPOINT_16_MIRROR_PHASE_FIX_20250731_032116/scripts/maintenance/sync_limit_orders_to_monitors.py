#!/usr/bin/env python3
"""
Sync existing limit orders from Bybit to monitor tracking
This ensures limit orders will be cancelled when TP1 hits
"""

import pickle
import logging
import asyncio
from datetime import datetime
from decimal import Decimal
from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2 as mirror_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def get_limit_orders_for_position(client, symbol: str, side: str, avg_price: float):
    """Get limit entry orders for a position"""
    try:
        response = await asyncio.to_thread(
            client.get_open_orders,
            category="linear",
            symbol=symbol
        )
        
        if response['retCode'] != 0:
            return []
            
        orders = response['result']['list']
        limit_orders = []
        
        for order in orders:
            # Check if it's an entry order (not reduceOnly)
            if not order.get('reduceOnly'):
                limit_orders.append({
                    'order_id': order['orderId'],
                    'order_link_id': order.get('orderLinkId', ''),
                    'side': order['side'],
                    'price': order['price'],
                    'qty': order['qty'],
                    'status': 'ACTIVE',
                    'created_at': order.get('createdTime', ''),
                    'order_type': 'Limit'
                })
        
        return limit_orders
        
    except Exception as e:
        logger.error(f"Error getting orders for {symbol}: {e}")
        return []

async def sync_all_limit_orders():
    """Sync limit orders from Bybit to monitor tracking"""
    
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    # Load pickle file
    try:
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        logger.error(f"Error loading pickle file: {e}")
        return
    
    # Get Enhanced TP/SL monitors
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    logger.info(f"\n{'='*60}")
    logger.info(f"🔄 SYNCING LIMIT ORDERS TO MONITORS")
    logger.info(f"{'='*60}")
    
    total_synced = 0
    positions_with_limits = 0
    
    # Process each monitor
    for key, monitor in enhanced_monitors.items():
        symbol = monitor.get('symbol')
        side = monitor.get('side')
        avg_price = float(monitor.get('avg_price', 0))
        is_mirror = key.endswith('_mirror')
        account = 'Mirror' if is_mirror else 'Main'
        
        # Get appropriate client
        client = mirror_client if is_mirror else bybit_client
        
        # Get limit orders from Bybit
        limit_orders = await get_limit_orders_for_position(client, symbol, side, avg_price)
        
        if limit_orders:
            # Update monitor with limit orders
            monitor['limit_orders'] = limit_orders
            positions_with_limits += 1
            total_synced += len(limit_orders)
            
            logger.info(f"\n✅ {symbol} {side} ({account}):")
            logger.info(f"   Found {len(limit_orders)} limit orders")
            for i, order in enumerate(limit_orders):
                logger.info(f"   Order {i+1}: {order['qty']} @ {order['price']}")
        else:
            # No limit orders, ensure empty array
            monitor['limit_orders'] = []
            logger.info(f"\n📝 {symbol} {side} ({account}): No limit orders")
    
    # Save updated data
    try:
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"\n✅ Successfully saved updated monitors with limit order tracking")
    except Exception as e:
        logger.error(f"Error saving pickle file: {e}")
        return
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 SYNC SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total positions checked: {len(enhanced_monitors)}")
    logger.info(f"Positions with limit orders: {positions_with_limits}")
    logger.info(f"Total limit orders synced: {total_synced}")
    
    logger.info(f"\n💡 NEXT STEPS:")
    logger.info(f"1. When any position hits TP1 (85%), its limit orders will be cancelled")
    logger.info(f"2. The cancellation happens automatically via CANCEL_LIMITS_ON_TP1 setting")
    logger.info(f"3. Monitor logs for 'Cancelling unfilled limit orders' messages")
    
    # Show which positions are ready for limit cancellation
    logger.info(f"\n🎯 POSITIONS READY FOR LIMIT CANCELLATION ON TP1:")
    for key, monitor in enhanced_monitors.items():
        if monitor.get('limit_orders'):
            symbol = monitor['symbol']
            side = monitor['side']
            account = 'Mirror' if key.endswith('_mirror') else 'Main'
            limit_count = len(monitor['limit_orders'])
            logger.info(f"   {symbol} {side} ({account}) - {limit_count} limit orders")

async def main():
    """Main execution"""
    await sync_all_limit_orders()

if __name__ == "__main__":
    asyncio.run(main())