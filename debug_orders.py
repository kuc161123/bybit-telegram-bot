#!/usr/bin/env python3
"""
Debug script to examine the structure of Bybit orders.
This helps identify the correct fields for TP/SL order prices.
"""

import asyncio
import logging
from typing import Dict, Any
from clients.bybit_client import BybitClient
from config.settings import BYBIT_CONFIG
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def debug_orders():
    """Fetch and analyze all open orders from Bybit."""
    try:
        # Initialize Bybit client
        client = BybitClient(BYBIT_CONFIG)
        
        # Get all open orders
        logger.info("Fetching all open orders...")
        orders = await client.get_all_open_orders()
        
        if not orders:
            logger.info("No open orders found.")
            return
        
        logger.info(f"Found {len(orders)} open orders")
        logger.info("=" * 80)
        
        # Analyze each order
        for i, order in enumerate(orders):
            logger.info(f"\nOrder {i + 1}:")
            logger.info("-" * 40)
            
            # Print all fields
            logger.info("All fields in order:")
            for key, value in order.items():
                logger.info(f"  {key}: {value}")
            
            logger.info("\nKey fields analysis:")
            # Check order type
            order_type = order.get('orderType', 'Unknown')
            logger.info(f"  Order Type: {order_type}")
            
            # Check if it's a TP/SL order
            stop_order_type = order.get('stopOrderType', None)
            if stop_order_type:
                logger.info(f"  Stop Order Type: {stop_order_type}")
            
            # Look for various price fields
            price_fields = [
                'price', 'triggerPrice', 'stopPx', 'takeProfitPrice',
                'stopLossPrice', 'avgPrice', 'lastPrice', 'markPrice',
                'indexPrice', 'triggerBy', 'triggerDirection'
            ]
            
            logger.info("\nPrice-related fields:")
            for field in price_fields:
                value = order.get(field)
                if value is not None:
                    logger.info(f"  {field}: {value}")
            
            # Check if this is a conditional order
            is_conditional = order.get('orderType') in ['Market', 'Limit'] and order.get('triggerPrice')
            if is_conditional:
                logger.info("\n  This appears to be a conditional order (TP/SL)")
            
            # Check order status
            order_status = order.get('orderStatus', 'Unknown')
            logger.info(f"\n  Order Status: {order_status}")
            
            # Check symbol and side
            symbol = order.get('symbol', 'Unknown')
            side = order.get('side', 'Unknown')
            logger.info(f"  Symbol: {symbol}")
            logger.info(f"  Side: {side}")
            
            logger.info("=" * 80)
        
        # Also check active positions for comparison
        logger.info("\n\nChecking active positions for comparison...")
        positions = await client.get_all_positions()
        
        if positions:
            logger.info(f"Found {len(positions)} active positions")
            for i, pos in enumerate(positions):
                if float(pos.get('size', 0)) != 0:  # Only show positions with size
                    logger.info(f"\nPosition {i + 1}:")
                    logger.info(f"  Symbol: {pos.get('symbol')}")
                    logger.info(f"  Side: {pos.get('side')}")
                    logger.info(f"  Size: {pos.get('size')}")
                    logger.info(f"  Take Profit: {pos.get('takeProfit')}")
                    logger.info(f"  Stop Loss: {pos.get('stopLoss')}")
        
        # Try to get order history to see filled TP/SL orders
        logger.info("\n\nChecking recent order history...")
        try:
            # This might need adjustment based on actual API
            history_response = await client._make_request(
                "GET",
                "/v5/order/history",
                params={"category": "linear", "limit": 10}
            )
            if history_response and 'list' in history_response:
                recent_orders = history_response['list']
                logger.info(f"Found {len(recent_orders)} recent orders in history")
                
                for order in recent_orders:
                    if order.get('stopOrderType') or order.get('triggerPrice'):
                        logger.info(f"\nHistorical TP/SL Order:")
                        logger.info(f"  Symbol: {order.get('symbol')}")
                        logger.info(f"  Order Type: {order.get('orderType')}")
                        logger.info(f"  Stop Order Type: {order.get('stopOrderType')}")
                        logger.info(f"  Trigger Price: {order.get('triggerPrice')}")
                        logger.info(f"  Price: {order.get('price')}")
                        logger.info(f"  Status: {order.get('orderStatus')}")
        except Exception as e:
            logger.error(f"Error fetching order history: {e}")
        
    except Exception as e:
        logger.error(f"Error in debug_orders: {e}", exc_info=True)
    finally:
        # Close the client connection
        if 'client' in locals():
            await client.close()


async def main():
    """Main entry point."""
    logger.info("Starting Bybit order structure debug...")
    await debug_orders()
    logger.info("Debug complete.")


if __name__ == "__main__":
    asyncio.run(main())