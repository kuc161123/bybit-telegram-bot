#!/usr/bin/env python3
"""
Script to add missing TP order for TIAUSDT on mirror account
TP should be at 19.069 (same as main account)
"""
import asyncio
import logging
from decimal import Decimal
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
from clients.bybit_helpers import api_call_with_retry, adjust_price_to_tick_size

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def get_mirror_position_and_orders(symbol: str):
    """Get current position and orders for TIAUSDT on mirror account"""
    if not is_mirror_trading_enabled():
        logger.error("Mirror trading is not enabled!")
        return None, None
    
    try:
        # Get position info
        logger.info(f"🔍 Fetching mirror account position for {symbol}...")
        position_response = await api_call_with_retry(
            lambda: bybit_client_2.get_positions(
                category="linear",
                symbol=symbol
            )
        )
        
        position = None
        if position_response and position_response.get("retCode") == 0:
            positions = position_response.get("result", {}).get("list", [])
            for pos in positions:
                if float(pos.get("size", 0)) > 0:
                    position = pos
                    break
        
        # Get open orders
        logger.info(f"🔍 Fetching mirror account orders for {symbol}...")
        orders_response = await api_call_with_retry(
            lambda: bybit_client_2.get_open_orders(
                category="linear",
                symbol=symbol
            )
        )
        
        orders = []
        if orders_response and orders_response.get("retCode") == 0:
            orders = orders_response.get("result", {}).get("list", [])
        
        return position, orders
        
    except Exception as e:
        logger.error(f"Error fetching mirror position/orders: {e}")
        return None, None

async def place_mirror_tp_order(symbol: str, side: str, qty: str, trigger_price: str, 
                               position_idx: int, order_link_id: str):
    """Place TP order on mirror account"""
    try:
        # Get current price
        ticker_response = await api_call_with_retry(
            lambda: bybit_client_2.get_tickers(
                category="linear",
                symbol=symbol
            )
        )
        
        current_price = 0
        if ticker_response and ticker_response.get("retCode") == 0:
            tickers = ticker_response.get("result", {}).get("list", [])
            if tickers:
                current_price = float(tickers[0].get("lastPrice", 0))
        
        logger.info(f"📊 Current price: {current_price}, TP trigger: {trigger_price}")
        
        # Determine trigger direction
        trigger_price_float = float(trigger_price)
        if side == "Buy":  # Closing short
            trigger_direction = 2 if trigger_price_float < current_price else 1
        else:  # Closing long  
            trigger_direction = 1 if trigger_price_float > current_price else 2
        
        # Adjust price to tick size
        adjusted_trigger_price = await adjust_price_to_tick_size(symbol, trigger_price)
        
        logger.info(f"🎯 Placing mirror TP order: {symbol} {side} {qty} @ {adjusted_trigger_price}")
        logger.info(f"📊 Order details: positionIdx={position_idx}, triggerDirection={trigger_direction}")
        
        # Place the order
        order_params = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Market",
            "qty": qty,
            "triggerPrice": str(adjusted_trigger_price),
            "triggerDirection": trigger_direction,
            "triggerBy": "LastPrice",
            "positionIdx": position_idx,
            "reduceOnly": True,
            "orderLinkId": order_link_id,
            "stopOrderType": "TakeProfit"
        }
        
        response = await api_call_with_retry(
            lambda: bybit_client_2.place_order(**order_params)
        )
        
        if response and response.get("retCode") == 0:
            result = response.get("result", {})
            order_id = result.get("orderId")
            logger.info(f"✅ Mirror TP order placed successfully: {order_id}")
            return True
        else:
            logger.error(f"❌ Failed to place mirror TP order: {response}")
            return False
            
    except Exception as e:
        logger.error(f"Error placing mirror TP order: {e}")
        return False

