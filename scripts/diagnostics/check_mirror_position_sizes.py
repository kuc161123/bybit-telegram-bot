#!/usr/bin/env python3
"""
Check mirror position sizes vs main account to verify proportions
"""
import asyncio
from decimal import Decimal
from pybit.unified_trading import HTTP
from config.settings import USE_TESTNET, BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2

async def check_position_proportions():
    """Check main vs mirror position sizes"""
    
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
    print("POSITION SIZE COMPARISON - MAIN vs MIRROR")
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
                key = f"{symbol}_{side}"
                main_positions[key] = {
                    "size": size,
                    "avgPrice": float(pos.get("avgPrice", 0)),
                    "unrealisedPnl": float(pos.get("unrealisedPnl", 0))
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
                key = f"{symbol}_{side}"
                mirror_positions[key] = {
                    "size": size,
                    "avgPrice": float(pos.get("avgPrice", 0)),
                    "unrealisedPnl": float(pos.get("unrealisedPnl", 0))
                }
    
    # Compare positions
    all_keys = set(main_positions.keys()) | set(mirror_positions.keys())
    
    total_main_value = 0
    total_mirror_value = 0
    
    for key in sorted(all_keys):
        symbol, side = key.split("_")
        main_data = main_positions.get(key, {"size": 0, "avgPrice": 0, "unrealisedPnl": 0})
        mirror_data = mirror_positions.get(key, {"size": 0, "avgPrice": 0, "unrealisedPnl": 0})
        
        main_size = main_data["size"]
        mirror_size = mirror_data["size"]
        
        # Calculate proportion
        if main_size > 0:
            proportion = (mirror_size / main_size) * 100
        else:
            proportion = 0
        
        # Calculate position values
        main_value = main_size * main_data["avgPrice"]
        mirror_value = mirror_size * mirror_data["avgPrice"]
        
        total_main_value += main_value
        total_mirror_value += mirror_value
        
        print(f"\n{symbol} {side}:")
        print(f"  Main:   {main_size:>10.1f} @ ${main_data['avgPrice']:<8.5f} = ${main_value:>10.2f}")
        print(f"  Mirror: {mirror_size:>10.1f} @ ${mirror_data['avgPrice']:<8.5f} = ${mirror_value:>10.2f}")
        print(f"  Proportion: {proportion:.1f}% (Expected: 50%)")
        
        if abs(proportion - 50) > 5 and main_size > 0:  # More than 5% deviation
            print(f"  ⚠️  WARNING: Proportion deviation of {abs(proportion - 50):.1f}%")
            print(f"  📊 Expected mirror size: {main_size * 0.5:.1f}")
            print(f"  📊 Actual mirror size: {mirror_size:.1f}")
            print(f"  📊 Difference: {(main_size * 0.5) - mirror_size:.1f}")
    
    print("\n" + "=" * 60)
    print(f"TOTAL POSITION VALUES:")
    print(f"  Main Account:   ${total_main_value:>10.2f}")
    print(f"  Mirror Account: ${total_mirror_value:>10.2f}")
    print(f"  Mirror/Main Ratio: {(total_mirror_value/total_main_value*100) if total_main_value > 0 else 0:.1f}%")
    print("=" * 60)
    
    # Check open orders
    print("\nCHECKING OPEN ORDERS...")
    
    # Get all open orders for both accounts
    main_orders = main_client.get_open_orders(category="linear", settleCoin="USDT")
    mirror_orders = mirror_client.get_open_orders(category="linear", settleCoin="USDT")
    
    main_order_count = len(main_orders.get("result", {}).get("list", []))
    mirror_order_count = len(mirror_orders.get("result", {}).get("list", []))
    
    print(f"\nMain Account Orders: {main_order_count}")
    print(f"Mirror Account Orders: {mirror_order_count}")
    
    # Show mirror orders for positions with discrepancies
    if mirror_orders.get("retCode") == 0:
        mirror_order_list = mirror_orders.get("result", {}).get("list", [])
        
        for key in all_keys:
            symbol, side = key.split("_")
            main_size = main_positions.get(key, {"size": 0})["size"]
            mirror_size = mirror_positions.get(key, {"size": 0})["size"]
            
            if main_size > 0 and abs((mirror_size / main_size * 100) - 50) > 5:
                print(f"\n📋 Mirror orders for {symbol}:")
                symbol_orders = [o for o in mirror_order_list if o.get("symbol") == symbol]
                
                for order in symbol_orders:
                    order_type = order.get("orderType")
                    order_side = order.get("side")
                    qty = order.get("qty")
                    price = order.get("price")
                    order_status = order.get("orderStatus")
                    link_id = order.get("orderLinkId", "")[:20]
                    
                    print(f"  - {order_type} {order_side}: {qty} @ ${price} [{order_status}] {link_id}...")

if __name__ == "__main__":
    asyncio.run(check_position_proportions())