#!/usr/bin/env python3
"""
Fix XRPUSDT mirror SL order by canceling oversized order and placing correct ones
"""
import asyncio
import logging
from decimal import Decimal
from typing import Dict, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from clients.bybit_helpers import get_open_orders
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled, get_mirror_positions

async def get_mirror_orders_detailed(symbol: str) -> Dict:
    """Get detailed mirror account orders"""
    if not bybit_client_2:
        return {"orders": [], "sl_order": None}
    
    try:
        response = bybit_client_2.get_open_orders(
            category="linear",
            symbol=symbol
        )
        
        if response and response.get('retCode') == 0:
            orders = response.get('result', {}).get('list', [])
            
            # Find the SL order
            sl_order = None
            for order in orders:
                if order.get('reduceOnly') and 'SL' in order.get('orderLinkId', ''):
                    sl_order = order
                    break
            
            return {"orders": orders, "sl_order": sl_order}
        else:
            logger.error(f"Error getting mirror orders: {response}")
            return {"orders": [], "sl_order": None}
            
    except Exception as e:
        logger.error(f"Exception getting mirror orders: {e}")
        return {"orders": [], "sl_order": None}

async def cancel_mirror_order(symbol: str, order_id: str) -> bool:
    """Cancel an order on mirror account"""
    if not bybit_client_2:
        return False
    
    try:
        logger.info(f"🔄 Canceling mirror order {order_id[:8]}...")
        
        response = bybit_client_2.cancel_order(
            category="linear",
            symbol=symbol,
            orderId=order_id
        )
        
        if response and response.get("retCode") == 0:
            logger.info(f"✅ Order cancelled successfully")
            return True
        elif response and response.get("retCode") == 110001:
            logger.info(f"ℹ️ Order already cancelled or filled")
            return True
        else:
            logger.error(f"❌ Cancel failed: {response}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Exception canceling order: {e}")
        return False

async def place_mirror_sl_order(
    symbol: str,
    side: str,
    qty: str,
    trigger_price: str,
    order_link_id: str
) -> Optional[Dict]:
    """Place a stop loss order on mirror account"""
    if not bybit_client_2:
        return None
    
    try:
        logger.info(f"🪞 MIRROR: Placing SL order {side} {qty} @ trigger {trigger_price}")
        
        # For a Buy position: SL triggers when price goes DOWN (Sell to close)
        trigger_direction = 2  # <= (price falls below trigger)
        
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

