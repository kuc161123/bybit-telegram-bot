#!/usr/bin/env python3
"""
Test script to verify startup rebalancer handles old format orders correctly.
Specifically tests INJUSDT position with stopOrderType='Stop' orders.
"""

import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the function we're testing
from startup_conservative_rebalancer import check_if_needs_rebalance

# Simulate INJUSDT position and orders
def create_test_position() -> Dict[str, Any]:
    """Create a test position for INJUSDT."""
    return {
        'symbol': 'INJUSDT',
        'side': 'Buy',
        'size': '22',
        'avgPrice': '23.064',
        'unrealisedPnl': '24.18',
        'cumRealisedPnl': '0',
        'markPrice': '24.166',
        'positionValue': '531.652',
        'riskId': 1,
        'riskLimitValue': '200000',
        'takeProfit': '',
        'stopLoss': '',
        'trailingStop': '0',
        'activePrice': '0',
        'positionStatus': 'Normal',
        'positionIdx': 0,
        'createdTime': '1735398872901',
        'updatedTime': '1735398872906',
        'liqPrice': '',
        'bustPrice': '0.5',
        'leverage': '10',
        'autoAddMargin': 0,
        'positionBalance': '0',
        'adlRankIndicator': 2,
        'isReduceOnly': False,
        'mmrSysUpdateTime': '',
        'leverageSysUpdatedTime': '',
        'seq': 23373211718,
        'positionMM': '5.4285912',
        'positionIM': '53.5029952',
        'tpslMode': 'Full',
        'sessionAvgPrice': '0',
        'markPriceE10000': '241660000',
        'positionBalanceE8': '0',
        'cumRealisedPnlE8': '0',
        'unrealisedPnlE8': '241800000'
    }

def create_test_orders() -> List[Dict[str, Any]]:
    """Create test orders with old format (stopOrderType='Stop')."""
    return [
        # TP Orders with old format
        {
            'orderId': '1930fec2-fe59-4ec5-89a5-95dbfb96ffb7',
            'orderLinkId': 'BOT_CONS_INJ_TP1_1735398873',
            'symbol': 'INJUSDT',
            'side': 'Sell',
            'orderType': 'Limit',
            'price': '27.5',
            'qty': '18.7',
            'orderStatus': 'Untriggered',
            'stopOrderType': 'Stop',  # Old format
            'triggerPrice': '27.5',
            'triggerBy': 'LastPrice',
            'triggerDirection': 1,
            'reduceOnly': True,
            'closeOnTrigger': False
        },
        {
            'orderId': '77db3b67-6d02-4db5-8d18-5fb73de7c695',
            'orderLinkId': 'BOT_CONS_INJ_TP2_1735398873',
            'symbol': 'INJUSDT',
            'side': 'Sell',
            'orderType': 'Limit',
            'price': '37.5',
            'qty': '1.1',
            'orderStatus': 'Untriggered',
            'stopOrderType': 'Stop',  # Old format
            'triggerPrice': '37.5',
            'triggerBy': 'LastPrice',
            'triggerDirection': 1,
            'reduceOnly': True,
            'closeOnTrigger': False
        },
        {
            'orderId': '2fa0e7eb-5ed1-442c-b0ec-e7fe79e36e95',
            'orderLinkId': 'BOT_CONS_INJ_TP3_1735398873',
            'symbol': 'INJUSDT',
            'side': 'Sell',
            'orderType': 'Limit',
            'price': '55',
            'qty': '1.1',
            'orderStatus': 'Untriggered',
            'stopOrderType': 'Stop',  # Old format
            'triggerPrice': '55',
            'triggerBy': 'LastPrice',
            'triggerDirection': 1,
            'reduceOnly': True,
            'closeOnTrigger': False
        },
        {
            'orderId': '6e012c93-60de-413b-9ad7-58f64e37c2f0',
            'orderLinkId': 'BOT_CONS_INJ_TP4_1735398873',
            'symbol': 'INJUSDT',
            'side': 'Sell',
            'orderType': 'Limit',
            'price': '100',
            'qty': '1.1',
            'orderStatus': 'Untriggered',
            'stopOrderType': 'Stop',  # Old format
            'triggerPrice': '100',
            'triggerBy': 'LastPrice',
            'triggerDirection': 1,
            'reduceOnly': True,
            'closeOnTrigger': False
        },
        # SL Order with old format
        {
            'orderId': 'abf49aef-1c3f-4bdb-adec-8b2a68ddff90',
            'orderLinkId': 'BOT_CONS_INJ_SL_1735398873',
            'symbol': 'INJUSDT',
            'side': 'Sell',
            'orderType': 'Market',
            'price': '0',
            'qty': '22',
            'orderStatus': 'Untriggered',
            'stopOrderType': 'Stop',  # Old format
            'triggerPrice': '18.75',
            'triggerBy': 'LastPrice',
            'triggerDirection': 2,
            'reduceOnly': True,
            'closeOnTrigger': False
        }
    ]

