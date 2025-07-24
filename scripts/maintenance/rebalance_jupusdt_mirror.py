#!/usr/bin/env python3
"""
Rebalance JUPUSDT on mirror account
"""

import asyncio
from decimal import Decimal
import logging
import time

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    """Rebalance JUPUSDT on mirror account"""
    
    logger.info("🔄 REBALANCING JUPUSDT ON MIRROR ACCOUNT...")
    logger.info("="*60)
    
    from execution.mirror_trader import (
        bybit_client_2,
        get_mirror_positions,
        place_mirror_tp_sl_order,
        get_mirror_position_info
    )
    from clients.bybit_helpers import get_instrument_info, get_all_open_orders
    from utils.helpers import value_adjusted_to_step, safe_decimal_conversion
    
    # Check mirror position
    positions = await get_mirror_positions()
    jup_position = next((p for p in positions if p.get('symbol') == 'JUPUSDT' and float(p.get('size', 0)) > 0), None)
    
    if not jup_position:
        logger.error("❌ No JUPUSDT position found on mirror account")
        return
    
    position_size = safe_decimal_conversion(jup_position.get('size', '0'))
    side = jup_position.get('side')
    avg_price = safe_decimal_conversion(jup_position.get('avgPrice', '0'))
    
    logger.info(f"✅ Found JUPUSDT mirror position: {position_size} @ {avg_price} ({side})")
    
    # Get main account orders to copy TP/SL prices
    main_orders = await get_all_open_orders()
    jup_main_orders = [o for o in main_orders if o.get('symbol') == 'JUPUSDT']
    
    # Extract TP prices from main account
    tp_prices = []
    for order in jup_main_orders:
        if 'TP1' in order.get('orderLinkId', ''):
            tp_prices.insert(0, safe_decimal_conversion(order.get('triggerPrice')))
        elif 'TP2' in order.get('orderLinkId', ''):
            tp_prices.insert(1, safe_decimal_conversion(order.get('triggerPrice')))
        elif 'TP3' in order.get('orderLinkId', ''):
            tp_prices.insert(2, safe_decimal_conversion(order.get('triggerPrice')))
        elif 'TP4' in order.get('orderLinkId', ''):
            tp_prices.insert(3, safe_decimal_conversion(order.get('triggerPrice')))
    
    # Find SL price
    sl_price = None
    for order in jup_main_orders:
        if 'SL' in order.get('orderLinkId', '') and order.get('stopOrderType') == 'StopLoss':
            sl_price = safe_decimal_conversion(order.get('triggerPrice'))
            break
    
    logger.info(f"Found {len(tp_prices)} TP prices from main account")
    logger.info(f"SL price: {sl_price}")
    
    # Get symbol info
    symbol_info = await get_instrument_info('JUPUSDT')
    qty_step = safe_decimal_conversion(symbol_info.get('lotSizeFilter', {}).get('qtyStep', '0.001'))
    
    # Calculate quantities for conservative approach
    tp_distributions = [0.85, 0.05, 0.05, 0.05]
    tp_quantities = []
    
    for pct in tp_distributions:
        qty = position_size * Decimal(str(pct))
        qty = value_adjusted_to_step(qty, qty_step)
        tp_quantities.append(qty)
    
    sl_quantity = value_adjusted_to_step(position_size, qty_step)
    
    # Place TP orders
    tp_side = "Sell" if side == "Buy" else "Buy"
    trade_group_id = "manual"
    
    logger.info("📍 Placing TP orders on mirror account...")
    
    for i, (tp_price, tp_qty) in enumerate(zip(tp_prices, tp_quantities), 1):
        if tp_price and tp_qty > 0:
            timestamp = int(time.time() * 1000) % 100000
            order_link_id = f"BOT_CONS_{trade_group_id}_TP{i}_MIRROR_{timestamp}"
            
            result = await place_mirror_tp_sl_order(
                symbol='JUPUSDT',
                side=tp_side,
                qty=str(tp_qty),
                trigger_price=str(tp_price),
                position_idx=0,  # Will be auto-detected
                order_link_id=order_link_id,
                stop_order_type="TakeProfit"
            )
            
            if result:
                logger.info(f"✅ Placed TP{i}: {tp_qty} @ {tp_price}")
            else:
                logger.error(f"❌ Failed to place TP{i}")
    
    # Place SL order
    if sl_price and sl_quantity > 0:
        logger.info("📍 Placing SL order on mirror account...")
        
        timestamp = int(time.time() * 1000) % 100000
        order_link_id = f"BOT_CONS_{trade_group_id}_SL_MIRROR_{timestamp}"
        
        result = await place_mirror_tp_sl_order(
            symbol='JUPUSDT',
            side=tp_side,
            qty=str(sl_quantity),
            trigger_price=str(sl_price),
            position_idx=0,  # Will be auto-detected
            order_link_id=order_link_id,
            stop_order_type="StopLoss"
        )
        
        if result:
            logger.info(f"✅ Placed SL: {sl_quantity} @ {sl_price}")
        else:
            logger.error("❌ Failed to place SL")
    
    logger.info("\n" + "="*60)
    logger.info("✅ JUPUSDT MIRROR REBALANCING COMPLETE!")
    logger.info("="*60)

if __name__ == "__main__":
    asyncio.run(main())