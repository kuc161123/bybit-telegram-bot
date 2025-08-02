#!/usr/bin/env python3
"""
Enhanced order identification system for TP/SL orders.
Provides unified detection logic across the entire codebase.
"""

import logging
from typing import Dict, List, Tuple, Optional
from decimal import Decimal
import re
from datetime import datetime

logger = logging.getLogger(__name__)

# Standard order type constants
ORDER_TYPE_TP = "TP"
ORDER_TYPE_SL = "SL"
ORDER_TYPE_LIMIT = "LIMIT"
ORDER_TYPE_MARKET = "MARKET"
ORDER_TYPE_UNKNOWN = "UNKNOWN"

# Confidence levels
CONFIDENCE_HIGH = 0.9
CONFIDENCE_MEDIUM = 0.7
CONFIDENCE_LOW = 0.5

# Order patterns - supports both new and legacy formats
TP_PATTERNS = [
    r'BOT_.*_TP\d*',      # New format: BOT_CONS_BTCUSDT_TP1 (conservative only)
    r'TP\d*_',            # Legacy: TP1_, TP2_, etc
    r'_TP\d*$',           # Legacy: ending with _TP1
    r'TakeProfit',        # Generic
    r'tp_',               # Lowercase variants
    r'_tp\d*',
]

SL_PATTERNS = [
    r'BOT_.*_SL',         # New format: BOT_CONS_BTCUSDT_SL (conservative only)
    r'SL_',               # Legacy: SL_
    r'_SL$',              # Legacy: ending with _SL
    r'StopLoss',          # Generic
    r'sl_',               # Lowercase variants
    r'_sl$',
]

LIMIT_PATTERNS = [
    r'BOT_.*_LIMIT\d*',   # New format: BOT_CONS_BTCUSDT_LIMIT1
    r'_LIMIT\d*$',        # Legacy: ending with _LIMIT1
    r'limit_',            # Generic
]


