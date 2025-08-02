#!/usr/bin/env python3
"""
Position identifier module - Determines if positions are bot-created or external
"""
import logging
from typing import Dict, List, Optional, Set
import os

# Import after path fix
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.constants import BOT_ORDER_PREFIXES, MANAGE_EXTERNAL_POSITIONS

logger = logging.getLogger(__name__)

class PositionIdentifier:
    """Identifies whether positions were created by the bot or externally"""

    def __init__(self):
        self.bot_positions: Set[str] = set()  # Set of symbol_side combinations
        self.manage_external = os.getenv('MANAGE_EXTERNAL_POSITIONS', str(MANAGE_EXTERNAL_POSITIONS)).lower() == 'true'

    def is_bot_position(self, position: Dict, orders: List[Dict]) -> bool:
        """
        Determine if a position was created by the bot

        Args:
            position: Position data from Bybit
            orders: All orders for this symbol

        Returns:
            True if position was created by bot, False if external
        """
        # If configured to manage all positions, always return True
        if self.manage_external:
            logger.warning(
                "⚠️ MANAGE_EXTERNAL_POSITIONS is True - treating all positions as bot positions. "
                "Set to False to protect external trades."
            )
            return True

        symbol = position.get('symbol', '')
        side = position.get('side', '')
        position_key = f"{symbol}_{side}"

        # Check cached bot positions
        if position_key in self.bot_positions:
            return True

        # Check if position has bot-created orders
        has_bot_orders = self._has_bot_orders(orders)

        if has_bot_orders:
            # Cache for future checks
            self.bot_positions.add(position_key)
            logger.info(f"✅ Identified {symbol} {side} as BOT position (has bot orders)")
            return True

        # Check for any reduce-only orders with bot prefixes (TP/SL)
        reduce_only_bot_orders = any(
            order.get('reduceOnly', False) and self._has_bot_prefix(order.get('orderLinkId', ''))
            for order in orders
        )

        if reduce_only_bot_orders:
            self.bot_positions.add(position_key)
            logger.info(f"✅ Identified {symbol} {side} as BOT position (has bot TP/SL orders)")
            return True

        logger.info(f"🛡️ Identified {symbol} {side} as EXTERNAL position - will not manage")
        return False

    def _has_bot_orders(self, orders: List[Dict]) -> bool:
        """
        Check if any orders have bot-created identifiers

        Args:
            orders: List of orders to check

        Returns:
            True if any order has bot prefix
        """
        for order in orders:
            if self._has_bot_prefix(order.get('orderLinkId', '')):
                return True

        return False

    def _has_bot_prefix(self, order_link_id: str) -> bool:
        """Check if orderLinkId has any bot prefix"""
        if not order_link_id:
            return False

        for prefix in BOT_ORDER_PREFIXES:
            if order_link_id.startswith(prefix):
                return True

        return False

    def identify_bot_positions(self, positions: List[Dict], all_orders: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Separate positions into bot and external categories

        Args:
            positions: All active positions
            all_orders: All open orders

        Returns:
            Dict with 'bot' and 'external' position lists
        """
        # Group orders by symbol for efficiency
        orders_by_symbol = {}
        for order in all_orders:
            symbol = order.get('symbol')
            if symbol not in orders_by_symbol:
                orders_by_symbol[symbol] = []
            orders_by_symbol[symbol].append(order)

        bot_positions = []
        external_positions = []

        for position in positions:
            symbol = position.get('symbol')
            symbol_orders = orders_by_symbol.get(symbol, [])

            if self.is_bot_position(position, symbol_orders):
                bot_positions.append(position)
            else:
                external_positions.append(position)

        logger.info(f"📊 Position identification: {len(bot_positions)} bot, {len(external_positions)} external")

        return {
            'bot': bot_positions,
            'external': external_positions
        }

    def mark_position_as_bot(self, symbol: str, side: str):
        """
        Manually mark a position as bot-created
        Used when bot creates a new position
        """
        position_key = f"{symbol}_{side}"
        self.bot_positions.add(position_key)
        logger.info(f"📌 Marked {symbol} {side} as bot position")

    def get_bot_order_link_id(self, order_type: str, symbol: str, additional_info: str = "") -> str:
        """
        Generate a bot-specific orderLinkId

        Args:
            order_type: Type of order (e.g., "LIMIT", "TP", "SL")
            symbol: Trading symbol
            additional_info: Any additional info to include

        Returns:
            Bot-prefixed orderLinkId
        """
        import time
        timestamp = str(int(time.time() * 1000))[-8:]  # Last 8 digits of timestamp

        if additional_info:
            return f"{BOT_PREFIX}{order_type}_{symbol}_{additional_info}_{timestamp}"
        else:
            return f"{BOT_PREFIX}{order_type}_{symbol}_{timestamp}"


# Singleton instance
position_identifier = PositionIdentifier()


# Convenience functions
def is_bot_position(position: Dict, orders: List[Dict]) -> bool:
    """Check if position is bot-created"""
    return position_identifier.is_bot_position(position, orders)


def identify_bot_positions(positions: List[Dict], all_orders: List[Dict]) -> Dict[str, List[Dict]]:
    """Separate bot and external positions"""
    return position_identifier.identify_bot_positions(positions, all_orders)


def mark_position_as_bot(symbol: str, side: str):
    """Mark position as bot-created"""
    position_identifier.mark_position_as_bot(symbol, side)


def get_bot_order_link_id(order_type: str, symbol: str, additional_info: str = "") -> str:
    """Generate bot orderLinkId"""
    return position_identifier.get_bot_order_link_id(order_type, symbol, additional_info)


if __name__ == "__main__":
    # Test the identifier
    import asyncio
    from clients.bybit_helpers import get_all_positions, get_all_open_orders

    async def test():
        positions = await get_all_positions()
        orders = await get_all_open_orders()

        active_positions = [p for p in positions if float(p.get('size', 0)) > 0]

        results = identify_bot_positions(active_positions, orders)

        print(f"\n=== Position Identification Test ===")
        print(f"Total positions: {len(active_positions)}")
        print(f"Bot positions: {len(results['bot'])}")
        print(f"External positions: {len(results['external'])}")

        print("\nBot positions:")
        for pos in results['bot']:
            print(f"  - {pos.get('symbol')} {pos.get('side')}")

        print("\nExternal positions:")
        for pos in results['external']:
            print(f"  - {pos.get('symbol')} {pos.get('side')}")

    asyncio.run(test())