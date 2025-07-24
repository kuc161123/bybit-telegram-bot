#!/usr/bin/env python3
"""
Check DOGEUSDT instrument info
"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_doge_instrument():
    """Check DOGEUSDT instrument info"""
    try:
        from clients.bybit_helpers import get_instrument_info
        
        info = await get_instrument_info('DOGEUSDT')
        if info:
            logger.info("DOGEUSDT Instrument Info:")
            lot_size = info.get('lotSizeFilter', {})
            logger.info(f"  Qty Step: {lot_size.get('qtyStep')}")
            logger.info(f"  Min Order Qty: {lot_size.get('minOrderQty')}")
            logger.info(f"  Max Order Qty: {lot_size.get('maxOrderQty')}")
            
            price_filter = info.get('priceFilter', {})
            logger.info(f"  Price Tick Size: {price_filter.get('tickSize')}")
        else:
            logger.error("Could not get instrument info")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_doge_instrument())