async def main():
    """Main function to add missing TP order for TIAUSDT"""
    symbol = "TIAUSDT"
    tp_price = "19.069"  # Same as main account
    
    logger.info("=" * 60)
    logger.info(f"🔧 Fixing missing TP order for {symbol} on mirror account")
    logger.info(f"🎯 Target TP price: {tp_price}")
    logger.info("=" * 60)
    
    # Check if mirror trading is enabled
    if not is_mirror_trading_enabled():
        logger.error("❌ Mirror trading is not enabled! Please check your .env configuration")
        return
    
    # Get current position and orders
    position, orders = await get_mirror_position_and_orders(symbol)
    
    if not position:
        logger.error(f"❌ No active position found for {symbol} on mirror account")
        return
    
    # Extract position details
    position_size = position.get("size", "0")
    side = position.get("side", "")
    avg_price = position.get("avgPrice", "0")
    position_idx = position.get("positionIdx", 0)
    
    logger.info(f"📊 Found position: {side} {position_size} @ {avg_price}")
    logger.info(f"📊 Position index: {position_idx}")
    
    # Determine order side for TP (opposite of position side)
    tp_side = "Sell" if side == "Buy" else "Buy"
    
    # Check existing orders
    tp_orders = []
    sl_orders = []
    
    for order in orders:
        order_link_id = order.get("orderLinkId", "")
        trigger_price = order.get("triggerPrice", "")
        stop_order_type = order.get("stopOrderType", "")
        
        if trigger_price:  # It's a conditional order
            if stop_order_type == "TakeProfit" or "_TP" in order_link_id or "TP" in order_link_id:
                tp_orders.append(order)
            elif stop_order_type == "StopLoss" or "_SL" in order_link_id or "SL" in order_link_id:
                sl_orders.append(order)
    
    logger.info(f"📊 Existing TP orders: {len(tp_orders)}")
    logger.info(f"📊 Existing SL orders: {len(sl_orders)}")
    
    # Show existing TP orders
    if tp_orders:
        logger.info("📋 Current TP orders:")
        for i, tp in enumerate(tp_orders):
            logger.info(f"  TP{i+1}: {tp.get('triggerPrice')} (ID: {tp.get('orderId', '')[:8]}...)")
    
    # Check if TP at 19.069 already exists
    tp_exists = False
    for tp in tp_orders:
        if abs(float(tp.get("triggerPrice", "0")) - float(tp_price)) < 0.001:
            tp_exists = True
            logger.info(f"✅ TP order at {tp_price} already exists!")
            break
    
    if tp_exists:
        logger.info("✅ No action needed - TP order already in place")
        return
    
    # Create order link ID for the new TP
    # Use a pattern that matches existing orders if possible
    if tp_orders:
        # Try to match the pattern of existing orders
        existing_link_id = tp_orders[0].get("orderLinkId", "")
        if "_MIRROR" in existing_link_id:
            # Extract base pattern and add TP suffix
            base_pattern = existing_link_id.split("_TP")[0].split("_MIRROR")[0]
            order_link_id = f"{base_pattern}_TP1_MIRROR"
        else:
            order_link_id = f"BOT_CONS_{symbol}_TP1_MIRROR"
    else:
        order_link_id = f"BOT_CONS_{symbol}_TP1_MIRROR"
    
    logger.info(f"📝 Using orderLinkId: {order_link_id}")
    
    # Place the missing TP order
    success = await place_mirror_tp_order(
        symbol=symbol,
        side=tp_side,
        qty=position_size,
        trigger_price=tp_price,
        position_idx=position_idx,
        order_link_id=order_link_id
    )
    
    if success:
        logger.info("✅ Successfully added missing TP order!")
        
        # Verify the order was placed
        await asyncio.sleep(2)  # Wait a bit for order to register
        _, new_orders = await get_mirror_position_and_orders(symbol)
        
        new_tp_count = sum(1 for o in new_orders if o.get("triggerPrice") and 
                          (o.get("stopOrderType") == "TakeProfit" or "TP" in o.get("orderLinkId", "")))
        
        logger.info(f"✅ Verification: Now have {new_tp_count} TP orders")
    else:
        logger.error("❌ Failed to add missing TP order")

if __name__ == "__main__":
    asyncio.run(main())