#!/usr/bin/env python3
"""
Mirror Trading Module - Replicates trades on a second Bybit account
This module operates as a sidecar to the main trading system.
It does NOT modify existing trade logic, only adds mirror functionality.
"""
import os
import asyncio
import logging
import time
from typing import Optional, Dict, Any, Tuple
from decimal import Decimal
from pybit.unified_trading import HTTP

logger = logging.getLogger(__name__)

# Initialize second Bybit client ONLY if mirror trading is enabled
ENABLE_MIRROR_TRADING = os.getenv("ENABLE_MIRROR_TRADING", "false").lower() == "true"
BYBIT_API_KEY_2 = os.getenv("BYBIT_API_KEY_2", "")
BYBIT_API_SECRET_2 = os.getenv("BYBIT_API_SECRET_2", "")
USE_TESTNET = os.getenv("USE_TESTNET", "false").lower() == "true"

# Only initialize if credentials are provided
bybit_client_2 = None
if ENABLE_MIRROR_TRADING and BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
    try:
        bybit_client_2 = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2
        )
        logger.info("✅ Mirror trading client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize mirror trading client: {e}")
        ENABLE_MIRROR_TRADING = False

# Position mode cache for mirror account
POSITION_MODE_CACHE = {}
POSITION_MODE_CACHE_TTL = 300  # 5 minutes cache

async def detect_position_mode_for_symbol_mirror(symbol: str) -> Tuple[bool, int]:
    """
    Detect position mode for a specific symbol on the mirror account.
    
    Returns:
        Tuple[bool, int]: (is_hedge_mode, default_position_idx)
        - is_hedge_mode: True if hedge mode, False if one-way mode
        - default_position_idx: 0 for one-way, 1 for hedge mode Buy, 2 for hedge mode Sell
    """
    if not ENABLE_MIRROR_TRADING or not bybit_client_2:
        return False, 0  # Default to one-way mode if mirror trading disabled
    
    try:
        # Check cache first
        global POSITION_MODE_CACHE
        current_time = time.time()
        
        if symbol in POSITION_MODE_CACHE:
            mode, timestamp = POSITION_MODE_CACHE[symbol]
            if current_time - timestamp < POSITION_MODE_CACHE_TTL:
                logger.debug(f"🔄 MIRROR: Using cached position mode for {symbol}: {mode}")
                if mode == "hedge":
                    return True, 1  # Hedge mode, default to Buy side
                else:
                    return False, 0  # One-way mode
        
        logger.info(f"🔍 MIRROR: Detecting position mode for {symbol}...")
        
        # Get existing positions to detect mode
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client_2.get_positions(
                category="linear",
                symbol=symbol
            )
        )
        
        if response and response.get("retCode") == 0:
            positions = response.get("result", {}).get("list", [])
            
            # Check if any positions have non-zero positionIdx (indicating hedge mode)
            hedge_mode_detected = False
            for pos in positions:
                pos_idx = pos.get("positionIdx", 0)
                logger.debug(f"🔍 MIRROR: Position {symbol}: positionIdx={pos_idx}, size={pos.get('size', '0')}")
                if pos_idx in [1, 2]:  # Hedge mode indices
                    hedge_mode_detected = True
                    logger.info(f"🎯 MIRROR: Hedge mode detected for {symbol} (positionIdx={pos_idx})")
                    break
            
            # Cache the result
            mode = "hedge" if hedge_mode_detected else "one-way"
            POSITION_MODE_CACHE[symbol] = (mode, current_time)
            
            if hedge_mode_detected:
                logger.info(f"✅ MIRROR: Position mode for {symbol}: HEDGE")
                return True, 1  # Default to Buy side for hedge mode
            else:
                logger.info(f"✅ MIRROR: Position mode for {symbol}: ONE-WAY")
                return False, 0
        else:
            logger.warning(f"⚠️ MIRROR: Could not detect position mode for {symbol}, defaulting to ONE-WAY")
            # Default to one-way mode if we can't detect
            POSITION_MODE_CACHE[symbol] = ("one-way", current_time)
            return False, 0
            
    except Exception as e:
        logger.error(f"❌ MIRROR: Error detecting position mode for {symbol}: {e}")
        # Default to one-way mode on error
        return False, 0

