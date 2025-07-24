#!/usr/bin/env python3
"""
Automatic TP/SL verification system
Ensures all positions have proper risk management orders
"""
import asyncio
import logging
from typing import Dict, List, Tuple, Optional
from decimal import Decimal
from datetime import datetime, timedelta

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_helpers import get_all_positions, get_all_open_orders, place_order_with_retry
from utils.helpers import value_adjusted_to_step, safe_decimal_conversion
from utils.position_identifier import identify_bot_positions, get_bot_order_link_id

logger = logging.getLogger(__name__)

class TPSLVerifier:
    """Verify and fix missing TP/SL orders for positions"""

    def __init__(self):
        self.last_check = {}
        self.check_interval = 300  # 5 minutes

    async def verify_all_positions(self) -> Dict[str, Dict]:
        """
        Verify all BOT positions have proper TP/SL orders
        Returns a dict with verification results
        """
        try:
            # Get all positions and orders
            positions = await get_all_positions()
            all_orders = await get_all_open_orders()

            # Filter active positions
            active_positions = [p for p in positions if float(p.get('size', 0)) > 0]

            # Identify bot vs external positions
            position_results = identify_bot_positions(active_positions, all_orders)
            bot_positions = position_results['bot']
            external_positions = position_results['external']

            logger.info(f"🔍 Verifying {len(bot_positions)} bot positions (ignoring {len(external_positions)} external)")

            # Only verify bot positions
            active_positions = bot_positions

            # Group orders by symbol
            orders_by_symbol = {}
            for order in all_orders:
                symbol = order.get('symbol')
                if symbol not in orders_by_symbol:
                    orders_by_symbol[symbol] = []
                orders_by_symbol[symbol].append(order)

            # Verification results
            results = {
                'total_positions': len(active_positions),
                'bot_positions': len(bot_positions),
                'external_positions': len(external_positions),
                'verified': 0,
                'missing_tp': [],
                'missing_sl': [],
                'fixed': [],
                'errors': []
            }

            # Check each position
            for pos in active_positions:
                symbol = pos.get('symbol')
                side = pos.get('side')
                size = float(pos.get('size', 0))

                # Get orders for this symbol
                symbol_orders = orders_by_symbol.get(symbol, [])

                # Identify TP/SL orders
                tp_orders, sl_orders = self._identify_tp_sl_orders(symbol_orders, side)

                has_tp = len(tp_orders) > 0
                has_sl = len(sl_orders) > 0

                if has_tp and has_sl:
                    results['verified'] += 1
                else:
                    if not has_tp:
                        results['missing_tp'].append({
                            'symbol': symbol,
                            'side': side,
                            'size': size,
                            'position': pos
                        })
                    if not has_sl:
                        results['missing_sl'].append({
                            'symbol': symbol,
                            'side': side,
                            'size': size,
                            'position': pos
                        })

            return results

        except Exception as e:
            logger.error(f"Error verifying positions: {e}")
            return {
                'error': str(e),
                'total_positions': 0,
                'verified': 0
            }

    def _identify_tp_sl_orders(self, orders: List[Dict], position_side: str) -> Tuple[List[Dict], List[Dict]]:
        """
        Identify TP and SL orders from a list of orders
        Uses multiple detection methods
        """
        tp_orders = []
        sl_orders = []

        for order in orders:
            order_side = order.get('side')
            stop_order_type = order.get('stopOrderType', '')
            trigger_direction = order.get('triggerDirection', 0)
            trigger_price_str = order.get('triggerPrice', '')
            trigger_price = float(trigger_price_str) if trigger_price_str else 0
            reduce_only = order.get('reduceOnly', False)
            order_link_id = order.get('orderLinkId', '')

            # Skip non-triggered orders
            if not trigger_price or not reduce_only:
                continue

            # Method 1: Check stopOrderType field
            if stop_order_type:
                if 'TakeProfit' in stop_order_type:
                    tp_orders.append(order)
                elif 'StopLoss' in stop_order_type:
                    sl_orders.append(order)
                elif stop_order_type == 'Stop':
                    # Use trigger direction to determine type
                    if trigger_direction == 1:  # Price rises
                        if position_side == 'Buy' and order_side == 'Sell':
                            tp_orders.append(order)
                        elif position_side == 'Sell' and order_side == 'Buy':
                            sl_orders.append(order)
                    elif trigger_direction == 2:  # Price falls
                        if position_side == 'Buy' and order_side == 'Sell':
                            sl_orders.append(order)
                        elif position_side == 'Sell' and order_side == 'Buy':
                            tp_orders.append(order)
                continue

            # Method 2: Check orderLinkId patterns
            order_link_upper = order_link_id.upper()
            if any(pattern in order_link_upper for pattern in ['_TP', 'TAKE_PROFIT', 'TAKEPROFIT']):
                tp_orders.append(order)
            elif any(pattern in order_link_upper for pattern in ['_SL', 'STOP_LOSS', 'STOPLOSS']):
                sl_orders.append(order)

        return tp_orders, sl_orders

    async def fix_missing_orders(self, missing_tp: List[Dict], missing_sl: List[Dict]) -> Dict[str, List]:
        """
        Create missing TP/SL orders
        """
        fixed = {
            'tp_created': [],
            'sl_created': [],
            'errors': []
        }

        # Fix missing TP orders
        for item in missing_tp:
            try:
                result = await self._create_default_tp_orders(item['position'])
                if result:
                    fixed['tp_created'].append({
                        'symbol': item['symbol'],
                        'orders': result
                    })
            except Exception as e:
                fixed['errors'].append({
                    'symbol': item['symbol'],
                    'type': 'TP',
                    'error': str(e)
                })

        # Fix missing SL orders
        for item in missing_sl:
            try:
                result = await self._create_default_sl_order(item['position'])
                if result:
                    fixed['sl_created'].append({
                        'symbol': item['symbol'],
                        'order': result
                    })
            except Exception as e:
                fixed['errors'].append({
                    'symbol': item['symbol'],
                    'type': 'SL',
                    'error': str(e)
                })

        return fixed

    async def _create_default_tp_orders(self, position: Dict) -> Optional[List[str]]:
        """
        Create default TP orders based on position
        Uses conservative approach by default
        """
        symbol = position.get('symbol')
        side = position.get('side')
        size = float(position.get('size', 0))
        avg_price = float(position.get('avgPrice', 0))
        position_idx = int(position.get('positionIdx', 0))

        # Calculate TP prices (conservative approach)
        if side == 'Buy':
            tp1_price = avg_price * 1.065  # 6.5%
            tp2_price = avg_price * 1.075  # 7.5%
            tp3_price = avg_price * 1.085  # 8.5%
            tp4_price = avg_price * 1.105  # 10.5%
        else:
            tp1_price = avg_price * 0.935
            tp2_price = avg_price * 0.925
            tp3_price = avg_price * 0.915
            tp4_price = avg_price * 0.895

        # Get tick size (simplified - should be fetched from instrument info)
        tick_size = self._estimate_tick_size(avg_price)

        # Adjust prices
        tp_prices = [
            float(value_adjusted_to_step(Decimal(str(tp1_price)), tick_size)),
            float(value_adjusted_to_step(Decimal(str(tp2_price)), tick_size)),
            float(value_adjusted_to_step(Decimal(str(tp3_price)), tick_size)),
            float(value_adjusted_to_step(Decimal(str(tp4_price)), tick_size))
        ]

        # Calculate quantities
        quantities = [
            int(size * 0.7),   # TP1: 70%
            int(size * 0.1),   # TP2: 10%
            int(size * 0.1),   # TP3: 10%
            size - int(size * 0.9)  # TP4: remaining
        ]

        created_orders = []
        timestamp = datetime.now().strftime('%H%M%S')

        for i, (price, qty) in enumerate(zip(tp_prices, quantities)):
            if qty <= 0:
                continue

            try:
                result = await place_order_with_retry(
                    symbol=symbol,
                    side="Sell" if side == "Buy" else "Buy",
                    order_type="Market",
                    qty=str(qty),
                    trigger_price=str(price),
                    position_idx=position_idx,
                    reduce_only=True,
                    order_link_id=get_bot_order_link_id(f"TP{i+1}", symbol, timestamp)
                )

                if result and result.get('retCode') == 0:
                    order_id = result.get('result', {}).get('orderId')
                    created_orders.append(order_id)
                    logger.info(f"✅ Created TP{i+1} for {symbol}: {qty} @ {price}")

            except Exception as e:
                logger.error(f"Error creating TP{i+1} for {symbol}: {e}")

        return created_orders if created_orders else None

    async def _create_default_sl_order(self, position: Dict) -> Optional[str]:
        """
        Create default SL order based on position
        """
        symbol = position.get('symbol')
        side = position.get('side')
        size = float(position.get('size', 0))
        avg_price = float(position.get('avgPrice', 0))
        position_idx = int(position.get('positionIdx', 0))

        # Calculate SL price (6% loss)
        if side == 'Buy':
            sl_price = avg_price * 0.94
        else:
            sl_price = avg_price * 1.06

        # Get tick size
        tick_size = self._estimate_tick_size(avg_price)
        sl_price = float(value_adjusted_to_step(Decimal(str(sl_price)), tick_size))

        timestamp = datetime.now().strftime('%H%M%S')

        try:
            result = await place_order_with_retry(
                symbol=symbol,
                side="Sell" if side == "Buy" else "Buy",
                order_type="Market",
                qty=str(size),
                trigger_price=str(sl_price),
                position_idx=position_idx,
                reduce_only=True,
                order_link_id=get_bot_order_link_id("SL", symbol, timestamp)
            )

            if result and result.get('retCode') == 0:
                order_id = result.get('result', {}).get('orderId')
                logger.info(f"✅ Created SL for {symbol}: {size} @ {sl_price}")
                return order_id

        except Exception as e:
            logger.error(f"Error creating SL for {symbol}: {e}")

        return None

    def _estimate_tick_size(self, price: float) -> Decimal:
        """
        Estimate tick size based on price
        This is a simplified version - should use actual instrument info
        """
        if price < 0.01:
            return Decimal("0.000001")
        elif price < 0.1:
            return Decimal("0.00001")
        elif price < 1:
            return Decimal("0.0001")
        elif price < 10:
            return Decimal("0.001")
        elif price < 100:
            return Decimal("0.01")
        elif price < 1000:
            return Decimal("0.1")
        else:
            return Decimal("1")

    async def run_periodic_verification(self, interval_minutes: int = 5):
        """
        Run verification periodically
        """
        while True:
            try:
                logger.info("🔍 Running TP/SL verification...")

                # Verify positions
                results = await self.verify_all_positions()

                # Log results
                logger.info(f"✅ Verified: {results['verified']}/{results['total_positions']} positions")

                if results['missing_tp'] or results['missing_sl']:
                    logger.warning(f"⚠️ Missing TP: {len(results['missing_tp'])}, Missing SL: {len(results['missing_sl'])}")

                    # Auto-fix if configured
                    if self.should_auto_fix():
                        fix_results = await self.fix_missing_orders(
                            results['missing_tp'],
                            results['missing_sl']
                        )
                        logger.info(f"🔧 Fixed: {len(fix_results['tp_created'])} TP, {len(fix_results['sl_created'])} SL")

                # Wait for next check
                await asyncio.sleep(interval_minutes * 60)

            except Exception as e:
                logger.error(f"Error in periodic verification: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error

    def should_auto_fix(self) -> bool:
        """
        Determine if orders should be auto-fixed
        Can be configured via environment variable
        """
        import os
        return os.getenv('AUTO_FIX_MISSING_ORDERS', 'false').lower() == 'true'


# Singleton instance
tp_sl_verifier = TPSLVerifier()


async def verify_position_orders(symbol: str) -> Dict:
    """
    Verify a specific position has proper TP/SL orders
    """
    return await tp_sl_verifier.verify_all_positions()


async def start_verification_service():
    """
    Start the background verification service
    """
    logger.info("🚀 Starting TP/SL verification service...")
    await tp_sl_verifier.run_periodic_verification()


if __name__ == "__main__":
    # Test the verifier
    async def test():
        verifier = TPSLVerifier()
        results = await verifier.verify_all_positions()

        print("\n=== TP/SL Verification Results ===")
        print(f"Total active positions: {results.get('bot_positions', 0) + results.get('external_positions', 0)}")
        print(f"Bot positions: {results.get('bot_positions', 0)}")
        print(f"External positions (ignored): {results.get('external_positions', 0)}")
        print(f"Verified bot positions (has both TP & SL): {results['verified']}")
        print(f"Bot positions missing TP: {len(results.get('missing_tp', []))}")
        print(f"Bot positions missing SL: {len(results.get('missing_sl', []))}")

        if results.get('missing_tp'):
            print("\nPositions missing TP:")
            for item in results['missing_tp']:
                print(f"  - {item['symbol']} ({item['side']})")

        if results.get('missing_sl'):
            print("\nPositions missing SL:")
            for item in results['missing_sl']:
                print(f"  - {item['symbol']} ({item['side']})")

    asyncio.run(test())