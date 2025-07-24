#!/usr/bin/env python3
"""
Enhanced Mirror TP/SL Manager with Comprehensive Error Handling
==============================================================

This module handles TP/SL order synchronization for mirror accounts with:
- Robust error handling and retry logic
- Circuit breaker pattern to prevent cascading failures
- Position size tolerance checks
- Order validation before execution
- Detailed error logging and categorization
"""

import asyncio
import logging
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional, Any, Tuple
import time
import pickle
import os

from pybit.unified_trading import HTTP
from pybit.exceptions import InvalidRequestError

# Import error handler
from create_enhanced_mirror_error_handling import EnhancedMirrorErrorHandler, CircuitBreaker

# Set up logging
logger = logging.getLogger(__name__)

# Position size tolerance (0.1%)
POSITION_SIZE_TOLERANCE = Decimal('0.001')

# Maximum sync attempts per position
MAX_SYNC_ATTEMPTS = 3

# Sync cooldown period (seconds)
SYNC_COOLDOWN = 30

class MirrorEnhancedTPSL:
    """Enhanced TP/SL management for mirror trading with comprehensive error handling"""

    def __init__(self, client: HTTP, account_prefix: str = "Mirror"):
        self.client = client
        self.account_prefix = account_prefix
        self.error_handler = EnhancedMirrorErrorHandler()
        self.sync_attempts = {}  # Track sync attempts per position
        self.last_sync_time = {}  # Track last sync time per position

        logger.info(f"Initialized {account_prefix} Enhanced TP/SL Manager with error handling")

    def validate_quantity(self, symbol: str, quantity: Decimal) -> Decimal:
        """Validate and format quantity for order placement"""
        try:
            # Get instrument info for precision
            response = self.client.get_instruments_info(
                category="linear",
                symbol=symbol
            )

            if response['retCode'] == 0 and response['result']['list']:
                instrument = response['result']['list'][0]

                # Get quantity precision
                qty_filter = instrument['lotSizeFilter']
                min_qty = Decimal(qty_filter['minOrderQty'])
                max_qty = Decimal(qty_filter['maxOrderQty'])
                qty_step = Decimal(qty_filter['qtyStep'])

                # Validate quantity
                if quantity < min_qty:
                    logger.warning(f"{symbol}: Quantity {quantity} below minimum {min_qty}")
                    return min_qty

                if quantity > max_qty:
                    logger.warning(f"{symbol}: Quantity {quantity} above maximum {max_qty}")
                    return max_qty

                # Round to qty step
                if qty_step > 0:
                    quantity = (quantity / qty_step).quantize(Decimal('1'), rounding=ROUND_DOWN) * qty_step

                return quantity

        except Exception as e:
            logger.error(f"Error validating quantity for {symbol}: {e}")
            return quantity

    def validate_price(self, symbol: str, price: Decimal, side: str) -> Decimal:
        """Validate and format price for order placement"""
        try:
            # Get instrument info for precision
            response = self.client.get_instruments_info(
                category="linear",
                symbol=symbol
            )

            if response['retCode'] == 0 and response['result']['list']:
                instrument = response['result']['list'][0]

                # Get price precision
                price_filter = instrument['priceFilter']
                tick_size = Decimal(price_filter['tickSize'])

                # Round to tick size
                if tick_size > 0:
                    price = (price / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size

                return price

        except Exception as e:
            logger.error(f"Error validating price for {symbol}: {e}")
            return price

    def check_position_sync(self, main_position: Dict, mirror_position: Optional[Dict]) -> bool:
        """Check if positions are in sync within tolerance"""
        if not mirror_position:
            return False

        main_size = abs(Decimal(str(main_position.get('size', '0'))))
        mirror_size = abs(Decimal(str(mirror_position.get('size', '0'))))

        if main_size == 0 and mirror_size == 0:
            return True

        if main_size == 0 or mirror_size == 0:
            return False

        # Check if sizes are within tolerance
        size_diff = abs(main_size - mirror_size)
        tolerance = main_size * POSITION_SIZE_TOLERANCE

        return size_diff <= tolerance

    def should_attempt_sync(self, symbol: str, side: str) -> bool:
        """Check if we should attempt sync based on cooldown and attempt limits"""
        key = f"{symbol}_{side}"

        # Check attempt limit
        attempts = self.sync_attempts.get(key, 0)
        if attempts >= MAX_SYNC_ATTEMPTS:
            logger.warning(f"Max sync attempts reached for {key}")
            return False

        # Check cooldown
        last_sync = self.last_sync_time.get(key, 0)
        if time.time() - last_sync < SYNC_COOLDOWN:
            logger.info(f"Sync cooldown active for {key}")
            return False

        return True

    def record_sync_attempt(self, symbol: str, side: str, success: bool):
        """Record sync attempt for tracking"""
        key = f"{symbol}_{side}"

        if success:
            # Reset on success
            self.sync_attempts[key] = 0
            self.last_sync_time[key] = 0
        else:
            # Increment attempts and set cooldown
            self.sync_attempts[key] = self.sync_attempts.get(key, 0) + 1
            self.last_sync_time[key] = time.time()

    async def cancel_order_safe(self, symbol: str, order_id: str) -> bool:
        """Safely cancel an order with error handling"""
        try:
            result = await self.error_handler.execute_with_retry(
                self._cancel_order_internal,
                symbol=symbol,
                order_id=order_id
            )
            return result
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id} for {symbol}: {e}")
            return False

    async def _cancel_order_internal(self, symbol: str, order_id: str):
        """Internal method to cancel order"""
        response = self.client.cancel_order(
            category="linear",
            symbol=symbol,
            orderId=order_id
        )

        if response['retCode'] != 0:
            raise Exception(f"Cancel failed: {response.get('retMsg', 'Unknown error')}")

        return True

    async def place_order_safe(self, order_params: Dict) -> Optional[str]:
        """Safely place an order with validation and error handling"""
        try:
            # Validate parameters
            symbol = order_params.get('symbol')
            if not symbol:
                raise ValueError("Symbol is required")

            # Validate and format quantity
            if 'qty' in order_params:
                order_params['qty'] = str(self.validate_quantity(
                    symbol,
                    Decimal(str(order_params['qty']))
                ))

            # Validate and format price
            if 'price' in order_params:
                order_params['price'] = str(self.validate_price(
                    symbol,
                    Decimal(str(order_params['price'])),
                    order_params.get('side', 'Buy')
                ))

            # Place order with retry
            result = await self.error_handler.execute_with_retry(
                self._place_order_internal,
                order_params=order_params,
                symbol=symbol
            )

            return result

        except Exception as e:
            logger.error(f"Failed to place order for {symbol}: {e}")
            return None

    async def _place_order_internal(self, order_params: Dict, symbol: str):
        """Internal method to place order"""
        response = self.client.place_order(**order_params)

        if response['retCode'] != 0:
            raise Exception(f"Place order failed: {response.get('retMsg', 'Unknown error')}")

        return response['result']['orderId']

    async def sync_tp_sl_orders(self, main_position: Dict, mirror_position: Optional[Dict]) -> bool:
        """Sync TP/SL orders with comprehensive error handling"""
        symbol = main_position['symbol']
        side = main_position['side']

        try:
            # Check if sync should be attempted
            if not self.should_attempt_sync(symbol, side):
                return False

            # Validate position sync
            if not self.check_position_sync(main_position, mirror_position):
                logger.warning(f"{symbol}: Positions not in sync, skipping TP/SL sync")
                self.record_sync_attempt(symbol, side, False)
                return False

            # Get current orders
            main_orders = await self.get_active_orders(symbol, "Main")
            mirror_orders = await self.get_active_orders(symbol, "Mirror")

            # Sync TP orders
            tp_success = await self.sync_order_type(
                symbol, side, main_orders, mirror_orders,
                mirror_position, "TakeProfit"
            )

            # Sync SL orders
            sl_success = await self.sync_order_type(
                symbol, side, main_orders, mirror_orders,
                mirror_position, "StopLoss"
            )

            success = tp_success and sl_success
            self.record_sync_attempt(symbol, side, success)

            return success

        except Exception as e:
            logger.error(f"Error syncing TP/SL for {symbol}: {e}")
            self.record_sync_attempt(symbol, side, False)
            return False

    async def sync_order_type(self, symbol: str, side: str, main_orders: List[Dict],
                            mirror_orders: List[Dict], mirror_position: Dict,
                            order_type: str) -> bool:
        """Sync specific order type with error handling"""
        try:
            # Filter orders by type
            main_type_orders = [o for o in main_orders if o.get('orderType') == order_type]
            mirror_type_orders = [o for o in mirror_orders if o.get('orderType') == order_type]

            # Cancel excess mirror orders
            if len(mirror_type_orders) > len(main_type_orders):
                for order in mirror_type_orders[len(main_type_orders):]:
                    await self.cancel_order_safe(symbol, order['orderId'])

            # Create or update mirror orders
            for i, main_order in enumerate(main_type_orders):
                if i < len(mirror_type_orders):
                    # Update existing order if needed
                    mirror_order = mirror_type_orders[i]
                    if not self.orders_match(main_order, mirror_order):
                        await self.cancel_order_safe(symbol, mirror_order['orderId'])
                        await self.create_mirror_order(main_order, mirror_position)
                else:
                    # Create new mirror order
                    await self.create_mirror_order(main_order, mirror_position)

            return True

        except Exception as e:
            logger.error(f"Error syncing {order_type} orders for {symbol}: {e}")
            return False

    def orders_match(self, main_order: Dict, mirror_order: Dict) -> bool:
        """Check if orders match within tolerance"""
        try:
            # Compare trigger prices
            main_trigger = Decimal(str(main_order.get('triggerPrice', '0')))
            mirror_trigger = Decimal(str(mirror_order.get('triggerPrice', '0')))

            if main_trigger != mirror_trigger:
                return False

            # Compare quantities within tolerance
            main_qty = Decimal(str(main_order.get('qty', '0')))
            mirror_qty = Decimal(str(mirror_order.get('qty', '0')))

            qty_diff = abs(main_qty - mirror_qty)
            tolerance = main_qty * POSITION_SIZE_TOLERANCE

            return qty_diff <= tolerance

        except Exception as e:
            logger.error(f"Error comparing orders: {e}")
            return False

    async def create_mirror_order(self, main_order: Dict, mirror_position: Dict) -> bool:
        """Create mirror order based on main order"""
        try:
            order_params = {
                'category': 'linear',
                'symbol': main_order['symbol'],
                'side': main_order['side'],
                'orderType': main_order['orderType'],
                'qty': main_order['qty'],
                'triggerPrice': main_order['triggerPrice'],
                'triggerDirection': main_order.get('triggerDirection', 1),
                'orderLinkId': f"{self.account_prefix}_Enhanced_{main_order['symbol']}_{main_order['orderType']}_{int(time.time()*1000)}",
                'positionIdx': mirror_position.get('positionIdx', 0),
                'reduceOnly': True
            }

            # Add price for limit orders
            if main_order.get('price'):
                order_params['price'] = main_order['price']
                order_params['orderType'] = 'Limit'
            else:
                order_params['orderType'] = 'Market'

            result = await self.place_order_safe(order_params)
            return result is not None

        except Exception as e:
            logger.error(f"Error creating mirror order: {e}")
            return False

    async def get_active_orders(self, symbol: str, account_type: str) -> List[Dict]:
        """Get active orders with error handling"""
        try:
            response = self.client.get_open_orders(
                category="linear",
                symbol=symbol
            )

            if response['retCode'] == 0:
                return response['result']['list']
            else:
                logger.error(f"Error getting orders: {response.get('retMsg')}")
                return []

        except Exception as e:
            logger.error(f"Error fetching active orders for {symbol}: {e}")
            return []

    def create_dashboard_monitor_entry(self, symbol: str, side: str, chat_id: int) -> bool:
        """Create dashboard monitor entry for tracking"""
        try:
            # Load current pickle data
            pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'

            if os.path.exists(pickle_file):
                with open(pickle_file, 'rb') as f:
                    data = pickle.load(f)
            else:
                data = {'bot_data': {}, 'user_data': {}}

            # Ensure structure exists
            if 'monitor_tasks' not in data['bot_data']:
                data['bot_data']['monitor_tasks'] = {}

            # Create monitor key
            monitor_key = f"{chat_id}_{symbol}_enhanced_{self.account_prefix.lower()}"

            # Add monitor entry
            data['bot_data']['monitor_tasks'][monitor_key] = {
                'symbol': symbol,
                'side': side,
                'approach': 'enhanced',
                'account_type': self.account_prefix.lower(),
                'chat_id': chat_id,
                'created_at': datetime.now().isoformat(),
                'status': 'active'
            }

            # Save updated data
            with open(pickle_file, 'wb') as f:
                pickle.dump(data, f)

            logger.info(f"Created dashboard monitor entry: {monitor_key}")
            return True

        except Exception as e:
            logger.error(f"Error creating dashboard monitor entry: {e}")
            return False

# Export the enhanced class
__all__ = ['MirrorEnhancedTPSL']
