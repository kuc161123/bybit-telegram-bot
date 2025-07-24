#!/usr/bin/env python3
"""
Fix issues with fast approach positions:
1. TIAUSDT - Fix SL orders that don't have proper OrderLinkIDs
2. BTCUSDT - Remove duplicate SL order
3. Check INJUSDT SL price issue
"""

import asyncio
import logging
from decimal import Decimal
from clients.bybit_helpers import (
    get_position_info, get_all_open_orders, 
    cancel_order_with_retry
)
from clients.bybit_client import bybit_client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def fix_tiausdt_sl():
    """Fix TIAUSDT SL orders that don't have proper OrderLinkIDs"""
    logger.info("=" * 60)
    logger.info("🔧 Fixing TIAUSDT SL orders")
    logger.info("=" * 60)
    
    # Get position info
    positions = await get_position_info("TIAUSDT")
    if not positions:
        logger.warning("❌ No TIAUSDT position found")
        return
        
    position = positions[0]
    if float(position.get('size', 0)) <= 0:
        logger.warning("❌ TIAUSDT position is closed")
        return
        
    position_size = Decimal(str(position.get('size')))
    avg_price = Decimal(str(position.get('avgPrice')))
    side = position.get('side')
    
    logger.info(f"📊 Position: {side} {position_size} @ {avg_price}")
    
    # Get all orders
    all_orders = await get_all_open_orders()
    tiausdt_orders = [o for o in all_orders if o.get('symbol') == 'TIAUSDT']
    
    # Find SL orders without proper OrderLinkIDs
    bad_sl_orders = []
    for order in tiausdt_orders:
        if (order.get('stopOrderType') == 'StopLoss' and 
            order.get('reduceOnly') and
            not (order.get('orderLinkId', '').startswith('BOT_') or 
                 'SL' in order.get('orderLinkId', ''))):
            bad_sl_orders.append(order)
    
    if bad_sl_orders:
        logger.info(f"🔍 Found {len(bad_sl_orders)} SL orders without proper OrderLinkIDs")
        
        # Cancel bad orders
        for order in bad_sl_orders:
            logger.info(f"❌ Cancelling order {order.get('orderId')[:8]}... at {order.get('triggerPrice')}")
            try:
                await cancel_order_with_retry(
                    symbol="TIAUSDT",
                    order_id=order.get('orderId')
                )
                logger.info("✅ Cancelled successfully")
            except Exception as e:
                logger.error(f"❌ Failed to cancel: {e}")
        
        # Place new SL with proper OrderLinkID
        if bad_sl_orders:
            # Use the highest trigger price for sell positions
            sl_price = max(Decimal(str(o.get('triggerPrice'))) for o in bad_sl_orders)
            
            logger.info(f"📝 Placing new SL order at {sl_price}")
            
            # Determine position index
            position_idx = 1 if side == "Buy" else 2
            
            try:
                result = await bybit_client.place_order(
                    category="linear",
                    symbol="TIAUSDT",
                    side="Buy" if side == "Sell" else "Sell",
                    orderType="Market",
                    qty=str(position_size),
                    triggerPrice=str(sl_price),
                    triggerDirection=2 if side == "Sell" else 1,
                    reduceOnly=True,
                    positionIdx=position_idx,
                    orderLinkId=f"BOT_FAST_TIAUSDT_SL_{int(asyncio.get_event_loop().time())}"
                )
                logger.info(f"✅ New SL order placed: {result['result'].get('orderId', 'Unknown')}")
            except Exception as e:
                logger.error(f"❌ Failed to place SL: {e}")
    else:
        logger.info("✅ TIAUSDT SL orders are properly configured")