async def test_rebalancer():
    """Test the check_if_needs_rebalance function."""
    logger.info("=" * 60)
    logger.info("Testing Startup Rebalancer with Old Format Orders")
    logger.info("=" * 60)
    
    position = create_test_position()
    orders = create_test_orders()
    
    logger.info(f"\nTest Position: {position['symbol']} {position['side']} size={position['size']}")
    logger.info(f"Entry Price: {position['avgPrice']}")
    logger.info(f"Current Price: {position['markPrice']}")
    logger.info(f"Unrealized PnL: ${position['unrealisedPnl']}")
    
    logger.info("\nTest Orders:")
    for order in orders:
        order_type = "TP" if "TP" in order['orderLinkId'] else "SL"
        logger.info(f"  {order_type}: {order['orderLinkId']} - "
                   f"qty={order['qty']}, trigger={order['triggerPrice']}, "
                   f"stopOrderType={order.get('stopOrderType', 'None')}")
    
    logger.info("\n" + "-" * 60)
    logger.info("Running check_if_needs_rebalance()...")
    logger.info("-" * 60)
    
    # Test the function
    try:
        # Extract position data for the function
        symbol = position['symbol']
        side = position['side']
        size = Decimal(position['size'])
        
        needs_rebalance, reason = await check_if_needs_rebalance(symbol, side, size, orders)
        
        logger.info(f"\nResult: needs_rebalance = {needs_rebalance}")
        logger.info(f"Reason: {reason}")
        
        # Analyze what the function detected
        logger.info("\nAnalysis:")
        
        # Check TP detection
        tp_orders = [o for o in orders if "TP" in o['orderLinkId']]
        logger.info(f"  - Found {len(tp_orders)} TP orders in test data")
        
        # Check SL detection
        sl_orders = [o for o in orders if "SL" in o['orderLinkId']]
        logger.info(f"  - Found {len(sl_orders)} SL orders in test data")
        
        # Check approach detection
        if any("CONS" in o['orderLinkId'] for o in orders):
            approach = "Conservative"
        elif any("FAST" in o['orderLinkId'] for o in orders):
            approach = "Fast"
        else:
            approach = "Unknown"
        logger.info(f"  - Detected approach: {approach}")
        
        # Check quantities
        total_tp_qty = sum(Decimal(o['qty']) for o in tp_orders)
        total_sl_qty = sum(Decimal(o['qty']) for o in sl_orders)
        position_size = Decimal(position['size'])
        
        logger.info(f"\n  - Position size: {position_size}")
        logger.info(f"  - Total TP quantity: {total_tp_qty}")
        logger.info(f"  - Total SL quantity: {total_sl_qty}")
        
        # Expected quantities for Conservative approach
        if approach == "Conservative":
            expected_tp1 = position_size * Decimal('0.85')
            expected_tp234 = position_size * Decimal('0.05')
            logger.info(f"\n  - Expected TP1 (85%): {expected_tp1}")
            logger.info(f"  - Expected TP2,3,4 (5% each): {expected_tp234}")
            
            # Check if current distribution matches
            actual_tp1 = Decimal(tp_orders[0]['qty']) if tp_orders else Decimal('0')
            logger.info(f"\n  - Actual TP1: {actual_tp1}")
            if abs(actual_tp1 - expected_tp1) > Decimal('0.1'):
                logger.info(f"  - TP1 mismatch detected! Expected {expected_tp1}, got {actual_tp1}")
        
        logger.info("\n" + "=" * 60)
        logger.info("Test Completed Successfully!")
        
        if needs_rebalance:
            logger.warning("\n⚠️  REBALANCE WOULD BE TRIGGERED!")
            logger.warning(f"Reason: {reason}")
        else:
            logger.info("\n✅ NO REBALANCE NEEDED - Orders are properly balanced")
        
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)

async def main():
    """Run the test."""
    await test_rebalancer()

if __name__ == "__main__":
    asyncio.run(main())