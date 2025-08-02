#!/usr/bin/env python3
"""
Copy WIFUSDT TP/SL orders from main to mirror account with proper sizing
"""
import asyncio
from decimal import Decimal
from pybit.unified_trading import HTTP
from config.settings import USE_TESTNET, BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
from utils.helpers import value_adjusted_to_step
from clients.bybit_helpers import get_instrument_info
import time

# Set to True to actually place orders
EXECUTE_ORDERS = True

async def copy_wif_orders():
    """Copy WIFUSDT orders from main to mirror with 50% sizing"""
    
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
    
    print("=" * 80)
    print("COPYING WIFUSDT ORDERS FROM MAIN TO MIRROR")
    print("=" * 80)
    print(f"Mode: {'EXECUTE ORDERS' if EXECUTE_ORDERS else 'DRY RUN'}")
    print("=" * 80)
    
    # Get positions
    main_pos_response = main_client.get_positions(category="linear", symbol="WIFUSDT")
    mirror_pos_response = mirror_client.get_positions(category="linear", symbol="WIFUSDT")
    
    main_position = None
    mirror_position = None
    
    if main_pos_response.get("retCode") == 0:
        positions = main_pos_response.get("result", {}).get("list", [])
        if positions:
            main_position = positions[0]
    
    if mirror_pos_response.get("retCode") == 0:
        positions = mirror_pos_response.get("result", {}).get("list", [])
        if positions:
            mirror_position = positions[0]
    
    if not main_position or not mirror_position:
        print("❌ Missing position data")
        return
    
    main_size = Decimal(main_position.get("size", "0"))
    mirror_size = Decimal(mirror_position.get("size", "0"))
    position_side = main_position.get("side")
    
    print(f"Main position: {position_side} {main_size}")
    print(f"Mirror position: {position_side} {mirror_size}")
    print(f"Size ratio: {float(mirror_size/main_size)*100:.1f}%")
    
    # Get main account orders
    main_orders_response = main_client.get_open_orders(
        category="linear",
        symbol="WIFUSDT"
    )
    
    if main_orders_response.get("retCode") != 0:
        print("❌ Failed to get main orders")
        return
    
    main_orders = main_orders_response.get("result", {}).get("list", [])
    
    # Get instrument info
    instrument_info = await get_instrument_info("WIFUSDT")
    qty_step = Decimal("1")
    if instrument_info:
        lot_size_filter = instrument_info.get("lotSizeFilter", {})
        qty_step = Decimal(lot_size_filter.get("qtyStep", "1"))
    
    # Calculate size ratio for proportional orders
    size_ratio = mirror_size / main_size
    
    print(f"\nUsing size ratio: {float(size_ratio)*100:.1f}%")
    
    # Process orders
    orders_to_place = []
    
    for order in main_orders:
        order_link_id = order.get("orderLinkId", "")
        order_type = order.get("orderType")
        side = order.get("side")
        qty = Decimal(order.get("qty", "0"))
        price = order.get("price", "0")
        trigger_price = order.get("triggerPrice", "0")
        stop_order_type = order.get("stopOrderType", "")
        
        # Skip non-bot orders
        if not order_link_id.startswith("BOT_"):
            continue
        
        # Calculate proportional quantity
        mirror_qty = qty * size_ratio
        mirror_qty = value_adjusted_to_step(mirror_qty, qty_step)
        
        # Determine order type
        if "TP" in order_link_id or stop_order_type == "TakeProfit":
            order_category = "TP"
            # Extract TP number
            if "TP1" in order_link_id:
                tp_num = 1
            elif "TP2" in order_link_id:
                tp_num = 2
            elif "TP3" in order_link_id:
                tp_num = 3
            elif "TP4" in order_link_id:
                tp_num = 4
            else:
                tp_num = 1
            mirror_link_id = f"BOT_MIR_WIFUSDT_TP{tp_num}_{int(time.time())}"
        elif "SL" in order_link_id or stop_order_type == "StopLoss":
            order_category = "SL"
            mirror_link_id = f"BOT_MIR_WIFUSDT_SL_{int(time.time())}"
        else:
            continue  # Skip other orders
        
        order_data = {
            "category": order_category,
            "type": order_type,
            "side": side,
            "qty": str(mirror_qty),
            "price": price,
            "trigger_price": trigger_price,
            "stop_order_type": stop_order_type,
            "link_id": mirror_link_id,
            "original_qty": str(qty),
            "ratio": f"{float(mirror_qty/qty)*100:.1f}%"
        }
        
        orders_to_place.append(order_data)
        
        print(f"\n{order_category} Order:")
        print(f"  Main: {qty} @ ${price or trigger_price}")
        print(f"  Mirror: {mirror_qty} @ ${price or trigger_price} ({order_data['ratio']})")
    
    if not orders_to_place:
        print("\n❌ No orders to copy")
        return
    
    print(f"\n📋 Orders to place: {len(orders_to_place)}")
    
    if not EXECUTE_ORDERS:
        print("\n⚠️  DRY RUN MODE - No orders will be placed")
        print("Set EXECUTE_ORDERS = True to place real orders")
        return
    
    print("\n⚠️  Placing orders on mirror account...")
    
    success_count = 0
    
    for order in orders_to_place:
        try:
            print(f"\n{order['category']}:")
            
            if order['category'] == 'TP':
                # Place TP order
                response = mirror_client.place_order(
                    category="linear",
                    symbol="WIFUSDT",
                    side=order["side"],
                    orderType="Limit",
                    qty=order["qty"],
                    price=order["price"],
                    reduceOnly=True,
                    orderLinkId=order["link_id"],
                    timeInForce="GTC",
                    positionIdx=0
                )
            else:  # SL
                # Place SL order
                response = mirror_client.place_order(
                    category="linear",
                    symbol="WIFUSDT",
                    side=order["side"],
                    orderType="Market",
                    qty=order["qty"],
                    triggerPrice=order["trigger_price"],
                    reduceOnly=True,
                    orderLinkId=order["link_id"],
                    positionIdx=0,
                    stopOrderType="StopLoss"
                )
            
            if response.get("retCode") == 0:
                order_id = response.get("result", {}).get("orderId", "")
                print(f"  ✅ Order placed: {order_id}")
                success_count += 1
            else:
                print(f"  ❌ Failed: {response.get('retMsg', 'Unknown error')}")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    print("\n" + "=" * 80)
    print(f"COMPLETE: {success_count}/{len(orders_to_place)} orders placed successfully")
    print("Run check_wif_orders.py to verify")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(copy_wif_orders())