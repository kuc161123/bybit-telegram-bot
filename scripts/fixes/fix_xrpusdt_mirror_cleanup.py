#!/usr/bin/env python3
"""
Fix XRPUSDT mirror orders by canceling incorrectly created TP orders and placing correct ones
"""
import asyncio
import logging
from decimal import Decimal
from typing import List, Dict, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from clients.bybit_helpers import get_open_orders
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled, get_mirror_positions

async def get_xrpusdt_mirror_orders() -> Dict:
    """Get all XRPUSDT orders on mirror account"""
    if not bybit_client_2:
        return {"all_orders": [], "incorrect_tp_orders": [], "entry_orders": [], "sl_orders": []}
    
    try:
        response = bybit_client_2.get_open_orders(
            category="linear",
            symbol="XRPUSDT"
        )
        
        if response and response.get('retCode') == 0:
            all_orders = response.get('result', {}).get('list', [])
            
            incorrect_tp_orders = []
            entry_orders = []
            sl_orders = []
            
            for order in all_orders:
                order_link_id = order.get('orderLinkId', '')
                
                # Identify incorrectly created TP orders (Sell orders with TP in name but no reduceOnly)
                if 'TP' in order_link_id and order.get('side') == 'Sell' and not order.get('reduceOnly'):
                    incorrect_tp_orders.append(order)
                # Legitimate entry orders (Buy orders)
                elif order.get('side') == 'Buy' and not order.get('reduceOnly'):
                    entry_orders.append(order)
                # SL orders
                elif 'SL' in order_link_id and order.get('reduceOnly'):
                    sl_orders.append(order)
            
            return {
                "all_orders": all_orders,
                "incorrect_tp_orders": incorrect_tp_orders,
                "entry_orders": entry_orders,
                "sl_orders": sl_orders
            }
        else:
            logger.error(f"Error getting mirror orders: {response}")
            return {"all_orders": [], "incorrect_tp_orders": [], "entry_orders": [], "sl_orders": []}
            
    except Exception as e:
        logger.error(f"Exception getting mirror orders: {e}")
        return {"all_orders": [], "incorrect_tp_orders": [], "entry_orders": [], "sl_orders": []}

async def cancel_mirror_order(symbol: str, order_id: str, order_link_id: str) -> bool:
    """Cancel an order on mirror account"""
    if not bybit_client_2:
        return False
    
    try:
        logger.info(f"  Canceling {order_link_id}")
        
        response = bybit_client_2.cancel_order(
            category="linear",
            symbol=symbol,
            orderId=order_id
        )
        
        if response and response.get("retCode") == 0:
            logger.info(f"    ✅ Cancelled successfully")
            return True
        elif response and response.get("retCode") == 110001:
            logger.info(f"    ℹ️ Already cancelled or filled")
            return True
        else:
            logger.error(f"    ❌ Failed: {response}")
            return False
            
    except Exception as e:
        logger.error(f"    ❌ Exception: {e}")
        return False

async def place_mirror_tp_order(
    symbol: str,
    side: str,
    qty: str,
    price: str,
    order_link_id: str
) -> Optional[Dict]:
    """Place a TP limit order with reduceOnly on mirror account"""
    if not bybit_client_2:
        return None
    
    try:
        logger.info(f"  Placing TP: {side} {qty} @ {price}")
        
        response = bybit_client_2.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Limit",
            qty=qty,
            price=price,
            reduceOnly=True,  # Critical flag
            orderLinkId=order_link_id,
            positionIdx=0  # Mirror uses One-Way mode
        )
        
        if response and response.get("retCode") == 0:
            result = response.get("result", {})
            order_id = result.get("orderId", "")
            logger.info(f"    ✅ Placed: {order_id[:8]}...")
            return result
        else:
            logger.error(f"    ❌ Failed: {response}")
            return None
            
    except Exception as e:
        logger.error(f"    ❌ Exception: {e}")
        return None

