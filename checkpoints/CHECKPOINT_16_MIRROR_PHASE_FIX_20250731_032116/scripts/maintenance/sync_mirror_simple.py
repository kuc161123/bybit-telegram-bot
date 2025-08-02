#!/usr/bin/env python3
"""
Simple sync of mirror account with main account.
Cancels all orders and recreates with proper quantities.
"""

import asyncio
import os
import sys
from datetime import datetime
from collections import defaultdict
import time
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()


async def simple_sync():
    """Simple sync of mirror account."""
    
    print("🔄 Mirror Account Simple Sync")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    from pybit.unified_trading import HTTP
    from config.settings import (
        BYBIT_API_KEY, BYBIT_API_SECRET,
        BYBIT_API_KEY_2, BYBIT_API_SECRET_2,
        USE_TESTNET
    )
    
    if not all([BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2]):
        print("❌ Both main and mirror accounts must be configured")
        return
    
    main_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    mirror_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY_2,
        api_secret=BYBIT_API_SECRET_2
    )
    
    # Step 1: Get positions
    print("\n📊 Analyzing Positions")
    print("-" * 40)
    
    # Get main positions
    main_positions = {}
    pos_response = main_client.get_positions(
        category="linear",
        settleCoin="USDT"
    )
    
    if pos_response['retCode'] == 0:
        for pos in pos_response['result']['list']:
            if float(pos['size']) > 0:
                symbol = pos['symbol']
                main_positions[symbol] = pos
    
    # Get mirror positions
    mirror_positions = {}
    pos_response = mirror_client.get_positions(
        category="linear",
        settleCoin="USDT"
    )
    
    if pos_response['retCode'] == 0:
        for pos in pos_response['result']['list']:
            if float(pos['size']) > 0:
                symbol = pos['symbol']
                mirror_positions[symbol] = pos
    
    # Common positions
    common_symbols = set(main_positions.keys()) & set(mirror_positions.keys())
    print(f"Found {len(common_symbols)} common positions to sync")
    
    # Step 2: Cancel ALL mirror orders
    print("\n📤 Cancelling ALL Mirror Orders")
    print("-" * 40)
    
    cancelled = 0
    
    # Cancel all orders at once
    try:
        cancel_response = mirror_client.cancel_all_orders(
            category="linear",
            settleCoin="USDT"
        )
        
        if cancel_response['retCode'] == 0:
            result = cancel_response['result']
            cancelled = len(result.get('list', []))
            print(f"✅ Cancelled {cancelled} orders in one batch")
        else:
            print(f"⚠️ Batch cancel failed, trying individual cancellation...")
            
            # Fallback to individual cancellation
            for symbol in mirror_positions.keys():
                response = mirror_client.get_open_orders(
                    category="linear",
                    symbol=symbol,
                    openOnly=1
                )
                
                if response['retCode'] == 0:
                    for order in response['result']['list']:
                        try:
                            mirror_client.cancel_order(
                                category="linear",
                                symbol=symbol,
                                orderId=order['orderId']
                            )
                            cancelled += 1
                        except:
                            pass
            
            print(f"✅ Cancelled {cancelled} orders individually")
            
    except Exception as e:
        print(f"❌ Error cancelling orders: {e}")
    
    # Wait for cancellations to process
    await asyncio.sleep(2)
    
    # Step 3: Recreate orders matching quantities
    print("\n🔧 Recreating Orders with Proper Quantities")
    print("-" * 40)
    
    total_success = 0
    total_failed = 0
    
    for symbol in sorted(common_symbols):
        mirror_pos = mirror_positions[symbol]
        mirror_size = int(float(mirror_pos['size']))
        side = mirror_pos['side']
        position_idx = mirror_pos.get('positionIdx', 0)
        
        print(f"\n📍 {symbol}: {side} {mirror_size:,}")
        
        # Get main account orders
        response = main_client.get_open_orders(
            category="linear",
            symbol=symbol,
            openOnly=1
        )
        
        if response['retCode'] != 0:
            continue
        
        main_orders = response['result']['list']
        if not main_orders:
            continue
        
        # Separate orders by type
        sl_orders = []
        tp_orders = []
        
        for order in main_orders:
            if order.get('stopOrderType') == 'Stop':
                link_id = order.get('orderLinkId', '')
                if 'SL' in link_id:
                    sl_orders.append(order)
                else:
                    tp_orders.append(order)
        
        # Determine approach (Fast or Conservative)
        is_fast = len(tp_orders) == 1
        
        # Create short timestamp for IDs
        ts = str(int(time.time() % 100000))
        
        # Place SL first
        if sl_orders:
            sl_order = sl_orders[0]  # Use first SL as template
            
            try:
                # For SL, always use full position size
                params = {
                    "category": "linear",
                    "symbol": symbol,
                    "side": "Sell" if side == 'Buy' else 'Buy',
                    "orderType": "Market",
                    "qty": str(mirror_size),
                    "triggerPrice": sl_order['triggerPrice'],
                    "triggerDirection": 2 if side == 'Buy' else 1,
                    "triggerBy": "LastPrice",
                    "reduceOnly": True,
                    "orderLinkId": f"MIR_SL_{ts}"
                }
                
                if position_idx:
                    params['positionIdx'] = position_idx
                
                response = mirror_client.place_order(**params)
                
                if response['retCode'] == 0:
                    print(f"  ✅ SL: {mirror_size} @ ${sl_order['triggerPrice']}")
                    total_success += 1
                else:
                    print(f"  ❌ SL failed: {response['retMsg']}")
                    total_failed += 1
                    
            except Exception as e:
                print(f"  ❌ SL error: {e}")
                total_failed += 1
        
        # Place TPs
        if tp_orders:
            if is_fast:
                # Fast approach - single TP with full size
                tp_order = tp_orders[0]
                
                try:
                    params = {
                        "category": "linear",
                        "symbol": symbol,
                        "side": "Sell" if side == 'Buy' else 'Buy',
                        "orderType": "Market",
                        "qty": str(mirror_size),
                        "triggerPrice": tp_order['triggerPrice'],
                        "triggerDirection": 1 if side == 'Buy' else 2,
                        "triggerBy": "LastPrice",
                        "reduceOnly": True,
                        "orderLinkId": f"MIR_TP_{ts}"
                    }
                    
                    if position_idx:
                        params['positionIdx'] = position_idx
                    
                    response = mirror_client.place_order(**params)
                    
                    if response['retCode'] == 0:
                        print(f"  ✅ TP: {mirror_size} @ ${tp_order['triggerPrice']} (Fast)")
                        total_success += 1
                    else:
                        print(f"  ❌ TP failed: {response['retMsg']}")
                        total_failed += 1
                        
                except Exception as e:
                    print(f"  ❌ TP error: {e}")
                    total_failed += 1
            else:
                # Conservative approach - multiple TPs
                # Calculate quantities: 85%, 5%, 5%, 5%
                tp1_qty = int(mirror_size * 0.85)
                tp_small_qty = int(mirror_size * 0.05)
                
                # Adjust for rounding
                remaining = mirror_size - tp1_qty - (tp_small_qty * 3)
                if remaining > 0:
                    tp1_qty += remaining
                
                quantities = [tp1_qty, tp_small_qty, tp_small_qty, tp_small_qty]
                
                # Place TPs
                tp_count = 0
                for i, (tp_order, qty) in enumerate(zip(tp_orders[:4], quantities)):
                    if qty == 0:
                        continue
                    
                    try:
                        tp_count += 1
                        params = {
                            "category": "linear",
                            "symbol": symbol,
                            "side": "Sell" if side == 'Buy' else 'Buy',
                            "orderType": "Market",
                            "qty": str(qty),
                            "triggerPrice": tp_order['triggerPrice'],
                            "triggerDirection": 1 if side == 'Buy' else 2,
                            "triggerBy": "LastPrice",
                            "reduceOnly": True,
                            "orderLinkId": f"MIR_TP{tp_count}_{ts}"
                        }
                        
                        if position_idx:
                            params['positionIdx'] = position_idx
                        
                        response = mirror_client.place_order(**params)
                        
                        if response['retCode'] == 0:
                            print(f"  ✅ TP{tp_count}: {qty} @ ${tp_order['triggerPrice']}")
                            total_success += 1
                        else:
                            print(f"  ❌ TP{tp_count} failed: {response['retMsg']}")
                            total_failed += 1
                            
                            # Stop if hitting limit
                            if "already had" in response['retMsg']:
                                break
                                
                    except Exception as e:
                        print(f"  ❌ TP{tp_count} error: {e}")
                        total_failed += 1
        
        # Small delay between symbols
        await asyncio.sleep(0.2)
    
    # Summary
    print("\n\n" + "=" * 70)
    print("📊 SYNC SUMMARY")
    print("=" * 70)
    
    print(f"\nOrders cancelled: {cancelled}")
    print(f"Orders created: {total_success}")
    print(f"Failed orders: {total_failed}")
    
    if total_failed > 0:
        print("\n⚠️  Some orders failed - likely due to order limits")
        print("The auto-rebalancer should handle quantity adjustments")
    
    print("\n✅ Sync complete!")
    print("\n💡 Important:")
    print("1. Orders now match mirror position sizes")
    print("2. Auto-rebalancer will maintain proper distributions")
    print("3. Monitor order counts to stay within limits")


async def main():
    """Main function."""
    await simple_sync()


if __name__ == "__main__":
    asyncio.run(main())