#!/usr/bin/env python3
"""
Retry placing XRPUSDT TP orders on mirror account
"""
import asyncio
import logging
from clients.bybit_helpers import get_open_orders
from execution.mirror_trader import bybit_client_2

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

async def place_mirror_limit_order(symbol, side, qty, price, order_link_id):
    """Place a limit order on mirror account"""
    try:
        logger.info(f"Placing {side} {qty} @ {price}")
        
        response = bybit_client_2.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Limit",
            qty=qty,
            price=price,
            reduceOnly=True,
            orderLinkId=order_link_id,
            positionIdx=0
        )
        
        if response and response.get("retCode") == 0:
            order_id = response.get("result", {}).get("orderId", "")
            logger.info(f"✅ Success: {order_id[:8]}...")
            return True
        else:
            logger.error(f"❌ Failed: {response}")
            return False
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

async def main():
    # Get main account TP orders as reference
    main_orders = await get_open_orders("XRPUSDT")
    main_tp_orders = [o for o in main_orders if o.get('reduceOnly') and 'TP' in o.get('orderLinkId', '') and o.get('orderType') == 'Limit']
    main_tp_orders.sort(key=lambda x: float(x.get('price', 0)), reverse=True)
    
    if not main_tp_orders:
        logger.error("No TP orders found on main account")
        return
    
    # Try placing TP orders with quantities for 87 position
    tp_configs = [
        (74, main_tp_orders[0].get('price'), "BOT_MIRROR_XRPUSDT_TP1_RETRY"),
        (4, main_tp_orders[1].get('price'), "BOT_MIRROR_XRPUSDT_TP2_RETRY"),
        (4, main_tp_orders[2].get('price'), "BOT_MIRROR_XRPUSDT_TP3_RETRY"),
        (5, main_tp_orders[3].get('price'), "BOT_MIRROR_XRPUSDT_TP4_RETRY"),
    ]
    
    success_count = 0
    for qty, price, order_link_id in tp_configs:
        if await place_mirror_limit_order("XRPUSDT", "Sell", str(qty), str(price), order_link_id):
            success_count += 1
        await asyncio.sleep(0.5)  # Small delay between orders
    
    logger.info(f"\n✅ Placed {success_count}/4 TP orders")

if __name__ == "__main__":
    asyncio.run(main())