async def main():
    logger.info("Starting XRPUSDT Mirror Order Cleanup...")
    logger.info("=" * 60)
    
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
    logger.info(f"Mirror position: Buy {position_size} XRPUSDT")
    
    # Step 2: Get current orders
    order_data = await get_xrpusdt_mirror_orders()
    incorrect_tp_orders = order_data["incorrect_tp_orders"]
    entry_orders = order_data["entry_orders"]
    sl_orders = order_data["sl_orders"]
    
    logger.info(f"\nCurrent orders:")
    logger.info(f"  Incorrect TP orders: {len(incorrect_tp_orders)}")
    logger.info(f"  Legitimate entry orders: {len(entry_orders)}")
    logger.info(f"  SL orders: {len(sl_orders)}")
    
    # Step 3: Cancel incorrect TP orders
    if incorrect_tp_orders:
        logger.info(f"\nCanceling {len(incorrect_tp_orders)} incorrect TP orders...")
        cancelled_count = 0
        
        for order in incorrect_tp_orders:
            order_id = order.get('orderId')
            order_link_id = order.get('orderLinkId')
            qty = order.get('qty')
            price = order.get('price')
            
            logger.info(f"\nOrder: {order_link_id}")
            logger.info(f"  Details: Sell {qty} @ {price}")
            
            if await cancel_mirror_order("XRPUSDT", order_id, order_link_id):
                cancelled_count += 1
            
            await asyncio.sleep(0.5)  # Small delay between cancellations
        
        logger.info(f"\n✅ Cancelled {cancelled_count}/{len(incorrect_tp_orders)} incorrect orders")
    
    # Step 4: Wait for cancellations to process
    await asyncio.sleep(2)
    
    # Step 5: Get main account TP prices as reference
    main_orders = await get_open_orders("XRPUSDT")
    main_tp_orders = [o for o in main_orders if o.get('reduceOnly') and 'TP' in o.get('orderLinkId', '') and o.get('orderType') == 'Limit']
    main_tp_orders.sort(key=lambda x: float(x.get('price', 0)), reverse=True)  # Sort descending for Buy position
    
    if not main_tp_orders or len(main_tp_orders) < 4:
        logger.error("❌ Insufficient TP orders on main account for reference")
        return
    
    # Step 6: Place correct TP orders
    logger.info(f"\nPlacing correct TP orders for {position_size} contracts...")
    
    # Calculate quantities for 87 position
    if position_size == 87:
        tp_quantities = [74, 4, 4, 5]  # 85%, 5%, 5%, remainder
    else:
        # General calculation
        tp1_qty = int(position_size * 0.85)
        tp2_qty = int(position_size * 0.05)
        tp3_qty = int(position_size * 0.05)
        tp4_qty = int(position_size) - tp1_qty - tp2_qty - tp3_qty
        tp_quantities = [tp1_qty, tp2_qty, tp3_qty, tp4_qty]
    
    placed_count = 0
    for i, (main_tp, tp_qty) in enumerate(zip(main_tp_orders[:4], tp_quantities)):
        if tp_qty <= 0:
            continue
            
        tp_num = i + 1
        tp_price = main_tp.get('price')
        order_link_id = f"BOT_MIRROR_XRPUSDT_TP{tp_num}_FIXED"
        
        logger.info(f"\nTP{tp_num}:")
        
        result = await place_mirror_tp_order(
            symbol="XRPUSDT",
            side="Sell",  # Opposite of Buy position
            qty=str(tp_qty),
            price=str(tp_price),
            order_link_id=order_link_id
        )
        
        if result:
            placed_count += 1
        
        await asyncio.sleep(0.5)  # Small delay between orders
    
    logger.info(f"\n✅ Placed {placed_count}/4 TP orders")
    
    # Step 7: Final verification
    logger.info("\n" + "=" * 60)
    logger.info("Final Verification:")
    
    await asyncio.sleep(2)
    final_orders = await get_xrpusdt_mirror_orders()
    
    # Count correct orders
    correct_tp_count = sum(1 for o in final_orders["all_orders"] 
                          if o.get('reduceOnly') and 'TP' in o.get('orderLinkId', ''))
    
    logger.info(f"  Position size: {position_size}")
    logger.info(f"  Correct TP orders: {correct_tp_count}")
    logger.info(f"  SL orders: {len(final_orders['sl_orders'])}")
    logger.info(f"  Entry orders: {len(final_orders['entry_orders'])}")
    
    # Show entry order details
    if final_orders['entry_orders']:
        logger.info("\nRemaining entry orders (Conservative approach):")
        for order in final_orders['entry_orders']:
            logger.info(f"  Buy {order.get('qty')} @ {order.get('price')}")
    
    logger.info("\n✅ XRPUSDT Mirror Cleanup Completed!")

if __name__ == "__main__":
    asyncio.run(main())