#!/usr/bin/env python3
"""
Monitor and maintain mirror account synchronization.
Prevents order accumulation and ensures consistency.
"""

import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MirrorSyncMaintainer:
    """Maintains mirror account synchronization."""

    def __init__(self):
        self.check_interval = 300  # 5 minutes
        self.max_orders_per_symbol = 8
        self.running = False

    async def check_and_fix_symbol(self, main_client, mirror_client, symbol: str):
        """Check and fix orders for a specific symbol."""

        try:
            # Get orders from both accounts
            main_orders = main_client.get_open_orders(
                category="linear",
                symbol=symbol,
                openOnly=1
            )

            mirror_orders = mirror_client.get_open_orders(
                category="linear",
                symbol=symbol,
                openOnly=1
            )

            if main_orders['retCode'] != 0 or mirror_orders['retCode'] != 0:
                return

            main_stop_orders = [o for o in main_orders['result']['list']
                              if o.get('stopOrderType') == 'Stop']
            mirror_stop_orders = [o for o in mirror_orders['result']['list']
                                if o.get('stopOrderType') == 'Stop']

            # Check if mirror has too many orders
            if len(mirror_stop_orders) > self.max_orders_per_symbol:
                logger.warning(f"{symbol}: Mirror has {len(mirror_stop_orders)} orders (main has {len(main_stop_orders)})")

                # Cancel excess orders
                excess = len(mirror_stop_orders) - self.max_orders_per_symbol
                for order in mirror_stop_orders[:excess]:
                    try:
                        mirror_client.cancel_order(
                            category="linear",
                            symbol=symbol,
                            orderId=order['orderId']
                        )
                        logger.info(f"Cancelled excess order for {symbol}")
                    except:
                        pass

        except Exception as e:
            logger.error(f"Error checking {symbol}: {e}")

    async def run_sync_check(self):
        """Run synchronization check."""

        try:
            from pybit.unified_trading import HTTP
            from config.settings import (
                BYBIT_API_KEY, BYBIT_API_SECRET,
                BYBIT_API_KEY_2, BYBIT_API_SECRET_2,
                USE_TESTNET
            )

            if not all([BYBIT_API_KEY_2, BYBIT_API_SECRET_2]):
                return

            main_client = HTTP(
                testnet=USE_TESTNET,
                api_key=BYBIT_API_KEY,
                api_secret=BYBIT_API_SECRET
            )

            mirror_client = HTTP(
                testnet=USE_TESTNET,
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2
            )

            # Get all positions
            response = mirror_client.get_positions(
                category="linear",
                settleCoin="USDT"
            )

            if response['retCode'] == 0:
                symbols = set()
                for pos in response['result']['list']:
                    if float(pos['size']) > 0:
                        symbols.add(pos['symbol'])

                # Check each symbol
                for symbol in symbols:
                    await self.check_and_fix_symbol(main_client, mirror_client, symbol)
                    await asyncio.sleep(0.1)  # Rate limiting

        except Exception as e:
            logger.error(f"Error in sync check: {e}")

    async def start(self):
        """Start the sync maintainer."""
        self.running = True
        logger.info("Mirror sync maintainer started")

        while self.running:
            try:
                await self.run_sync_check()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in sync maintainer: {e}")
                await asyncio.sleep(60)

# Global instance
mirror_sync_maintainer = MirrorSyncMaintainer()
