#!/usr/bin/env python3
"""
Fix TIAUSDT main position - Low TP coverage (50%)
"""
import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional
import pickle

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from clients.bybit_client import bybit_client
from clients.bybit_helpers import get_open_orders, get_position_info
from utils.helpers import value_adjusted_to_step

async def analyze_tiausdt_position():
    """Analyze TIAUSDT position and orders"""
    logger.info("Analyzing TIAUSDT position on main account...")
    
    # Get position
    positions = await get_position_info("TIAUSDT")
    position = None
    for pos in positions:
        if float(pos.get('size', 0)) > 0 and pos.get('side') == 'Buy':
            position = pos
            break
    
    if not position:
        logger.error("No TIAUSDT Buy position found on main account")
        return None, None, None
    
    position_size = Decimal(str(position['size']))
    avg_price = Decimal(str(position['avgPrice']))
    
    logger.info(f"Position: Buy {position_size} @ avg price {avg_price}")
    
    # Get orders
    orders = await get_open_orders("TIAUSDT")
    
    # Categorize orders
    tp_orders = []
    sl_order = None
    entry_orders = []
    
    for order in orders:
        order_link_id = order.get('orderLinkId', '')
        if order.get('reduceOnly'):
            if 'TP' in order_link_id:
                tp_orders.append(order)
            elif 'SL' in order_link_id:
                sl_order = order
        else:
            # Pending entry orders
            entry_orders.append(order)
    
    # Calculate current TP coverage
    tp_total_qty = sum(Decimal(str(tp.get('qty', '0'))) for tp in tp_orders)
    tp_coverage = (tp_total_qty / position_size * 100) if position_size > 0 else 0
    
    logger.info(f"Current TP coverage: {tp_coverage:.1f}% ({tp_total_qty}/{position_size})")
    logger.info(f"Found {len(tp_orders)} TP orders")
    
    # Sort TP orders by price (descending for Buy position)
    tp_orders.sort(key=lambda x: float(x.get('price', 0)), reverse=True)
    
    for i, tp in enumerate(tp_orders):
        logger.info(f"  TP{i+1}: {tp.get('qty')} @ {tp.get('price')} (ID: {tp.get('orderLinkId')})")
    
    return position, tp_orders, sl_order

