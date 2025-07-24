#!/usr/bin/env python3
"""
Manually close all positions and cancel all orders
"""

import asyncio
import logging
from decimal import Decimal
from clients.bybit_client import bybit_client
from clients.bybit_helpers import get_all_positions, get_all_open_orders, api_call_with_retry, cancel_order_with_retry
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def cancel_all_orders(account="main"):
    """Cancel all orders for an account"""
    logger.info(f"\n{'='*60}")
    logger.info(f"CANCELLING ALL ORDERS - {account.upper()} ACCOUNT")
    logger.info(f"{'='*60}")
    
    if account == "main":
        orders = await get_all_open_orders()
    else:
        response = await api_call_with_retry(
            lambda: bybit_client_2.get_open_orders(
                category="linear",
                settleCoin="USDT",
                limit=200
            ),
            timeout=30
        )
        orders = response.get("result", {}).get("list", []) if response and response.get("retCode") == 0 else []
    
    logger.info(f"Found {len(orders)} orders to cancel")
    
    success_count = 0
    for order in orders:
        try:
            symbol = order.get("symbol", "")
            order_id = order.get("orderId", "")
            
            if account == "main":
                result = await cancel_order_with_retry(symbol, order_id)
            else:
                response = await api_call_with_retry(
                    lambda: bybit_client_2.cancel_order(
                        category="linear",
                        symbol=symbol,
                        orderId=order_id
                    ),
                    timeout=20
                )
                result = response and response.get("retCode") == 0
            
            if result:
                success_count += 1
                logger.info(f"✅ Cancelled {symbol} order {order_id[:8]}...")
            else:
                logger.error(f"❌ Failed to cancel {symbol} order {order_id[:8]}...")
                
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
        
        await asyncio.sleep(0.1)  # Small delay
    
    logger.info(f"\n✅ Cancelled {success_count}/{len(orders)} orders")
    return success_count


async def close_all_positions(account="main"):
    """Close all positions for an account"""
    logger.info(f"\n{'='*60}")
    logger.info(f"CLOSING ALL POSITIONS - {account.upper()} ACCOUNT")
    logger.info(f"{'='*60}")
    
    if account == "main":
        positions = await get_all_positions()
        client = bybit_client
    else:
        response = await api_call_with_retry(
            lambda: bybit_client_2.get_positions(
                category="linear",
                settleCoin="USDT"
            ),
            timeout=30
        )
        positions = response.get("result", {}).get("list", []) if response and response.get("retCode") == 0 else []
        client = bybit_client_2
    
    # Filter active positions
    active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
    logger.info(f"Found {len(active_positions)} active positions")
    
    success_count = 0
    total_value = Decimal('0')
    
    for position in active_positions:
        try:
            symbol = position.get("symbol", "")
            side = position.get("side", "")
            size = position.get("size", "0")
            position_idx = position.get("positionIdx", 0)
            
            # Determine opposite side for closing
            close_side = "Sell" if side == "Buy" else "Buy"
            
            logger.info(f"\nClosing {symbol} {side} position, size: {size}")
            
            # Place market order to close
            response = await api_call_with_retry(
                lambda: client.place_order(
                    category="linear",
                    symbol=symbol,
                    side=close_side,
                    orderType="Market",
                    qty=size,
                    reduceOnly=True,
                    positionIdx=position_idx
                ),
                timeout=20
            )
            
            if response and response.get("retCode") == 0:
                success_count += 1
                position_value = Decimal(str(position.get('positionValue', '0')))
                total_value += abs(position_value)
                order_id = response.get("result", {}).get("orderId", "")
                logger.info(f"✅ Closed {symbol} position with order {order_id[:8]}...")
            else:
                error_msg = response.get("retMsg", "Unknown error") if response else "No response"
                logger.error(f"❌ Failed to close {symbol}: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error closing position: {e}")
        
        await asyncio.sleep(0.2)  # Small delay between positions
    
    logger.info(f"\n✅ Closed {success_count}/{len(active_positions)} positions")
    logger.info(f"💰 Total value closed: ${total_value:.2f}")
    return success_count, total_value


async def main():
    """Main function"""
    logger.info("\n🚨 MANUAL POSITION AND ORDER CLOSURE")
    logger.info("="*60)
    
    try:
        # Cancel all orders first
        logger.info("\n📝 PHASE 1: CANCEL ALL ORDERS")
        main_orders_cancelled = await cancel_all_orders("main")
        
        if is_mirror_trading_enabled():
            mirror_orders_cancelled = await cancel_all_orders("mirror")
        else:
            mirror_orders_cancelled = 0
        
        # Small delay
        await asyncio.sleep(1)
        
        # Close all positions
        logger.info("\n💰 PHASE 2: CLOSE ALL POSITIONS")
        main_positions_closed, main_value = await close_all_positions("main")
        
        if is_mirror_trading_enabled():
            mirror_positions_closed, mirror_value = await close_all_positions("mirror")
        else:
            mirror_positions_closed = 0
            mirror_value = Decimal('0')
        
        # Summary
        logger.info(f"\n{'='*60}")
        logger.info("🏁 CLOSURE SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"\n📊 MAIN ACCOUNT:")
        logger.info(f"  Orders cancelled: {main_orders_cancelled}")
        logger.info(f"  Positions closed: {main_positions_closed}")
        logger.info(f"  Value closed: ${main_value:.2f}")
        
        if is_mirror_trading_enabled():
            logger.info(f"\n🔄 MIRROR ACCOUNT:")
            logger.info(f"  Orders cancelled: {mirror_orders_cancelled}")
            logger.info(f"  Positions closed: {mirror_positions_closed}")
            logger.info(f"  Value closed: ${mirror_value:.2f}")
        
        logger.info(f"\n✅ TOTAL:")
        logger.info(f"  Orders cancelled: {main_orders_cancelled + mirror_orders_cancelled}")
        logger.info(f"  Positions closed: {main_positions_closed + mirror_positions_closed}")
        logger.info(f"  Value closed: ${main_value + mirror_value:.2f}")
        
    except Exception as e:
        logger.error(f"Critical error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())