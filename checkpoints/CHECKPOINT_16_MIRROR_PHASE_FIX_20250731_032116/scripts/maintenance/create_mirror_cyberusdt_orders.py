#!/usr/bin/env python3
"""
Create Mirror CYBERUSDT Orders

Creates TP/SL orders for the mirror account CYBERUSDT position using proper mirror trading functions.
"""
import asyncio
import logging
import sys
import os
from decimal import Decimal

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.order_identifier import generate_order_link_id
from utils.helpers import value_adjusted_to_step

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Target prices and quantities for mirror account (1402.8 position size)
TP_PRICES = [Decimal("1.297"), Decimal("1.321"), Decimal("1.346"), Decimal("1.370")]
TP_QUANTITIES = [Decimal("1192.3"), Decimal("70.1"), Decimal("70.1"), Decimal("70.1")]  # Pre-calculated
SL_PRICE = Decimal("1.196")
SL_QUANTITY = Decimal("1402.8")

async def create_mirror_orders():
    """Create TP/SL orders for mirror CYBERUSDT position"""
    try:
        from execution.mirror_trader import (
            mirror_limit_order, mirror_tp_sl_order, 
            is_mirror_trading_enabled
        )
        from clients.bybit_helpers import get_correct_position_idx
        
        if not is_mirror_trading_enabled():
            logger.error("❌ Mirror trading not enabled")
            return
        
        # For mirror account, use positionIdx=1 (from the position check we did earlier)
        # The mirror account shows CYBERUSDT position with positionIdx=1
        position_idx = 1
        logger.info(f"📍 Using position index: {position_idx} (mirror account hedge mode)")
        
        logger.info("🚀 Creating mirror CYBERUSDT TP/SL orders...")
        
        # Create TP orders using mirror_limit_order (for reduce-only limit orders)
        for i, (price, qty) in enumerate(zip(TP_PRICES, TP_QUANTITIES), 1):
            order_link_id = generate_order_link_id("CONS", "CYBERUSDT", "TP", i)
            
            logger.info(f"📍 Creating mirror TP{i}: {qty} @ {price}")
            
            result = await mirror_limit_order(
                symbol="CYBERUSDT",
                side="Sell",  # Close long position
                qty=str(qty),
                price=str(price),
                position_idx=position_idx,
                order_link_id=order_link_id
            )
            
            if result:
                logger.info(f"✅ Mirror TP{i} created successfully")
            else:
                logger.error(f"❌ Failed to create mirror TP{i}")
        
        # Create SL order using mirror_tp_sl_order
        logger.info(f"🛡️ Creating mirror SL: {SL_QUANTITY} @ {SL_PRICE}")
        
        sl_order_link_id = generate_order_link_id("CONS", "CYBERUSDT", "SL")
        
        sl_result = await mirror_tp_sl_order(
            symbol="CYBERUSDT",
            side="Sell",  # Close long position
            qty=str(SL_QUANTITY),
            trigger_price=str(SL_PRICE),
            position_idx=position_idx,
            order_type="Market",
            reduce_only=True,
            order_link_id=sl_order_link_id,
            stop_order_type="StopLoss"
        )
        
        if sl_result:
            logger.info("✅ Mirror SL created successfully")
        else:
            logger.error("❌ Failed to create mirror SL")
        
        logger.info("✅ Mirror CYBERUSDT order creation completed")
        
    except ImportError:
        logger.error("❌ Mirror trading functions not available")
    except Exception as e:
        logger.error(f"❌ Error creating mirror orders: {e}")

if __name__ == "__main__":
    asyncio.run(create_mirror_orders())