async def place_missing_tp_orders(position: Dict, existing_tps: List[Dict]):
    """Place missing TP orders to reach 100% coverage"""
    position_size = Decimal(str(position['size']))
    avg_price = Decimal(str(position['avgPrice']))
    
    # Conservative approach: 85%, 5%, 5%, 5%
    target_percentages = [Decimal("0.85"), Decimal("0.05"), Decimal("0.05"), Decimal("0.05")]
    
    # Calculate what we have vs what we need
    existing_total = sum(Decimal(str(tp.get('qty', '0'))) for tp in existing_tps)
    missing_qty = position_size - existing_total
    
    logger.info(f"Need to place TPs for {missing_qty} contracts")
    
    # Determine which TPs are missing
    if len(existing_tps) == 0:
        # No TPs exist, place all 4
        logger.info("No existing TPs, placing full set...")
        
        # Calculate TP prices based on typical conservative approach
        # For Buy position: TP1 closest, TP4 furthest
        tp_distances = [
            Decimal("0.01"),  # 1% above entry
            Decimal("0.015"), # 1.5% above entry
            Decimal("0.02"),  # 2% above entry
            Decimal("0.025")  # 2.5% above entry
        ]
        
        placed_count = 0
        for i, (percentage, distance) in enumerate(zip(target_percentages, tp_distances)):
            tp_num = i + 1
            tp_price = avg_price * (Decimal("1") + distance)
            tp_qty = value_adjusted_to_step(position_size * percentage, Decimal("0.1"))
            
            if tp_qty <= 0:
                continue
            
            order_link_id = f"BOT_TIAUSDT_TP{tp_num}_FIX"
            
            try:
                logger.info(f"Placing TP{tp_num}: Sell {tp_qty} @ {tp_price}")
                
                response = bybit_client.place_order(
                    category="linear",
                    symbol="TIAUSDT",
                    side="Sell",  # Opposite of Buy position
                    orderType="Limit",
                    qty=str(tp_qty),
                    price=str(tp_price),
                    reduceOnly=True,
                    orderLinkId=order_link_id,
                    positionIdx=0
                )
                
                if response and response.get("retCode") == 0:
                    result = response.get("result", {})
                    order_id = result.get("orderId", "")
                    logger.info(f"✅ TP{tp_num} placed: {order_id[:8]}...")
                    placed_count += 1
                else:
                    logger.error(f"❌ TP{tp_num} failed: {response}")
                    
            except Exception as e:
                logger.error(f"❌ Exception placing TP{tp_num}: {e}")
            
            await asyncio.sleep(0.5)
        
        return placed_count
    
    else:
        # Some TPs exist, need to adjust or add missing ones
        logger.info(f"Found {len(existing_tps)} existing TPs, adjusting coverage...")
        
        # If we have TP1 but it's only 50%, we need to add more TPs
        # Place additional TPs with the missing quantity
        missing_tp_count = 4 - len(existing_tps)
        
        if missing_tp_count > 0:
            # Get the highest TP price as reference
            highest_tp_price = Decimal(str(existing_tps[0].get('price', '0')))
            
            # Place missing TPs at increasing distances
            qty_per_tp = missing_qty / missing_tp_count
            qty_per_tp = value_adjusted_to_step(qty_per_tp, Decimal("0.1"))
            
            placed_count = 0
            for i in range(missing_tp_count):
                tp_num = len(existing_tps) + i + 1
                # Add 0.5% for each additional TP
                price_increment = highest_tp_price * Decimal("0.005") * (i + 1)
                tp_price = highest_tp_price + price_increment
                
                order_link_id = f"BOT_TIAUSDT_TP{tp_num}_COVERAGE_FIX"
                
                try:
                    logger.info(f"Placing TP{tp_num}: Sell {qty_per_tp} @ {tp_price}")
                    
                    response = bybit_client.place_order(
                        category="linear",
                        symbol="TIAUSDT",
                        side="Sell",
                        orderType="Limit",
                        qty=str(qty_per_tp),
                        price=str(tp_price),
                        reduceOnly=True,
                        orderLinkId=order_link_id,
                        positionIdx=0
                    )
                    
                    if response and response.get("retCode") == 0:
                        result = response.get("result", {})
                        order_id = result.get("orderId", "")
                        logger.info(f"✅ TP{tp_num} placed: {order_id[:8]}...")
                        placed_count += 1
                    else:
                        logger.error(f"❌ TP{tp_num} failed: {response}")
                        
                except Exception as e:
                    logger.error(f"❌ Exception placing TP{tp_num}: {e}")
                
                await asyncio.sleep(0.5)
            
            return placed_count
        
        else:
            logger.warning("All 4 TP slots filled but coverage is low. Manual intervention may be needed.")
            return 0

async def main():
    logger.info("Starting TIAUSDT Main TP Coverage Fix...")
    logger.info("=" * 60)
    
    # Analyze current situation
    position, tp_orders, sl_order = await analyze_tiausdt_position()
    
    if not position:
        return
    
    # Place missing TP orders
    placed_count = await place_missing_tp_orders(position, tp_orders)
    
    if placed_count > 0:
        logger.info(f"\n✅ Placed {placed_count} TP orders to improve coverage")
        
        # Verify new coverage
        await asyncio.sleep(2)
        _, new_tp_orders, _ = await analyze_tiausdt_position()
        
        position_size = Decimal(str(position['size']))
        new_total_qty = sum(Decimal(str(tp.get('qty', '0'))) for tp in new_tp_orders)
        new_coverage = (new_total_qty / position_size * 100) if position_size > 0 else 0
        
        logger.info(f"New TP coverage: {new_coverage:.1f}%")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ TIAUSDT Main TP Coverage Fix Completed!")

if __name__ == "__main__":
    asyncio.run(main())