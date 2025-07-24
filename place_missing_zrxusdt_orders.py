#!/usr/bin/env python3
"""
Place missing ZRXUSDT orders:
1. Main account SL (was cancelled but not replaced)
2. Mirror account proper orders
"""
import asyncio
import logging
from decimal import Decimal
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def place_missing_orders():
    """Place missing ZRXUSDT orders"""
    try:
        from clients.bybit_client import bybit_client
        from clients.bybit_helpers import (
            place_order_with_retry,
            get_position_info,
            get_position_info_for_account,
            get_instrument_info
        )
        from execution.mirror_trader import bybit_client_2
        
        symbol = "ZRXUSDT"
        
        logger.info("=" * 80)
        logger.info("Placing Missing ZRXUSDT Orders")
        logger.info("=" * 80)
        
        # Get instrument info
        instrument_info = await get_instrument_info(symbol)
        if not instrument_info:
            logger.error("Failed to get instrument info")
            return
            
        qty_step = Decimal(str(instrument_info.get('lotSizeFilter', {}).get('qtyStep', '1')))
        
        # MAIN ACCOUNT - Place SL
        logger.info("\n🔷 MAIN ACCOUNT - Placing SL")
        logger.info("-" * 40)
        
        # Get position
        positions = await get_position_info(symbol)
        main_position = None
        for pos in positions:
            if pos.get('side') == 'Buy' and Decimal(str(pos.get('size', '0'))) > 0:
                main_position = pos
                break
        
        if main_position:
            position_size = Decimal(str(main_position['size']))
            sl_price = "0.2049"  # From the cancelled order
            
            logger.info(f"Position size: {position_size}")
            logger.info(f"Placing SL at {sl_price}...")
            
            # Try with conditional order parameters
            try:
                response = bybit_client.place_order(
                    category="linear",
                    symbol=symbol,
                    side="Sell",
                    orderType="Market",
                    qty=str(position_size),
                    triggerPrice=sl_price,
                    triggerDirection=2,  # Below market
                    triggerBy="LastPrice",
                    reduceOnly=True,
                    positionIdx=0,
                    orderLinkId=f"BOT_CONS_{symbol}_SL_{int(datetime.now().timestamp())}"
                )
                
                if response and response.get('retCode') == 0:
                    order_id = response['result']['orderId']
                    logger.info(f"✅ Placed SL order: {order_id[:8]}...")
                else:
                    logger.error(f"❌ Failed to place SL: {response}")
            except Exception as e:
                logger.error(f"❌ Error placing SL: {e}")
        
        # MIRROR ACCOUNT - Place proper TP/SL orders
        logger.info("\n\n🔷 MIRROR ACCOUNT - Placing TP/SL orders")
        logger.info("-" * 40)
        
        # Get position
        mirror_positions = await get_position_info_for_account(symbol, 'mirror')
        mirror_position = None
        for pos in mirror_positions:
            if pos.get('side') == 'Buy' and Decimal(str(pos.get('size', '0'))) > 0:
                mirror_position = pos
                break
        
        if mirror_position:
            position_size = Decimal(str(mirror_position['size']))
            logger.info(f"Position size: {position_size}")
            
            # Place SL
            sl_price = "0.2049"
            logger.info(f"\nPlacing SL at {sl_price}...")
            
            try:
                response = bybit_client_2.place_order(
                    category="linear",
                    symbol=symbol,
                    side="Sell",
                    orderType="Market",
                    qty=str(position_size),
                    triggerPrice=sl_price,
                    triggerDirection=2,
                    triggerBy="LastPrice",
                    reduceOnly=True,
                    positionIdx=0,
                    orderLinkId=f"MIR_SL_{symbol}_{int(datetime.now().timestamp())}"
                )
                
                if response and response.get('retCode') == 0:
                    order_id = response['result']['orderId']
                    logger.info(f"✅ Placed SL order: {order_id[:8]}...")
                else:
                    logger.error(f"❌ Failed to place SL: {response}")
            except Exception as e:
                logger.error(f"❌ Error placing SL: {e}")
            
            # Place TP orders as limit orders
            tp_prices = ["0.2429", "0.2523", "0.2806"]  # TP2, TP3, TP4
            
            # Distribute position across TPs
            base_qty = (position_size / 3).quantize(qty_step)
            quantities = [base_qty, base_qty, position_size - (base_qty * 2)]
            
            for i, (price, qty) in enumerate(zip(tp_prices, quantities)):
                tp_num = i + 2
                logger.info(f"\nPlacing TP{tp_num} at {price} for {qty} {symbol}...")
                
                try:
                    response = bybit_client_2.place_order(
                        category="linear",
                        symbol=symbol,
                        side="Sell",
                        orderType="Limit",
                        qty=str(qty),
                        price=price,
                        reduceOnly=True,
                        positionIdx=0,
                        orderLinkId=f"MIR_TP{tp_num}_{symbol}_{int(datetime.now().timestamp())}"
                    )
                    
                    if response and response.get('retCode') == 0:
                        order_id = response['result']['orderId']
                        logger.info(f"✅ Placed TP{tp_num} order: {order_id[:8]}...")
                    else:
                        logger.error(f"❌ Failed to place TP{tp_num}: {response}")
                except Exception as e:
                    logger.error(f"❌ Error placing TP{tp_num}: {e}")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ Order placement completed!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Error in place_missing_orders: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(place_missing_orders())