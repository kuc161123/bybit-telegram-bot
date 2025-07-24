#!/usr/bin/env python3
"""
Fix AUCTIONUSDT SL orders with correct trigger direction
"""
import asyncio
import sys
import os
from decimal import Decimal
import logging

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def fix_sl_orders():
    """Fix SL orders for AUCTIONUSDT with correct parameters"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        # Import after env vars are loaded
        from clients.bybit_client import create_bybit_client
        from execution.mirror_trader import bybit_client_2
        
        logger.info("🔧 FIXING AUCTIONUSDT SL ORDERS")
        logger.info("=" * 60)
        
        bybit_client = create_bybit_client()
        
        # Process main account
        logger.info("\n📈 MAIN ACCOUNT:")
        
        # Get current position
        positions = bybit_client.get_positions(
            category="linear",
            symbol="AUCTIONUSDT"
        )
        
        current_position_size = Decimal("0")
        position_side = None
        if positions['retCode'] == 0:
            for pos in positions['result']['list']:
                if float(pos.get('size', 0)) > 0:
                    current_position_size = Decimal(str(pos.get('size')))
                    position_side = pos.get('side')
                    logger.info(f"  Current position: {position_side} {current_position_size}")
                    break
        
        if current_position_size > 0 and position_side == 'Buy':
            # Place new SL order
            sl_price = "8.662"  # Original SL price
            
            try:
                new_sl_result = bybit_client.place_order(
                    category="linear",
                    symbol="AUCTIONUSDT",
                    side="Sell",
                    orderType="Market",
                    qty=str(current_position_size),
                    stopOrderType="Stop",
                    triggerPrice=sl_price,
                    triggerDirection="2",  # 2 = Below (for stop loss on long position)
                    reduceOnly=True,
                    orderLinkId=f"BOT_FIXED_SL_{int(asyncio.get_event_loop().time())}"
                )
                
                if new_sl_result['retCode'] == 0:
                    logger.info(f"  ✅ Placed new SL order:")
                    logger.info(f"     Order ID: {new_sl_result['result']['orderId']}")
                    logger.info(f"     Trigger Price: {sl_price}")
                    logger.info(f"     Quantity: {current_position_size}")
                else:
                    logger.error(f"  ❌ Failed to place new SL: {new_sl_result}")
            except Exception as e:
                logger.error(f"  ❌ Error placing SL: {e}")
        
        # Process mirror account
        if bybit_client_2:
            logger.info("\n\n🪞 MIRROR ACCOUNT:")
            
            # Get current position
            positions = bybit_client_2.get_positions(
                category="linear",
                symbol="AUCTIONUSDT"
            )
            
            current_position_size = Decimal("0")
            position_side = None
            if positions['retCode'] == 0:
                for pos in positions['result']['list']:
                    if float(pos.get('size', 0)) > 0:
                        current_position_size = Decimal(str(pos.get('size')))
                        position_side = pos.get('side')
                        logger.info(f"  Current position: {position_side} {current_position_size}")
                        break
            
            if current_position_size > 0 and position_side == 'Buy':
                # Place new SL order
                sl_price = "8.662"  # Original SL price
                
                try:
                    new_sl_result = bybit_client_2.place_order(
                        category="linear",
                        symbol="AUCTIONUSDT",
                        side="Sell",
                        orderType="Market",
                        qty=str(current_position_size),
                        stopOrderType="Stop",
                        triggerPrice=sl_price,
                        triggerDirection="2",  # 2 = Below (for stop loss on long position)
                        reduceOnly=True,
                        orderLinkId=f"MIR_FIXED_SL_{int(asyncio.get_event_loop().time())}"
                    )
                    
                    if new_sl_result['retCode'] == 0:
                        logger.info(f"  ✅ Placed new SL order:")
                        logger.info(f"     Order ID: {new_sl_result['result']['orderId']}")
                        logger.info(f"     Trigger Price: {sl_price}")
                        logger.info(f"     Quantity: {current_position_size}")
                    else:
                        logger.error(f"  ❌ Failed to place new SL: {new_sl_result}")
                except Exception as e:
                    logger.error(f"  ❌ Error placing SL: {e}")
        
        logger.info("\n✅ SL ORDER FIX COMPLETE")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fix_sl_orders())