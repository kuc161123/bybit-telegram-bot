#!/usr/bin/env python3
"""
Enhanced approach detection that handles mixed Fast/Conservative orders.
This will update the auto_rebalancer to better detect trading approaches.
"""
import logging
from typing import Dict, List, Tuple
from decimal import Decimal
from collections import defaultdict

logger = logging.getLogger(__name__)

def detect_approach_from_orders_enhanced(orders: List[Dict], position: Dict) -> Tuple[str, List[Dict]]:
    """
    Enhanced approach detection that can identify mixed orders.
    
    Returns:
        Tuple of (approach, problematic_orders)
        - approach: "Fast", "Conservative", "Mixed", or "Unknown"
        - problematic_orders: Orders that don't fit the detected approach
    """
    if not orders:
        return "Unknown", []
    
    position_size = Decimal(str(position.get('size', 0)))
    if position_size == 0:
        return "Unknown", []
    
    side = position['side']
    
    # Group orders by type
    tp_orders = []
    sl_orders = []
    limit_orders = []
    
    for order in orders:
        order_side = order.get('side')
        # TP orders are opposite side of position
        if order_side and order_side != side:
            tp_orders.append(order)
        elif order.get('triggerPrice'):
            sl_orders.append(order)
        else:
            # Check if it's a limit entry order
            if not order.get('reduceOnly'):
                limit_orders.append(order)
    
    # Analyze TP orders by their orderLinkId patterns
    fast_tps = []
    conservative_tps = []
    unknown_tps = []
    
    for tp in tp_orders:
        link_id = tp.get('orderLinkId', '')
        if 'FAST' in link_id:
            fast_tps.append(tp)
        elif 'CONS' in link_id:
            conservative_tps.append(tp)
        else:
            unknown_tps.append(tp)
    
    # Analyze SL orders
    fast_sls = []
    conservative_sls = []
    unknown_sls = []
    
    for sl in sl_orders:
        link_id = sl.get('orderLinkId', '')
        if 'FAST' in link_id:
            fast_sls.append(sl)
        elif 'CONS' in link_id:
            conservative_sls.append(sl)
        else:
            unknown_sls.append(sl)
    
    # Determine approach
    has_fast = len(fast_tps) > 0 or len(fast_sls) > 0
    has_conservative = len(conservative_tps) > 0 or len(conservative_sls) > 0
    
    problematic_orders = []
    
    if has_fast and has_conservative:
        # Mixed approaches - this is the problem!
        approach = "Mixed"
        logger.warning(f"⚠️ Mixed Fast and Conservative orders detected!")
        logger.warning(f"   Fast: {len(fast_tps)} TPs, {len(fast_sls)} SLs")
        logger.warning(f"   Conservative: {len(conservative_tps)} TPs, {len(conservative_sls)} SLs")
        
        # Determine which set to keep based on which has more complete coverage
        fast_coverage = calculate_order_coverage(position_size, fast_tps, fast_sls)
        cons_coverage = calculate_order_coverage(position_size, conservative_tps, conservative_sls)
        
        if fast_coverage >= cons_coverage:
            # Keep Fast, mark Conservative as problematic
            problematic_orders.extend(conservative_tps)
            problematic_orders.extend(conservative_sls)
            approach = "Fast"
        else:
            # Keep Conservative, mark Fast as problematic
            problematic_orders.extend(fast_tps)
            problematic_orders.extend(fast_sls)
            approach = "Conservative"
            
    elif has_fast:
        approach = "Fast"
        # Check if Fast orders are complete
        if len(fast_tps) != 1:
            logger.warning(f"Fast approach should have 1 TP, found {len(fast_tps)}")
        if len(fast_sls) != 1:
            logger.warning(f"Fast approach should have 1 SL, found {len(fast_sls)}")
            
    elif has_conservative:
        approach = "Conservative"
        # Check if Conservative orders are complete
        if len(conservative_tps) != 4:
            logger.warning(f"Conservative approach should have 4 TPs, found {len(conservative_tps)}")
        if len(conservative_sls) != 1:
            logger.warning(f"Conservative approach should have 1 SL, found {len(conservative_sls)}")
    else:
        # No clear approach markers, fall back to count-based detection
        if len(tp_orders) == 1:
            approach = "Fast"
        elif len(tp_orders) == 4:
            approach = "Conservative"
        else:
            approach = f"Custom_{len(tp_orders)}TP"
    
    # Add any unknown orders to problematic list
    problematic_orders.extend(unknown_tps)
    problematic_orders.extend(unknown_sls)
    
    return approach, problematic_orders