async def place_mirror_limit_order(
    symbol: str,
    side: str,
    qty: str,
    price: str,
    order_link_id: str
) -> Optional[Dict]:
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
    logger.info("Starting XRPUSDT Mirror SL Correction...")
    logger.info("=" * 50)
    
    if not is_mirror_trading_enabled():
        logger.error("❌ Mirror trading is not enabled")
        return
    
    # Step 1: Get mirror position
    mirror_positions = await get_mirror_positions()
    mirror_position = None
    for pos in mirror_positions:
        if pos.get('symbol') == 'XRPUSDT' and float(pos.get('size', 0)) > 0 and pos.get('side') == 'Buy':
            mirror_position = pos
            break
    
    if not mirror_position:
        logger.error("❌ No active XRPUSDT Buy position found on mirror account")
        return
    
    position_size = float(mirror_position['size'])
    logger.info(f"✅ Mirror position size: {position_size}")
    
    # Step 2: Get current orders
    order_data = await get_mirror_orders_detailed("XRPUSDT")
    sl_order = order_data["sl_order"]
    
    if sl_order:
        sl_qty = float(sl_order.get('qty', 0))
        sl_order_id = sl_order.get('orderId')
        logger.info(f"Found SL order: {sl_qty} contracts (OrderID: {sl_order_id[:8]}...)")
        
        if sl_qty != position_size:
            logger.warning(f"⚠️ SL order size ({sl_qty}) doesn't match position ({position_size})")
            
            # Step 3: Cancel oversized SL order
            if await cancel_mirror_order("XRPUSDT", sl_order_id):
                logger.info("✅ Oversized SL order cancelled")
                await asyncio.sleep(1)  # Wait for cancellation to process
            else:
                logger.error("❌ Failed to cancel oversized SL order")
                return
    
    # Step 4: Get main account orders as reference
    main_orders = await get_open_orders("XRPUSDT")
    
    # Find main account SL and TP orders
    main_sl = None
    main_tp_orders = []
    
    for order in main_orders:
        order_link_id = order.get('orderLinkId', '')
        if order.get('reduceOnly'):
            if 'SL' in order_link_id and order.get('stopOrderType') == 'Stop':
                main_sl = order
            elif 'TP' in order_link_id and order.get('orderType') == 'Limit':
                main_tp_orders.append(order)
    
    # Step 5: Place new SL order with correct size
    if main_sl and (not sl_order or sl_qty != position_size):
        sl_trigger_price = main_sl.get('triggerPrice')
        order_link_id = "BOT_MIRROR_XRPUSDT_SL_CORRECTED"
        
        logger.info(f"\nPlacing corrected SL order...")
        sl_result = await place_mirror_sl_order(
            symbol="XRPUSDT",
            side="Sell",  # Opposite of Buy position
            qty=str(int(position_size)),  # XRPUSDT needs whole numbers
            trigger_price=str(sl_trigger_price),
            order_link_id=order_link_id
        )
        
        if sl_result:
            logger.info("✅ New SL order placed with correct size")
        else:
            logger.error("❌ Failed to place new SL order")
    
    # Step 6: Place TP orders
    if main_tp_orders:
        logger.info(f"\nPlacing {len(main_tp_orders)} TP orders...")
        
        # Sort TP orders by price (descending for Buy position)
        main_tp_orders.sort(key=lambda x: float(x.get('price', 0)), reverse=True)
        
        # Calculate quantities for XRPUSDT (87 contracts)
        # Conservative approach: 85%, 5%, 5%, 5%
        if position_size == 87:
            tp_quantities = [74, 4, 4, 5]  # Exact distribution for 87
        else:
            # General calculation
            tp1_qty = int(position_size * 0.85)
            tp2_qty = int(position_size * 0.05)
            tp3_qty = int(position_size * 0.05)
            tp4_qty = int(position_size) - tp1_qty - tp2_qty - tp3_qty  # Remainder
            tp_quantities = [tp1_qty, tp2_qty, tp3_qty, tp4_qty]
        
        placed_tp_count = 0
        for i, (main_tp, tp_qty) in enumerate(zip(main_tp_orders, tp_quantities)):
            if tp_qty <= 0:
                continue
                
            tp_num = i + 1
            tp_price = main_tp.get('price')
            order_link_id = f"BOT_MIRROR_XRPUSDT_TP{tp_num}_CORRECTED"
            
            logger.info(f"   TP{tp_num}: {tp_qty} @ {tp_price}")
            
            result = await place_mirror_limit_order(
                symbol="XRPUSDT",
                side="Sell",  # Opposite of Buy position
                qty=str(tp_qty),
                price=str(tp_price),
                order_link_id=order_link_id
            )
            
            if result:
                placed_tp_count += 1
        
        logger.info(f"✅ Placed {placed_tp_count} TP orders")
    
    # Step 7: Enable Enhanced TP/SL monitoring
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
    
    # Final verification
    logger.info("\n" + "=" * 50)
    logger.info("Verification:")
    
    # Check new orders
    await asyncio.sleep(2)  # Wait for orders to settle
    final_orders = await get_mirror_orders_detailed("XRPUSDT")
    
    tp_count = sum(1 for o in final_orders["orders"] if o.get('reduceOnly') and 'TP' in o.get('orderLinkId', ''))
    sl_count = sum(1 for o in final_orders["orders"] if o.get('reduceOnly') and 'SL' in o.get('orderLinkId', ''))
    
    logger.info(f"Final order count: {tp_count} TP orders, {sl_count} SL order")
    
    if final_orders["sl_order"]:
        final_sl_qty = float(final_orders["sl_order"].get('qty', 0))
        logger.info(f"SL order size: {final_sl_qty} (matches position: {'✅' if final_sl_qty == position_size else '❌'})")
    
    logger.info("\n✅ XRPUSDT Mirror SL Correction Completed!")

if __name__ == "__main__":
    asyncio.run(main())