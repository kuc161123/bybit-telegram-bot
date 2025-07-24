#!/usr/bin/env python3
"""
Fix IDUSDT mirror position by placing missing TP/SL orders
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
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled, get_mirror_positions
from utils.helpers import value_adjusted_to_step

async def get_idusdt_position_and_orders():
    """Get IDUSDT position and orders on both accounts"""
    # Main account
    main_positions = await get_position_info("IDUSDT")
    main_position = None
    for pos in main_positions:
        if float(pos.get('size', 0)) > 0 and pos.get('side') == 'Sell':
            main_position = pos
            break
    
    main_orders = await get_open_orders("IDUSDT")
    
    # Mirror account
    mirror_positions = await get_mirror_positions()
    mirror_position = None
    for pos in mirror_positions:
        if pos.get('symbol') == 'IDUSDT' and float(pos.get('size', 0)) > 0:
            mirror_position = pos
            break
    
    # Get mirror orders
    mirror_orders = []
    if bybit_client_2:
        response = bybit_client_2.get_open_orders(
            category="linear",
            symbol="IDUSDT"
        )
        if response and response.get('retCode') == 0:
            mirror_orders = response.get('result', {}).get('list', [])
    
    return main_position, main_orders, mirror_position, mirror_orders

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
    logger.info("Starting IDUSDT Mirror Orders Fix...")
    logger.info("=" * 60)
    
    if not is_mirror_trading_enabled():
        logger.error("❌ Mirror trading is not enabled")
        return
    
    # Step 1: Get positions and orders
    main_position, main_orders, mirror_position, mirror_orders = await get_idusdt_position_and_orders()
    
    if not main_position:
        logger.error("❌ No active IDUSDT position found on main account")
        return
    
    if not mirror_position:
        logger.error("❌ No active IDUSDT position found on mirror account")
        return
    
    logger.info(f"Main position: {main_position.get('side')} {main_position.get('size')}")
    logger.info(f"Mirror position: {mirror_position.get('side')} {mirror_position.get('size')}")
    
    # Step 2: Analyze orders
    # Main account orders
    main_tp_orders = []
    main_sl_order = None
    main_entry_orders = []
    
    for order in main_orders:
        order_link_id = order.get('orderLinkId', '')
        if order.get('reduceOnly'):
            if 'TP' in order_link_id:
                main_tp_orders.append(order)
            elif 'SL' in order_link_id:
                main_sl_order = order
        else:
            main_entry_orders.append(order)
    
    # Mirror account orders
    mirror_tp_count = sum(1 for o in mirror_orders if o.get('reduceOnly') and 'TP' in o.get('orderLinkId', ''))
    mirror_sl_count = sum(1 for o in mirror_orders if o.get('reduceOnly') and 'SL' in o.get('orderLinkId', ''))
    mirror_entry_orders = [o for o in mirror_orders if not o.get('reduceOnly')]
    
    logger.info(f"\nMain account: {len(main_tp_orders)} TP, {1 if main_sl_order else 0} SL, {len(main_entry_orders)} entry orders")
    logger.info(f"Mirror account: {mirror_tp_count} TP, {mirror_sl_count} SL, {len(mirror_entry_orders)} entry orders")
    
    # Step 3: Calculate sizes
    mirror_current_size = Decimal(str(mirror_position['size']))
    mirror_pending_size = sum(Decimal(str(o.get('qty', '0'))) for o in mirror_entry_orders)
    mirror_target_size = mirror_current_size + mirror_pending_size
    
    logger.info(f"\nMirror position sizing:")
    logger.info(f"  Current filled: {mirror_current_size}")
    logger.info(f"  Pending entries: {mirror_pending_size}")
    logger.info(f"  Target size: {mirror_target_size}")
    
    # Step 4: Place missing TP orders
    if mirror_tp_count == 0 and main_tp_orders:
        logger.info(f"\nPlacing {len(main_tp_orders)} TP orders...")
        
        # Sort TP orders by price (ascending for Sell position)
        main_tp_orders.sort(key=lambda x: float(x.get('price', 0)))
        
        # Conservative approach: 85%, 5%, 5%, 5%
        tp_percentages = [Decimal("0.85"), Decimal("0.05"), Decimal("0.05"), Decimal("0.05")]
        
        placed_tp_count = 0
        for i, (main_tp, percentage) in enumerate(zip(main_tp_orders[:4], tp_percentages)):
            tp_num = i + 1
            tp_price = main_tp.get('price')
            tp_qty = value_adjusted_to_step(mirror_current_size * percentage, Decimal("1"))
            
            if tp_qty <= 0:
                continue
            
            order_link_id = f"BOT_MIRROR_IDUSDT_TP{tp_num}_FIX"
            
            result = await place_mirror_tp_order(
                symbol="IDUSDT",
                side="Buy",  # Opposite of Sell position
                qty=str(tp_qty),
                price=str(tp_price),
                order_link_id=order_link_id
            )
            
            if result:
                placed_tp_count += 1
            
            await asyncio.sleep(0.5)
        
        logger.info(f"✅ Placed {placed_tp_count} TP orders")
    
    # Step 5: Place missing SL order
    if mirror_sl_count == 0 and main_sl_order:
        logger.info(f"\nPlacing SL order...")
        
        sl_trigger_price = main_sl_order.get('triggerPrice')
        # SL should cover full target position including pending orders
        sl_qty = mirror_target_size
        
        order_link_id = "BOT_MIRROR_IDUSDT_SL_FULL_COVERAGE_FIX"
        
        result = await place_mirror_sl_order(
            symbol="IDUSDT",
            side="Buy",  # Opposite of Sell position
            qty=str(int(sl_qty)),
            trigger_price=str(sl_trigger_price),
            order_link_id=order_link_id
        )
        
        if result:
            logger.info("✅ SL order placed with full coverage")
    
    # Step 6: Update Enhanced TP/SL monitor
    logger.info("\nUpdating Enhanced TP/SL monitor...")
    
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    try:
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        monitor_key = "IDUSDT_Sell"
        
        if monitor_key in enhanced_monitors:
            monitor_data = enhanced_monitors[monitor_key]
            monitor_data['has_mirror'] = True
            monitor_data['mirror_synced'] = True
            monitor_data['target_size'] = str(mirror_target_size)
            monitor_data['current_size'] = str(mirror_current_size)
            
            with open(pickle_file, 'wb') as f:
                pickle.dump(data, f)
            logger.info("✅ Updated Enhanced monitor")
        else:
            logger.warning("⚠️ No Enhanced TP/SL monitor found for IDUSDT_Sell")
            
    except Exception as e:
        logger.error(f"❌ Error updating monitor: {e}")
    
    # Step 7: Trigger position sync
    try:
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        await enhanced_tp_sl_manager.sync_existing_positions()
        logger.info("✅ Triggered Enhanced TP/SL position sync")
    except Exception as e:
        logger.warning(f"⚠️ Could not trigger position sync: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ IDUSDT Mirror Orders Fix Completed!")

if __name__ == "__main__":
    asyncio.run(main())