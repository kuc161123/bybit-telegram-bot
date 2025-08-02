"""
Mirror TP order placement function to ensure all TP orders are limit orders
"""
import asyncio
from typing import Optional, Dict
from decimal import Decimal
import logging

from .mirror_trader import (
    ENABLE_MIRROR_TRADING, 
    bybit_client_2,
    mirror_limit_order,
    detect_position_mode_for_symbol_mirror,
    get_position_idx_for_side,
    validate_quantity_for_order,
    format_quantity_for_exchange,
    logger as mirror_logger
)

logger = logging.getLogger(__name__)

async def mirror_tp_order(
    symbol: str,
    side: str,
    qty: str,
    price: str,
    position_idx: int = 0,
    order_link_id: Optional[str] = None,
    tp_number: int = 1
) -> Optional[Dict]:
    """
    Place a TP order on mirror account - ALWAYS as a limit order
    
    Args:
        symbol: Trading symbol
        side: Order side (opposite of position side)
        qty: Order quantity
        price: TP price (as limit price, not trigger price)
        position_idx: Position index
        order_link_id: Order link ID
        tp_number: TP number (1-4) for logging
        
    Returns:
        Order result or None if failed
    """
    if not ENABLE_MIRROR_TRADING or not bybit_client_2:
        return None
        
    try:
        # Use the existing mirror_limit_order function which already handles everything correctly
        result = await mirror_limit_order(
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            position_idx=position_idx,
            order_link_id=order_link_id or f"MIR_TP{tp_number}_{symbol}"
        )
        
        if result:
            logger.info(f"✅ MIRROR: TP{tp_number} limit order placed for {symbol}")
        else:
            logger.error(f"❌ MIRROR: Failed to place TP{tp_number} limit order for {symbol}")
            
        return result
        
    except Exception as e:
        logger.error(f"❌ MIRROR: Exception placing TP order: {e}")
        return None


def should_use_limit_for_tp(order_link_id: str = None, stop_order_type: str = None) -> bool:
    """
    Determine if an order should be placed as a limit order (for TP) or stop order (for SL)
    
    Args:
        order_link_id: The order link ID
        stop_order_type: The stop order type if provided
        
    Returns:
        True if should use limit order, False for stop order
    """
    # If it's explicitly a stop loss, use stop order
    if stop_order_type == "StopLoss" or (order_link_id and "SL" in order_link_id.upper()):
        return False
        
    # If it's a TP order, use limit order
    if stop_order_type == "TakeProfit" or (order_link_id and "TP" in order_link_id.upper()):
        return True
        
    # Default to stop order for safety (SL)
    return False