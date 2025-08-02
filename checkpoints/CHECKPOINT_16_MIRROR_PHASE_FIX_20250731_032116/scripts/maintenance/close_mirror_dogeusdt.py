#!/usr/bin/env python3
"""
Script to close DOGEUSDT position and orders on mirror account only
"""
import asyncio
import logging
from decimal import Decimal
from pybit.unified_trading import HTTP
from clients.bybit_client import create_bybit_client
from config.settings import USE_TESTNET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment variables
import os
from dotenv import load_dotenv
load_dotenv()

# Re-import settings after loading env
from config.settings import USE_TESTNET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2

async def close_mirror_dogeusdt():
    """Close DOGEUSDT position and cancel orders on mirror account"""
    try:
        # Check if mirror credentials are configured
        if not BYBIT_API_KEY_2 or not BYBIT_API_SECRET_2:
            logger.error("❌ Mirror account API credentials not configured!")
            logger.info("Please set BYBIT_API_KEY_2 and BYBIT_API_SECRET_2 in .env")
            return
            
        logger.info(f"🔑 Using mirror account with API key: {BYBIT_API_KEY_2[:8]}...")
        
        # Initialize mirror client using HTTP directly
        mirror_client = HTTP(
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2,
            testnet=USE_TESTNET
        )
        
        logger.info("🔍 Checking DOGEUSDT position on mirror account...")
        
        # Get position info
        position_response = mirror_client.get_positions(
            category="linear",
            symbol="DOGEUSDT"
        )
        
        positions = position_response.get("result", {}).get("list", [])
        if not positions:
            logger.info("✅ No DOGEUSDT position found on mirror account")
            return
        
        position = positions[0]
        position_size = Decimal(position.get("size", "0"))
        position_side = position.get("side")
        
        if position_size == 0:
            logger.info("✅ DOGEUSDT position already closed on mirror account")
        else:
            logger.info(f"📊 Found DOGEUSDT {position_side} position: {position_size} DOGE")
            logger.info(f"💰 Unrealized P&L: ${position.get('unrealisedPnl', 0)}")
        
        # Cancel open orders first
        logger.info("🔍 Checking for open DOGEUSDT orders...")
        
        orders_response = mirror_client.get_open_orders(
            category="linear",
            symbol="DOGEUSDT"
        )
        
        orders = orders_response.get("result", {}).get("list", [])
        
        if orders:
            logger.info(f"📋 Found {len(orders)} open orders to cancel")
            
            for order in orders:
                order_id = order.get("orderId")
                order_link_id = order.get("orderLinkId", "")
                order_qty = order.get("qty")
                order_price = order.get("price")
                
                logger.info(f"❌ Cancelling order: {order_link_id} ({order_qty} @ ${order_price})")
                
                try:
                    cancel_response = mirror_client.cancel_order(
                        category="linear",
                        symbol="DOGEUSDT",
                        orderId=order_id
                    )
                    
                    if cancel_response.get("retCode") == 0:
                        logger.info(f"✅ Successfully cancelled order: {order_id}")
                    else:
                        logger.error(f"❌ Failed to cancel order: {cancel_response}")
                        
                except Exception as e:
                    logger.error(f"❌ Error cancelling order {order_id}: {e}")
        else:
            logger.info("✅ No open DOGEUSDT orders found")
        
        # Close position if it exists
        if position_size > 0:
            logger.info(f"📈 Closing {position_side} position of {position_size} DOGE...")
            
            # Determine order side (opposite of position side)
            close_side = "Buy" if position_side == "Sell" else "Sell"
            
            # Place market order to close position
            close_response = mirror_client.place_order(
                category="linear",
                symbol="DOGEUSDT",
                side=close_side,
                orderType="Market",
                qty=str(position_size),
                reduceOnly=True,
                positionIdx=0  # One-way mode
            )
            
            if close_response.get("retCode") == 0:
                order_id = close_response.get("result", {}).get("orderId")
                logger.info(f"✅ Position close order placed successfully: {order_id}")
                
                # Wait a moment for execution
                await asyncio.sleep(2)
                
                # Verify position is closed
                verify_response = mirror_client.get_positions(
                    category="linear",
                    symbol="DOGEUSDT"
                )
                
                verify_positions = verify_response.get("result", {}).get("list", [])
                if verify_positions:
                    new_size = Decimal(verify_positions[0].get("size", "0"))
                    if new_size == 0:
                        logger.info("✅ DOGEUSDT position successfully closed on mirror account")
                        
                        # Get realized P&L
                        realised_pnl = verify_positions[0].get("realisedPnl", 0)
                        logger.info(f"💰 Final realized P&L: ${realised_pnl}")
                    else:
                        logger.warning(f"⚠️ Position still open with size: {new_size}")
                else:
                    logger.info("✅ Position closed - no active position found")
                    
            else:
                logger.error(f"❌ Failed to close position: {close_response}")
        
        logger.info("🎯 DOGEUSDT cleanup complete on mirror account")
        
    except Exception as e:
        logger.error(f"❌ Error in close_mirror_dogeusdt: {e}")
        raise

if __name__ == "__main__":
    # Run the async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(close_mirror_dogeusdt())
    except Exception as e:
        logger.error(f"❌ Main execution error: {e}", exc_info=True)
    finally:
        loop.close()