#!/usr/bin/env python3
"""
Cancel ALL orders on mirror account.
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from execution.mirror_trader import bybit_client_2
from config.settings import ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2


async def cancel_all_orders():
    """Cancel all orders on mirror account."""
    
    print("🗑️  CANCELLING ALL ORDERS ON MIRROR ACCOUNT")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    if not ENABLE_MIRROR_TRADING or not BYBIT_API_KEY_2 or not BYBIT_API_SECRET_2 or not bybit_client_2:
        print("❌ Mirror account not configured")
        return
    
    try:
        # Get all orders
        print("\n1️⃣ Getting all orders...")
        orders_resp = bybit_client_2.get_open_orders(
            category="linear",
            settleCoin="USDT",
            limit=200
        )
        
        if orders_resp and orders_resp.get('retCode') == 0:
            all_orders = orders_resp.get('result', {}).get('list', [])
            
            # Filter active orders
            active_orders = [
                order for order in all_orders 
                if order.get('orderStatus') in ['New', 'PartiallyFilled', 'Untriggered']
            ]
            
            print(f"   Found {len(active_orders)} active orders to cancel")
            
            if not active_orders:
                print("   ✅ No orders to cancel!")
                return
            
            # Cancel each order
            print("\n2️⃣ Cancelling orders...")
            cancelled = 0
            failed = 0
            
            for i, order in enumerate(active_orders, 1):
                try:
                    symbol = order['symbol']
                    order_id = order['orderId']
                    order_type = 'TP' if 'TP' in order.get('orderLinkId', '').upper() else 'SL' if 'SL' in order.get('orderLinkId', '').upper() else 'Other'
                    
                    print(f"   [{i}/{len(active_orders)}] Cancelling {symbol} {order_type} order...", end='')
                    
                    cancel_resp = bybit_client_2.cancel_order(
                        category="linear",
                        symbol=symbol,
                        orderId=order_id
                    )
                    
                    if cancel_resp.get('retCode') == 0:
                        cancelled += 1
                        print(" ✅")
                    else:
                        failed += 1
                        print(f" ❌ {cancel_resp.get('retMsg')}")
                except Exception as e:
                    failed += 1
                    print(f" ❌ Error: {e}")
                
                # Small delay to avoid rate limits
                if i % 10 == 0:
                    await asyncio.sleep(0.5)
            
            # Summary
            print(f"\n3️⃣ Summary:")
            print(f"   ✅ Successfully cancelled: {cancelled} orders")
            if failed > 0:
                print(f"   ❌ Failed to cancel: {failed} orders")
            
            # Verify
            await asyncio.sleep(2)
            print("\n4️⃣ Verifying...")
            
            verify_resp = bybit_client_2.get_open_orders(
                category="linear",
                settleCoin="USDT",
                limit=200
            )
            
            if verify_resp and verify_resp.get('retCode') == 0:
                remaining = verify_resp.get('result', {}).get('list', [])
                active_remaining = [
                    o for o in remaining 
                    if o.get('orderStatus') in ['New', 'PartiallyFilled', 'Untriggered']
                ]
                
                if not active_remaining:
                    print("   ✅ All orders successfully cancelled!")
                else:
                    print(f"   ⚠️  {len(active_remaining)} orders still remain")
            
        else:
            print(f"❌ Error fetching orders: {orders_resp}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main function."""
    await cancel_all_orders()
    print("\n✅ Mirror account cleanup complete!")


if __name__ == "__main__":
    asyncio.run(main())