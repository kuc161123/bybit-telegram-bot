#!/usr/bin/env python3
"""
Close all positions and orders on both main and mirror accounts for a fresh start
"""

import asyncio
import sys
import os
from datetime import datetime
from decimal import Decimal
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pybit.unified_trading import HTTP
from config.settings import BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2

async def close_all_positions_and_orders(account_type="main"):
    """Close all positions and cancel all orders for an account"""
    
    # Select API credentials
    if account_type == "main":
        api_key = BYBIT_API_KEY
        api_secret = BYBIT_API_SECRET
    else:
        api_key = BYBIT_API_KEY_2
        api_secret = BYBIT_API_SECRET_2
        
    if not api_key or not api_secret:
        print(f"⚠️  {account_type.upper()} account not configured")
        return {"positions_closed": 0, "orders_cancelled": 0}
    
    # Create client
    if USE_TESTNET:
        client = HTTP(testnet=True, api_key=api_key, api_secret=api_secret)
    else:
        client = HTTP(testnet=False, api_key=api_key, api_secret=api_secret)
    
    positions_closed = 0
    orders_cancelled = 0
    errors = []
    
    print(f"\n{'=' * 80}")
    print(f"{account_type.upper()} ACCOUNT - CLOSING ALL POSITIONS AND ORDERS")
    print("=" * 80)
    
    try:
        # Step 1: Cancel all open orders first
        print("\n📋 Cancelling all open orders...")
        
        # Cancel regular orders
        response = client.get_open_orders(category="linear", settleCoin="USDT", limit=50)
        orders = response.get('result', {}).get('list', [])
        
        for order in orders:
            try:
                cancel_response = client.cancel_order(
                    category="linear",
                    symbol=order['symbol'],
                    orderId=order['orderId']
                )
                if cancel_response.get('retCode') == 0:
                    orders_cancelled += 1
                    print(f"  ✅ Cancelled {order['symbol']} {order['orderType']} order")
                else:
                    print(f"  ❌ Failed to cancel {order['symbol']} order: {cancel_response}")
            except Exception as e:
                print(f"  ❌ Error cancelling order: {e}")
        
        # Cancel conditional/stop orders
        response = client.get_open_orders(category="linear", settleCoin="USDT", orderFilter="StopOrder", limit=50)
        stop_orders = response.get('result', {}).get('list', [])
        
        for order in stop_orders:
            try:
                cancel_response = client.cancel_order(
                    category="linear",
                    symbol=order['symbol'],
                    orderId=order['orderId']
                )
                if cancel_response.get('retCode') == 0:
                    orders_cancelled += 1
                    print(f"  ✅ Cancelled {order['symbol']} stop order")
                else:
                    print(f"  ❌ Failed to cancel {order['symbol']} stop order: {cancel_response}")
            except Exception as e:
                print(f"  ❌ Error cancelling stop order: {e}")
        
        print(f"\n✅ Total orders cancelled: {orders_cancelled}")
        
        # Wait a moment for orders to be cancelled
        await asyncio.sleep(1)
        
        # Step 2: Close all positions
        print("\n📊 Closing all positions...")
        
        response = client.get_positions(category="linear", settleCoin="USDT")
        positions = response.get('result', {}).get('list', [])
        
        active_positions = []
        for pos in positions:
            if float(pos.get('size', 0)) > 0:
                active_positions.append(pos)
        
        print(f"Found {len(active_positions)} active positions")
        
        for pos in active_positions:
            symbol = pos['symbol']
            side = pos['side']
            size = pos['size']
            
            # Determine closing side
            close_side = "Sell" if side == "Buy" else "Buy"
            
            print(f"\n  Closing {symbol} {side} position (size: {size})...")
            
            try:
                # Place market order to close position
                close_response = client.place_order(
                    category="linear",
                    symbol=symbol,
                    side=close_side,
                    orderType="Market",
                    qty=str(size),
                    reduceOnly=True,
                    orderLinkId=f"CLOSE_ALL_{symbol}_{int(time.time() * 1000)}"
                )
                
                if close_response.get('retCode') == 0:
                    positions_closed += 1
                    order_id = close_response.get('result', {}).get('orderId')
                    print(f"  ✅ Position closed - Order ID: {order_id}")
                    
                    # Wait for fill
                    await asyncio.sleep(0.5)
                    
                    # Check if position is closed
                    check_response = client.get_positions(category="linear", symbol=symbol)
                    check_positions = check_response.get('result', {}).get('list', [])
                    
                    still_open = False
                    for check_pos in check_positions:
                        if float(check_pos.get('size', 0)) > 0:
                            still_open = True
                            break
                    
                    if still_open:
                        print(f"  ⚠️  Position may still be open - check manually")
                    else:
                        print(f"  ✅ Position confirmed closed")
                else:
                    print(f"  ❌ Failed to close position: {close_response}")
                    errors.append(f"{symbol}: {close_response.get('retMsg', 'Unknown error')}")
                    
            except Exception as e:
                print(f"  ❌ Error closing position: {e}")
                errors.append(f"{symbol}: {str(e)}")
        
        print(f"\n✅ Total positions closed: {positions_closed}")
        
        # Step 3: Final verification
        print("\n🔍 Final verification...")
        
        # Check remaining positions
        response = client.get_positions(category="linear", settleCoin="USDT")
        positions = response.get('result', {}).get('list', [])
        
        remaining_positions = 0
        for pos in positions:
            if float(pos.get('size', 0)) > 0:
                remaining_positions += 1
                print(f"  ⚠️  Still open: {pos['symbol']} {pos['side']} {pos['size']}")
        
        # Check remaining orders
        response = client.get_open_orders(category="linear", settleCoin="USDT")
        remaining_orders = len(response.get('result', {}).get('list', []))
        
        response = client.get_open_orders(category="linear", settleCoin="USDT", orderFilter="StopOrder")
        remaining_orders += len(response.get('result', {}).get('list', []))
        
        print(f"\n📊 Final Status:")
        print(f"  Remaining positions: {remaining_positions}")
        print(f"  Remaining orders: {remaining_orders}")
        
        if remaining_positions == 0 and remaining_orders == 0:
            print(f"\n✅ {account_type.upper()} account successfully cleared!")
        else:
            print(f"\n⚠️  {account_type.upper()} account still has open positions/orders")
        
    except Exception as e:
        print(f"\n❌ Critical error: {e}")
        import traceback
        traceback.print_exc()
        errors.append(f"Critical error: {str(e)}")
    
    return {
        "positions_closed": positions_closed,
        "orders_cancelled": orders_cancelled,
        "remaining_positions": remaining_positions,
        "remaining_orders": remaining_orders,
        "errors": errors
    }

