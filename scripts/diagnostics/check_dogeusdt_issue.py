#!/usr/bin/env python3
"""
Check DOGEUSDT position and orders to understand the issue
"""
import asyncio
import logging
from decimal import Decimal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_dogeusdt():
    """Check DOGEUSDT position and orders"""
    try:
        from clients.bybit_helpers import get_all_positions, get_open_orders, get_order_history
        from execution.mirror_trader import is_mirror_trading_enabled, get_mirror_positions
        
        logger.info("🔍 Checking DOGEUSDT position issue...")
        
        # Get main account position
        positions = await get_all_positions()
        doge_position = None
        for pos in positions:
            if pos.get('symbol') == 'DOGEUSDT':
                doge_position = pos
                break
        
        if doge_position:
            logger.info("\n📊 MAIN ACCOUNT - DOGEUSDT Position:")
            logger.info(f"   Side: {doge_position.get('side')}")
            logger.info(f"   Size: {doge_position.get('size')}")
            logger.info(f"   Entry Price: ${doge_position.get('avgPrice')}")
            logger.info(f"   Mark Price: ${doge_position.get('markPrice')}")
            logger.info(f"   Unrealized P&L: ${doge_position.get('unrealisedPnl')}")
        else:
            logger.info("❌ No DOGEUSDT position found on main account")
        
        # Get orders
        all_orders = await get_open_orders()
        doge_orders = [o for o in all_orders if o.get('symbol') == 'DOGEUSDT']
        
        logger.info(f"\n📋 MAIN ACCOUNT - DOGEUSDT Orders ({len(doge_orders)}):")
        
        # Group by type
        tp_orders = []
        sl_orders = []
        limit_orders = []
        
        for order in doge_orders:
            order_link_id = order.get('orderLinkId', '')
            if 'TP' in order_link_id:
                tp_orders.append(order)
            elif 'SL' in order_link_id:
                sl_orders.append(order)
            elif order.get('orderType') == 'Limit' and not order.get('reduceOnly'):
                limit_orders.append(order)
        
        # Sort TP orders by price
        tp_orders.sort(key=lambda x: float(x.get('price', '0')))
        
        logger.info(f"\n🎯 TP Orders ({len(tp_orders)}):")
        for i, order in enumerate(tp_orders):
            qty = order.get('qty', '0')
            price = order.get('price', '0')
            order_id = order.get('orderId', '')
            link_id = order.get('orderLinkId', '')
            logger.info(f"   TP{i+1}: Qty={qty}, Price=${price}")
            logger.info(f"        ID: {order_id[:8]}...")
            logger.info(f"        LinkID: {link_id}")
        
        logger.info(f"\n🛡️ SL Orders ({len(sl_orders)}):")
        for order in sl_orders:
            qty = order.get('qty', '0')
            trigger_price = order.get('triggerPrice', '0')
            order_id = order.get('orderId', '')
            logger.info(f"   SL: Qty={qty}, Trigger=${trigger_price}")
            logger.info(f"       ID: {order_id[:8]}...")
        
        # Check mirror account if enabled
        if is_mirror_trading_enabled():
            logger.info("\n" + "="*50)
            logger.info("🪞 MIRROR ACCOUNT CHECK")
            
            # Get mirror positions
            mirror_positions = await get_mirror_positions()
            mirror_doge = None
            for pos in mirror_positions:
                if pos.get('symbol') == 'DOGEUSDT':
                    mirror_doge = pos
                    break
            
            if mirror_doge:
                logger.info("\n📊 MIRROR - DOGEUSDT Position:")
                logger.info(f"   Side: {mirror_doge.get('side')}")
                logger.info(f"   Size: {mirror_doge.get('size')}")
                logger.info(f"   Entry Price: ${mirror_doge.get('avgPrice')}")
            else:
                logger.info("❌ No DOGEUSDT position on mirror account")
            
            # Get mirror orders
            from execution.mirror_trader import bybit_client_2
            from clients.bybit_helpers import get_all_open_orders
            mirror_orders = await get_all_open_orders(bybit_client_2)
            mirror_doge_orders = [o for o in mirror_orders if o.get('symbol') == 'DOGEUSDT']
            
            logger.info(f"\n📋 MIRROR - DOGEUSDT Orders ({len(mirror_doge_orders)}):")
            for order in mirror_doge_orders:
                order_type = order.get('orderType')
                qty = order.get('qty', '0')
                price = order.get('price', order.get('triggerPrice', '0'))
                link_id = order.get('orderLinkId', '')
                logger.info(f"   {order_type}: Qty={qty}, Price=${price}")
                logger.info(f"        LinkID: {link_id}")
        
        # Check order history for recent fills
        logger.info("\n" + "="*50)
        logger.info("📜 Recent DOGEUSDT Order History:")
        
        history = await get_order_history('DOGEUSDT', limit=20)
        filled_orders = [o for o in history if o.get('orderStatus') == 'Filled']
        
        logger.info(f"Found {len(filled_orders)} filled orders")
        for order in filled_orders[:5]:  # Show last 5 fills
            qty = order.get('cumExecQty', '0')
            price = order.get('avgPrice', '0')
            link_id = order.get('orderLinkId', '')
            created = order.get('createdTime', '')
            logger.info(f"\n   Filled: Qty={qty}, Price=${price}")
            logger.info(f"   LinkID: {link_id}")
            logger.info(f"   Time: {created}")
        
        # Calculate expected vs actual
        if doge_position:
            position_size = Decimal(str(doge_position.get('size', '0')))
            logger.info("\n" + "="*50)
            logger.info("📊 ANALYSIS:")
            logger.info(f"Current position size: {position_size}")
            
            # For conservative approach, TP1 should be 85% of original position
            # If current is 531, and 28.33% was filled, original was ~740
            original_estimate = position_size / Decimal('0.7167')  # 1 - 0.2833
            logger.info(f"Estimated original size: {original_estimate:.0f}")
            logger.info(f"Expected TP1 size (85%): {original_estimate * Decimal('0.85'):.0f}")
            logger.info(f"Actual fill: {original_estimate - position_size:.0f} (28.33%)")
            
            logger.info("\n⚠️ ISSUE: Only limit orders were filled (28.33%), not TP1 (85%)")
            logger.info("This suggests the limit orders executed but TP1 hasn't triggered yet")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_dogeusdt())