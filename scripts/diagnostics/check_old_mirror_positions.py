#!/usr/bin/env python3
"""Check old mirror positions that started at bot launch"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import logging
from decimal import Decimal

# Import after setting up path
from config import *
from execution.mirror_trader import bybit_client_2

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def check_startup_positions():
    """Check the 4 positions from startup"""
    if not bybit_client_2:
        logger.error("Mirror trading not enabled")
        return
    
    logger.info("Checking mirror positions from startup...")
    logger.info("=" * 60)
    
    # Positions that were active at startup
    startup_symbols = ['BOMEUSDT', 'ZILUSDT', 'IOTXUSDT', 'CAKEUSDT']
    
    for symbol in startup_symbols:
        try:
            # Get position
            pos_response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: bybit_client_2.get_positions(
                    category="linear",
                    symbol=symbol
                )
            )
            
            if not pos_response or pos_response.get("retCode") != 0:
                logger.error(f"Failed to get position for {symbol}")
                continue
            
            positions = pos_response.get("result", {}).get("list", [])
            
            has_position = False
            for pos in positions:
                size = float(pos.get("size", "0"))
                if size > 0:
                    has_position = True
                    side = pos.get("side")
                    avg_price = pos.get("avgPrice")
                    unrealized_pnl = pos.get("unrealisedPnl")
                    
                    logger.info(f"\n{symbol} {side}")
                    logger.info(f"  Size: {size}")
                    logger.info(f"  Avg Price: {avg_price}")
                    logger.info(f"  Unrealized PnL: {unrealized_pnl}")
                    
                    # Get orders
                    order_response = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: bybit_client_2.get_open_orders(
                            category="linear",
                            symbol=symbol
                        )
                    )
                    
                    if order_response and order_response.get("retCode") == 0:
                        orders = order_response.get("result", {}).get("list", [])
                        
                        tp_orders = [o for o in orders if o.get("stopOrderType") == "TakeProfit"]
                        sl_orders = [o for o in orders if o.get("stopOrderType") == "StopLoss"]
                        
                        logger.info(f"  TP Orders: {len(tp_orders)}")
                        for i, tp in enumerate(tp_orders, 1):
                            logger.info(f"    TP{i}: {tp.get('qty')} @ {tp.get('triggerPrice')}")
                        
                        logger.info(f"  SL Orders: {len(sl_orders)}")
                        for sl in sl_orders:
                            logger.info(f"    SL: {sl.get('qty')} @ {sl.get('triggerPrice')}")
                    break
            
            if not has_position:
                logger.info(f"\n{symbol} - No position (may have been closed)")
            
        except Exception as e:
            logger.error(f"Error checking {symbol}: {e}")

if __name__ == "__main__":
    asyncio.run(check_startup_positions())