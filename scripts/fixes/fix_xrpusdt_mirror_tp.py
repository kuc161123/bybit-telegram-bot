#!/usr/bin/env python3
"""
Fix XRPUSDT mirror position by copying missing TP orders from main account
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

from clients.bybit_helpers import get_open_orders
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

async def main():
    logger.info("Starting XRPUSDT mirror TP fix...")
    logger.info("=" * 50)
    
    if not is_mirror_trading_enabled():
        logger.error("❌ Mirror trading is not enabled")
        return
    
    # Get mirror position
    mirror_positions = await get_mirror_positions()
    mirror_position = None
    for pos in mirror_positions:
        if pos.get('symbol') == 'XRPUSDT' and float(pos.get('size', 0)) > 0 and pos.get('side') == 'Buy':
            mirror_position = pos
            break
    
    if not mirror_position:
        logger.error("❌ No active XRPUSDT Buy position found on mirror account")
        return
    
    mirror_size = Decimal(str(mirror_position['size']))
    logger.info(f"✅ Mirror position size: {mirror_size}")
    
    # Get main account orders
    main_orders = await get_open_orders("XRPUSDT")
    
    # Find TP orders on main account
    tp_orders = []
    for order in main_orders:
        order_link_id = order.get('orderLinkId', '')
        
        # Skip entry orders (non-reduce-only)
        if not order.get('reduceOnly'):
            continue
            
        # Check for TP orders (limit orders with TP in name)
        if 'TP' in order_link_id and order.get('orderType') == 'Limit':
            tp_orders.append(order)
    
    logger.info(f"Found {len(tp_orders)} TP orders on main account to replicate")
    
    if not tp_orders:
        logger.error("❌ No TP orders found on main account")
        return
    
    # Check existing mirror orders
    response = bybit_client_2.get_open_orders(
        category="linear",
        symbol="XRPUSDT"
    )
    
    existing_mirror_orders = []
    if response and response.get('retCode') == 0:
        existing_mirror_orders = response.get('result', {}).get('list', [])
    
    # Check what's already placed
    existing_tp_count = sum(1 for o in existing_mirror_orders if 'TP' in o.get('orderLinkId', '') and o.get('reduceOnly'))
    
    logger.info(f"Mirror account already has: {existing_tp_count} TP orders")
    
    if existing_tp_count > 0:
        logger.warning("⚠️ Mirror account already has TP orders, skipping")
        return
    
    placed_orders = []
    
    # Place TP orders
    logger.info("\nPlacing TP orders...")
    
    # Sort TP orders by price (descending for Buy position)
    tp_orders.sort(key=lambda x: float(x.get('price', 0)), reverse=True)
    
    # Calculate proportional quantities
    # Conservative approach: 85%, 5%, 5%, 5%
    # For XRPUSDT with position size 87:
    # TP1: 74 (85%)
    # TP2: 4 (5%)
    # TP3: 4 (5%)
    # TP4: 5 (5% + remainder to make total = 87)
    tp_quantities = [74, 4, 4, 5] if mirror_size == 87 else [
        int(mirror_size * Decimal("0.85")),
        int(mirror_size * Decimal("0.05")),
        int(mirror_size * Decimal("0.05")),
        int(mirror_size * Decimal("0.05"))
    ]
    
    # Adjust last TP to ensure total equals position size
    total_allocated = sum(tp_quantities[:-1])
    tp_quantities[-1] = int(mirror_size - total_allocated)
    
    for i, (tp_order, tp_qty) in enumerate(zip(tp_orders, tp_quantities)):
        tp_num = i + 1
        tp_price = tp_order.get('price')
        
        # Generate order link ID
        order_link_id = f"BOT_MIRROR_XRPUSDT_TP{tp_num}_MANUAL"
        
        logger.info(f"   TP{tp_num}: {tp_qty} @ {tp_price}")
        
        result = await place_mirror_limit_order(
            symbol="XRPUSDT",
            side="Sell",  # Opposite of position side (Buy)
            qty=str(tp_qty),
            price=str(tp_price),
            order_link_id=order_link_id
        )
        
        if result:
            placed_orders.append(('TP', result.get('orderId')))
    
    logger.info("\n" + "=" * 50)
    logger.info(f"✅ Placed {len(placed_orders)} TP orders on mirror account")
    
    # Enable Enhanced TP/SL monitoring
    logger.info("\nEnabling Enhanced TP/SL monitoring...")
    
    import pickle
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    try:
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        monitor_key = "XRPUSDT_Buy"
        
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
            logger.warning("⚠️ No Enhanced TP/SL monitor found for XRPUSDT_Buy")
            
    except Exception as e:
        logger.error(f"❌ Error updating monitor: {e}")
    
    logger.info("\n✅ XRPUSDT mirror TP fix completed!")

if __name__ == "__main__":
    asyncio.run(main())