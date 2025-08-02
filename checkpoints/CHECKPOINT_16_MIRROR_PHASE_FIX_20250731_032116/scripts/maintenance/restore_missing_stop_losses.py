#!/usr/bin/env python3
"""
Restore missing stop losses for positions.
This script will:
1. Find all positions missing stop losses
2. Look up original SL prices from trade logs
3. Place the missing SL orders
"""
import asyncio
import logging
import json
from typing import Dict, List, Optional
from decimal import Decimal

from clients.bybit_client import bybit_client
from clients.bybit_helpers import get_all_positions, get_open_orders, place_order_with_retry
from config.settings import USE_TESTNET

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_original_sl_from_logs(symbol: str, side: str) -> Optional[str]:
    """Try to find original SL price from trade logs."""
    try:
        # Check trade history file
        trade_file = "data/trade_history.json"
        try:
            with open(trade_file, 'r') as f:
                trades = json.load(f)
                
            # Look for matching trades
            for trade in trades:
                if (trade.get('symbol') == symbol and 
                    trade.get('side') == side and
                    trade.get('status') == 'active'):
                    sl_price = trade.get('sl_trigger_price')
                    if sl_price:
                        logger.info(f"Found SL price from trade log: {sl_price}")
                        return sl_price
        except FileNotFoundError:
            logger.warning("Trade history file not found")
        except Exception as e:
            logger.error(f"Error reading trade history: {e}")
            
        # If not found in logs, calculate based on 7.5% risk
        return None
        
    except Exception as e:
        logger.error(f"Error getting SL from logs: {e}")
        return None

async def restore_missing_stop_losses():
    """Main function to restore missing stop losses."""
    try:
        logger.info("🔍 Checking for positions with missing stop losses...")
        
        # Get all positions
        positions = await get_all_positions()
        active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
        
        if not active_positions:
            logger.info("No active positions found")
            return
            
        logger.info(f"Found {len(active_positions)} active positions")
        
        # Get all open orders
        all_orders = await get_open_orders()
        
        # Group orders by symbol
        orders_by_symbol = {}
        for order in all_orders:
            symbol = order.get('symbol', '')
            if symbol:
                if symbol not in orders_by_symbol:
                    orders_by_symbol[symbol] = []
                orders_by_symbol[symbol].append(order)
        
        positions_missing_sl = []
        
        # Check each position for missing SL
        for position in active_positions:
            symbol = position['symbol']
            side = position['side']
            size = float(position['size'])
            avg_price = float(position['avgPrice'])
            
            # Get orders for this symbol
            symbol_orders = orders_by_symbol.get(symbol, [])
            
            # Find SL orders
            sl_orders = []
            for order in symbol_orders:
                if not order.get('reduceOnly'):
                    continue
                    
                trigger_price = float(order.get('triggerPrice', 0))
                if trigger_price == 0:
                    continue
                
                # Check if it's a stop loss
                if side == 'Buy' and trigger_price < avg_price:
                    sl_orders.append(order)
                elif side == 'Sell' and trigger_price > avg_price:
                    sl_orders.append(order)
            
            if not sl_orders:
                positions_missing_sl.append(position)
                logger.warning(f"⚠️ {symbol} {side} position missing stop loss!")
        
        if not positions_missing_sl:
            logger.info("✅ All positions have stop losses")
            return
            
        logger.info(f"Found {len(positions_missing_sl)} positions missing stop losses")
        
        # Restore missing stop losses
        restored_count = 0
        
        for position in positions_missing_sl:
            symbol = position['symbol']
            side = position['side']
            size = float(position['size'])
            avg_price = float(position['avgPrice'])
            position_idx = position.get('positionIdx', 0)
            
            logger.info(f"\n📊 Restoring SL for {symbol} {side}")
            logger.info(f"   Size: {size}, Avg Price: {avg_price}")
            
            # Try to find original SL from logs
            original_sl = await get_original_sl_from_logs(symbol, side)
            
            if original_sl:
                sl_price = original_sl
                logger.info(f"   Using original SL from logs: {sl_price}")
            else:
                # Calculate SL based on 7.5% risk
                risk_percentage = 7.5
                if side == 'Buy':
                    sl_price = avg_price * (1 - risk_percentage / 100)
                else:
                    sl_price = avg_price * (1 + risk_percentage / 100)
                logger.info(f"   Calculated SL at 7.5% risk: {sl_price}")
            
            # Get instrument info for price precision
            from clients.bybit_helpers import get_instrument_info
            info = await get_instrument_info(symbol)
            
            if info:
                tick_size = float(info.get('priceFilter', {}).get('tickSize', '0.01'))
                tick_str = f"{tick_size:.10f}".rstrip('0')
                precision = len(tick_str.split('.')[1]) if '.' in tick_str else 0
                sl_price_str = f"{sl_price:.{precision}f}"
            else:
                sl_price_str = str(sl_price)
            
            # Place SL order
            import time
            order_params = {
                "symbol": symbol,
                "side": "Sell" if side == "Buy" else "Buy",
                "order_type": "Market",
                "qty": str(int(size)),
                "trigger_price": sl_price_str,
                "stop_order_type": "StopLoss",
                "reduce_only": True,
                "order_link_id": f"BOT_RESTORE_SL_{int(time.time())}"
            }
            
            if position_idx:
                order_params['position_idx'] = position_idx
            
            result = await place_order_with_retry(**order_params)
            
            if result:
                restored_count += 1
                logger.info(f"✅ Successfully restored SL for {symbol} at {sl_price_str}")
                
                # Update trade log if possible
                try:
                    trade_file = "data/trade_history.json"
                    with open(trade_file, 'r') as f:
                        trades = json.load(f)
                    
                    # Find and update the trade
                    for trade in trades:
                        if (trade.get('symbol') == symbol and 
                            trade.get('side') == side and
                            trade.get('status') == 'active'):
                            trade['sl_trigger_price'] = sl_price_str
                            trade['sl_order_id'] = result.get('orderId', '')
                            break
                    
                    with open(trade_file, 'w') as f:
                        json.dump(trades, f, indent=2)
                    logger.info("   Updated trade log with SL info")
                except Exception as e:
                    logger.warning(f"   Could not update trade log: {e}")
            else:
                logger.error(f"❌ Failed to restore SL for {symbol}")
        
        logger.info(f"\n✅ Restoration complete! Restored {restored_count}/{len(positions_missing_sl)} stop losses")
        
    except Exception as e:
        logger.error(f"Error in restore_missing_stop_losses: {e}")

async def main():
    """Main entry point."""
    await restore_missing_stop_losses()

if __name__ == "__main__":
    asyncio.run(main())