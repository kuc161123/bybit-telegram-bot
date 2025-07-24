#!/usr/bin/env python3
"""
Test script to verify enhanced TP/SL order detection.
This script tests the improved order detection logic that checks:
1. stopOrderType field
2. orderLinkId patterns
3. trigger price relative to entry price
"""

import asyncio
import logging
from typing import Dict, List
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the enhanced functions
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_helpers import (
    get_active_tp_sl_orders,
    get_detailed_order_info,
    get_all_positions,
    api_call_with_retry,
    bybit_client
)

async def test_tp_sl_detection(symbol: str = None):
    """Test the enhanced TP/SL order detection"""
    try:
        logger.info("=" * 80)
        logger.info("Testing Enhanced TP/SL Order Detection")
        logger.info("=" * 80)
        
        # If no symbol provided, get all active positions
        if not symbol:
            logger.info("No symbol provided, checking all active positions...")
            positions = await get_all_positions()
            active_symbols = []
            
            for pos in positions:
                if float(pos.get("size", "0")) > 0:
                    sym = pos.get("symbol", "")
                    if sym:
                        active_symbols.append(sym)
                        logger.info(f"Found active position: {sym}")
            
            if not active_symbols:
                logger.warning("No active positions found. Please specify a symbol to test.")
                return
        else:
            active_symbols = [symbol]
        
        # Test each symbol
        for test_symbol in active_symbols:
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Testing symbol: {test_symbol}")
            logger.info(f"{'=' * 60}")
            
            # Method 1: Get TP/SL orders using enhanced detection
            logger.info(f"\n1. Testing get_active_tp_sl_orders()...")
            tp_sl_orders = await get_active_tp_sl_orders(test_symbol)
            
            if tp_sl_orders:
                logger.info(f"✅ Found {len(tp_sl_orders)} TP/SL orders")
                for i, order in enumerate(tp_sl_orders):
                    logger.info(f"\n  Order {i+1}:")
                    logger.info(f"    Order ID: {order.get('orderId', '')[:8]}...")
                    logger.info(f"    Link ID: {order.get('orderLinkId', '')}")
                    logger.info(f"    Type: {order.get('orderType', '')}")
                    logger.info(f"    Stop Order Type: {order.get('stopOrderType', 'N/A')}")
                    logger.info(f"    Side: {order.get('side', '')}")
                    logger.info(f"    Qty: {order.get('qty', '')}")
                    logger.info(f"    Trigger Price: {order.get('triggerPrice', '')}")
                    logger.info(f"    Reduce Only: {order.get('reduceOnly', False)}")
            else:
                logger.info("❌ No TP/SL orders found")
            
            # Method 2: Get detailed order info for comprehensive analysis
            logger.info(f"\n2. Testing get_detailed_order_info()...")
            detailed_info = await get_detailed_order_info(test_symbol)
            
            if "error" not in detailed_info:
                logger.info(f"\n✅ Order Summary for {test_symbol}:")
                logger.info(f"  Total Orders: {detailed_info['total_orders']}")
                logger.info(f"  Limit Orders: {detailed_info['limit_orders']['count']}")
                logger.info(f"  TP Orders: {detailed_info['tp_orders']['count']}")
                logger.info(f"  SL Orders: {detailed_info['sl_orders']['count']}")
                logger.info(f"  Other Orders: {detailed_info['other_orders']['count']}")
                
                # Show TP orders details
                if detailed_info['tp_orders']['orders']:
                    logger.info(f"\n  TP Orders Details:")
                    for tp in detailed_info['tp_orders']['orders']:
                        logger.info(f"    - {tp['orderId'][:8]}... @ {tp.get('triggerPrice', tp.get('price', 'N/A'))}")
                        logger.info(f"      Stop Type: {tp.get('stopOrderType', 'N/A')}, Link ID: {tp.get('orderLinkId', '')}")
                
                # Show SL orders details
                if detailed_info['sl_orders']['orders']:
                    logger.info(f"\n  SL Orders Details:")
                    for sl in detailed_info['sl_orders']['orders']:
                        logger.info(f"    - {sl['orderId'][:8]}... @ {sl.get('triggerPrice', sl.get('price', 'N/A'))}")
                        logger.info(f"      Stop Type: {sl.get('stopOrderType', 'N/A')}, Link ID: {sl.get('orderLinkId', '')}")
            else:
                logger.error(f"❌ Error getting detailed info: {detailed_info['error']}")
            
            # Method 3: Raw API call to see all fields
            logger.info(f"\n3. Raw API call to inspect all order fields...")
            try:
                response = await api_call_with_retry(
                    lambda: bybit_client.get_open_orders(
                        category="linear",
                        symbol=test_symbol
                    ),
                    timeout=20
                )
                
                if response and response.get("retCode") == 0:
                    raw_orders = response.get("result", {}).get("list", [])
                    if raw_orders:
                        logger.info(f"\n✅ Raw order data (first order as example):")
                        first_order = raw_orders[0]
                        # Pretty print the order
                        logger.info(json.dumps(first_order, indent=2))
                        
                        # Check for any additional fields we might have missed
                        all_fields = set(first_order.keys())
                        expected_fields = {
                            'orderId', 'orderLinkId', 'symbol', 'side', 'orderType',
                            'price', 'qty', 'triggerPrice', 'stopOrderType', 'reduceOnly',
                            'orderStatus', 'createdTime', 'updatedTime'
                        }
                        extra_fields = all_fields - expected_fields
                        if extra_fields:
                            logger.info(f"\n⚠️ Additional fields found: {extra_fields}")
                    else:
                        logger.info("No orders found in raw API response")
            except Exception as e:
                logger.error(f"Error in raw API call: {e}")
        
        logger.info("\n" + "=" * 80)
        logger.info("Enhanced TP/SL Order Detection Test Complete")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Error in test_tp_sl_detection: {e}", exc_info=True)


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test enhanced TP/SL order detection')
    parser.add_argument('--symbol', type=str, help='Symbol to test (e.g., BTCUSDT)')
    args = parser.parse_args()
    
    await test_tp_sl_detection(args.symbol)


if __name__ == "__main__":
    asyncio.run(main())