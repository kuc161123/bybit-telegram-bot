#!/usr/bin/env python3
"""
Fix JUPUSDT mirror position by copying the conservative TP limit orders and SL from main account
"""
import asyncio
import logging
from decimal import Decimal
from typing import List, Dict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from clients.bybit_helpers import get_open_orders, place_order_with_retry
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled, get_mirror_positions
from utils.helpers import value_adjusted_to_step

async def place_mirror_limit_order(
    symbol: str,
    side: str,
    qty: str,
    price: str,
    order_link_id: str
) -> Dict:
    """Place a limit order on mirror account"""
    if not bybit_client_2:
        return None
    
    try:
        logger.info(f"🪞 MIRROR: Placing limit order {side} {qty} @ {price}")
        
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
            logger.info(f"✅ MIRROR: Limit order placed: {order_id[:8]}...")
            return result
        else:
            logger.error(f"❌ MIRROR: Limit order failed: {response}")
            return None
            
    except Exception as e:
        logger.error(f"❌ MIRROR: Exception placing limit order: {e}")
        return None

async def place_mirror_stop_order(
    symbol: str,
    side: str,
    qty: str,
    trigger_price: str,
    order_link_id: str
) -> Dict:
    """Place a stop order on mirror account"""
    if not bybit_client_2:
        return None
    
    try:
        logger.info(f"🪞 MIRROR: Placing stop order {side} {qty} @ trigger {trigger_price}")
        
        # Determine trigger direction based on side
        # For a Sell position: SL triggers when price goes UP (Buy to close)
        # For a Buy position: SL triggers when price goes DOWN (Sell to close)
        if side == "Buy":  # This is the closing side
            trigger_direction = 1  # >=
        else:  # side == "Sell"
            trigger_direction = 2  # <=
        
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
            logger.info(f"✅ MIRROR: Stop order placed: {order_id[:8]}...")
            return result
        else:
            logger.error(f"❌ MIRROR: Stop order failed: {response}")
            return None
            
    except Exception as e:
        logger.error(f"❌ MIRROR: Exception placing stop order: {e}")
        return None

async def main():
    logger.info("Starting JUPUSDT Conservative mirror fix...")
    logger.info("=" * 50)
    
    if not is_mirror_trading_enabled():
        logger.error("❌ Mirror trading is not enabled")
        return
    
    # Get mirror position
    mirror_positions = await get_mirror_positions()
    mirror_position = None
    for pos in mirror_positions:
        if pos.get('symbol') == 'JUPUSDT' and float(pos.get('size', 0)) > 0 and pos.get('side') == 'Sell':
            mirror_position = pos
            break
    
    if not mirror_position:
        logger.error("❌ No active JUPUSDT Sell position found on mirror account")
        return
    
    mirror_size = Decimal(str(mirror_position['size']))
    logger.info(f"✅ Mirror position size: {mirror_size}")
    
    # Get main account orders
    main_orders = await get_open_orders("JUPUSDT")
    
    # Separate orders by type
    tp_orders = []
    sl_order = None
    
    for order in main_orders:
        order_link_id = order.get('orderLinkId', '')
        
        # Skip entry orders (non-reduce-only)
        if not order.get('reduceOnly'):
            continue
            
        # Check for TP orders (limit orders with TP in name)
        if 'TP' in order_link_id and order.get('orderType') == 'Limit':
            tp_orders.append(order)
        
        # Check for SL order (stop order)
        elif 'SL' in order_link_id and order.get('stopOrderType') == 'Stop':
            sl_order = order
    
    logger.info(f"Found {len(tp_orders)} TP orders and {'1' if sl_order else '0'} SL order to replicate")
    
    # Check existing mirror orders
    response = bybit_client_2.get_open_orders(
        category="linear",
        symbol="JUPUSDT"
    )
    
    existing_mirror_orders = []
    if response and response.get('retCode') == 0:
        existing_mirror_orders = response.get('result', {}).get('list', [])
    
    # Check what's already placed
    existing_tp_count = sum(1 for o in existing_mirror_orders if 'TP' in o.get('orderLinkId', '') and o.get('reduceOnly'))
    existing_sl_count = sum(1 for o in existing_mirror_orders if 'SL' in o.get('orderLinkId', '') and o.get('reduceOnly'))
    
    logger.info(f"Mirror account already has: {existing_tp_count} TP orders, {existing_sl_count} SL orders")
    
    placed_orders = []
    
    # Place TP orders
    if tp_orders and existing_tp_count == 0:
        logger.info("\nPlacing TP orders...")
        
        # Sort TP orders by price
        tp_orders.sort(key=lambda x: float(x.get('price', 0)))
        
        # Calculate proportional quantities
        # Conservative approach: 85%, 5%, 5%, 5%
        tp_percentages = [Decimal("0.85"), Decimal("0.05"), Decimal("0.05"), Decimal("0.05")]
        
        for i, (tp_order, percentage) in enumerate(zip(tp_orders, tp_percentages)):
            tp_num = i + 1
            tp_price = tp_order.get('price')
            tp_qty = value_adjusted_to_step(mirror_size * percentage, Decimal("1"))
            
            # Generate order link ID
            order_link_id = f"BOT_MIRROR_JUPUSDT_TP{tp_num}_MANUAL"
            
            logger.info(f"   TP{tp_num}: {tp_qty} @ {tp_price}")
            
            result = await place_mirror_limit_order(
                symbol="JUPUSDT",
                side="Buy",  # Opposite of position side
                qty=str(tp_qty),
                price=str(tp_price),
                order_link_id=order_link_id
            )
            
            if result:
                placed_orders.append(('TP', result.get('orderId')))
    
    # Place SL order
    if sl_order and existing_sl_count == 0:
        logger.info("\nPlacing SL order...")
        
        sl_trigger_price = sl_order.get('triggerPrice')
        sl_qty = mirror_size  # SL covers full position
        
        # Generate order link ID
        order_link_id = "BOT_MIRROR_JUPUSDT_SL_MANUAL"
        
        logger.info(f"   SL: {sl_qty} @ trigger {sl_trigger_price}")
        
        result = await place_mirror_stop_order(
            symbol="JUPUSDT",
            side="Buy",  # Opposite of position side
            qty=str(sl_qty),
            trigger_price=str(sl_trigger_price),
            order_link_id=order_link_id
        )
        
        if result:
            placed_orders.append(('SL', result.get('orderId')))
    
    logger.info("\n" + "=" * 50)
    logger.info(f"✅ Placed {len(placed_orders)} orders on mirror account")
    
    # Enable Enhanced TP/SL monitoring
    logger.info("\nEnabling Enhanced TP/SL monitoring...")
    
    import pickle
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    try:
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        monitor_key = "JUPUSDT_Sell"
        
        if monitor_key in enhanced_monitors:
            monitor_data = enhanced_monitors[monitor_key]
            if not monitor_data.get('has_mirror'):
                monitor_data['has_mirror'] = True
                monitor_data['mirror_synced'] = True
                
                with open(pickle_file, 'wb') as f:
                    pickle.dump(data, f)
                logger.info("✅ Enabled mirror monitoring")
            else:
                logger.info("✅ Mirror monitoring already enabled")
        else:
            logger.warning("⚠️ No Enhanced TP/SL monitor found for JUPUSDT_Sell")
            
    except Exception as e:
        logger.error(f"❌ Error updating monitor: {e}")
    
    logger.info("\n✅ JUPUSDT Conservative mirror fix completed!")

if __name__ == "__main__":
    asyncio.run(main())