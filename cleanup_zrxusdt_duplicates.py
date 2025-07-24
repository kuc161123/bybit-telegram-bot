#!/usr/bin/env python3
"""
Cleanup duplicate ZRXUSDT orders and fix remaining issues
"""
import asyncio
import logging
from decimal import Decimal
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def cleanup_zrxusdt():
    """Cleanup duplicate orders and fix remaining issues"""
    try:
        from clients.bybit_client import bybit_client
        from clients.bybit_helpers import (
            cancel_order_with_retry,
            get_position_info,
            get_open_orders,
            get_position_info_for_account,
            get_all_open_orders
        )
        from execution.mirror_trader import bybit_client_2, cancel_mirror_order
        
        symbol = "ZRXUSDT"
        
        logger.info("=" * 80)
        logger.info("ZRXUSDT Duplicate Cleanup")
        logger.info("=" * 80)
        
        # MAIN ACCOUNT - Remove duplicate SL
        logger.info("\n🔷 MAIN ACCOUNT - Removing duplicate SL")
        logger.info("-" * 40)
        
        orders = await get_open_orders(symbol)
        
        # Find duplicate SL orders
        sl_orders = []
        for order in orders:
            if (order['orderType'] == 'Market' and 
                order.get('triggerPrice') == '0.2049' and
                order.get('reduceOnly', True)):
                sl_orders.append(order)
        
        if len(sl_orders) > 1:
            logger.info(f"Found {len(sl_orders)} SL orders, removing duplicates...")
            # Keep the newest one
            sl_orders.sort(key=lambda x: x.get('createdTime', 0), reverse=True)
            
            for order in sl_orders[1:]:  # Skip the first (newest)
                logger.info(f"  Cancelling duplicate SL: {order['orderId'][:8]}...")
                success = await cancel_order_with_retry(symbol, order['orderId'])
                if success:
                    logger.info("  ✅ Cancelled")
                else:
                    logger.error("  ❌ Failed to cancel")
        
        # MIRROR ACCOUNT - Cleanup duplicates and fix TP4
        logger.info("\n\n🔷 MIRROR ACCOUNT - Cleanup and fixes")
        logger.info("-" * 40)
        
        all_mirror_orders = await get_all_open_orders(client=bybit_client_2)
        mirror_orders = [o for o in all_mirror_orders if o['symbol'] == symbol]
        
        # Group orders by type
        sl_orders = []
        tp2_orders = []
        tp3_orders = []
        tp4_orders = []
        
        for order in mirror_orders:
            link_id = order.get('orderLinkId', '')
            trigger_price = order.get('triggerPrice', '')
            
            if '0.2049' in str(trigger_price) or 'SL' in link_id:
                sl_orders.append(order)
            elif '0.2429' in str(trigger_price) or 'TP2' in link_id:
                tp2_orders.append(order)
            elif '0.2523' in str(trigger_price) or 'TP3' in link_id:
                tp3_orders.append(order)
            elif '0.2806' in str(trigger_price) or 'TP4' in link_id:
                tp4_orders.append(order)
        
        # Remove duplicate SL orders
        if len(sl_orders) > 1:
            logger.info(f"\n📍 Found {len(sl_orders)} SL orders, removing duplicates...")
            sl_orders.sort(key=lambda x: x.get('createdTime', 0), reverse=True)
            
            for order in sl_orders[1:]:
                logger.info(f"  Cancelling duplicate SL: {order['orderId'][:8]}...")
                success = await cancel_mirror_order(symbol, order['orderId'])
                if success:
                    logger.info("  ✅ Cancelled")
        
        # Remove duplicate TP2 orders
        if len(tp2_orders) > 1:
            logger.info(f"\n📍 Found {len(tp2_orders)} TP2 orders, removing duplicates...")
            # Keep only limit orders
            tp2_limits = [o for o in tp2_orders if o['orderType'] == 'Limit']
            tp2_stops = [o for o in tp2_orders if o['orderType'] == 'Market']
            
            # Cancel all stops
            for order in tp2_stops:
                logger.info(f"  Cancelling stop TP2: {order['orderId'][:8]}...")
                await cancel_mirror_order(symbol, order['orderId'])
            
            # Keep only one limit order
            if len(tp2_limits) > 1:
                tp2_limits.sort(key=lambda x: x.get('createdTime', 0), reverse=True)
                for order in tp2_limits[1:]:
                    logger.info(f"  Cancelling duplicate limit TP2: {order['orderId'][:8]}...")
                    await cancel_mirror_order(symbol, order['orderId'])
        
        # Fix TP3 orders
        if len(tp3_orders) > 1:
            logger.info(f"\n📍 Found {len(tp3_orders)} TP3 orders, cleaning up...")
            # Cancel all stop orders
            for order in tp3_orders:
                if order['orderType'] == 'Market':
                    logger.info(f"  Cancelling stop TP3: {order['orderId'][:8]}...")
                    await cancel_mirror_order(symbol, order['orderId'])
        
        # Cancel TP4 stop order (will place proper limit order after)
        logger.info(f"\n📍 Fixing TP4 orders...")
        for order in tp4_orders:
            if order['orderType'] == 'Market':  # Stop order
                logger.info(f"  Cancelling stop TP4: {order['orderId'][:8]}...")
                await cancel_mirror_order(symbol, order['orderId'])
        
        # Calculate proper TP quantities
        mirror_positions = await get_position_info_for_account(symbol, 'mirror')
        mirror_position = None
        for pos in mirror_positions:
            if pos.get('side') == 'Buy' and Decimal(str(pos.get('size', '0'))) > 0:
                mirror_position = pos
                break
        
        if mirror_position:
            position_size = Decimal(str(mirror_position['size']))
            logger.info(f"\n📍 Rebalancing TP quantities for position size: {position_size}")
            
            # Cancel remaining small TP orders
            remaining_orders = await get_all_open_orders(client=bybit_client_2)
            mirror_orders = [o for o in remaining_orders if o['symbol'] == symbol]
            
            for order in mirror_orders:
                if (order['orderType'] == 'Limit' and 
                    order.get('reduceOnly', False) and
                    Decimal(str(order['qty'])) < 10):
                    logger.info(f"  Cancelling small TP order: {order['orderId'][:8]}... (Qty: {order['qty']})")
                    await cancel_mirror_order(symbol, order['orderId'])
            
            # Place proper TP4
            logger.info("\n📍 Placing proper TP4 order...")
            # Since we have TP2 and TP3 with 14 each, TP4 should be 15 (43 - 14 - 14 = 15)
            tp4_qty = position_size - 28  # 43 - 28 = 15
            
            response = bybit_client_2.place_order(
                category="linear",
                symbol=symbol,
                side="Sell",
                orderType="Limit",
                qty=str(tp4_qty),
                price="0.2806",
                reduceOnly=True,
                positionIdx=0,
                orderLinkId=f"MIR_TP4_{symbol}_{int(datetime.now().timestamp())}"
            )
            
            if response and response.get('retCode') == 0:
                logger.info(f"✅ Placed TP4 limit order for {tp4_qty} {symbol}")
            else:
                logger.error(f"❌ Failed to place TP4: {response}")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ Cleanup completed!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Error in cleanup: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(cleanup_zrxusdt())