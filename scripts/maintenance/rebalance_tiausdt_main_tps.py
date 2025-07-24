#!/usr/bin/env python3
"""
Rebalance TIAUSDT main position TPs to achieve 100% coverage
Cancel existing TPs and place new ones with correct quantities
"""
import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from clients.bybit_client import bybit_client
from clients.bybit_helpers import get_open_orders, get_position_info
from utils.helpers import value_adjusted_to_step

async def cancel_existing_tp_orders(symbol: str) -> int:
    """Cancel all existing TP orders"""
    orders = await get_open_orders(symbol)
    
    cancelled_count = 0
    for order in orders:
        order_link_id = order.get('orderLinkId', '')
        if order.get('reduceOnly') and 'TP' in order_link_id:
            try:
                logger.info(f"Cancelling TP order: {order.get('orderId')[:8]}...")
                response = bybit_client.cancel_order(
                    category="linear",
                    symbol=symbol,
                    orderId=order.get('orderId')
                )
                if response and response.get('retCode') == 0:
                    cancelled_count += 1
                    logger.info(f"✅ Cancelled {order_link_id}")
                else:
                    logger.error(f"❌ Failed to cancel: {response}")
            except Exception as e:
                logger.error(f"Error cancelling order: {e}")
            
            await asyncio.sleep(0.3)
    
    return cancelled_count

async def place_balanced_tp_orders(position: Dict):
    """Place new TP orders with correct distribution"""
    position_size = Decimal(str(position['size']))
    avg_price = Decimal(str(position['avgPrice']))
    
    logger.info(f"Placing TPs for position: Buy {position_size} @ {avg_price}")
    
    # Conservative approach: 85%, 5%, 5%, 5%
    tp_percentages = [Decimal("0.85"), Decimal("0.05"), Decimal("0.05"), Decimal("0.05")]
    
    # Get existing TP prices from cancelled orders as reference
    orders = await get_open_orders("TIAUSDT")
    tp_prices = []
    for order in orders:
        if 'TP' in order.get('orderLinkId', '') and order.get('price'):
            tp_prices.append(Decimal(str(order['price'])))
    
    # Sort prices ascending (for Buy position, TP1 is closest/lowest)
    tp_prices.sort()
    
    # If we don't have 4 prices, calculate them
    if len(tp_prices) < 4:
        logger.info("Calculating new TP prices...")
        tp_prices = [
            avg_price * Decimal("1.06"),  # ~6% above
            avg_price * Decimal("1.08"),  # ~8% above
            avg_price * Decimal("1.11"),  # ~11% above
            avg_price * Decimal("1.19")   # ~19% above (matches existing TP4 at 1.9)
        ]
    
    placed_count = 0
    for i, (percentage, price) in enumerate(zip(tp_percentages, tp_prices[:4])):
        tp_num = i + 1
        tp_qty = value_adjusted_to_step(position_size * percentage, Decimal("0.1"))
        
        if tp_qty <= 0:
            continue
        
        order_link_id = f"BOT_TIAUSDT_TP{tp_num}_REBALANCED"
        
        try:
            logger.info(f"Placing TP{tp_num}: Sell {tp_qty} @ {price} ({percentage*100}%)")
            
            response = bybit_client.place_order(
                category="linear",
                symbol="TIAUSDT",
                side="Sell",  # Opposite of Buy position
                orderType="Limit",
                qty=str(tp_qty),
                price=str(price),
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

async def main():
    logger.info("Starting TIAUSDT Main TP Rebalancing...")
    logger.info("=" * 60)
    
    # Get current position
    positions = await get_position_info("TIAUSDT")
    position = None
    for pos in positions:
        if float(pos.get('size', 0)) > 0 and pos.get('side') == 'Buy':
            position = pos
            break
    
    if not position:
        logger.error("No TIAUSDT Buy position found")
        return
    
    # Cancel existing TPs
    logger.info("\nCancelling existing TP orders...")
    cancelled = await cancel_existing_tp_orders("TIAUSDT")
    logger.info(f"Cancelled {cancelled} TP orders")
    
    # Wait a moment for cancellations to process
    await asyncio.sleep(2)
    
    # Place new balanced TPs
    logger.info("\nPlacing new balanced TP orders...")
    placed = await place_balanced_tp_orders(position)
    
    if placed > 0:
        logger.info(f"\n✅ Placed {placed} new TP orders")
        
        # Verify coverage
        await asyncio.sleep(2)
        orders = await get_open_orders("TIAUSDT")
        
        position_size = Decimal(str(position['size']))
        tp_total = Decimal("0")
        
        for order in orders:
            if order.get('reduceOnly') and 'TP' in order.get('orderLinkId', ''):
                tp_total += Decimal(str(order.get('qty', '0')))
        
        coverage = (tp_total / position_size * 100) if position_size > 0 else 0
        logger.info(f"New TP coverage: {coverage:.1f}% ({tp_total}/{position_size})")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ TIAUSDT Main TP Rebalancing Completed!")

if __name__ == "__main__":
    asyncio.run(main())