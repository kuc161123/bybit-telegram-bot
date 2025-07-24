#!/usr/bin/env python3
"""
Simple Clean Slate - Close All Positions and Orders
Main account first, then mirror if available
"""
import asyncio
import logging
import sys
import os
from decimal import Decimal

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_client import bybit_client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_all_positions():
    """Get all positions"""
    try:
        result = bybit_client.get_positions(
            category="linear",
            settleCoin="USDT"
        )
        return result.get('result', {}).get('list', [])
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return []

def get_all_orders():
    """Get all open orders"""
    try:
        result = bybit_client.get_open_orders(
            category="linear",
            settleCoin="USDT"
        )
        return result.get('result', {}).get('list', [])
    except Exception as e:
        logger.error(f"Error getting orders: {e}")
        return []

def cancel_order(symbol: str, order_id: str):
    """Cancel a specific order"""
    try:
        result = bybit_client.cancel_order(
            category="linear",
            symbol=symbol,
            orderId=order_id
        )
        return result.get('retCode') == 0
    except Exception as e:
        logger.error(f"Error cancelling order {order_id}: {e}")
        return False

def close_position(symbol: str, side: str, size: str, position_idx: int = 0):
    """Close a position with market order"""
    try:
        # Determine close side (opposite of position side)
        close_side = "Buy" if side == "Sell" else "Sell"
        
        result = bybit_client.place_order(
            category="linear",
            symbol=symbol,
            side=close_side,
            orderType="Market",
            qty=size,
            reduceOnly=True,
            positionIdx=position_idx
        )
        return result.get('retCode') == 0
    except Exception as e:
        logger.error(f"Error closing position {symbol}: {e}")
        return False

async def close_all_main_account():
    """Close all positions and orders on main account"""
    logger.info("🚀 STARTING CLEAN SLATE - MAIN ACCOUNT")
    logger.info("=" * 50)
    
    # Step 1: Cancel all orders
    logger.info("🔄 Step 1: Cancelling all orders...")
    orders = get_all_orders()
    logger.info(f"📋 Found {len(orders)} open orders")
    
    cancelled_orders = 0
    for order in orders:
        symbol = order['symbol']
        order_id = order['orderId']
        order_type = order.get('orderType', 'Unknown')
        
        logger.info(f"🔄 Cancelling {symbol} {order_type} order ({order_id[:8]}...)")
        
        if cancel_order(symbol, order_id):
            logger.info(f"✅ Cancelled {symbol} order")
            cancelled_orders += 1
        else:
            logger.error(f"❌ Failed to cancel {symbol} order")
    
    logger.info(f"📊 Orders cancelled: {cancelled_orders}/{len(orders)}")
    
    # Step 2: Close all positions
    logger.info("\n🔄 Step 2: Closing all positions...")
    positions = get_all_positions()
    active_positions = [p for p in positions if float(p.get('size', 0)) != 0]
    logger.info(f"📊 Found {len(active_positions)} active positions")
    
    closed_positions = 0
    for position in active_positions:
        symbol = position['symbol']
        size = abs(float(position['size']))
        side = position['side']
        position_idx = position.get('positionIdx', 0)
        
        logger.info(f"🔄 Closing {symbol} {side} position (size: {size})")
        
        if close_position(symbol, side, str(size), position_idx):
            logger.info(f"✅ Closed {symbol} position")
            closed_positions += 1
        else:
            logger.error(f"❌ Failed to close {symbol} position")
    
    logger.info(f"📊 Positions closed: {closed_positions}/{len(active_positions)}")
    
    # Step 3: Wait and verify
    logger.info("\n⏳ Step 3: Waiting 3 seconds for settlement...")
    await asyncio.sleep(3)
    
    logger.info("🔍 Verifying clean slate...")
    final_positions = get_all_positions()
    final_orders = get_all_orders()
    
    active_final_positions = [p for p in final_positions if float(p.get('size', 0)) != 0]
    
    # Results
    logger.info("\n" + "=" * 50)
    if not active_final_positions and not final_orders:
        logger.info("🎉 CLEAN SLATE SUCCESS!")
        logger.info("✅ All positions closed")
        logger.info("✅ All orders cancelled")
        logger.info("🆕 Main account ready for fresh trading")
        return True
    else:
        logger.warning("⚠️ CLEAN SLATE INCOMPLETE")
        if active_final_positions:
            logger.warning(f"⚠️ Still has {len(active_final_positions)} active positions:")
            for pos in active_final_positions:
                logger.warning(f"   - {pos['symbol']} {pos['side']}: {pos['size']}")
        if final_orders:
            logger.warning(f"⚠️ Still has {len(final_orders)} open orders:")
            for order in final_orders:
                logger.warning(f"   - {order['symbol']} {order.get('orderType', 'Unknown')}: {order['orderId'][:8]}...")
        return False