class OrderIdentifier:
    """Enhanced order identification with multi-method detection"""

    @staticmethod
    def identify_order_type(order: Dict, position: Dict = None) -> Tuple[str, float]:
        """
        Identify order type using multiple detection methods.

        Args:
            order: Order data from Bybit
            position: Optional position data for context

        Returns:
            Tuple of (order_type, confidence_score)
        """
        order_type = ORDER_TYPE_UNKNOWN
        confidence = 0.0

        # Method 1: Check orderLinkId patterns (highest confidence)
        link_type, link_confidence = OrderIdentifier._check_order_link_id(order)
        if link_confidence > confidence:
            order_type = link_type
            confidence = link_confidence

        # Method 2: Check stopOrderType field
        stop_type, stop_confidence = OrderIdentifier._check_stop_order_type(order)
        if stop_confidence > confidence:
            order_type = stop_type
            confidence = stop_confidence

        # Method 3: Check order structure (limit vs market)
        struct_type, struct_confidence = OrderIdentifier._check_order_structure(order, position)
        if struct_confidence > confidence:
            order_type = struct_type
            confidence = struct_confidence

        # Method 4: Check trigger price direction (if position provided)
        if position and order.get('triggerPrice'):
            trigger_type, trigger_confidence = OrderIdentifier._check_trigger_direction(order, position)
            if trigger_confidence > confidence:
                order_type = trigger_type
                confidence = trigger_confidence

        return order_type, confidence

    @staticmethod
    def _check_order_link_id(order: Dict) -> Tuple[str, float]:
        """Check orderLinkId for patterns"""
        order_link_id = order.get('orderLinkId', '')

        # Check TP patterns
        for pattern in TP_PATTERNS:
            if re.search(pattern, order_link_id, re.IGNORECASE):
                return ORDER_TYPE_TP, CONFIDENCE_HIGH

        # Check SL patterns
        for pattern in SL_PATTERNS:
            if re.search(pattern, order_link_id, re.IGNORECASE):
                return ORDER_TYPE_SL, CONFIDENCE_HIGH

        # Check LIMIT patterns
        for pattern in LIMIT_PATTERNS:
            if re.search(pattern, order_link_id, re.IGNORECASE):
                return ORDER_TYPE_LIMIT, CONFIDENCE_HIGH

        return ORDER_TYPE_UNKNOWN, 0.0

    @staticmethod
    def _check_stop_order_type(order: Dict) -> Tuple[str, float]:
        """Check stopOrderType field"""
        stop_order_type = order.get('stopOrderType', '')

        if stop_order_type in ['TakeProfit', 'PartialTakeProfit']:
            return ORDER_TYPE_TP, CONFIDENCE_HIGH
        elif stop_order_type in ['StopLoss', 'PartialStopLoss']:
            return ORDER_TYPE_SL, CONFIDENCE_HIGH
        elif stop_order_type == 'Stop':
            # Generic stop order - need more context
            return ORDER_TYPE_UNKNOWN, CONFIDENCE_LOW

        return ORDER_TYPE_UNKNOWN, 0.0

    @staticmethod
    def _check_order_structure(order: Dict, position: Dict = None) -> Tuple[str, float]:
        """Check order structure (limit vs market, reduce-only, etc)"""
        order_type = order.get('orderType', '')
        reduce_only = order.get('reduceOnly', False)

        # Limit orders
        if order_type == 'Limit':
            if reduce_only and position:
                # Reduce-only limit order on opposite side is usually TP
                order_side = order.get('side')
                position_side = position.get('side')
                if order_side != position_side:
                    return ORDER_TYPE_TP, CONFIDENCE_MEDIUM
            elif not reduce_only:
                # Non-reduce-only limit order is entry order
                return ORDER_TYPE_LIMIT, CONFIDENCE_HIGH

        # Market orders with trigger price
        elif order_type == 'Market' and order.get('triggerPrice'):
            # Need more context to determine if TP or SL
            return ORDER_TYPE_UNKNOWN, CONFIDENCE_LOW

        return ORDER_TYPE_UNKNOWN, 0.0

    @staticmethod
    def _check_trigger_direction(order: Dict, position: Dict) -> Tuple[str, float]:
        """Check trigger price relative to mark price"""
        trigger_price = float(order.get('triggerPrice', 0))
        mark_price = float(position.get('markPrice', 0))

        if trigger_price == 0 or mark_price == 0:
            return ORDER_TYPE_UNKNOWN, 0.0

        position_side = position.get('side')

        if position_side == 'Buy':  # Long position
            if trigger_price > mark_price:
                return ORDER_TYPE_TP, CONFIDENCE_MEDIUM
            else:
                return ORDER_TYPE_SL, CONFIDENCE_MEDIUM
        else:  # Short position
            if trigger_price < mark_price:
                return ORDER_TYPE_TP, CONFIDENCE_MEDIUM
            else:
                return ORDER_TYPE_SL, CONFIDENCE_MEDIUM

    @staticmethod
    def generate_order_link_id(approach: str, symbol: str, order_type: str,
                             index: int = None, extra: str = "") -> str:
        """
        Generate standardized orderLinkId with length validation.

        Format: BOT_{APPROACH}_{SYMBOL}_{TYPE}{INDEX}_{EXTRA}_{TIMESTAMP}
        Max length: 45 characters

        Examples:
        - BOT_CONS_BTCUSDT_TP_123456
        - BOT_CONS_BTCUSDT_TP1_123456
        - BOT_CONS_BTCUSDT_LIMIT2_123456
        """
        timestamp = datetime.now().strftime('%H%M%S')[:6]  # 6 chars instead of 8

        # Abbreviate approach names
        approach_abbrev = {
            'CONSERVATIVE': 'CONS',
            'GGSHOT': 'GG'
        }.get(approach.upper(), 'CONS')  # Default to CONS (conservative only)

        # Build components
        parts = ["BOT", approach_abbrev, symbol, order_type.upper()]

        # Add index if provided (for TP1, TP2, LIMIT1, etc)
        if index is not None:
            parts[-1] += str(index)

        # Add extra info if provided
        if extra:
            parts.append(extra)

        # Add timestamp
        parts.append(timestamp)

        # Join and validate length
        order_link_id = "_".join(parts)

        # If too long, truncate symbol or remove extra
        if len(order_link_id) > 45:
            if extra:
                # Remove extra first
                parts = parts[:-2] + [timestamp]  # Remove extra, keep timestamp
                order_link_id = "_".join(parts)

            if len(order_link_id) > 45:
                # Truncate symbol if still too long
                max_symbol_len = 45 - len("_".join([parts[0], parts[1], "", parts[3], timestamp]))
                symbol_truncated = symbol[:max_symbol_len]
                parts[2] = symbol_truncated
                order_link_id = "_".join(parts)

        return order_link_id

    @staticmethod
    def generate_adjusted_order_link_id(original_id: str, adjustment_count: int = 1) -> str:
        """
        Generate adjusted order link ID for order modifications.
        Instead of appending _ADJ multiple times, use a counter.

        Args:
            original_id: Original order link ID
            adjustment_count: Number of adjustments made (1, 2, 3, etc.)

        Returns:
            Adjusted order link ID that stays within 45 character limit
        """
        # Remove any existing _ADJ suffixes
        base_id = original_id.replace("_ADJ", "")

        # Add adjustment counter
        adjusted_id = f"{base_id}_A{adjustment_count}"

        # If still too long, truncate from the middle (symbol part)
        if len(adjusted_id) > 45:
            parts = base_id.split("_")
            if len(parts) >= 4:
                # Calculate how much we need to trim
                excess = len(adjusted_id) - 45
                symbol_part = parts[2]

                # Trim symbol part
                if len(symbol_part) > excess:
                    parts[2] = symbol_part[:-excess]
                    base_id = "_".join(parts)
                    adjusted_id = f"{base_id}_A{adjustment_count}"

        return adjusted_id[:45]  # Ensure it never exceeds 45 chars

    @staticmethod
    def extract_order_info(order_link_id: str) -> Dict:
        """
        Extract information from orderLinkId.

        Returns dict with:
        - approach: CONS/GG/UNKNOWN (conservative or ggshot only)
        - symbol: Trading symbol
        - order_type: TP/SL/LIMIT
        - index: Order index (1,2,3,4 for TPs)
        - is_bot_order: True if BOT_ prefix
        """
        info = {
            'approach': 'UNKNOWN',
            'symbol': '',
            'order_type': ORDER_TYPE_UNKNOWN,
            'index': None,
            'is_bot_order': False
        }

        # Check if bot order
        if order_link_id.startswith('BOT_'):
            info['is_bot_order'] = True

            # Try to parse standardized format
            parts = order_link_id.split('_')
            if len(parts) >= 4:
                info['approach'] = parts[1]
                info['symbol'] = parts[2]

                # Extract type and index
                type_part = parts[3]
                if type_part.startswith('TP'):
                    info['order_type'] = ORDER_TYPE_TP
                    if len(type_part) > 2:
                        try:
                            info['index'] = int(type_part[2:])
                        except:
                            pass
                elif type_part.startswith('SL'):
                    info['order_type'] = ORDER_TYPE_SL
                elif type_part.startswith('LIMIT'):
                    info['order_type'] = ORDER_TYPE_LIMIT
                    if len(type_part) > 5:
                        try:
                            info['index'] = int(type_part[5:])
                        except:
                            pass

        return info

    @staticmethod
    def group_orders_by_type(orders: List[Dict], position: Dict = None) -> Dict[str, List[Dict]]:
        """
        Group orders by their identified type.

        Returns:
        {
            'tp_orders': [...],
            'sl_orders': [...],
            'limit_orders': [...],
            'unknown_orders': [...]
        }
        """
        grouped = {
            'tp_orders': [],
            'sl_orders': [],
            'limit_orders': [],
            'unknown_orders': []
        }

        for order in orders:
            order_type, confidence = OrderIdentifier.identify_order_type(order, position)

            if order_type == ORDER_TYPE_TP:
                grouped['tp_orders'].append(order)
            elif order_type == ORDER_TYPE_SL:
                grouped['sl_orders'].append(order)
            elif order_type == ORDER_TYPE_LIMIT:
                grouped['limit_orders'].append(order)
            else:
                grouped['unknown_orders'].append(order)

        return grouped

    @staticmethod
    def validate_order_coverage(position: Dict, orders: List[Dict]) -> Dict:
        """
        Validate if position has complete TP/SL coverage.

        Returns dict with:
        - has_complete_coverage: bool
        - tp_coverage_pct: float
        - sl_coverage_pct: float
        - issues: List of issues found
        """
        position_size = Decimal(str(position.get('size', 0)))
        if position_size == 0:
            return {
                'has_complete_coverage': False,
                'tp_coverage_pct': 0,
                'sl_coverage_pct': 0,
                'issues': ['ZERO_POSITION_SIZE']
            }

        # Group orders
        grouped = OrderIdentifier.group_orders_by_type(orders, position)

        # Calculate coverage
        tp_total = sum(Decimal(str(o.get('qty', 0))) for o in grouped['tp_orders'])
        sl_total = sum(Decimal(str(o.get('qty', 0))) for o in grouped['sl_orders'])

        tp_coverage_pct = float((tp_total / position_size) * 100)
        sl_coverage_pct = float((sl_total / position_size) * 100)

        # Check for issues
        issues = []

        if len(grouped['sl_orders']) == 0:
            issues.append('NO_SL')
        elif sl_coverage_pct < 99.5:
            issues.append('INCOMPLETE_SL')
        elif sl_coverage_pct > 100.5:
            issues.append('EXCESS_SL')

        if len(grouped['tp_orders']) == 0:
            issues.append('NO_TP')
        elif tp_coverage_pct < 99.5:
            issues.append('INCOMPLETE_TP')
        elif tp_coverage_pct > 100.5:
            issues.append('EXCESS_TP')

        if len(grouped['unknown_orders']) > 0:
            issues.append(f'UNKNOWN_ORDERS_{len(grouped["unknown_orders"])}')

        has_complete_coverage = (
            99.5 <= tp_coverage_pct <= 100.5 and
            99.5 <= sl_coverage_pct <= 100.5 and
            len(grouped['unknown_orders']) == 0
        )

        return {
            'has_complete_coverage': has_complete_coverage,
            'tp_coverage_pct': tp_coverage_pct,
            'sl_coverage_pct': sl_coverage_pct,
            'tp_count': len(grouped['tp_orders']),
            'sl_count': len(grouped['sl_orders']),
            'unknown_count': len(grouped['unknown_orders']),
            'issues': issues
        }


# Convenience functions
def identify_order_type(order: Dict, position: Dict = None) -> Tuple[str, float]:
    """Identify order type with confidence score"""
    return OrderIdentifier.identify_order_type(order, position)


def generate_order_link_id(approach: str, symbol: str, order_type: str,
                          index: int = None, extra: str = "") -> str:
    """Generate standardized orderLinkId"""
    return OrderIdentifier.generate_order_link_id(approach, symbol, order_type, index, extra)


def generate_adjusted_order_link_id(original_id: str, adjustment_count: int = 1) -> str:
    """Generate adjusted order link ID for order modifications"""
    return OrderIdentifier.generate_adjusted_order_link_id(original_id, adjustment_count)


def group_orders_by_type(orders: List[Dict], position: Dict = None) -> Dict[str, List[Dict]]:
    """Group orders by type"""
    return OrderIdentifier.group_orders_by_type(orders, position)


def validate_order_coverage(position: Dict, orders: List[Dict]) -> Dict:
    """Validate position coverage"""
    return OrderIdentifier.validate_order_coverage(position, orders)