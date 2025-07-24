#!/usr/bin/env python3
"""
Fix mirror account TP orders to have correct quantities matching position sizes
"""
import asyncio
from decimal import Decimal
from pybit.unified_trading import HTTP
from config.settings import USE_TESTNET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
from utils.helpers import value_adjusted_to_step
from clients.bybit_helpers import get_instrument_info
import time

# Set to True to actually execute (dry run by default)
EXECUTE_ORDERS = True

async def fix_mirror_tp_orders():
    """Fix TP orders for TIAUSDT, LINKUSDT, and WIFUSDT"""
    
    # Initialize mirror client
    mirror_client = HTTP(
        api_key=BYBIT_API_KEY_2,
        api_secret=BYBIT_API_SECRET_2,
        testnet=USE_TESTNET
    )
    
    print("=" * 80)
    print("FIXING MIRROR ACCOUNT TP ORDERS")
    print("=" * 80)
    print(f"Mode: {'EXECUTE ORDERS' if EXECUTE_ORDERS else 'DRY RUN'}")
    print("=" * 80)
    
    # Define fixes needed
    fixes = {
        "TIAUSDT": {
            "position_size": Decimal("84.1"),
            "tp_prices": ["1.697", "1.737", "1.778", "1.9"],
            "tp_percentages": [85, 5, 5, 5],
            "side": "Buy"  # Position side
        },
        "LINKUSDT": {
            "position_size": Decimal("10.2"),
            "tp_prices": ["14.096", "14.714", "15.332", "17.186"],
            "tp_percentages": [85, 5, 5, 5],
            "side": "Buy"
        },
        "WIFUSDT": {
            "position_size": Decimal("663"),
            "tp_prices": ["0.9236", "0.947", "0.9704", "1.0406"],
            "tp_percentages": [85, 5, 5, 5],
            "side": "Buy"
        }
    }
    
    for symbol, fix_data in fixes.items():
        print(f"\n{'='*60}")
        print(f"Processing {symbol}")
        print(f"{'='*60}")
        
        # Get instrument info for quantity step
        instrument_info = await get_instrument_info(symbol)
        if instrument_info:
            lot_size_filter = instrument_info.get("lotSizeFilter", {})
            qty_step = Decimal(lot_size_filter.get("qtyStep", "1"))
            price_filter = instrument_info.get("priceFilter", {})
            tick_size = Decimal(price_filter.get("tickSize", "0.0001"))
        else:
            qty_step = Decimal("0.1")
            tick_size = Decimal("0.0001")
            print(f"⚠️ Could not get instrument info, using defaults")
        
        position_size = fix_data["position_size"]
        tp_prices = fix_data["tp_prices"]
        tp_percentages = fix_data["tp_percentages"]
        position_side = fix_data["side"]
        
        # Calculate TP quantities
        tp_quantities = []
        for percentage in tp_percentages:
            qty = position_size * Decimal(str(percentage)) / Decimal("100")
            qty = value_adjusted_to_step(qty, qty_step)
            tp_quantities.append(qty)
        
        # Verify total coverage
        total_qty = sum(tp_quantities)
        coverage = (total_qty / position_size * 100).quantize(Decimal("0.01"))
        
        print(f"\nPosition: {position_side} {position_size}")
        print(f"TP Order Plan:")
        for i, (qty, price, pct) in enumerate(zip(tp_quantities, tp_prices, tp_percentages), 1):
            print(f"  TP{i}: {qty} @ ${price} ({pct}%)")
        print(f"Total Coverage: {coverage}%")
        
        if not EXECUTE_ORDERS:
            print("\n⚠️ DRY RUN - No orders will be placed")
            continue
        
        # Step 1: Cancel existing TP orders
        print(f"\nStep 1: Canceling existing TP orders...")
        
        try:
            # Get current open orders
            orders_response = mirror_client.get_open_orders(
                category="linear",
                symbol=symbol
            )
            
            if orders_response.get("retCode") == 0:
                orders = orders_response.get("result", {}).get("list", [])
                tp_orders = []
                
                # Find TP orders
                for order in orders:
                    link_id = order.get("orderLinkId", "")
                    stop_type = order.get("stopOrderType", "")
                    order_type = order.get("orderType", "")
                    order_side = order.get("side")
                    
                    # For long positions, TPs are sell limit orders
                    if position_side == "Buy" and order_side == "Sell":
                        if "TP" in link_id or stop_type == "TakeProfit" or (order_type == "Limit" and not stop_type):
                            tp_orders.append(order)
                    # For short positions, TPs are buy limit orders
                    elif position_side == "Sell" and order_side == "Buy":
                        if "TP" in link_id or stop_type == "TakeProfit" or (order_type == "Limit" and not stop_type):
                            tp_orders.append(order)
                
                print(f"Found {len(tp_orders)} TP orders to cancel")
                
                # Cancel each TP order
                for order in tp_orders:
                    order_id = order.get("orderId")
                    try:
                        cancel_response = mirror_client.cancel_order(
                            category="linear",
                            symbol=symbol,
                            orderId=order_id
                        )
                        if cancel_response.get("retCode") == 0:
                            print(f"  ✅ Cancelled order {order_id[:8]}...")
                        else:
                            print(f"  ❌ Failed to cancel {order_id[:8]}: {cancel_response.get('retMsg')}")
                    except Exception as e:
                        print(f"  ❌ Error cancelling {order_id[:8]}: {e}")
                
        except Exception as e:
            print(f"❌ Error getting orders: {e}")
            continue
        
        # Step 2: Place new TP orders
        print(f"\nStep 2: Placing new TP orders...")
        
        # Determine order side (opposite of position side)
        order_side = "Sell" if position_side == "Buy" else "Buy"
        
        success_count = 0
        for i, (qty, price, pct) in enumerate(zip(tp_quantities, tp_prices, tp_percentages), 1):
            try:
                # Format price to tick size
                price_decimal = Decimal(price)
                formatted_price = str(value_adjusted_to_step(price_decimal, tick_size))
                
                response = mirror_client.place_order(
                    category="linear",
                    symbol=symbol,
                    side=order_side,
                    orderType="Limit",
                    qty=str(qty),
                    price=formatted_price,
                    reduceOnly=True,
                    orderLinkId=f"BOT_MIR_{symbol}_TP{i}_{int(time.time())}",
                    timeInForce="GTC",
                    positionIdx=0
                )
                
                if response.get("retCode") == 0:
                    order_id = response.get("result", {}).get("orderId", "")
                    print(f"  ✅ TP{i} placed: {qty} @ ${formatted_price} (ID: {order_id[:8]}...)")
                    success_count += 1
                else:
                    print(f"  ❌ TP{i} failed: {response.get('retMsg', 'Unknown error')}")
                    
            except Exception as e:
                print(f"  ❌ TP{i} error: {e}")
        
        print(f"\nResult: {success_count}/4 TP orders placed successfully")
    
    print("\n" + "=" * 80)
    print("COMPLETE!")
    print("Run verify_all_mirror_tp_sl.py to verify the fixes")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(fix_mirror_tp_orders())