def get_position_idx_for_side(side: str, is_hedge_mode: bool) -> int:
    """Get the correct positionIdx for the given side and mode"""
    if not is_hedge_mode:
        return 0  # One-way mode
    else:
        # Hedge mode
        return 1 if side.lower() in ["buy", "long"] else 2

async def mirror_market_order(
    symbol: str,
    side: str,
    qty: str,
    position_idx: int,
    order_link_id: Optional[str] = None
) -> Optional[Dict]:
    """
    Mirror a market order on the second account.
    Returns None on failure to ensure it doesn't affect primary trading.
    """
    if not ENABLE_MIRROR_TRADING or not bybit_client_2:
        return None
    
    try:
        # Detect position mode for mirror account and get correct positionIdx
        is_hedge_mode, _ = await detect_position_mode_for_symbol_mirror(symbol)
        mirror_position_idx = get_position_idx_for_side(side, is_hedge_mode)
        
        logger.info(f"🔄 MIRROR: Position mode for {symbol}: {'HEDGE' if is_hedge_mode else 'ONE-WAY'}, using positionIdx={mirror_position_idx}")
        
        # Use order link ID as-is if it already contains _MIRROR, otherwise add _MIRROR suffix
        if order_link_id and "_MIRROR" in order_link_id:
            mirror_link_id = order_link_id
        else:
            mirror_link_id = f"{order_link_id}_MIRROR" if order_link_id else None
        
        # Execute mirror order in thread executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client_2.place_order(
                category="linear",
                symbol=symbol,
                side=side,
                orderType="Market",
                qty=qty,
                positionIdx=mirror_position_idx,  # Use detected position index
                orderLinkId=mirror_link_id
            )
        )
        
        if response and response.get("retCode") == 0:
            result = response.get("result", {})
            order_id = result.get("orderId", "")
            logger.info(f"✅ MIRROR: Market order placed successfully: {order_id[:8]}...")
            return result
        else:
            logger.error(f"❌ MIRROR: Market order failed: {response}")
            return None
            
    except Exception as e:
        logger.error(f"❌ MIRROR: Exception placing market order: {e}")
        return None

async def mirror_limit_order(
    symbol: str,
    side: str,
    qty: str,
    price: str,
    position_idx: int,
    order_link_id: Optional[str] = None
) -> Optional[Dict]:
    """
    Mirror a limit order on the second account.
    Returns None on failure to ensure it doesn't affect primary trading.
    """
    if not ENABLE_MIRROR_TRADING or not bybit_client_2:
        return None
    
    try:
        # Detect position mode for mirror account and get correct positionIdx
        is_hedge_mode, _ = await detect_position_mode_for_symbol_mirror(symbol)
        mirror_position_idx = get_position_idx_for_side(side, is_hedge_mode)
        
        logger.info(f"🔄 MIRROR: Position mode for {symbol}: {'HEDGE' if is_hedge_mode else 'ONE-WAY'}, using positionIdx={mirror_position_idx}")
        
        # Use order link ID as-is if it already contains _MIRROR, otherwise add _MIRROR suffix
        if order_link_id and "_MIRROR" in order_link_id:
            mirror_link_id = order_link_id
        else:
            mirror_link_id = f"{order_link_id}_MIRROR" if order_link_id else None
        
        # Execute mirror order in thread executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client_2.place_order(
                category="linear",
                symbol=symbol,
                side=side,
                orderType="Limit",
                qty=qty,
                price=price,
                positionIdx=mirror_position_idx,  # Use detected position index
                orderLinkId=mirror_link_id
            )
        )
        
        if response and response.get("retCode") == 0:
            result = response.get("result", {})
            order_id = result.get("orderId", "")
            logger.info(f"✅ MIRROR: Limit order placed successfully: {order_id[:8]}...")
            return result
        else:
            logger.error(f"❌ MIRROR: Limit order failed: {response}")
            return None
            
    except Exception as e:
        logger.error(f"❌ MIRROR: Exception placing limit order: {e}")
        return None

