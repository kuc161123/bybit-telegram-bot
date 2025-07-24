#!/usr/bin/env python3
"""
Fix ICPUSDT mirror position - CRITICAL: Has NO TP/SL orders
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

from clients.bybit_helpers import get_open_orders, get_position_info
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
from utils.helpers import value_adjusted_to_step

async def get_main_icpusdt_orders():
    """Get ICPUSDT orders from main account as reference"""
    logger.info("Getting main account ICPUSDT orders...")
    
    # Get main position
    main_positions = await get_position_info("ICPUSDT")
    main_position = None
    for pos in main_positions:
        if float(pos.get('size', 0)) > 0 and pos.get('side') == 'Sell':
            main_position = pos
            break
    
    if not main_position:
        logger.error("No ICPUSDT Sell position found on main account")
        return None, None
    
    # Get main orders
    main_orders = await get_open_orders("ICPUSDT")
    
    # Categorize orders
    tp_orders = []
    sl_order = None
    
    for order in main_orders:
        order_link_id = order.get('orderLinkId', '')
        if order.get('reduceOnly'):
            if 'TP' in order_link_id:
                tp_orders.append(order)
            elif 'SL' in order_link_id:
                sl_order = order
    
    # Sort TP orders by price (ascending for Sell position)
    tp_orders.sort(key=lambda x: float(x.get('price', 0)))
    
    return tp_orders, sl_order

async def place_mirror_tp_order(
    symbol: str,
    side: str,
    qty: str,
    price: str,
    order_link_id: str
) -> Optional[Dict]:
    """Place TP limit order on mirror account"""
    if not bybit_client_2:
        return None
    
    try:
        logger.info(f"🪞 MIRROR: Placing TP order {side} {qty} @ {price}")
        
        response = bybit_client_2.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Limit",
            qty=qty,
            price=price,
            reduceOnly=True,
            orderLinkId=order_link_id,
            positionIdx=0  # Mirror uses One-Way mode
        )
        
        if response and response.get("retCode") == 0:
            result = response.get("result", {})
            order_id = result.get("orderId", "")
            logger.info(f"✅ MIRROR: TP order placed: {order_id[:8]}...")
            return result
        else:
            logger.error(f"❌ MIRROR: TP order failed: {response}")
            return None
            
    except Exception as e:
        logger.error(f"❌ MIRROR: Exception placing TP order: {e}")
        return None

async def place_mirror_sl_order(
    symbol: str,
    side: str,
    qty: str,
    trigger_price: str,
    order_link_id: str
) -> Optional[Dict]:
    """Place SL stop order on mirror account"""
    if not bybit_client_2:
        return None
    
    try:
        logger.info(f"🛡️ MIRROR: Placing SL order {side} {qty} @ trigger {trigger_price}")
        
        # For a Sell position: SL triggers when price goes UP (Buy to close)
        trigger_direction = 1  # >= (price rises above trigger)
        
        response = bybit_client_2.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=qty,
            triggerPrice=trigger_price,
            triggerDirection=trigger_direction,
            reduceOnly=True,
            orderLinkId=order_link_id,
            positionIdx=0  # Mirror uses One-Way mode
        )
        
        if response and response.get("retCode") == 0:
            result = response.get("result", {})
            order_id = result.get("orderId", "")
            logger.info(f"✅ MIRROR: SL order placed: {order_id[:8]}...")
            return result
        else:
            logger.error(f"❌ MIRROR: SL order failed: {response}")
            return None
            
    except Exception as e:
        logger.error(f"❌ MIRROR: Exception placing SL order: {e}")
        return None

async def main():
    logger.info("Starting ICPUSDT Mirror CRITICAL Fix...")
    logger.info("=" * 60)
    
    if not is_mirror_trading_enabled():
        logger.error("❌ Mirror trading is not enabled")
        return
    
    # Get mirror position
    response = bybit_client_2.get_positions(
        category="linear",
        symbol="ICPUSDT"
    )
    
    mirror_position = None
    if response and response.get('retCode') == 0:
        positions = response.get('result', {}).get('list', [])
        for pos in positions:
            if pos.get('symbol') == 'ICPUSDT' and pos.get('side') == 'Sell' and float(pos.get('size', 0)) > 0:
                mirror_position = pos
                break
    
    if not mirror_position:
        logger.error("❌ No active ICPUSDT Sell position found on mirror account")
        return
    
    mirror_size = Decimal(str(mirror_position['size']))
    mirror_avg_price = Decimal(str(mirror_position['avgPrice']))
    
    logger.info(f"Mirror position: Sell {mirror_size} @ avg price {mirror_avg_price}")
    
    # Get main account orders as reference
    main_tp_orders, main_sl_order = await get_main_icpusdt_orders()
    
    if not main_tp_orders or not main_sl_order:
        logger.error("❌ Could not get reference orders from main account")
        return
    
    logger.info(f"Found {len(main_tp_orders)} TP orders and 1 SL order on main account")
    
    # Conservative approach: 85%, 5%, 5%, 5%
    tp_percentages = [Decimal("0.85"), Decimal("0.05"), Decimal("0.05"), Decimal("0.05")]
    
    # Place TP orders
    placed_tp_count = 0
    for i, (main_tp, percentage) in enumerate(zip(main_tp_orders[:4], tp_percentages)):
        tp_num = i + 1
        tp_price = main_tp.get('price')
        tp_qty = value_adjusted_to_step(mirror_size * percentage, Decimal("0.1"))
        
        if tp_qty <= 0:
            continue
        
        order_link_id = f"BOT_MIRROR_ICPUSDT_TP{tp_num}_CRITICAL_FIX"
        
        result = await place_mirror_tp_order(
            symbol="ICPUSDT",
            side="Buy",  # Opposite of Sell position
            qty=str(tp_qty),
            price=str(tp_price),
            order_link_id=order_link_id
        )
        
        if result:
            placed_tp_count += 1
        
        await asyncio.sleep(0.5)
    
    logger.info(f"✅ Placed {placed_tp_count} TP orders")
    
    # Place SL order
    sl_trigger_price = main_sl_order.get('triggerPrice')
    
    # Calculate pending entries to get full target size
    response = bybit_client_2.get_open_orders(
        category="linear",
        symbol="ICPUSDT"
    )
    
    pending_qty = Decimal("0")
    if response and response.get('retCode') == 0:
        orders = response.get('result', {}).get('list', [])
        for order in orders:
            if not order.get('reduceOnly'):
                pending_qty += Decimal(str(order.get('qty', '0')))
    
    target_size = mirror_size + pending_qty
    
    logger.info(f"SL will cover full target position: {target_size} (current: {mirror_size}, pending: {pending_qty})")
    
    order_link_id = "BOT_MIRROR_ICPUSDT_SL_CRITICAL_FIX"
    
    result = await place_mirror_sl_order(
        symbol="ICPUSDT",
        side="Buy",  # Opposite of Sell position
        qty=str(int(target_size)),
        trigger_price=str(sl_trigger_price),
        order_link_id=order_link_id
    )
    
    if result:
        logger.info("✅ SL order placed with full coverage")
    
    # Update Enhanced TP/SL monitor
    logger.info("\nUpdating Enhanced TP/SL monitor...")
    
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    try:
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        monitor_key = "ICPUSDT_Sell"
        
        if monitor_key in enhanced_monitors:
            monitor_data = enhanced_monitors[monitor_key]
            monitor_data['has_mirror'] = True
            monitor_data['mirror_synced'] = True
            monitor_data['target_size'] = str(target_size)
            monitor_data['current_size'] = str(mirror_size)
            
            with open(pickle_file, 'wb') as f:
                pickle.dump(data, f)
            logger.info("✅ Updated Enhanced monitor")
        else:
            logger.warning("⚠️ No Enhanced TP/SL monitor found for ICPUSDT_Sell")
            
    except Exception as e:
        logger.error(f"❌ Error updating monitor: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ ICPUSDT Mirror CRITICAL Fix Completed!")
    logger.info(f"   Placed {placed_tp_count} TP orders and 1 SL order")

if __name__ == "__main__":
    asyncio.run(main())