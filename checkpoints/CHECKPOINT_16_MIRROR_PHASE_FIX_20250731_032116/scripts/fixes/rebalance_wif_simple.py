#!/usr/bin/env python3
"""
Simple WIF TP rebalancing script using direct Bybit API calls
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pybit.unified_trading import HTTP
from decimal import Decimal
from config.settings import USE_TESTNET, BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
from utils.helpers import value_adjusted_to_step
import pickle
import time

def rebalance_wif_tps():
    """Rebalance WIFUSDT TP orders"""
    
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
    print("WIFUSDT TP REBALANCING")
    print("=" * 80)
    
    # Process both accounts
    for account_name, client in [("main", main_client), ("mirror", mirror_client)]:
        print(f"\n{account_name.upper()} ACCOUNT:")
        print("-" * 40)
        
        try:
            # Get position
            pos_response = client.get_positions(
                category="linear",
                symbol="WIFUSDT"
            )
            
            if pos_response.get("retCode") != 0:
                print(f"Failed to get position: {pos_response}")
                continue
                
            positions = pos_response.get("result", {}).get("list", [])
            if not positions:
                print("No WIFUSDT position found")
                continue
                
            position = positions[0]
            current_size = Decimal(position.get("size", 0))
            side = position.get("side", "")
            avg_price = position.get("avgPrice", 0)
            
            print(f"Position: {side} {current_size} @ ${avg_price}")
            
            if current_size == 0:
                print("Position size is 0, skipping")
                continue
            
            # Get open orders
            orders_response = client.get_open_orders(
                category="linear",
                symbol="WIFUSDT"
            )
            
            if orders_response.get("retCode") != 0:
                print(f"Failed to get orders: {orders_response}")
                continue
                
            orders = orders_response.get("result", {}).get("list", [])
            
            # Find and cancel existing TP orders
            tp_orders = []
            print("\nCancelling existing TP orders...")
            
            for order in orders:
                link_id = order.get("orderLinkId", "")
                stop_type = order.get("stopOrderType", "")
                order_side = order.get("side")
                
                # TP orders are opposite side of position
                is_tp = (("TP" in link_id or stop_type == "TakeProfit") and 
                        ((side == "Buy" and order_side == "Sell") or 
                         (side == "Sell" and order_side == "Buy")))
                
                if is_tp:
                    order_id = order.get("orderId")
                    price = Decimal(order.get("price", 0) or order.get("triggerPrice", 0))
                    
                    # Cancel the order
                    try:
                        cancel_response = client.cancel_order(
                            category="linear",
                            symbol="WIFUSDT",
                            orderId=order_id
                        )
                        if cancel_response.get("retCode") == 0:
                            print(f"✅ Cancelled TP order: {order_id[:8]}...")
                            tp_orders.append({"price": price})
                        else:
                            print(f"❌ Failed to cancel: {cancel_response}")
                    except Exception as e:
                        print(f"Error cancelling order: {e}")
            
            # Sort TP prices
            if side == "Buy":
                tp_orders.sort(key=lambda x: x["price"])
            else:
                tp_orders.sort(key=lambda x: x["price"], reverse=True)
            
            # Get instrument info
            instrument_response = client.get_instruments_info(
                category="linear",
                symbol="WIFUSDT"
            )
            
            qty_step = Decimal("1")
            if instrument_response.get("retCode") == 0:
                instruments = instrument_response.get("result", {}).get("list", [])
                if instruments:
                    qty_step = Decimal(instruments[0].get("lotSizeFilter", {}).get("qtyStep", "1"))
            
            # Place new TP orders with correct quantities
            print("\nPlacing new TP orders...")
            tp_percentages = [85, 5, 5, 5]
            placed_quantity = Decimal("0")
            
            for i, (tp, percentage) in enumerate(zip(tp_orders[:4], tp_percentages), 1):
                if i < 4:
                    # Calculate quantity for first 3 TPs
                    quantity = value_adjusted_to_step(current_size * Decimal(percentage) / 100, qty_step)
                else:
                    # Last TP gets remaining quantity
                    quantity = current_size - placed_quantity
                    quantity = value_adjusted_to_step(quantity, qty_step)
                
                if quantity <= 0:
                    print(f"TP{i} quantity is 0, skipping")
                    continue
                
                # Place TP order
                try:
                    place_response = client.place_order(
                        category="linear",
                        symbol="WIFUSDT",
                        side="Buy" if side == "Sell" else "Sell",
                        orderType="Limit",
                        qty=str(quantity),
                        price=str(tp["price"]),
                        reduceOnly=True,
                        orderLinkId=f"TP{i}_{account_name}_{int(time.time())}"
                    )
                    
                    if place_response.get("retCode") == 0:
                        print(f"✅ Placed TP{i}: {quantity} @ ${tp['price']} ({percentage}%)")
                        placed_quantity += quantity
                    else:
                        print(f"❌ Failed to place TP{i}: {place_response}")
                except Exception as e:
                    print(f"Error placing TP{i}: {e}")
            
            print(f"\nTotal TP quantity placed: {placed_quantity}/{current_size}")
            
        except Exception as e:
            print(f"Error processing {account_name} account: {e}")
    
    # Update pickle file
    print("\nUpdating monitor flags...")
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        if 'enhanced_tp_sl_monitors' in data:
            for key in ['WIFUSDT_Sell_main', 'WIFUSDT_Sell_mirror']:
                if key in data['enhanced_tp_sl_monitors']:
                    data['enhanced_tp_sl_monitors'][key]['manual_rebalance_done'] = True
                    data['enhanced_tp_sl_monitors'][key]['manual_rebalance_time'] = int(time.time())
                    data['enhanced_tp_sl_monitors'][key]['last_known_size'] = data['enhanced_tp_sl_monitors'][key].get('remaining_size', 0)
        
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        print("✅ Updated pickle file")
    except Exception as e:
        print(f"Error updating pickle: {e}")
    
    print("\n" + "=" * 80)
    print("REBALANCING COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    rebalance_wif_tps()