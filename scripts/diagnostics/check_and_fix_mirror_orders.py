import asyncio
import os
from pybit.unified_trading import HTTP
import json

async def check_and_fix_mirror_orders():
    # Get credentials for both accounts
    main_api_key = os.getenv('BYBIT_API_KEY')
    main_api_secret = os.getenv('BYBIT_API_SECRET')
    mirror_api_key = os.getenv('BYBIT_API_KEY_2')
    mirror_api_secret = os.getenv('BYBIT_API_SECRET_2')
    testnet = os.getenv('USE_TESTNET', 'false').lower() == 'true'
    
    if not all([main_api_key, main_api_secret, mirror_api_key, mirror_api_secret]):
        print("API credentials not found!")
        return
    
    # Create clients
    main_client = HTTP(testnet=testnet, api_key=main_api_key, api_secret=main_api_secret)
    mirror_client = HTTP(testnet=testnet, api_key=mirror_api_key, api_secret=mirror_api_secret)
    
    # Symbols to check (from mirror positions)
    symbols = ['PYTHUSDT', 'UNIUSDT', 'CHRUSDT', 'STRKUSDT', 'AVAXUSDT']
    
    print("=== CHECKING MAIN ACCOUNT ORDERS ===")
    
    main_order_data = {}
    
    for symbol in symbols:
        try:
            response = main_client.get_open_orders(category="linear", symbol=symbol)
            orders = response.get('result', {}).get('list', [])
            
            if orders:
                print(f"\n{symbol} - Main Account Orders ({len(orders)}):")
                
                tp_orders = []
                sl_orders = []
                
                for order in orders:
                    order_type = order.get('stopOrderType', '')
                    if order_type == 'TakeProfit':
                        tp_orders.append(order)
                    elif order_type == 'StopLoss':
                        sl_orders.append(order)
                
                # Store the trigger prices
                if symbol not in main_order_data:
                    main_order_data[symbol] = {'tp_prices': [], 'sl_price': None}
                
                # Sort TP orders by price to match order
                tp_orders_sorted = sorted(tp_orders, key=lambda x: float(x.get('triggerPrice', 0)))
                
                for o in tp_orders_sorted:
                    price = o.get('triggerPrice', 0)
                    main_order_data[symbol]['tp_prices'].append(price)
                    print(f"  TP: {price}")
                
                for o in sl_orders:
                    price = o.get('triggerPrice', 0)
                    main_order_data[symbol]['sl_price'] = price
                    print(f"  SL: {price}")
            else:
                print(f"\n{symbol} - No orders found in main account")
                
        except Exception as e:
            print(f"Error checking {symbol}: {e}")
    
    print("\n=== MAIN ACCOUNT ORDER DATA ===")
    print(json.dumps(main_order_data, indent=2))
    
    # Check if we have PYTHUSDT data from existing main position
    if 'PYTHUSDT' not in main_order_data or not main_order_data['PYTHUSDT']['tp_prices']:
        # Try to get from existing logs or known values
        print("\n⚠️ PYTHUSDT not found in main account, using known conservative values:")
        main_order_data['PYTHUSDT'] = {
            'tp_prices': ['0.1011', '0.1028', '0.1046', '0.1098'],
            'sl_price': '0.0916'
        }
        print(f"  Using TP prices: {main_order_data['PYTHUSDT']['tp_prices']}")
        print(f"  Using SL price: {main_order_data['PYTHUSDT']['sl_price']}")
    
    # Now fix mirror orders
    print("\n=== FIXING MIRROR ACCOUNT ORDERS ===")
    
    for symbol in symbols:
        if symbol not in main_order_data or not main_order_data[symbol]['tp_prices']:
            print(f"\n⚠️ Skipping {symbol} - no main account reference data")
            continue
            
        print(f"\n{symbol} - Fixing mirror orders...")
        
        try:
            # Get mirror orders
            response = mirror_client.get_open_orders(category="linear", symbol=symbol)
            orders = response.get('result', {}).get('list', [])
            
            tp_orders = []
            sl_orders = []
            
            for order in orders:
                order_type = order.get('stopOrderType', '')
                if order_type == 'TakeProfit':
                    tp_orders.append(order)
                elif order_type == 'StopLoss':
                    sl_orders.append(order)
            
            # Sort by quantity to match TP order (TP1 has most qty)
            tp_orders_sorted = sorted(tp_orders, key=lambda x: float(x.get('qty', 0)), reverse=True)
            
            # Cancel and replace orders with correct trigger prices
            tp_prices = main_order_data[symbol]['tp_prices']
            sl_price = main_order_data[symbol]['sl_price']
            
            # Cancel and recreate TP orders
            for i, order in enumerate(tp_orders_sorted):
                if i < len(tp_prices):
                    order_id = order.get('orderId')
                    qty = order.get('qty')
                    link_id = order.get('orderLinkId', '')
                    
                    print(f"  Cancelling TP{i+1} order {order_id[:8]}...")
                    try:
                        mirror_client.cancel_order(
                            category="linear",
                            symbol=symbol,
                            orderId=order_id
                        )
                        
                        # Recreate with correct trigger price
                        new_link_id = link_id.replace('_REBAL_', '_FIXED_')
                        print(f"  Creating new TP{i+1} @ {tp_prices[i]} for qty {qty}...")
                        
                        mirror_client.place_order(
                            category="linear",
                            symbol=symbol,
                            side="Sell",
                            orderType="Market",
                            qty=qty,
                            triggerPrice=tp_prices[i],
                            triggerDirection=1,
                            triggerBy="LastPrice",
                            reduceOnly=True,
                            orderLinkId=new_link_id,
                            stopOrderType="TakeProfit"
                        )
                        print(f"  ✅ TP{i+1} fixed with trigger price {tp_prices[i]}")
                    except Exception as e:
                        print(f"  ❌ Error fixing TP{i+1}: {e}")
            
            # Cancel and recreate SL order
            if sl_orders and sl_price:
                for order in sl_orders:
                    order_id = order.get('orderId')
                    qty = order.get('qty')
                    link_id = order.get('orderLinkId', '')
                    
                    print(f"  Cancelling SL order {order_id[:8]}...")
                    try:
                        mirror_client.cancel_order(
                            category="linear",
                            symbol=symbol,
                            orderId=order_id
                        )
                        
                        # Recreate with correct trigger price
                        new_link_id = link_id.replace('_REBAL_', '_FIXED_')
                        print(f"  Creating new SL @ {sl_price} for qty {qty}...")
                        
                        mirror_client.place_order(
                            category="linear",
                            symbol=symbol,
                            side="Sell",
                            orderType="Market",
                            qty=qty,
                            triggerPrice=sl_price,
                            triggerDirection=2,
                            triggerBy="LastPrice",
                            reduceOnly=True,
                            orderLinkId=new_link_id,
                            stopOrderType="StopLoss"
                        )
                        print(f"  ✅ SL fixed with trigger price {sl_price}")
                    except Exception as e:
                        print(f"  ❌ Error fixing SL: {e}")
                        
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
    
    print("\n✅ Mirror order fix complete!")
    print("\nNow run the bot to activate monitoring for these positions.")

asyncio.run(check_and_fix_mirror_orders())