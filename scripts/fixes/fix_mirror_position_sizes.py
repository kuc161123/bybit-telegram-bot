#!/usr/bin/env python3
"""
Fix mirror position sizes to be 50% of main positions
WARNING: This will place REAL ORDERS on the mirror account!
"""
import asyncio
from decimal import Decimal
from pybit.unified_trading import HTTP
from config.settings import USE_TESTNET, BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
from utils.helpers import value_adjusted_to_step
from clients.bybit_helpers import get_instrument_info

# Set this to True to actually place orders (dry run by default)
EXECUTE_ORDERS = False

async def fix_mirror_positions():
    """Fix mirror positions to be 50% of main"""
    
    # Initialize clients
    main_client = HTTP(
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET,
        testnet=USE_TESTNET
    )
    
    mirror_client = HTTP(
        api_key=BYBIT_API_KEY_2,
        api_secret=BYBIT_API_SECRET_2,
        testnet=USE_TESTNET
    )
    
    print("=" * 60)
    print("MIRROR POSITION SIZE FIX - 50% PROPORTION")
    print("=" * 60)
    print(f"Mode: {'EXECUTE ORDERS' if EXECUTE_ORDERS else 'DRY RUN'}")
    print("=" * 60)
    
    # Get main positions
    main_response = main_client.get_positions(
        category="linear",
        settleCoin="USDT"
    )
    
    main_positions = {}
    if main_response.get("retCode") == 0:
        for pos in main_response.get("result", {}).get("list", []):
            size = float(pos.get("size", 0))
            if size > 0:
                symbol = pos.get("symbol")
                side = pos.get("side")
                main_positions[symbol] = {
                    "side": side,
                    "size": size,
                    "avgPrice": float(pos.get("avgPrice", 0))
                }
    
    # Get mirror positions
    mirror_response = mirror_client.get_positions(
        category="linear",
        settleCoin="USDT"
    )
    
    mirror_positions = {}
    if mirror_response.get("retCode") == 0:
        for pos in mirror_response.get("result", {}).get("list", []):
            size = float(pos.get("size", 0))
            if size > 0:
                symbol = pos.get("symbol")
                side = pos.get("side")
                mirror_positions[symbol] = {
                    "side": side,
                    "size": size,
                    "avgPrice": float(pos.get("avgPrice", 0))
                }
    
    # Process each main position
    orders_to_place = []
    
    for symbol, main_data in main_positions.items():
        main_size = main_data["size"]
        main_side = main_data["side"]
        target_mirror_size = main_size * 0.5  # 50% proportion
        
        current_mirror_size = 0
        if symbol in mirror_positions:
            current_mirror_size = mirror_positions[symbol]["size"]
        
        size_difference = target_mirror_size - current_mirror_size
        
        print(f"\n{symbol} {main_side}:")
        print(f"  Main size: {main_size}")
        print(f"  Current mirror size: {current_mirror_size}")
        print(f"  Target mirror size: {target_mirror_size} (50%)")
        print(f"  Difference: {size_difference:+.1f}")
        
        if abs(size_difference) < 0.1:  # Less than 0.1 unit difference
            print("  ✅ Already in sync")
            continue
        
        # Get instrument info for quantity step
        instrument_info = await get_instrument_info(symbol)
        if instrument_info:
            lot_size_filter = instrument_info.get("lotSizeFilter", {})
            qty_step = Decimal(lot_size_filter.get("qtyStep", "1"))
        else:
            qty_step = Decimal("1")
        
        if size_difference > 0:
            # Need to increase mirror position
            order_qty = value_adjusted_to_step(Decimal(str(abs(size_difference))), qty_step)
            order_side = main_side  # Same side to increase position
            action = "INCREASE"
        else:
            # Need to decrease mirror position
            order_qty = value_adjusted_to_step(Decimal(str(abs(size_difference))), qty_step)
            order_side = "Sell" if main_side == "Buy" else "Buy"  # Opposite side to reduce
            action = "DECREASE"
        
        orders_to_place.append({
            "symbol": symbol,
            "side": order_side,
            "qty": str(order_qty),
            "action": action,
            "current": current_mirror_size,
            "target": target_mirror_size
        })
        
        print(f"  📋 Order to {action}: {order_side} {order_qty} {symbol}")
    
    if not orders_to_place:
        print("\n✅ All positions are already in sync!")
        return
    
    print("\n" + "=" * 60)
    print(f"ORDERS TO PLACE: {len(orders_to_place)}")
    print("=" * 60)
    
    if not EXECUTE_ORDERS:
        print("\n⚠️  DRY RUN MODE - No orders will be placed")
        print("Set EXECUTE_ORDERS = True to place real orders")
        return
    
    # Confirm before execution
    print("\n⚠️  WARNING: This will place REAL ORDERS on the mirror account!")
    confirm = input("Type 'YES' to proceed: ")
    
    if confirm != "YES":
        print("❌ Cancelled")
        return
    
    # Execute orders
    print("\n📊 Placing orders...")
    
    for order in orders_to_place:
        try:
            print(f"\n{order['symbol']}:")
            print(f"  Placing {order['side']} market order for {order['qty']} units...")
            
            response = mirror_client.place_order(
                category="linear",
                symbol=order["symbol"],
                side=order["side"],
                orderType="Market",
                qty=order["qty"],
                positionIdx=0  # One-way mode
            )
            
            if response.get("retCode") == 0:
                order_id = response.get("result", {}).get("orderId", "")
                print(f"  ✅ Order placed: {order_id}")
            else:
                print(f"  ❌ Failed: {response.get('retMsg', 'Unknown error')}")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    print("\n✅ Position adjustment complete!")
    print("\nRun check_mirror_position_sizes.py to verify results")

if __name__ == "__main__":
    # Safety check
    print("⚠️  This script will adjust mirror positions to 50% of main positions")
    print("Make sure you understand the implications before proceeding")
    print()
    
    asyncio.run(fix_mirror_positions())