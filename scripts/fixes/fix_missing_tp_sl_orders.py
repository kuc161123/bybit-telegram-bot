#!/usr/bin/env python3
"""
Fix missing TP/SL orders for specific positions
"""
import asyncio
from decimal import Decimal
from clients.bybit_helpers import get_all_positions, get_all_open_orders, place_order_with_retry
from utils.helpers import value_adjusted_to_step
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_tp_orders_for_sandusdt():
    """Create missing TP orders for SANDUSDT position"""
    
    # Get position info
    positions = await get_all_positions()
    sandusdt_pos = None
    
    for pos in positions:
        if pos.get('symbol') == 'SANDUSDT' and float(pos.get('size', 0)) > 0:
            sandusdt_pos = pos
            break
    
    if not sandusdt_pos:
        logger.error("No SANDUSDT position found")
        return
    
    # Position details
    side = sandusdt_pos.get('side')  # Buy
    size = float(sandusdt_pos.get('size', 0))  # 4541
    avg_price = float(sandusdt_pos.get('avgPrice', 0))  # 0.2595
    position_idx = int(sandusdt_pos.get('positionIdx', 0))  # Get actual position index
    
    logger.info(f"SANDUSDT Position: {side} {size} @ ${avg_price:.4f}, positionIdx: {position_idx}")
    
    # Calculate TP prices based on conservative approach (4 TPs)
    # TP1: 70% of position at 6.5% gain
    # TP2-4: 10% each at 7.5%, 8.5%, 10.5% gain
    
    if side == 'Buy':
        tp1_price = avg_price * 1.065  # 6.5% gain
        tp2_price = avg_price * 1.075  # 7.5% gain
        tp3_price = avg_price * 1.085  # 8.5% gain
        tp4_price = avg_price * 1.105  # 10.5% gain
    else:
        tp1_price = avg_price * 0.935  # 6.5% gain for short
        tp2_price = avg_price * 0.925  # 7.5% gain
        tp3_price = avg_price * 0.915  # 8.5% gain
        tp4_price = avg_price * 0.895  # 10.5% gain
    
    # Get tick size for SANDUSDT
    tick_size = Decimal("0.0001")  # Common for SANDUSDT
    
    # Adjust prices to tick size
    tp1_price = float(value_adjusted_to_step(Decimal(str(tp1_price)), tick_size))
    tp2_price = float(value_adjusted_to_step(Decimal(str(tp2_price)), tick_size))
    tp3_price = float(value_adjusted_to_step(Decimal(str(tp3_price)), tick_size))
    tp4_price = float(value_adjusted_to_step(Decimal(str(tp4_price)), tick_size))
    
    # Calculate quantities
    tp1_qty = int(size * 0.7)  # 70%
    tp2_qty = int(size * 0.1)  # 10%
    tp3_qty = int(size * 0.1)  # 10%
    tp4_qty = size - tp1_qty - tp2_qty - tp3_qty  # Remaining
    
    logger.info(f"Creating TP orders:")
    logger.info(f"  TP1: {tp1_qty} @ ${tp1_price:.4f} (6.5% gain)")
    logger.info(f"  TP2: {tp2_qty} @ ${tp2_price:.4f} (7.5% gain)")
    logger.info(f"  TP3: {tp3_qty} @ ${tp3_price:.4f} (8.5% gain)")
    logger.info(f"  TP4: {tp4_qty} @ ${tp4_price:.4f} (10.5% gain)")
    
    # Create TP orders
    tp_orders = [
        ('TP1', tp1_price, tp1_qty),
        ('TP2', tp2_price, tp2_qty),
        ('TP3', tp3_price, tp3_qty),
        ('TP4', tp4_price, tp4_qty)
    ]
    
    for tp_name, price, qty in tp_orders:
        if qty <= 0:
            continue
            
        try:
            # Place TP order using the helper function
            result = await place_order_with_retry(
                symbol="SANDUSDT",
                side="Sell" if side == "Buy" else "Buy",
                order_type="Market",
                qty=str(qty),
                trigger_price=str(price),
                position_idx=position_idx,
                reduce_only=True,
                order_link_id=f"MANUAL_SANDUSDT_{tp_name}"
            )
            
            if result and result.get('retCode') == 0:
                order_id = result.get('result', {}).get('orderId')
                logger.info(f"✅ {tp_name} order created: {order_id}")
            else:
                logger.error(f"❌ Failed to create {tp_name}: {result}")
                
        except Exception as e:
            logger.error(f"❌ Error creating {tp_name}: {e}")

async def create_sl_order_for_bchusdt():
    """Create missing SL order for BCHUSDT position"""
    
    # Get position info
    positions = await get_all_positions()
    bchusdt_pos = None
    
    for pos in positions:
        if pos.get('symbol') == 'BCHUSDT' and float(pos.get('size', 0)) > 0:
            bchusdt_pos = pos
            break
    
    if not bchusdt_pos:
        logger.error("No BCHUSDT position found")
        return
    
    # Position details
    side = bchusdt_pos.get('side')  # Sell
    size = float(bchusdt_pos.get('size', 0))  # 1.65
    avg_price = float(bchusdt_pos.get('avgPrice', 0))  # 444.8
    position_idx = int(bchusdt_pos.get('positionIdx', 0))  # Get actual position index
    
    logger.info(f"BCHUSDT Position: {side} {size} @ ${avg_price:.1f}, positionIdx: {position_idx}")
    
    # Calculate SL price (6% loss)
    if side == 'Sell':
        sl_price = avg_price * 1.06  # 6% above entry for short
    else:
        sl_price = avg_price * 0.94  # 6% below entry for long
    
    # Get tick size for BCHUSDT
    tick_size = Decimal("0.1")  # Common for BCHUSDT
    
    # Adjust price to tick size
    sl_price = float(value_adjusted_to_step(Decimal(str(sl_price)), tick_size))
    
    logger.info(f"Creating SL order: {size} @ ${sl_price:.1f} (6% loss)")
    
    try:
        # Place SL order using the helper function
        result = await place_order_with_retry(
            symbol="BCHUSDT",
            side="Buy" if side == "Sell" else "Sell",
            order_type="Market",
            qty=str(size),
            trigger_price=str(sl_price),
            position_idx=position_idx,
            reduce_only=True,
            order_link_id=f"MANUAL_BCHUSDT_SL_2"  # Changed to avoid duplicate
        )
        
        if result and result.get('retCode') == 0:
            order_id = result.get('result', {}).get('orderId')
            logger.info(f"✅ SL order created: {order_id}")
        else:
            logger.error(f"❌ Failed to create SL: {result}")
            
    except Exception as e:
        logger.error(f"❌ Error creating SL: {e}")

async def main():
    """Fix missing TP/SL orders"""
    logger.info("=== Fixing Missing TP/SL Orders ===")
    
    # Fix SANDUSDT (missing TPs)
    logger.info("\n1. Fixing SANDUSDT - Creating missing TP orders...")
    await create_tp_orders_for_sandusdt()
    
    # Fix BCHUSDT (missing SL)
    logger.info("\n2. Fixing BCHUSDT - Creating missing SL order...")
    await create_sl_order_for_bchusdt()
    
    logger.info("\n=== Complete ===")

if __name__ == "__main__":
    asyncio.run(main())