#!/usr/bin/env python3
"""
Debug script to test fast approach order behavior
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_helpers import get_all_open_orders, get_order_info, get_position_info
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def monitor_order_states():
    """Monitor order state transitions to understand cancellation"""
    
    print("\n=== FAST APPROACH ORDER STATE MONITOR ===")
    print("This will monitor order states every 2 seconds")
    print("Press Ctrl+C to stop\n")
    
    # Get initial snapshot
    all_orders = await get_all_open_orders()
    
    # Filter for TP/SL orders
    monitored_orders = {}
    for order in all_orders:
        order_link_id = order.get('orderLinkId', '')
        if ('FAST_' in order_link_id or 'BOT_FAST' in order_link_id) and \
           ('_TP' in order_link_id or '_SL' in order_link_id):
            order_id = order.get('orderId')
            monitored_orders[order_id] = {
                'symbol': order.get('symbol'),
                'type': 'TP' if '_TP' in order_link_id else 'SL',
                'trigger_price': order.get('triggerPrice'),
                'status': order.get('orderStatus'),
                'link_id': order_link_id,
                'states': [(time.time(), order.get('orderStatus'))]
            }
    
    if not monitored_orders:
        print("No Fast approach TP/SL orders found to monitor")
        return
    
    print(f"Found {len(monitored_orders)} Fast approach orders to monitor:")
    for order_id, info in monitored_orders.items():
        print(f"  - {info['symbol']} {info['type']}: {order_id[:8]}... @ {info['trigger_price']}")
    
    print("\nMonitoring order states...")
    print("-" * 80)
    
    try:
        while True:
            # Check each order
            for order_id, info in list(monitored_orders.items()):
                symbol = info['symbol']
                
                # Get current order info
                order_info = await get_order_info(symbol, order_id)
                
                if order_info:
                    current_status = order_info.get('orderStatus', 'Unknown')
                    last_status = info['states'][-1][1] if info['states'] else None
                    
                    # Check if status changed
                    if current_status != last_status:
                        timestamp = time.time()
                        info['states'].append((timestamp, current_status))
                        
                        # Get position info for context
                        positions = await get_position_info(symbol)
                        position_size = 0
                        if positions:
                            for pos in positions:
                                if float(pos.get('size', 0)) > 0:
                                    position_size = pos.get('size')
                                    break
                        
                        print(f"\n🔄 STATE CHANGE DETECTED!")
                        print(f"   Order: {info['symbol']} {info['type']} {order_id[:8]}...")
                        print(f"   Status: {last_status} → {current_status}")
                        print(f"   Position Size: {position_size}")
                        print(f"   Trigger Price: {info['trigger_price']}")
                        
                        # Additional info for specific states
                        if current_status == "Triggered":
                            print(f"   ⚡ Order TRIGGERED - waiting for fill...")
                            print(f"   Current Price: {order_info.get('lastPrice', 'N/A')}")
                        elif current_status == "Filled":
                            print(f"   ✅ Order FILLED")
                            print(f"   Fill Price: {order_info.get('avgPrice', 'N/A')}")
                            print(f"   Fill Qty: {order_info.get('cumExecQty', 'N/A')}")
                        elif current_status == "Cancelled":
                            print(f"   ❌ Order CANCELLED!")
                            print(f"   Cancel Type: {order_info.get('cancelType', 'Unknown')}")
                            print(f"   Reason: {order_info.get('rejectReason', 'Unknown')}")
                            
                            # Show state history
                            print(f"\n   State History:")
                            for ts, state in info['states']:
                                elapsed = ts - info['states'][0][0]
                                print(f"     +{elapsed:.1f}s: {state}")
                        
                        print("-" * 80)
                        
                        # Remove from monitoring if final state
                        if current_status in ["Filled", "Cancelled", "Rejected"]:
                            del monitored_orders[order_id]
                            print(f"   Removed {order_id[:8]}... from monitoring (final state)")
                else:
                    # Order not found
                    print(f"\n❓ Order {order_id[:8]}... not found - may have been filled/cancelled")
                    del monitored_orders[order_id]
            
            if not monitored_orders:
                print("\n✅ All orders reached final state. Monitoring complete.")
                break
            
            # Wait before next check
            await asyncio.sleep(2)
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
        
    # Final summary
    print("\n=== SUMMARY ===")
    for order_id, info in monitored_orders.items():
        print(f"\n{info['symbol']} {info['type']} {order_id[:8]}...")
        print(f"  Final Status: {info['states'][-1][1] if info['states'] else 'Unknown'}")
        print(f"  State Changes: {len(info['states'])}")

async def check_order_configuration():
    """Check how Fast approach orders are configured"""
    
    print("\n=== FAST APPROACH ORDER CONFIGURATION CHECK ===")
    
    all_orders = await get_all_open_orders()
    fast_orders = []
    
    for order in all_orders:
        order_link_id = order.get('orderLinkId', '')
        if 'FAST_' in order_link_id or 'BOT_FAST' in order_link_id:
            fast_orders.append(order)
    
    if not fast_orders:
        print("No Fast approach orders found")
        return
    
    print(f"\nFound {len(fast_orders)} Fast approach orders:")
    
    for order in fast_orders:
        print(f"\n{order.get('symbol')} - {order.get('orderLinkId')}")
        print(f"  Order ID: {order.get('orderId', '')[:8]}...")
        print(f"  Type: {order.get('orderType')} ({order.get('stopOrderType', 'N/A')})")
        print(f"  Status: {order.get('orderStatus')}")
        print(f"  Side: {order.get('side')}")
        print(f"  Reduce Only: {order.get('reduceOnly', False)}")
        print(f"  Trigger Price: {order.get('triggerPrice', 'N/A')}")
        print(f"  Trigger By: {order.get('triggerBy', 'N/A')}")
        print(f"  Trigger Direction: {order.get('triggerDirection', 'N/A')}")
        print(f"  Time in Force: {order.get('timeInForce', 'N/A')}")
        print(f"  Close on Trigger: {order.get('closeOnTrigger', False)}")

async def main():
    """Main menu"""
    while True:
        print("\n=== FAST APPROACH ORDER DEBUG TOOL ===")
        print("1. Monitor order state changes")
        print("2. Check order configuration")
        print("3. Exit")
        
        choice = input("\nSelect option: ")
        
        if choice == "1":
            await monitor_order_states()
        elif choice == "2":
            await check_order_configuration()
        elif choice == "3":
            break
        else:
            print("Invalid choice")

if __name__ == "__main__":
    asyncio.run(main())