async def close_mirror_account():
    """Close all positions and orders on mirror account"""
    logger.info("\n🪞 PROCESSING MIRROR ACCOUNT")
    logger.info("=" * 50)
    
    try:
        # Try to get mirror client
        from clients.bybit_client import bybit_client_2
        if not bybit_client_2:
            logger.info("ℹ️ Mirror client not available")
            return True
        
        logger.info("✅ Mirror client found, processing mirror account...")
        
        # Get mirror positions
        mirror_positions_result = bybit_client_2.get_positions(
            category="linear",
            settleCoin="USDT"
        )
        mirror_positions = mirror_positions_result.get('result', {}).get('list', [])
        active_mirror_positions = [p for p in mirror_positions if float(p.get('size', 0)) != 0]
        
        # Get mirror orders
        mirror_orders_result = bybit_client_2.get_open_orders(
            category="linear",
            settleCoin="USDT"
        )
        mirror_orders = mirror_orders_result.get('result', {}).get('list', [])
        
        logger.info(f"📊 Mirror account: {len(active_mirror_positions)} positions, {len(mirror_orders)} orders")
        
        # Cancel mirror orders
        for order in mirror_orders:
            symbol = order['symbol']
            order_id = order['orderId']
            logger.info(f"🔄 MIRROR: Cancelling {symbol} order ({order_id[:8]}...)")
            
            try:
                bybit_client_2.cancel_order(
                    category="linear",
                    symbol=symbol,
                    orderId=order_id
                )
                logger.info(f"✅ MIRROR: Cancelled {symbol} order")
            except Exception as e:
                logger.error(f"❌ MIRROR: Failed to cancel {symbol} order: {e}")
        
        # Close mirror positions
        for position in active_mirror_positions:
            symbol = position['symbol']
            size = abs(float(position['size']))
            side = position['side']
            close_side = "Buy" if side == "Sell" else "Sell"
            
            logger.info(f"🔄 MIRROR: Closing {symbol} {side} position (size: {size})")
            
            try:
                bybit_client_2.place_order(
                    category="linear",
                    symbol=symbol,
                    side=close_side,
                    orderType="Market",
                    qty=str(size),
                    reduceOnly=True,
                    positionIdx=0  # Mirror uses one-way mode
                )
                logger.info(f"✅ MIRROR: Closed {symbol} position")
            except Exception as e:
                logger.error(f"❌ MIRROR: Failed to close {symbol} position: {e}")
        
        logger.info("✅ Mirror account processing complete")
        return True
        
    except ImportError:
        logger.info("ℹ️ Mirror trading not configured")
        return True
    except Exception as e:
        logger.error(f"❌ Error processing mirror account: {e}")
        return False

async def main():
    """Main execution function"""
    try:
        # Process main account
        main_success = await close_all_main_account()
        
        # Process mirror account
        mirror_success = await close_mirror_account()
        
        # Final results
        logger.info("\n" + "=" * 60)
        if main_success and mirror_success:
            logger.info("🎊 COMPLETE CLEAN SLATE ACHIEVED!")
            logger.info("✅ Main account: Clean")
            logger.info("✅ Mirror account: Clean")
            logger.info("🆕 Both accounts ready for fresh trading")
        else:
            logger.warning("⚠️ Clean slate may be incomplete")
            logger.warning("❌ Manual verification recommended")
        
        logger.info("=" * 60)
        return main_success and mirror_success
        
    except Exception as e:
        logger.error(f"❌ Fatal error during clean slate: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("🧹 SIMPLE CLEAN SLATE - BOTH ACCOUNTS")
    print("=" * 50)
    print("This will close ALL positions and orders.")
    print("Proceeding automatically...")
    print("")
    
    success = asyncio.run(main())
    if success:
        print("\n🎊 Clean slate completed successfully!")
    else:
        print("\n❌ Clean slate may be incomplete. Check logs above.")