async def main():
    """Close all positions and orders on both accounts"""
    
    print("🚨 CLOSING ALL POSITIONS AND ORDERS FOR FRESH START")
    print("⚠️  This will close ALL positions at MARKET price")
    print("⚠️  You may incur losses if positions are not in profit")
    
    # Countdown
    for i in range(5, 0, -1):
        print(f"\nStarting in {i} seconds... (Press Ctrl+C to cancel)")
        await asyncio.sleep(1)
    
    print("\n🚀 Starting closure process...")
    
    # Process both accounts
    results = {}
    
    # Close main account
    results['main'] = await close_all_positions_and_orders('main')
    
    # Close mirror account
    if BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
        results['mirror'] = await close_all_positions_and_orders('mirror')
    
    # Generate summary report
    print("\n" + "=" * 80)
    print("FINAL SUMMARY REPORT")
    print("=" * 80)
    
    total_positions_closed = 0
    total_orders_cancelled = 0
    all_errors = []
    
    for account, result in results.items():
        print(f"\n{account.upper()} Account:")
        print(f"  Positions closed: {result['positions_closed']}")
        print(f"  Orders cancelled: {result['orders_cancelled']}")
        print(f"  Remaining positions: {result.get('remaining_positions', 'Unknown')}")
        print(f"  Remaining orders: {result.get('remaining_orders', 'Unknown')}")
        
        total_positions_closed += result['positions_closed']
        total_orders_cancelled += result['orders_cancelled']
        
        if result['errors']:
            print(f"  Errors: {len(result['errors'])}")
            all_errors.extend(result['errors'])
    
    print(f"\n📊 TOTALS:")
    print(f"  Total positions closed: {total_positions_closed}")
    print(f"  Total orders cancelled: {total_orders_cancelled}")
    
    if all_errors:
        print(f"\n⚠️  Total errors: {len(all_errors)}")
        for error in all_errors[:5]:  # Show first 5 errors
            print(f"  - {error}")
    
    # Save summary to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_file = f"fresh_start_closure_summary_{timestamp}.txt"
    
    with open(summary_file, 'w') as f:
        f.write(f"Fresh Start Closure Summary - {datetime.now()}\n")
        f.write("=" * 80 + "\n\n")
        
        for account, result in results.items():
            f.write(f"{account.upper()} Account:\n")
            f.write(f"  Positions closed: {result['positions_closed']}\n")
            f.write(f"  Orders cancelled: {result['orders_cancelled']}\n")
            f.write(f"  Remaining positions: {result.get('remaining_positions', 'Unknown')}\n")
            f.write(f"  Remaining orders: {result.get('remaining_orders', 'Unknown')}\n")
            if result['errors']:
                f.write(f"  Errors:\n")
                for error in result['errors']:
                    f.write(f"    - {error}\n")
            f.write("\n")
        
        f.write(f"TOTALS:\n")
        f.write(f"  Total positions closed: {total_positions_closed}\n")
        f.write(f"  Total orders cancelled: {total_orders_cancelled}\n")
    
    print(f"\n📄 Summary saved to: {summary_file}")
    print("\n✅ Fresh start process completed!")
    print("🎯 You can now start fresh with new trades.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Process cancelled by user")
        sys.exit(1)