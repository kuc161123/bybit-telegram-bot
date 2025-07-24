#!/usr/bin/env python3
"""
Trade Verifier - Validates current positions against logged trade history
Detects discrepancies and provides correction suggestions
"""

import logging
from typing import Dict, List, Tuple, Optional
from decimal import Decimal
import asyncio

from utils.enhanced_trade_logger import trade_logger
from clients.bybit_helpers import get_all_positions, get_all_open_orders
from config.constants import CONSERVATIVE_TP_PERCENTAGES

logger = logging.getLogger(__name__)

class TradeVerifier:
    """Verify positions match logged trade history"""

    def __init__(self):
        self.logger = logger

    async def verify_position_quantities(self, symbol: str, side: str,
                                       position: Dict, orders: List[Dict]) -> Dict:
        """Verify position quantities match expected values from trade history"""
        try:
            # Get original trade data
            original_data = await trade_logger.get_original_trigger_prices(symbol, side)
            if not original_data:
                return {
                    "verified": False,
                    "reason": "No trade history found",
                    "discrepancies": []
                }

            approach = original_data["approach"]
            position_size = Decimal(str(position.get('size', 0)))
            discrepancies = []

            # Filter orders for this position
            position_orders = [
                o for o in orders
                if o['symbol'] == symbol and
                   o.get('positionIdx', 0) == (1 if side == 'Buy' else 2)
            ]

            # Separate TP and SL orders
            tp_orders = [o for o in position_orders if o.get('side') != side]
            sl_orders = [o for o in position_orders if o.get('triggerPrice') and o.get('side') == side]

            # Check if this is a dual-approach position (5 TPs = 1 Fast + 4 Conservative)
            is_dual_approach = len(tp_orders) == 5

            if is_dual_approach:
                # Log dual-approach detection
                logger.info(f"Detected dual-approach position for {symbol} with 5 TP orders")

                # For dual-approach, verify based on the requested approach
                # The caller should pass filtered orders for the specific approach
                if approach == "Fast":
                    expected_discrepancies = self._verify_fast_approach(
                        position_size, tp_orders, sl_orders
                    )
                else:  # Conservative
                    expected_discrepancies = self._verify_conservative_approach(
                        position_size, tp_orders, sl_orders
                    )

                # Add context about dual-approach
                if expected_discrepancies:
                    expected_discrepancies.append({
                        "type": "info",
                        "message": f"Note: This is a dual-approach position (Fast + Conservative)"
                    })
            else:
                # Single approach verification
                if approach == "Fast":
                    expected_discrepancies = self._verify_fast_approach(
                        position_size, tp_orders, sl_orders
                    )
                else:  # Conservative
                    expected_discrepancies = self._verify_conservative_approach(
                        position_size, tp_orders, sl_orders
                    )

            discrepancies.extend(expected_discrepancies)

            # Check trigger prices match
            price_discrepancies = await self._verify_trigger_prices(
                original_data, tp_orders, sl_orders
            )
            discrepancies.extend(price_discrepancies)

            return {
                "verified": len(discrepancies) == 0,
                "approach": approach,
                "position_size": str(position_size),
                "discrepancies": discrepancies,
                "original_data": original_data
            }

        except Exception as e:
            logger.error(f"Error verifying position quantities: {e}")
            return {
                "verified": False,
                "reason": f"Verification error: {str(e)}",
                "discrepancies": []
            }

    def _verify_fast_approach(self, position_size: Decimal,
                            tp_orders: List[Dict], sl_orders: List[Dict]) -> List[Dict]:
        """Verify Fast approach quantities (100% for both TP and SL)"""
        discrepancies = []

        # Filter only Fast-specific TP orders
        fast_tp_orders = [o for o in tp_orders if any(p in o.get('orderLinkId', '') for p in ['FAST_', '_FAST_', 'BOT_FAST_'])]

        # If we have Fast-specific orders, use those; otherwise use all TPs
        tp_orders_to_check = fast_tp_orders if fast_tp_orders else tp_orders

        # Should have exactly 1 TP with 100%
        if len(tp_orders_to_check) != 1:
            discrepancies.append({
                "type": "tp_count",
                "expected": 1,
                "actual": len(tp_orders_to_check),
                "message": f"Fast approach should have 1 TP order, found {len(tp_orders_to_check)}"
            })
        else:
            tp_qty = Decimal(str(tp_orders_to_check[0].get('qty', 0)))
            # For dual-approach positions, Fast TP might not be 100% of total position
            # So we check if it's a reasonable amount instead
            if tp_qty > position_size:
                discrepancies.append({
                    "type": "tp_quantity",
                    "expected": f"<= {position_size}",
                    "actual": str(tp_qty),
                    "message": f"Fast TP quantity ({tp_qty}) exceeds position size ({position_size})"
                })

        # Should have exactly 1 SL with 100%
        if len(sl_orders) != 1:
            discrepancies.append({
                "type": "sl_count",
                "expected": 1,
                "actual": len(sl_orders),
                "message": f"Should have 1 SL order, found {len(sl_orders)}"
            })
        else:
            sl_qty = Decimal(str(sl_orders[0].get('qty', 0)))
            # FIXED: Allow tolerance for SL quantity as well
            sl_tolerance = max(position_size * Decimal('0.005'), Decimal('0.001'))  # 0.5% tolerance
            if abs(sl_qty - position_size) > sl_tolerance:
                discrepancies.append({
                    "type": "sl_quantity",
                    "expected": str(position_size),
                    "actual": str(sl_qty),
                    "message": f"SL quantity should be 100% ({position_size}), found {sl_qty}"
                })

        return discrepancies

    def _verify_conservative_approach(self, position_size: Decimal,
                                    tp_orders: List[Dict], sl_orders: List[Dict]) -> List[Dict]:
        """Verify Conservative approach quantities (85%, 5%, 5%, 5%)"""
        discrepancies = []

        # Filter only Conservative-specific TP orders
        cons_tp_orders = [o for o in tp_orders if any(p in o.get('orderLinkId', '') for p in ['CONS_', 'TP1_', 'TP2_', 'TP3_', 'TP4_', 'BOT_CONS_'])]

        # If we have Conservative-specific orders, use those; otherwise use all TPs
        tp_orders_to_check = cons_tp_orders if cons_tp_orders else tp_orders

        # Should have exactly 4 TPs
        if len(tp_orders_to_check) != 4:
            discrepancies.append({
                "type": "tp_count",
                "expected": 4,
                "actual": len(tp_orders_to_check),
                "message": f"Conservative approach should have 4 TP orders, found {len(tp_orders_to_check)}"
            })

        # Verify TP quantities match expected distribution
        if len(tp_orders_to_check) == 4:
            # Sort by quantity (largest first)
            sorted_tps = sorted(tp_orders_to_check, key=lambda x: float(x.get('qty', 0)), reverse=True)

            for i, (tp, expected_pct) in enumerate(zip(sorted_tps, CONSERVATIVE_TP_PERCENTAGES)):
                expected_qty = position_size * Decimal(str(expected_pct)) / Decimal('100')
                actual_qty = Decimal(str(tp.get('qty', 0)))

                # FIXED: Allow larger tolerance for rounding and minor discrepancies
                tolerance = max(position_size * Decimal('0.005'), Decimal('0.001'))  # 0.5% tolerance or minimum 0.001

                if abs(actual_qty - expected_qty) > tolerance:
                    discrepancies.append({
                        "type": f"tp{i+1}_quantity",
                        "expected": str(expected_qty),
                        "actual": str(actual_qty),
                        "expected_percentage": expected_pct,
                        "message": f"TP{i+1} should be {expected_pct}% ({expected_qty}), found {actual_qty}"
                    })

        # Verify total TP quantity for Conservative orders
        total_tp_qty = sum(Decimal(str(o.get('qty', 0))) for o in tp_orders_to_check)
        # For dual-approach positions, Conservative TPs might not equal full position size
        # So we check if the total is reasonable instead
        if total_tp_qty > position_size:
            discrepancies.append({
                "type": "tp_total",
                "expected": f"<= {position_size}",
                "actual": str(total_tp_qty),
                "message": f"Total Conservative TP quantity ({total_tp_qty}) exceeds position size ({position_size})"
            })

        # Should have exactly 1 SL with 100%
        if len(sl_orders) != 1:
            discrepancies.append({
                "type": "sl_count",
                "expected": 1,
                "actual": len(sl_orders),
                "message": f"Should have 1 SL order, found {len(sl_orders)}"
            })
        else:
            sl_qty = Decimal(str(sl_orders[0].get('qty', 0)))
            # FIXED: Allow tolerance for SL quantity as well
            sl_tolerance = max(position_size * Decimal('0.005'), Decimal('0.001'))  # 0.5% tolerance
            if abs(sl_qty - position_size) > sl_tolerance:
                discrepancies.append({
                    "type": "sl_quantity",
                    "expected": str(position_size),
                    "actual": str(sl_qty),
                    "message": f"SL quantity should be 100% ({position_size}), found {sl_qty}"
                })

        return discrepancies

    async def _verify_trigger_prices(self, original_data: Dict,
                                   tp_orders: List[Dict], sl_orders: List[Dict]) -> List[Dict]:
        """Verify trigger prices match original values"""
        discrepancies = []

        # Get original prices
        original_tp_prices = [Decimal(p) for p in original_data.get("tp_prices", [])]
        original_sl_price = Decimal(original_data.get("sl_price", 0)) if original_data.get("sl_price") else None

        # Check TP prices
        current_tp_prices = sorted([Decimal(str(o.get('price', 0))) for o in tp_orders])
        original_tp_prices_sorted = sorted(original_tp_prices)

        if len(current_tp_prices) == len(original_tp_prices_sorted):
            for i, (current, original) in enumerate(zip(current_tp_prices, original_tp_prices_sorted)):
                if current != original:
                    discrepancies.append({
                        "type": f"tp{i+1}_price",
                        "expected": str(original),
                        "actual": str(current),
                        "message": f"TP{i+1} price changed from {original} to {current}"
                    })

        # Check SL price
        if sl_orders and original_sl_price:
            current_sl_price = Decimal(str(sl_orders[0].get('triggerPrice', 0)))
            if current_sl_price != original_sl_price:
                discrepancies.append({
                    "type": "sl_price",
                    "expected": str(original_sl_price),
                    "actual": str(current_sl_price),
                    "message": f"SL price changed from {original_sl_price} to {current_sl_price}"
                })

        return discrepancies

    async def verify_all_positions(self) -> Dict[str, Dict]:
        """Verify all active positions"""
        try:
            positions = await get_all_positions()
            orders = await get_all_open_orders()

            active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
            verification_results = {}

            for position in active_positions:
                symbol = position['symbol']
                side = position['side']
                key = f"{symbol}_{side}"

                result = await self.verify_position_quantities(
                    symbol, side, position, orders
                )
                verification_results[key] = result

            return verification_results

        except Exception as e:
            logger.error(f"Error verifying all positions: {e}")
            return {}

    def generate_correction_suggestions(self, verification_result: Dict) -> List[str]:
        """Generate suggestions for correcting discrepancies"""
        if verification_result.get("verified"):
            return ["Position is correctly balanced"]

        suggestions = []
        discrepancies = verification_result.get("discrepancies", [])
        approach = verification_result.get("approach", "Unknown")

        # Group discrepancies by type
        tp_count_issues = [d for d in discrepancies if d["type"] == "tp_count"]
        tp_qty_issues = [d for d in discrepancies if "tp" in d["type"] and "quantity" in d["type"]]
        sl_issues = [d for d in discrepancies if "sl" in d["type"]]
        price_issues = [d for d in discrepancies if "price" in d["type"]]

        if tp_count_issues or tp_qty_issues:
            suggestions.append(f"Rebalance TP orders to match {approach} approach distribution")

        if sl_issues:
            suggestions.append("Recreate SL order with 100% of position size")

        if price_issues:
            suggestions.append("Note: Trigger prices have changed from original values")
            suggestions.append("Consider if manual adjustment was intentional")

        if not suggestions:
            suggestions.append("Run auto-rebalancer to fix detected issues")

        return suggestions


# Global verifier instance
trade_verifier = TradeVerifier()


# Convenience functions
async def verify_position(symbol: str, side: str, position: Dict, orders: List[Dict]) -> Dict:
    """Verify a single position"""
    return await trade_verifier.verify_position_quantities(symbol, side, position, orders)

async def verify_all_positions() -> Dict[str, Dict]:
    """Verify all positions"""
    return await trade_verifier.verify_all_positions()

def get_correction_suggestions(verification_result: Dict) -> List[str]:
    """Get correction suggestions"""
    return trade_verifier.generate_correction_suggestions(verification_result)