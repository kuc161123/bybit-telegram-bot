#!/usr/bin/env python3
"""
Clean slate closure - Close all positions and orders for both accounts
"""
import asyncio
import logging
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from clients.bybit_client import bybit_client
from clients.bybit_helpers import api_call_with_retry

# Check if mirror trading is available
try:
    from execution.mirror_trader import bybit_client_2
    MIRROR_AVAILABLE = True
    logger.info("✅ Mirror trading available")
except ImportError:
    MIRROR_AVAILABLE = False
    bybit_client_2 = None
    logger.info("ℹ️ Mirror trading not available")


async def close_all_positions_and_orders():
    """Close all positions and cancel all orders for both accounts"""
    
    # Main account
    logger.info("🔄 Processing MAIN account...")
    await process_account(bybit_client, "MAIN")
    
    # Mirror account (if available)
    if MIRROR_AVAILABLE and bybit_client_2:
        logger.info("🔄 Processing MIRROR account...")
        await process_account(bybit_client_2, "MIRROR")
    else:
        logger.info("⏭️ Skipping mirror account (not configured)")
    
    logger.info("✅ Clean slate operation completed!")


async def process_account(client, account_name):
    """Process one account - cancel orders then close positions"""
    
    try:
        # Step 1: Cancel all open orders first
        logger.info(f"📋 Cancelling all open orders for {account_name} account...")
        
        orders_response = await api_call_with_retry(
            lambda: client.get_open_orders(category="linear", settleCoin="USDT"),
            timeout=20
        )
        
        if orders_response and orders_response.get('retCode') == 0:
            orders = orders_response.get('result', {}).get('list', [])
            logger.info(f"Found {len(orders)} open orders to cancel")
            
            for order in orders:
                order_id = order.get('orderId')
                symbol = order.get('symbol')
                
                try:
                    cancel_response = await api_call_with_retry(
                        lambda: client.cancel_order(
                            category="linear",
                            symbol=symbol,
                            orderId=order_id
                        ),
                        timeout=15
                    )
                    
                    if cancel_response and cancel_response.get('retCode') == 0:
                        logger.info(f"✅ Cancelled {symbol} order {order_id[:8]}...")
                    else:
                        error_msg = cancel_response.get('retMsg', 'Unknown error') if cancel_response else 'No response'
                        logger.warning(f"⚠️ Failed to cancel {symbol} order: {error_msg}")
                        
                except Exception as e:
                    logger.error(f"❌ Error cancelling order {order_id}: {e}")
        
        # Step 2: Close all positions
        logger.info(f"📊 Closing all positions for {account_name} account...")
        
        positions_response = await api_call_with_retry(
            lambda: client.get_positions(category="linear", settleCoin="USDT"),
            timeout=20
        )
        
        if positions_response and positions_response.get('retCode') == 0:
            all_positions = positions_response.get('result', {}).get('list', [])
            active_positions = [p for p in all_positions if float(p.get('size', 0)) > 0]
            
            logger.info(f"Found {len(active_positions)} active positions to close")
            
            for position in active_positions:
                symbol = position.get('symbol')
                side = position.get('side')
                size = position.get('size')
                position_idx = position.get('positionIdx', 0)
                
                logger.info(f"Closing {symbol} {side} position (size: {size})")
                
                # Determine close side
                close_side = "Sell" if side == "Buy" else "Buy"
                
                # Use timestamp to ensure unique order ID
                unique_timestamp = str(int(time.time() * 1000))
                order_link_id = f"CLEAN_SLATE_{symbol}_{unique_timestamp}"
                
                try:
                    close_response = await api_call_with_retry(
                        lambda: client.place_order(
                            category="linear",
                            symbol=symbol,
                            side=close_side,
                            orderType="Market",
                            qty=str(size),  # Use exact position size
                            reduceOnly=True,
                            positionIdx=position_idx,
                            orderLinkId=order_link_id
                        ),
                        timeout=20
                    )
                    
                    if close_response and close_response.get('retCode') == 0:
                        logger.info(f"✅ Successfully closed {symbol} {side}")
                    else:
                        error_msg = close_response.get('retMsg', 'Unknown error') if close_response else 'No response'
                        logger.error(f"❌ Failed to close {symbol}: {error_msg}")
                        
                except Exception as e:
                    logger.error(f"❌ Error closing {symbol} position: {e}")
        
        # Step 3: Verify everything is clean
        await asyncio.sleep(3)  # Wait for execution
        
        # Check remaining positions
        final_positions_response = await api_call_with_retry(
            lambda: client.get_positions(category="linear", settleCoin="USDT"),
            timeout=20
        )
        
        if final_positions_response and final_positions_response.get('retCode') == 0:
            remaining_positions = [p for p in final_positions_response.get('result', {}).get('list', []) if float(p.get('size', 0)) > 0]
            
            if remaining_positions:
                logger.warning(f"⚠️ {account_name}: Still have {len(remaining_positions)} positions remaining")
                for pos in remaining_positions:
                    logger.warning(f"   {pos.get('symbol')} {pos.get('side')}: {pos.get('size')}")
            else:
                logger.info(f"✅ {account_name}: All positions successfully closed")
        
        # Check remaining orders
        final_orders_response = await api_call_with_retry(
            lambda: client.get_open_orders(category="linear", settleCoin="USDT"),
            timeout=20
        )
        
        if final_orders_response and final_orders_response.get('retCode') == 0:
            remaining_orders = final_orders_response.get('result', {}).get('list', [])
            
            if remaining_orders:
                logger.warning(f"⚠️ {account_name}: Still have {len(remaining_orders)} orders remaining")
                for order in remaining_orders:
                    logger.warning(f"   {order.get('symbol')} {order.get('side')} {order.get('orderType')}: {order.get('orderId')[:8]}...")
            else:
                logger.info(f"✅ {account_name}: All orders successfully cancelled")
                
    except Exception as e:
        logger.error(f"❌ Error processing {account_name} account: {e}")


if __name__ == "__main__":
    asyncio.run(close_all_positions_and_orders())