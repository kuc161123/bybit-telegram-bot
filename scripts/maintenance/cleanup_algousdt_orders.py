#!/usr/bin/env python3
"""
Clean up ALGOUSDT orphaned orders
"""
import asyncio
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_helpers import api_call_with_retry
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled

async def cleanup_algousdt_orders():
    """Clean up ALGOUSDT orphaned orders"""
    
    if not is_mirror_trading_enabled() or not bybit_client_2:
        print("❌ Mirror trading is not enabled")
        return
    
    print("🧹 Cleaning up ALGOUSDT orphaned orders...\n")
    
    try:
        # Get ALGOUSDT orders
        order_response = await api_call_with_retry(
            lambda: bybit_client_2.get_open_orders(
                category="linear",
                symbol="ALGOUSDT"
            ),
            timeout=30
        )
        
        if order_response and order_response.get("retCode") == 0:
            orders = order_response.get("result", {}).get("list", [])
            
            if not orders:
                print("✅ No ALGOUSDT orders found")
                return
            
            print(f"Found {len(orders)} ALGOUSDT orders to cancel:\n")
            
            cancelled = 0
            for order in orders:
                order_id = order.get("orderId", "")
                order_type = order.get("orderType", "")
                side = order.get("side", "")
                qty = order.get("qty", "")
                
                try:
                    cancel_response = await api_call_with_retry(
                        lambda: bybit_client_2.cancel_order(
                            category="linear",
                            symbol="ALGOUSDT",
                            orderId=order_id
                        ),
                        timeout=20
                    )
                    
                    if cancel_response and cancel_response.get("retCode") == 0:
                        print(f"✅ Cancelled: {order_type} {side} {qty} (ID: {order_id[:8]}...)")
                        cancelled += 1
                    else:
                        error_msg = cancel_response.get("retMsg", "Unknown error") if cancel_response else "No response"
                        print(f"❌ Failed: {order_type} {side} {qty} - {error_msg}")
                        
                except Exception as e:
                    print(f"❌ Error cancelling order {order_id[:8]}...: {e}")
                
                await asyncio.sleep(0.2)
            
            print(f"\n✅ Cancelled {cancelled} ALGOUSDT orders")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(cleanup_algousdt_orders())