def calculate_order_coverage(position_size: Decimal, tp_orders: List[Dict], sl_orders: List[Dict]) -> float:
    """Calculate how well orders cover the position"""
    tp_total = sum(Decimal(str(o.get('qty', 0))) for o in tp_orders)
    sl_total = sum(Decimal(str(o.get('qty', 0))) for o in sl_orders)
    
    tp_coverage = float(tp_total / position_size) if position_size > 0 else 0
    sl_coverage = float(sl_total / position_size) if position_size > 0 else 0
    
    # Calculate combined coverage score (both should be close to 100%)
    tp_score = 1.0 - abs(1.0 - tp_coverage) if tp_coverage > 0 else 0
    sl_score = 1.0 - abs(1.0 - sl_coverage) if sl_coverage > 0 else 0
    
    return (tp_score + sl_score) / 2

def suggest_fix_for_mixed_orders(position: Dict, orders: List[Dict], preferred_approach: str = None) -> Dict:
    """
    Suggest how to fix mixed orders situation.
    
    Args:
        position: Current position
        orders: All orders for the position
        preferred_approach: "Fast" or "Conservative" (if None, will choose based on coverage)
        
    Returns:
        Dict with:
        - orders_to_cancel: List of order IDs to cancel
        - approach_to_keep: The approach that should be kept
        - reason: Explanation of the decision
    """
    approach, problematic_orders = detect_approach_from_orders_enhanced(orders, position)
    
    if approach != "Mixed":
        return {
            'orders_to_cancel': [],
            'approach_to_keep': approach,
            'reason': f"No mixed orders detected. Current approach: {approach}"
        }
    
    # If preferred approach specified, use it
    if preferred_approach in ["Fast", "Conservative"]:
        orders_to_cancel = []
        for order in orders:
            link_id = order.get('orderLinkId', '')
            if preferred_approach == "Fast" and 'CONS' in link_id:
                orders_to_cancel.append(order['orderId'])
            elif preferred_approach == "Conservative" and 'FAST' in link_id:
                orders_to_cancel.append(order['orderId'])
        
        return {
            'orders_to_cancel': orders_to_cancel,
            'approach_to_keep': preferred_approach,
            'reason': f"Keeping {preferred_approach} approach as requested"
        }
    
    # Otherwise, use the approach determined by detect_approach_from_orders_enhanced
    orders_to_cancel = [o['orderId'] for o in problematic_orders]
    
    return {
        'orders_to_cancel': orders_to_cancel,
        'approach_to_keep': approach,
        'reason': f"Keeping {approach} approach based on better order coverage"
    }

if __name__ == "__main__":
    # Test the enhanced detection
    logging.basicConfig(level=logging.INFO)
    
    # Example test data
    test_position = {'symbol': 'BTCUSDT', 'side': 'Buy', 'size': '0.1'}
    test_orders = [
        {'orderId': '1', 'side': 'Sell', 'qty': '0.1', 'orderLinkId': 'BOT_FAST_BTCUSDT_TP'},
        {'orderId': '2', 'side': 'Sell', 'qty': '0.085', 'orderLinkId': 'BOT_CONS_BTCUSDT_TP1'},
        {'orderId': '3', 'side': 'Sell', 'qty': '0.005', 'orderLinkId': 'BOT_CONS_BTCUSDT_TP2'},
        {'orderId': '4', 'triggerPrice': '40000', 'qty': '0.1', 'orderLinkId': 'BOT_FAST_BTCUSDT_SL'},
    ]
    
    approach, problematic = detect_approach_from_orders_enhanced(test_orders, test_position)
    print(f"Detected approach: {approach}")
    print(f"Problematic orders: {len(problematic)}")
    
    fix_suggestion = suggest_fix_for_mixed_orders(test_position, test_orders)
    print(f"\nFix suggestion: {fix_suggestion}")