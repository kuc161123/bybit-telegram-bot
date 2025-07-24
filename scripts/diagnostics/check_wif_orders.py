#!/usr/bin/env python3
"""
Check WIFUSDT orders on both main and mirror accounts
"""
from pybit.unified_trading import HTTP
from config.settings import USE_TESTNET, BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
from decimal import Decimal

def check_wif_orders():
    """Check WIFUSDT orders on both accounts"""
    
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
    print("WIFUSDT ORDER CHECK - MAIN vs MIRROR")
    print("=" * 80)
    
    # Check both accounts
    for account_name, client in [("MAIN", main_client), ("MIRROR", mirror_client)]:
        print(f"\n{account_name} ACCOUNT:")
        print("-" * 40)
        
        # Get position info
        pos_response = client.get_positions(
            category="linear",
            symbol="WIFUSDT"
        )
        
        if pos_response.get("retCode") == 0:
            positions = pos_response.get("result", {}).get("list", [])
            if positions:
                pos = positions[0]
                size = pos.get("size", 0)
                side = pos.get("side", "")
                avg_price = pos.get("avgPrice", 0)
                pnl = pos.get("unrealisedPnl", 0)
                
                print(f"Position: {side} {size} @ ${avg_price}")
                print(f"Unrealized P&L: ${pnl}")
            else:
                print("No position found")
        
        # Get orders
        orders_response = client.get_open_orders(
            category="linear",
            symbol="WIFUSDT"
        )
        
        if orders_response.get("retCode") == 0:
            orders = orders_response.get("result", {}).get("list", [])
            
            print(f"\nOpen Orders ({len(orders)} total):")
            
            # Categorize orders
            tp_orders = []
            sl_orders = []
            limit_orders = []
            
            for order in orders:
                order_type = order.get("orderType")
                side = order.get("side")
                qty = order.get("qty")
                price = order.get("price", 0)
                trigger_price = order.get("triggerPrice", 0)
                link_id = order.get("orderLinkId", "")
                status = order.get("orderStatus")
                stop_type = order.get("stopOrderType", "")
                
                order_info = {
                    "qty": qty,
                    "price": price or trigger_price,
                    "link_id": link_id,
                    "status": status,
                    "side": side,
                    "type": order_type,
                    "stop_type": stop_type
                }
                
                # Categorize by order link ID or type
                if "TP" in link_id or stop_type == "TakeProfit":
                    tp_orders.append(order_info)
                elif "SL" in link_id or stop_type == "StopLoss":
                    sl_orders.append(order_info)
                elif "LIMIT" in link_id or (order_type == "Limit" and not stop_type):
                    limit_orders.append(order_info)
                else:
                    # Try to guess based on side
                    if positions and positions[0].get("side") == "Buy":
                        if side == "Sell" and price > float(avg_price):
                            tp_orders.append(order_info)
                        elif side == "Sell" and price < float(avg_price):
                            sl_orders.append(order_info)
                        else:
                            limit_orders.append(order_info)
                    elif positions and positions[0].get("side") == "Sell":
                        if side == "Buy" and price < float(avg_price):
                            tp_orders.append(order_info)
                        elif side == "Buy" and price > float(avg_price):
                            sl_orders.append(order_info)
                        else:
                            limit_orders.append(order_info)
            
            # Display categorized orders
            if tp_orders:
                print(f"\n✅ Take Profit Orders ({len(tp_orders)}):")
                tp_orders.sort(key=lambda x: float(x["price"]))
                for i, tp in enumerate(tp_orders, 1):
                    print(f"  TP{i}: {tp['qty']} @ ${tp['price']} [{tp['status']}] {tp['link_id'][:30]}...")
            else:
                print("\n❌ No TP orders found")
            
            if sl_orders:
                print(f"\n✅ Stop Loss Orders ({len(sl_orders)}):")
                for sl in sl_orders:
                    print(f"  SL: {sl['qty']} @ ${sl['price']} [{sl['status']}] {sl['link_id'][:30]}...")
            else:
                print("\n❌ No SL orders found")
            
            if limit_orders:
                print(f"\n📋 Limit Orders ({len(limit_orders)}):")
                for limit in limit_orders:
                    print(f"  {limit['side']}: {limit['qty']} @ ${limit['price']} [{limit['status']}] {limit['link_id'][:30]}...")
    
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("Check if mirror has the same TP/SL structure as main account")
    print("Mirror should have TP/SL orders sized for the actual position size")
    print("=" * 80)

if __name__ == "__main__":
    check_wif_orders()