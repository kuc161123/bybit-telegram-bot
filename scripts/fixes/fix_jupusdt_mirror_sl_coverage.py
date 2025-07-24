#!/usr/bin/env python3
"""
Fix JUPUSDT mirror position - Low SL coverage (33.3%)
SL should cover full position including pending limit orders
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

async def analyze_jupusdt_mirror():
    """Analyze JUPUSDT position and orders on mirror account"""
    logger.info("Analyzing JUPUSDT position on mirror account...")
    
    if not is_mirror_trading_enabled() or not bybit_client_2:
        logger.error("Mirror trading not enabled")
        return None, None, None, None
    
    # Get position
    response = bybit_client_2.get_positions(
        category="linear",
        symbol="JUPUSDT"
    )
    
    position = None
    if response and response.get('retCode') == 0:
        positions = response.get('result', {}).get('list', [])
        for pos in positions:
            if pos.get('symbol') == 'JUPUSDT' and pos.get('side') == 'Sell' and float(pos.get('size', 0)) > 0:
                position = pos
                break
    
    if not position:
        logger.error("No JUPUSDT Sell position found on mirror account")
        return None, None, None, None
    
    position_size = Decimal(str(position['size']))
    avg_price = Decimal(str(position['avgPrice']))
    
    logger.info(f"Position: Sell {position_size} @ avg price {avg_price}")
    
    # Get orders
    response = bybit_client_2.get_open_orders(
        category="linear",
        symbol="JUPUSDT"
    )
    
    orders = []
    if response and response.get('retCode') == 0:
        orders = response.get('result', {}).get('list', [])
    
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
    
    # Calculate pending entry size
    pending_qty = sum(Decimal(str(e.get('qty', '0'))) for e in entry_orders)
    target_size = position_size + pending_qty
    
    # Calculate current SL coverage
    sl_qty = Decimal(str(sl_order.get('qty', '0'))) if sl_order else Decimal('0')
    sl_coverage = (sl_qty / target_size * 100) if target_size > 0 else 0
    
    logger.info(f"Current position: {position_size}")
    logger.info(f"Pending entries: {pending_qty}")
    logger.info(f"Target size: {target_size}")
    logger.info(f"Current SL coverage: {sl_coverage:.1f}% ({sl_qty}/{target_size})")
    
    if sl_order:
        logger.info(f"Existing SL: {sl_order.get('qty')} @ trigger {sl_order.get('triggerPrice')}")
    
    return position, sl_order, entry_orders, target_size

async def update_sl_coverage(position: Dict, sl_order: Dict, target_size: Decimal):
    """Update SL order to cover full target position"""
    
    # Cancel existing SL
    if sl_order:
        try:
            logger.info(f"Cancelling existing SL order: {sl_order.get('orderId')[:8]}...")
            response = bybit_client_2.cancel_order(
                category="linear",
                symbol="JUPUSDT",
                orderId=sl_order.get('orderId')
            )
            if response and response.get('retCode') == 0:
                logger.info("✅ Cancelled existing SL order")
            else:
                logger.error(f"❌ Failed to cancel SL: {response}")
                return False
        except Exception as e:
            logger.error(f"Error cancelling SL: {e}")
            return False
        
        await asyncio.sleep(1)
    
    # Place new SL with full coverage
    sl_trigger = sl_order.get('triggerPrice') if sl_order else None
    
    if not sl_trigger:
        # Calculate SL price if not available
        avg_price = Decimal(str(position['avgPrice']))
        sl_trigger = avg_price * Decimal("1.08")  # 8% above for Sell position
        logger.info(f"Calculated SL trigger price: {sl_trigger}")
    
    # For Sell position: SL triggers when price goes UP (Buy to close)
    trigger_direction = 1  # >= (price rises above trigger)
    
    order_link_id = "BOT_MIRROR_JUPUSDT_SL_FULL_COVERAGE"
    
    try:
        logger.info(f"Placing new SL: Buy {int(target_size)} @ trigger {sl_trigger}")
        
        response = bybit_client_2.place_order(
            category="linear",
            symbol="JUPUSDT",
            side="Buy",  # Opposite of Sell position
            orderType="Market",
            qty=str(int(target_size)),
            triggerPrice=str(sl_trigger),
            triggerDirection=trigger_direction,
            reduceOnly=True,
            orderLinkId=order_link_id,
            positionIdx=0  # Mirror uses One-Way mode
        )
        
        if response and response.get("retCode") == 0:
            result = response.get("result", {})
            order_id = result.get("orderId", "")
            logger.info(f"✅ New SL placed with full coverage: {order_id[:8]}...")
            return True
        else:
            logger.error(f"❌ Failed to place new SL: {response}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Exception placing new SL: {e}")
        return False

async def main():
    logger.info("Starting JUPUSDT Mirror SL Coverage Fix...")
    logger.info("=" * 60)
    
    # Analyze current situation
    position, sl_order, entry_orders, target_size = await analyze_jupusdt_mirror()
    
    if not position:
        return
    
    # Update SL coverage
    success = await update_sl_coverage(position, sl_order, target_size)
    
    if success:
        # Verify new coverage
        await asyncio.sleep(2)
        _, new_sl_order, _, _ = await analyze_jupusdt_mirror()
        
        if new_sl_order:
            new_sl_qty = Decimal(str(new_sl_order.get('qty', '0')))
            new_coverage = (new_sl_qty / target_size * 100) if target_size > 0 else 0
            logger.info(f"\n✅ New SL coverage: {new_coverage:.1f}% ({new_sl_qty}/{target_size})")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ JUPUSDT Mirror SL Coverage Fix Completed!")

if __name__ == "__main__":
    asyncio.run(main())