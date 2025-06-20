#!/usr/bin/env python3
"""
Test script for stop order limit checking functionality
"""
import asyncio
import logging
from clients.bybit_helpers import check_stop_order_limit

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_stop_order_limit():
    """Test the stop order limit checking"""
    print("Testing stop order limit checking...")
    
    # Test with a common symbol
    symbol = "BTCUSDT"
    
    try:
        result = await check_stop_order_limit(symbol)
        
        print(f"\nStop Order Limit Check for {symbol}:")
        print(f"  Current stop orders: {result['current_count']}")
        print(f"  Maximum allowed: {result['limit']}")
        print(f"  Available slots: {result['available_slots']}")
        print(f"  Number of existing orders: {len(result['existing_orders'])}")
        
        if result.get('error'):
            print(f"  Error: {result['error']}")
        
        # Show some existing orders if any
        if result['existing_orders']:
            print(f"\n  Sample existing orders:")
            for i, order in enumerate(result['existing_orders'][:3]):  # Show first 3
                print(f"    {i+1}. {order.get('symbol')} - {order.get('side')} - Trigger: {order.get('triggerPrice')}")
        
        return result
        
    except Exception as e:
        print(f"Error testing stop order limit: {e}")
        return None

if __name__ == "__main__":
    result = asyncio.run(test_stop_order_limit())
    print("\nTest completed!")