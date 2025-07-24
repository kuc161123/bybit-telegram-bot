#!/usr/bin/env python3
"""
Check DOGEUSDT position and orders on mirror account
"""

import asyncio
import logging
from datetime import datetime
from config.settings import (
    BYBIT_API_KEY_2, BYBIT_API_SECRET_2, USE_TESTNET,
    ENABLE_MIRROR_TRADING
)
from pybit.unified_trading import HTTP

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def check_dogeusdt_mirror():
    """Check DOGEUSDT position and orders on mirror account"""
    
    if not ENABLE_MIRROR_TRADING or not BYBIT_API_KEY_2 or not BYBIT_API_SECRET_2:
        print("❌ Mirror trading is not enabled or credentials not configured")
        return
    
    # Create mirror client
    mirror_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY_2,
        api_secret=BYBIT_API_SECRET_2
    )
    
    print(f"\n{'='*60}")
    print("MIRROR ACCOUNT - DOGEUSDT CHECK")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # Check DOGEUSDT position
    print("\n📊 DOGEUSDT POSITION:")
    try:
        response = mirror_client.get_positions(
            category="linear",
            symbol="DOGEUSDT",
            settleCoin="USDT"
        )
        
        if response.get("retCode") == 0:
            positions = response.get("result", {}).get("list", [])
            
            if positions:
                for pos in positions:
                    if float(pos.get('size', 0)) > 0:
                        print(f"\n✅ Found DOGEUSDT position:")
                        print(f"   Symbol: {pos.get('symbol')}")
                        print(f"   Side: {pos.get('side')}")
                        print(f"   Size: {pos.get('size')}")
                        print(f"   Average Entry Price: {pos.get('avgPrice')}")
                        print(f"   Mark Price: {pos.get('markPrice')}")
                        print(f"   Unrealized P&L: ${float(pos.get('unrealisedPnl', 0)):.4f}")
                        print(f"   Position Value: ${float(pos.get('positionValue', 0)):.4f}")
                        print(f"   Leverage: {pos.get('leverage')}")
                        print(f"   Position Mode: {pos.get('positionIdx')} (0=One-Way, 1=Buy-side, 2=Sell-side)")
                        print(f"   Created Time: {pos.get('createdTime')}")
                        print(f"   Updated Time: {pos.get('updatedTime')}")
                    else:
                        print("❌ No active DOGEUSDT position found")
            else:
                print("❌ No DOGEUSDT position found")
        else:
            print(f"❌ Error getting position: {response}")
    except Exception as e:
        print(f"❌ Exception getting position: {e}")
    
    # Check DOGEUSDT orders
    print("\n📝 DOGEUSDT ORDERS:")
    try:
        response = mirror_client.get_open_orders(
            category="linear",
            symbol="DOGEUSDT",
            settleCoin="USDT",
            limit=50
        )
        
        if response.get("retCode") == 0:
            orders = response.get("result", {}).get("list", [])
            
            if orders:
                print(f"\n✅ Found {len(orders)} DOGEUSDT orders:")
                for i, order in enumerate(orders, 1):
                    print(f"\nOrder #{i}:")
                    print(f"   Order ID: {order.get('orderId')}")
                    print(f"   Order Link ID: {order.get('orderLinkId')}")
                    print(f"   Order Type: {order.get('orderType')}")
                    print(f"   Side: {order.get('side')}")
                    print(f"   Quantity: {order.get('qty')}")
                    print(f"   Price: {order.get('price')}")
                    print(f"   Trigger Price: {order.get('triggerPrice', 'N/A')}")
                    print(f"   Trigger Direction: {order.get('triggerDirection', 'N/A')}")
                    print(f"   Trigger By: {order.get('triggerBy', 'N/A')}")
                    print(f"   Stop Order Type: {order.get('stopOrderType', 'N/A')}")
                    print(f"   Order Status: {order.get('orderStatus')}")
                    print(f"   Created Time: {order.get('createdTime')}")
            else:
                print("❌ No open DOGEUSDT orders found")
        else:
            print(f"❌ Error getting orders: {response}")
    except Exception as e:
        print(f"❌ Exception getting orders: {e}")
    
    # Also check all positions to see full context
    print("\n📊 ALL MIRROR POSITIONS (for context):")
    try:
        response = mirror_client.get_positions(category="linear", settleCoin="USDT")
        if response.get("retCode") == 0:
            all_positions = []
            for pos in response.get("result", {}).get("list", []):
                if float(pos.get('size', 0)) > 0:
                    all_positions.append(f"{pos.get('symbol')} {pos.get('side')} size={pos.get('size')}")
            
            if all_positions:
                print(f"Found {len(all_positions)} total positions:")
                for pos_str in all_positions:
                    print(f"  - {pos_str}")
            else:
                print("No active positions on mirror account")
    except Exception as e:
        print(f"Error checking all positions: {e}")


if __name__ == "__main__":
    asyncio.run(check_dogeusdt_mirror())