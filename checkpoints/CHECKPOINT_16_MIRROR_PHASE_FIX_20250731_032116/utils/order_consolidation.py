#!/usr/bin/env python3
"""
Order Consolidation System
Prevents order accumulation and enables smart consolidation
"""

import asyncio
import logging
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from clients.bybit_client import bybit_client
from clients.bybit_helpers import api_call_with_retry

logger = logging.getLogger(__name__)

class OrderConsolidator:
    """Handles order consolidation and conflict resolution"""

    def __init__(self):
        self.approach_patterns = {
            'conservative': ['BOT_CONS', 'CONS_', 'BOT_FAST', 'FAST_']  # All patterns now map to conservative
        }

    async def detect_existing_approach(self, symbol: str, side: str) -> Optional[str]:
        """Detect existing trading approach for symbol/side"""
        try:
            # Get all open orders for the symbol using proper API parameters with retry
            response = await api_call_with_retry(
                lambda: bybit_client.get_open_orders(
                    category="linear",
                    symbol=symbol,
                    limit=50
                ),
                timeout=30
            )

            if not response or response.get("retCode") != 0:
                logger.debug(f"No orders found or API error for {symbol}: {response}")
                return None

            orders = response.get("result", {}).get("list", [])
            if not orders:
                return None

            approaches_found = set()

            for order in orders:
                order_link_id = order.get('orderLinkId', '')

                # Check for Conservative approach (including legacy fast patterns)
                if any(pattern in order_link_id for pattern in self.approach_patterns['conservative']):
                    approaches_found.add('conservative')

            if len(approaches_found) > 1:
                return 'mixed'  # Both approaches present
            elif approaches_found:
                return approaches_found.pop()
            else:
                return 'unknown'  # Orders exist but approach unclear

        except Exception as e:
            logger.error(f"Error detecting existing approach for {symbol}: {e}")
            return None

    async def get_orders_by_approach(self, symbol: str, approach: str) -> List[Dict]:
        """Get orders filtered by trading approach"""
        try:
            # FIXED: Added category parameter
            response = await api_call_with_retry(
                lambda: bybit_client.get_open_orders(
                    category="linear",
                    symbol=symbol
                ),
                timeout=30
            )

            if not response or response.get("retCode") != 0:
                logger.debug(f"No orders found or API error for {symbol}: {response}")
                return []

            all_orders = response.get("result", {}).get("list", [])
            if not all_orders:
                return []

            approach_orders = []
            patterns = self.approach_patterns.get(approach, [])

            for order in all_orders:
                order_link_id = order.get('orderLinkId', '')

                if any(pattern in order_link_id for pattern in patterns):
                    approach_orders.append(order)

            return approach_orders

        except Exception as e:
            logger.error(f"Error getting {approach} orders for {symbol}: {e}")
            return []

    async def get_orders_at_price(self, symbol: str, price: float, tolerance: float = 0.001) -> List[Dict]:
        """Get orders at specific price level (with tolerance)"""
        try:
            # FIXED: Added category parameter
            response = await api_call_with_retry(
                lambda: bybit_client.get_open_orders(
                    category="linear",
                    symbol=symbol
                ),
                timeout=30
            )

            if not response or response.get("retCode") != 0:
                logger.debug(f"No orders found or API error for {symbol}: {response}")
                return []

            all_orders = response.get("result", {}).get("list", [])
            if not all_orders:
                return []

            matching_orders = []

            for order in all_orders:
                order_price = float(order.get('triggerPrice', order.get('price', 0)))

                if abs(order_price - price) <= tolerance:
                    matching_orders.append(order)

            return matching_orders

        except Exception as e:
            logger.error(f"Error getting orders at price {price} for {symbol}: {e}")
            return []

    async def cleanup_approach_orders(self, symbol: str, approach: str) -> int:
        """Cancel all orders for a specific approach"""
        try:
            approach_orders = await self.get_orders_by_approach(symbol, approach)

            if not approach_orders:
                logger.info(f"No {approach} orders found for {symbol}")
                return 0

            canceled_count = 0

            for order in approach_orders:
                try:
                    order_id = order['orderId']
                    order_link_id = order.get('orderLinkId', 'N/A')

                    # FIXED: Added category parameter and proper API call
                    response = await api_call_with_retry(
                        lambda: bybit_client.cancel_order(
                            category="linear",
                            symbol=symbol,
                            orderId=order_id
                        ),
                        timeout=30
                    )
                    canceled_count += 1

                    logger.info(f"Canceled {approach} order: {order_link_id}")

                    # Small delay between cancellations
                    await asyncio.sleep(0.2)

                except Exception as e:
                    logger.error(f"Failed to cancel order {order.get('orderId')}: {e}")

            logger.info(f"Canceled {canceled_count}/{len(approach_orders)} {approach} orders for {symbol}")
            return canceled_count

        except Exception as e:
            logger.error(f"Error cleaning up {approach} orders for {symbol}: {e}")
            return 0

    async def cleanup_all_orders(self, symbol: str, side: str) -> int:
        """Cancel all orders for symbol/side regardless of approach"""
        try:
            # FIXED: Added category parameter
            response = await api_call_with_retry(
                lambda: bybit_client.get_open_orders(
                    category="linear",
                    symbol=symbol
                ),
                timeout=30
            )

            if not response or response.get("retCode") != 0:
                logger.debug(f"No orders found or API error for {symbol}: {response}")
                return []

            all_orders = response.get("result", {}).get("list", [])
            if not all_orders:
                return 0

            # Filter orders by side (TP/SL are opposite side of position)
            opposite_side = "Buy" if side == "Sell" else "Sell"
            relevant_orders = [order for order in all_orders if order['side'] == opposite_side]

            canceled_count = 0

            for order in relevant_orders:
                try:
                    order_id = order['orderId']
                    order_link_id = order.get('orderLinkId', 'N/A')

                    # FIXED: Added category parameter and proper API call
                    response = await api_call_with_retry(
                        lambda: bybit_client.cancel_order(
                            category="linear",
                            symbol=symbol,
                            orderId=order_id
                        ),
                        timeout=30
                    )
                    canceled_count += 1

                    logger.info(f"Canceled order: {order_link_id}")
                    await asyncio.sleep(0.2)

                except Exception as e:
                    logger.error(f"Failed to cancel order {order.get('orderId')}: {e}")

            logger.info(f"Canceled {canceled_count} orders for {symbol} {side}")
            return canceled_count

        except Exception as e:
            logger.error(f"Error cleaning up all orders for {symbol}: {e}")
            return 0

    async def check_approach_conflicts(self, symbol: str, side: str, new_approach: str) -> Dict[str, any]:
        """Check for conflicts between trading approaches"""
        try:
            existing_approach = await self.detect_existing_approach(symbol, side)

            if not existing_approach:
                return {
                    "conflict": False,
                    "existing_approach": None,
                    "recommendation": "proceed"
                }

            if existing_approach == new_approach:
                return {
                    "conflict": False,
                    "existing_approach": existing_approach,
                    "recommendation": "replace_same_approach"
                }

            if existing_approach == 'mixed':
                return {
                    "conflict": True,
                    "existing_approach": "mixed",
                    "recommendation": "cleanup_all"
                }

            # Different approach detected
            return {
                "conflict": True,
                "existing_approach": existing_approach,
                "recommendation": f"replace_{existing_approach}_with_{new_approach}"
            }

        except Exception as e:
            logger.error(f"Error checking approach conflicts for {symbol}: {e}")
            return {
                "conflict": False,
                "existing_approach": None,
                "recommendation": "proceed",
                "error": str(e)
            }

    async def consolidate_orders_at_price(self, symbol: str, side: str, price: float,
                                        new_qty: float, approach: str, order_type: str = "Market") -> Optional[str]:
        """Consolidate multiple orders at same price level"""
        try:
            # Get existing orders at this price
            existing_orders = await self.get_orders_at_price(symbol, price)

            if existing_orders:
                logger.info(f"Found {len(existing_orders)} existing orders at ${price} for {symbol}")

                # Calculate total quantity
                existing_qty = sum(float(order['qty']) for order in existing_orders)
                total_qty = existing_qty + new_qty

                # Cancel existing orders
                for order in existing_orders:
                    try:
                        # FIXED: Added category parameter and proper API call
                        response = await api_call_with_retry(
                            lambda: bybit_client.cancel_order(
                                category="linear",
                                symbol=symbol,
                                orderId=order['orderId']
                            ),
                            timeout=30
                        )
                        logger.info(f"Canceled existing order: {order.get('orderLinkId')}")
                        await asyncio.sleep(0.2)
                    except Exception as e:
                        logger.error(f"Failed to cancel existing order: {e}")

                # Wait for cancellations to process
                await asyncio.sleep(1)

                logger.info(f"Consolidating: {existing_qty} + {new_qty} = {total_qty} at ${price}")
                new_qty = total_qty

            # Place consolidated order
            order_link_id = f"BOT_{approach.upper()}_{symbol}_{order_type}_{int(price*1000)}"

            # FIXED: Added category parameter and proper API call
            new_order_response = await api_call_with_retry(
                lambda: bybit_client.place_order(
                    category="linear",
                    symbol=symbol,
                    side=side,
                    orderType=order_type,
                    qty=str(new_qty),
                    triggerPrice=str(price) if order_type == "Market" else None,
                    price=str(price) if order_type == "Limit" else None,
                    orderLinkId=order_link_id,
                    reduceOnly=True
                ),
                timeout=30
            )

            if new_order_response and new_order_response.get("retCode") == 0:
                new_order = new_order_response.get("result", {})
            else:
                logger.error(f"Failed to place consolidated order: {new_order_response}")
                return None

            logger.info(f"Placed consolidated {approach} order: {new_qty} @ ${price}")
            return new_order.get('orderId')

        except Exception as e:
            logger.error(f"Error consolidating orders at ${price} for {symbol}: {e}")
            return None

# Global consolidator instance
consolidator = OrderConsolidator()

# Convenience functions
async def detect_existing_approach(symbol: str, side: str) -> Optional[str]:
    """Detect existing trading approach for symbol/side"""
    return await consolidator.detect_existing_approach(symbol, side)

async def cleanup_approach_orders(symbol: str, approach: str) -> int:
    """Cancel all orders for a specific approach"""
    return await consolidator.cleanup_approach_orders(symbol, approach)

async def check_approach_conflicts(symbol: str, side: str, new_approach: str) -> Dict[str, any]:
    """Check for conflicts between trading approaches"""
    return await consolidator.check_approach_conflicts(symbol, side, new_approach)

async def cleanup_all_orders(symbol: str, side: str) -> int:
    """Cancel all orders for symbol/side"""
    return await consolidator.cleanup_all_orders(symbol, side)