async def fix_btcusdt_duplicate_sl():
    """Remove duplicate SL order for BTCUSDT"""
    logger.info("=" * 60)
    logger.info("🔧 Fixing BTCUSDT duplicate SL orders")
    logger.info("=" * 60)
    
    # Get position info
    positions = await get_position_info("BTCUSDT")
    if not positions:
        logger.warning("❌ No BTCUSDT position found")
        return
        
    position = positions[0]
    if float(position.get('size', 0)) <= 0:
        logger.warning("❌ BTCUSDT position is closed")
        return
        
    position_size = Decimal(str(position.get('size')))
    avg_price = Decimal(str(position.get('avgPrice')))
    
    logger.info(f"📊 Position: Sell {position_size} @ {avg_price}")
    
    # Get all orders
    all_orders = await get_all_open_orders()
    btcusdt_orders = [o for o in all_orders if o.get('symbol') == 'BTCUSDT']
    
    # Find SL orders
    sl_orders = []
    for order in btcusdt_orders:
        if order.get('stopOrderType') == 'StopLoss' and order.get('reduceOnly'):
            sl_orders.append(order)
    
    if len(sl_orders) > 1:
        logger.info(f"🔍 Found {len(sl_orders)} SL orders (should be 1)")
        
        # Sort by trigger price (keep the closer one for sell position)
        sl_orders.sort(key=lambda x: Decimal(str(x.get('triggerPrice'))))
        
        # For sell position, keep the lower SL (closer to entry)
        keep_order = sl_orders[0]  # 109,900
        cancel_orders = sl_orders[1:]  # 112,000
        
        logger.info(f"✅ Keeping SL at {keep_order.get('triggerPrice')} (closer to entry)")
        
        for order in cancel_orders:
            logger.info(f"❌ Cancelling duplicate SL at {order.get('triggerPrice')}")
            try:
                await cancel_order_with_retry(
                    symbol="BTCUSDT",
                    order_id=order.get('orderId')
                )
                logger.info("✅ Cancelled successfully")
            except Exception as e:
                logger.error(f"❌ Failed to cancel: {e}")
    else:
        logger.info(f"✅ BTCUSDT has {len(sl_orders)} SL order(s) - no duplicates")

async def check_injusdt_sl():
    """Check INJUSDT SL price issue"""
    logger.info("=" * 60)
    logger.info("🔍 Checking INJUSDT SL price")
    logger.info("=" * 60)
    
    # Get position info
    positions = await get_position_info("INJUSDT")
    if not positions:
        logger.warning("❌ No INJUSDT position found")
        return
        
    position = positions[0]
    position_size = Decimal(str(position.get('size')))
    avg_price = Decimal(str(position.get('avgPrice')))
    side = position.get('side')
    
    logger.info(f"📊 Position: {side} {position_size} @ {avg_price}")
    
    # Get all orders
    all_orders = await get_all_open_orders()
    injusdt_orders = [o for o in all_orders if o.get('symbol') == 'INJUSDT']
    
    # Find SL order
    sl_order = None
    for order in injusdt_orders:
        if order.get('stopOrderType') == 'StopLoss' and order.get('reduceOnly'):
            sl_order = order
            break
    
    if sl_order:
        sl_price = Decimal(str(sl_order.get('triggerPrice')))
        logger.info(f"🔍 Current SL at {sl_price}")
        
        # For sell position, SL should be above entry
        if side == "Sell" and sl_price < avg_price:
            logger.warning(f"⚠️ SL price {sl_price} is below entry {avg_price}!")
            logger.warning("This seems incorrect for a sell position")
            
            # Calculate expected SL (e.g., 5% above entry)
            expected_sl = avg_price * Decimal("1.05")
            logger.info(f"💡 Expected SL would be around {expected_sl:.3f} (5% above entry)")
            logger.info("⚠️ Please verify this SL price is intentional")
        else:
            logger.info("✅ SL price seems reasonable")
    else:
        logger.warning("❌ No SL order found for INJUSDT")

async def main():
    """Run all fixes"""
    logger.info("🚀 Starting Fast Approach Order Fixes")
    
    # Fix TIAUSDT SL orders
    await fix_tiausdt_sl()
    
    # Fix BTCUSDT duplicate SL
    await fix_btcusdt_duplicate_sl()
    
    # Check INJUSDT SL price
    await check_injusdt_sl()
    
    logger.info("\n✅ Fast approach order fixes complete!")

if __name__ == "__main__":
    asyncio.run(main())