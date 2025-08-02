#!/usr/bin/env python3
"""
Recovery script to recreate missing stop loss orders for positions.
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime

from clients.bybit_client import bybit_client
from clients.bybit_helpers import (
    get_all_positions, get_all_open_orders,
    place_order_with_retry, get_instrument_info
)
from config.settings import ENABLE_MIRROR_TRADING

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def calculate_sl_price(position: Dict, risk_percentage: float = 7.5) -> Optional[float]:
    """Calculate stop loss price based on position and risk percentage."""
    try:
        avg_price = float(position.get('avgPrice', 0))
        if avg_price == 0:
            return None
            
        side = position.get('side')
        
        if side == 'Buy':
            # For long positions, SL is below entry
            sl_price = avg_price * (1 - risk_percentage / 100)
        else:  # Sell
            # For short positions, SL is above entry
            sl_price = avg_price * (1 + risk_percentage / 100)
            
        return sl_price
        
    except Exception as e:
        logger.error(f"Error calculating SL price: {e}")
        return None


async def get_price_precision(symbol: str) -> int:
    """Get price decimal precision for a symbol."""
    try:
        info = await get_instrument_info(symbol)
        if info:
            tick_size = float(info.get('priceFilter', {}).get('tickSize', '0.01'))
            # Count decimal places
            tick_str = f"{tick_size:.10f}".rstrip('0')
            if '.' in tick_str:
                return len(tick_str.split('.')[1])
        return 2
    except:
        return 2


async def format_price(price: float, symbol: str) -> str:
    """Format price according to symbol precision."""
    precision = await get_price_precision(symbol)
    return f"{price:.{precision}f}"


async def recover_missing_stop_losses():
    """Main recovery function to recreate missing SL orders."""
    try:
        logger.info("🔍 Starting stop loss recovery process...")
        
        # Get all positions and orders
        positions = await get_all_positions()
        all_orders = await get_all_open_orders()
        
        # Group orders by symbol
        orders_by_symbol = {}
        for order in all_orders:
            symbol = order.get('symbol')
            if symbol not in orders_by_symbol:
                orders_by_symbol[symbol] = []
            orders_by_symbol[symbol].append(order)
        
        # Track recovery statistics
        positions_checked = 0
        sl_orders_created = 0
        errors = []
        
        # Check each position
        for position in positions:
            if float(position.get('size', 0)) == 0:
                continue
                
            positions_checked += 1
            symbol = position['symbol']
            side = position['side']
            size = float(position['size'])
            avg_price = float(position.get('avgPrice', 0))
            position_idx = position.get('positionIdx', 0)
            
            logger.info(f"\n📊 Checking {symbol} {side} position (Size: {size})")
            
            # Check if SL order exists
            has_sl = False
            if symbol in orders_by_symbol:
                for order in orders_by_symbol[symbol]:
                    if not order.get('reduceOnly'):
                        continue
                        
                    trigger_price = float(order.get('triggerPrice', 0))
                    if trigger_price == 0:
                        continue
                        
                    # Check if it's a stop loss order
                    order_side = order.get('side')
                    if side == 'Buy' and order_side == 'Sell' and trigger_price < avg_price:
                        has_sl = True
                        logger.info(f"  ✅ Found existing SL at ${trigger_price}")
                        break
                    elif side == 'Sell' and order_side == 'Buy' and trigger_price > avg_price:
                        has_sl = True
                        logger.info(f"  ✅ Found existing SL at ${trigger_price}")
                        break
            
            if not has_sl:
                logger.warning(f"  ⚠️ No SL order found for {symbol}!")
                
                # Calculate SL price
                sl_price = await calculate_sl_price(position)
                if not sl_price:
                    logger.error(f"  ❌ Could not calculate SL price for {symbol}")
                    errors.append(f"{symbol}: Could not calculate SL price")
                    continue
                
                # Format price according to symbol precision
                sl_price_str = await format_price(sl_price, symbol)
                
                # Place SL order
                try:
                    order_params = {
                        "symbol": symbol,
                        "side": "Sell" if side == "Buy" else "Buy",
                        "order_type": "Market",
                        "qty": str(int(size)),
                        "trigger_price": sl_price_str,
                        "stop_order_type": "StopLoss",
                        "reduce_only": True,
                        "order_link_id": f"RECOVERY_SL_{int(datetime.now().timestamp())}"
                    }
                    
                    if position_idx:
                        order_params['position_idx'] = position_idx
                    
                    logger.info(f"  📤 Placing SL order at ${sl_price_str} for {size} units...")
                    
                    result = await place_order_with_retry(**order_params)
                    
                    if result:
                        sl_orders_created += 1
                        logger.info(f"  ✅ Successfully created SL order for {symbol}")
                    else:
                        logger.error(f"  ❌ Failed to create SL order for {symbol}")
                        errors.append(f"{symbol}: Failed to place SL order")
                        
                except Exception as e:
                    logger.error(f"  ❌ Error placing SL order: {e}")
                    errors.append(f"{symbol}: {str(e)}")
        
        # Summary
        logger.info("\n" + "="*50)
        logger.info("📊 RECOVERY SUMMARY")
        logger.info("="*50)
        logger.info(f"Positions checked: {positions_checked}")
        logger.info(f"SL orders created: {sl_orders_created}")
        logger.info(f"Errors encountered: {len(errors)}")
        
        if errors:
            logger.info("\n❌ ERRORS:")
            for error in errors:
                logger.info(f"  - {error}")
        
        if sl_orders_created > 0:
            logger.info("\n✅ Recovery completed! Please verify all SL orders in your trading interface.")
        else:
            logger.info("\n✅ No missing SL orders found or all recovery attempts failed.")
            
    except Exception as e:
        logger.error(f"Fatal error in recovery process: {e}")
        raise


async def main():
    """Main entry point."""
    try:
        await recover_missing_stop_losses()
    except Exception as e:
        logger.error(f"Main error: {e}")


if __name__ == "__main__":
    asyncio.run(main())