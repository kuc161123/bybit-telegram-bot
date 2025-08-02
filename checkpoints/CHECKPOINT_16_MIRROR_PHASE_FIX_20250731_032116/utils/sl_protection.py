#!/usr/bin/env python3
"""
Runtime protection for stop loss monitoring.
Checks positions every 30 seconds and auto-adds missing stop losses.
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class StopLossProtector:
    """Monitor positions and ensure all have stop losses."""

    def __init__(self):
        self.check_interval = 30  # Check every 30 seconds
        self.running = False
        self.sl_prices_cache = {}
        self.last_check = None

    async def get_sl_price_from_logs(self, symbol: str, side: str) -> Optional[float]:
        """Retrieve stop loss price from trading logs or cache."""

        # First check cache
        if symbol in self.sl_prices_cache:
            return self.sl_prices_cache[symbol]

        # Try to find in trade history
        try:
            import os
            trade_history_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'trade_history.json')

            if os.path.exists(trade_history_path):
                with open(trade_history_path, 'r') as f:
                    history = json.load(f)

                for trade in reversed(history.get('trades', [])):
                    if trade.get('symbol') == symbol:
                        sl_price = trade.get('stop_loss_price')
                        if sl_price:
                            self.sl_prices_cache[symbol] = float(sl_price)
                            return float(sl_price)
        except Exception as e:
            logger.error(f"Error reading trade history: {e}")

        # Fallback: calculate based on position (5% from entry)
        return None

    async def check_and_fix_position(self, client, position: Dict, account_name: str = "Main") -> bool:
        """Check a single position and add SL if missing."""

        try:
            symbol = position['symbol']
            side = position['side']
            size = float(position['size'])
            entry_price = float(position['avgPrice'])

            if size == 0:
                return True

            # Get open orders
            orders_response = client.get_open_orders(
                category="linear",
                symbol=symbol,
                openOnly=1
            )

            if orders_response['retCode'] != 0:
                logger.error(f"Failed to get orders for {symbol}: {orders_response['retMsg']}")
                return False

            # Check if stop loss exists
            has_sl = False
            orders = orders_response['result']['list']

            for order in orders:
                if order.get('stopOrderType') == 'Stop':
                    trigger_price = float(order['triggerPrice'])
                    trigger_direction = order.get('triggerDirection', 0)

                    # Verify it's actually a stop loss
                    if side == "Buy" and trigger_price < entry_price and trigger_direction == 2:
                        has_sl = True
                        break
                    elif side == "Sell" and trigger_price > entry_price and trigger_direction == 1:
                        has_sl = True
                        break

            if has_sl:
                return True

            # Missing stop loss - try to add it
            logger.warning(f"⚠️ {account_name} - {symbol} missing stop loss!")

            # Get SL price from logs
            sl_price = await self.get_sl_price_from_logs(symbol, side)

            if not sl_price:
                # Calculate default SL (5% from entry)
                if side == "Buy":
                    sl_price = entry_price * 0.95
                else:
                    sl_price = entry_price * 1.05

                logger.info(f"Using calculated SL price: {sl_price:.6f}")

            # Place stop loss order
            if side == "Buy":
                trigger_direction = 2
                order_side = "Sell"
            else:
                trigger_direction = 1
                order_side = "Buy"

            sl_response = client.place_order(
                category="linear",
                symbol=symbol,
                side=order_side,
                orderType="Market",
                qty=str(size),
                triggerPrice=str(sl_price),
                triggerDirection=trigger_direction,
                orderFilter="tpslOrder",
                reduceOnly=True,
                closeOnTrigger=True
            )

            if sl_response['retCode'] == 0:
                logger.info(f"✅ {account_name} - Added stop loss for {symbol} at {sl_price:.6f}")

                # Send alert to user
                try:
                    from alerts.alert_manager import alert_manager
                    await alert_manager.send_alert(
                        f"🛡️ Stop Loss Protection\n\n"
                        f"Added missing stop loss:\n"
                        f"Symbol: {symbol}\n"
                        f"Account: {account_name}\n"
                        f"Price: ${sl_price:.6f}",
                        priority="high"
                    )
                except:
                    pass

                return True
            else:
                logger.error(f"Failed to add SL for {symbol}: {sl_response['retMsg']}")
                return False

        except Exception as e:
            logger.error(f"Error checking position {position.get('symbol')}: {e}")
            return False

    async def check_all_positions(self):
        """Check all positions on both accounts."""

        try:
            from clients.bybit_client import bybit_client
            from clients.bybit_helpers import get_all_positions
            from execution.mirror_trader import bybit_client_2, get_mirror_positions

            checked = 0
            fixed = 0

            # Check main account
            try:
                positions = await get_all_positions()
                for position in positions:
                    if float(position.get('size', 0)) > 0:
                        checked += 1
                        if await self.check_and_fix_position(bybit_client._client, position, "Main"):
                            fixed += 1
            except Exception as e:
                logger.error(f"Error checking main account: {e}")

            # Check mirror account
            if bybit_client_2:
                try:
                    positions = await get_mirror_positions()
                    for position in positions:
                        if float(position.get('size', 0)) > 0:
                            checked += 1
                            if await self.check_and_fix_position(bybit_client_2, position, "Mirror"):
                                fixed += 1
                except Exception as e:
                    logger.error(f"Error checking mirror account: {e}")

            if checked > 0:
                logger.debug(f"Stop loss check complete: {checked} positions checked, {fixed} had SL")

        except Exception as e:
            logger.error(f"Error in position check: {e}")

    async def start_monitoring(self):
        """Start the stop loss protection monitor."""

        self.running = True
        logger.info("🛡️ Stop Loss Protection Monitor started")

        while self.running:
            try:
                await self.check_all_positions()
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Error in SL protection monitor: {e}")
                await asyncio.sleep(60)  # Wait longer on error

    def stop(self):
        """Stop the monitor."""
        self.running = False
        logger.info("🛑 Stop Loss Protection Monitor stopped")

# Global instance
sl_protector = StopLossProtector()

# Function to start protection (call from main bot)
async def start_sl_protection():
    """Start the stop loss protection monitor."""
    asyncio.create_task(sl_protector.start_monitoring())
    logger.info("Stop loss protection activated")
