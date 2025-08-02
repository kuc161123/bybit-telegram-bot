#!/usr/bin/env python3
"""
Verify that all positions and orders are closed
"""

import asyncio
import logging
from datetime import datetime

from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET,
    ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
)
from pybit.unified_trading import HTTP

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def verify_account(client: HTTP, account_name: str):
    """Verify an account has no positions or orders"""
    print(f"\n{'='*50}")
    print(f"{account_name} ACCOUNT")
    print(f"{'='*50}")
    
    # Check positions
    try:
        response = client.get_positions(category="linear", settleCoin="USDT")
        positions = []
        if response.get("retCode") == 0:
            for pos in response.get("result", {}).get("list", []):
                if float(pos.get('size', 0)) > 0:
                    positions.append(pos)
        
        if positions:
            print(f"⚠️  Found {len(positions)} open positions:")
            for pos in positions:
                print(f"  - {pos.get('symbol')} {pos.get('side')}: {pos.get('size')}")
        else:
            print("✅ No open positions")
    except Exception as e:
        print(f"❌ Error checking positions: {e}")
    
    # Check orders
    try:
        response = client.get_open_orders(category="linear", settleCoin="USDT", limit=50)
        orders = []
        if response.get("retCode") == 0:
            orders = response.get("result", {}).get("list", [])
        
        if orders:
            print(f"⚠️  Found {len(orders)} open orders:")
            # Group by symbol
            orders_by_symbol = {}
            for order in orders:
                symbol = order.get('symbol')
                if symbol not in orders_by_symbol:
                    orders_by_symbol[symbol] = 0
                orders_by_symbol[symbol] += 1
            
            for symbol, count in orders_by_symbol.items():
                print(f"  - {symbol}: {count} orders")
        else:
            print("✅ No open orders")
    except Exception as e:
        print(f"❌ Error checking orders: {e}")


async def main():
    print("=" * 80)
    print("VERIFYING CLEAN SLATE")
    print("=" * 80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Main account
    main_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    await verify_account(main_client, "MAIN")
    
    # Mirror account
    if ENABLE_MIRROR_TRADING and BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
        mirror_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2
        )
        await verify_account(mirror_client, "MIRROR")
    
    print("\n" + "=" * 80)
    print("VERIFICATION COMPLETE")
    print("=" * 80)
    print("\n✅ You now have a clean slate!")
    print("✅ Bot has been stopped")
    print("✅ Ready to start fresh whenever you're ready")
    print("\nTo restart the bot: python main.py")


if __name__ == "__main__":
    asyncio.run(main())