async def mirror_tp_sl_order(
    symbol: str,
    side: str,
    qty: str,
    trigger_price: str,
    position_idx: int,
    order_type: str = "Market",
    reduce_only: bool = True,
    order_link_id: Optional[str] = None
) -> Optional[Dict]:
    """
    Mirror a TP/SL order on the second account.
    Returns None on failure to ensure it doesn't affect primary trading.
    """
    if not ENABLE_MIRROR_TRADING or not bybit_client_2:
        return None
    
    try:
        # Detect position mode for mirror account and get correct positionIdx
        is_hedge_mode, _ = await detect_position_mode_for_symbol_mirror(symbol)
        mirror_position_idx = get_position_idx_for_side(side, is_hedge_mode)
        
        logger.debug(f"🔄 MIRROR TP/SL: Position mode for {symbol}: {'HEDGE' if is_hedge_mode else 'ONE-WAY'}, using positionIdx={mirror_position_idx}")
        
        # Use order link ID as-is if it already contains _MIRROR, otherwise add _MIRROR suffix
        if order_link_id and "_MIRROR" in order_link_id:
            mirror_link_id = order_link_id
        else:
            mirror_link_id = f"{order_link_id}_MIRROR" if order_link_id else None
        
        # Determine trigger direction
        current_price = await get_mirror_current_price(symbol)
        if current_price:
            trigger_price_float = float(trigger_price)
            if side == "Buy":  # Closing short
                trigger_direction = 2 if trigger_price_float < current_price else 1
            else:  # Closing long
                trigger_direction = 1 if trigger_price_float > current_price else 2
        else:
            trigger_direction = 1 if side == "Buy" else 2
        
        # Execute mirror order in thread executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client_2.place_order(
                category="linear",
                symbol=symbol,
                side=side,
                orderType=order_type,
                qty=qty,
                triggerPrice=trigger_price,
                triggerDirection=trigger_direction,
                triggerBy="LastPrice",
                positionIdx=mirror_position_idx,  # Use detected position index
                reduceOnly=reduce_only,
                orderLinkId=mirror_link_id
            )
        )
        
        if response and response.get("retCode") == 0:
            result = response.get("result", {})
            order_id = result.get("orderId", "")
            logger.info(f"✅ MIRROR: TP/SL order placed successfully: {order_id[:8]}...")
            return result
        else:
            logger.error(f"❌ MIRROR: TP/SL order failed: {response}")
            return None
            
    except Exception as e:
        logger.error(f"❌ MIRROR: Exception placing TP/SL order: {e}")
        return None

async def get_mirror_current_price(symbol: str) -> Optional[float]:
    """Get current price from mirror account."""
    if not bybit_client_2:
        return None
        
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client_2.get_tickers(
                category="linear",
                symbol=symbol
            )
        )
        
        if response and response.get("retCode") == 0:
            tickers = response.get("result", {}).get("list", [])
            if tickers:
                return float(tickers[0].get("lastPrice", 0))
        return None
        
    except Exception as e:
        logger.error(f"❌ MIRROR: Error getting current price: {e}")
        return None

async def cancel_mirror_order(symbol: str, order_id: str) -> bool:
    """Cancel an order on the mirror account."""
    if not ENABLE_MIRROR_TRADING or not bybit_client_2:
        return False
        
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: bybit_client_2.cancel_order(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )
        )
        
        if response and response.get("retCode") == 0:
            logger.info(f"✅ MIRROR: Order {order_id[:8]}... cancelled successfully")
            return True
        else:
            logger.error(f"❌ MIRROR: Failed to cancel order: {response}")
            return False
            
    except Exception as e:
        logger.error(f"❌ MIRROR: Exception cancelling order: {e}")
        return False

# Status check function
def is_mirror_trading_enabled() -> bool:
    """Check if mirror trading is enabled and properly configured."""
    return ENABLE_MIRROR_TRADING and bybit_client_2 is not None