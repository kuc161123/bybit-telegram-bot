#!/usr/bin/env python3
"""
Fix TIAUSDT mirror position - Low TP coverage (49.9%)
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

from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
from utils.helpers import value_adjusted_to_step

async def analyze_tiausdt_mirror():
    """Analyze TIAUSDT position and orders on mirror account"""
    logger.info("Analyzing TIAUSDT position on mirror account...")
    
    if not is_mirror_trading_enabled() or not bybit_client_2:
        logger.error("Mirror trading not enabled")
        return None, None, None
    
    # Get position
    response = bybit_client_2.get_positions(
        category="linear",
        symbol="TIAUSDT"
    )
    
    position = None
    if response and response.get('retCode') == 0:
        positions = response.get('result', {}).get('list', [])
        for pos in positions:
            if pos.get('symbol') == 'TIAUSDT' and pos.get('side') == 'Buy' and float(pos.get('size', 0)) > 0:
                position = pos
                break
    
    if not position:
        logger.error("No TIAUSDT Buy position found on mirror account")
        return None, None, None
    
    position_size = Decimal(str(position['size']))
    avg_price = Decimal(str(position['avgPrice']))
    
    logger.info(f"Position: Buy {position_size} @ avg price {avg_price}")
    
    # Get orders
    response = bybit_client_2.get_open_orders(
        category="linear",
        symbol="TIAUSDT"
    )
    
    orders = []
    if response and response.get('retCode') == 0:
        orders = response.get('result', {}).get('list', [])
    
    # Categorize orders
    tp_orders = []
    sl_order = None
    
    for order in orders:
        order_link_id = order.get('orderLinkId', '')
        if order.get('reduceOnly'):
            if 'TP' in order_link_id:
                tp_orders.append(order)
            elif 'SL' in order_link_id:
                sl_order = order
    
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

async def cancel_existing_tp_orders(symbol: str) -> int:
    """Cancel all existing TP orders"""
    response = bybit_client_2.get_open_orders(
        category="linear",
        symbol=symbol
    )
    
    orders = []
    if response and response.get('retCode') == 0:
        orders = response.get('result', {}).get('list', [])
    
    cancelled_count = 0
    for order in orders:
        order_link_id = order.get('orderLinkId', '')
        if order.get('reduceOnly') and 'TP' in order_link_id:
            try:
                logger.info(f"Cancelling TP order: {order.get('orderId')[:8]}...")
                response = bybit_client_2.cancel_order(
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

async def place_balanced_tp_orders(position: Dict, existing_tp_prices: List[Decimal] = None):
    """Place new TP orders with correct distribution"""
    position_size = Decimal(str(position['size']))
    avg_price = Decimal(str(position['avgPrice']))
    
    logger.info(f"Placing TPs for position: Buy {position_size} @ {avg_price}")
    
    # Conservative approach: 85%, 5%, 5%, 5%
    tp_percentages = [Decimal("0.85"), Decimal("0.05"), Decimal("0.05"), Decimal("0.05")]
    
    # Calculate TP prices if not provided
    if not existing_tp_prices or len(existing_tp_prices) < 4:
        logger.info("Calculating new TP prices...")
        # Mirror the main account's TP distances
        tp_prices = [
            avg_price * Decimal("1.06"),  # ~6% above
            avg_price * Decimal("1.08"),  # ~8% above
            avg_price * Decimal("1.11"),  # ~11% above
            avg_price * Decimal("1.19")   # ~19% above
        ]
    else:
        tp_prices = existing_tp_prices
    
    placed_count = 0
    for i, (percentage, price) in enumerate(zip(tp_percentages, tp_prices[:4])):
        tp_num = i + 1
        tp_qty = value_adjusted_to_step(position_size * percentage, Decimal("0.1"))
        
        if tp_qty <= 0:
            continue
        
        order_link_id = f"BOT_MIRROR_TIAUSDT_TP{tp_num}_REBALANCED"
        
        try:
            logger.info(f"Placing TP{tp_num}: Sell {tp_qty} @ {price} ({percentage*100}%)")
            
            response = bybit_client_2.place_order(
                category="linear",
                symbol="TIAUSDT",
                side="Sell",  # Opposite of Buy position
                orderType="Limit",
                qty=str(tp_qty),
                price=str(price),
                reduceOnly=True,
                orderLinkId=order_link_id,
                positionIdx=0  # Mirror uses One-Way mode
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
    logger.info("Starting TIAUSDT Mirror TP Coverage Fix...")
    logger.info("=" * 60)
    
    # Analyze current situation
    position, tp_orders, sl_order = await analyze_tiausdt_mirror()
    
    if not position:
        return
    
    # Get existing TP prices before cancelling
    existing_tp_prices = []
    for tp in tp_orders:
        if tp.get('price'):
            existing_tp_prices.append(Decimal(str(tp['price'])))
    existing_tp_prices.sort()  # Sort ascending for Buy position
    
    # Cancel existing TPs
    logger.info("\nCancelling existing TP orders...")
    cancelled = await cancel_existing_tp_orders("TIAUSDT")
    logger.info(f"Cancelled {cancelled} TP orders")
    
    # Wait a moment for cancellations to process
    await asyncio.sleep(2)
    
    # Place new balanced TPs
    logger.info("\nPlacing new balanced TP orders...")
    placed = await place_balanced_tp_orders(position, existing_tp_prices)
    
    if placed > 0:
        logger.info(f"\n✅ Placed {placed} new TP orders")
        
        # Verify coverage
        await asyncio.sleep(2)
        response = bybit_client_2.get_open_orders(
            category="linear",
            symbol="TIAUSDT"
        )
        
        orders = []
        if response and response.get('retCode') == 0:
            orders = response.get('result', {}).get('list', [])
        
        position_size = Decimal(str(position['size']))
        tp_total = Decimal("0")
        
        for order in orders:
            if order.get('reduceOnly') and 'TP' in order.get('orderLinkId', ''):
                tp_total += Decimal(str(order.get('qty', '0')))
        
        coverage = (tp_total / position_size * 100) if position_size > 0 else 0
        logger.info(f"New TP coverage: {coverage:.1f}% ({tp_total}/{position_size})")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ TIAUSDT Mirror TP Coverage Fix Completed!")

if __name__ == "__main__":
    asyncio.run(main())