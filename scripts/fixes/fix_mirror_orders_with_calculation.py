import asyncio
import os
from pybit.unified_trading import HTTP
import json

async def fix_mirror_orders_with_calculation():
    # Get credentials
    mirror_api_key = os.getenv('BYBIT_API_KEY_2')
    mirror_api_secret = os.getenv('BYBIT_API_SECRET_2')
    testnet = os.getenv('USE_TESTNET', 'false').lower() == 'true'
    
    if not all([mirror_api_key, mirror_api_secret]):
        print("Mirror API credentials not found!")
        return
    
    # Create client
    mirror_client = HTTP(testnet=testnet, api_key=mirror_api_key, api_secret=mirror_api_secret)
    
    print("=== GETTING MIRROR POSITIONS FOR PRICE CALCULATION ===")
    
    # Get positions to calculate appropriate TP/SL prices
    response = mirror_client.get_positions(category="linear", settleCoin="USDT")
    positions = response.get('result', {}).get('list', [])
    
    position_data = {}
    
    for pos in positions:
        if float(pos.get('size', 0)) > 0:
            symbol = pos.get('symbol')
            side = pos.get('side')
            avg_price = float(pos.get('avgPrice', 0))
            
            position_data[symbol] = {
                'side': side,
                'avg_price': avg_price
            }
            
            print(f"\n{symbol}:")
            print(f"  Side: {side}")
            print(f"  Avg Price: {avg_price}")
            
            # Calculate conservative TP/SL prices
            if side == 'Buy':
                # For long positions
                tp1 = avg_price * 1.04  # +4%
                tp2 = avg_price * 1.06  # +6%
                tp3 = avg_price * 1.08  # +8%
                tp4 = avg_price * 1.13  # +13%
                sl = avg_price * 0.945  # -5.5%
            else:
                # For short positions
                tp1 = avg_price * 0.96  # -4%
                tp2 = avg_price * 0.94  # -6%
                tp3 = avg_price * 0.92  # -8%
                tp4 = avg_price * 0.87  # -13%
                sl = avg_price * 1.055  # +5.5%
            
            # Get decimal precision from symbol info
            try:
                instruments = mirror_client.get_instruments_info(category="linear", symbol=symbol)
                tick_size = float(instruments['result']['list'][0]['priceFilter']['tickSize'])
                
                # Round to tick size
                def round_to_tick(price, tick):
                    return round(price / tick) * tick
                
                tp1 = round_to_tick(tp1, tick_size)
                tp2 = round_to_tick(tp2, tick_size)
                tp3 = round_to_tick(tp3, tick_size)
                tp4 = round_to_tick(tp4, tick_size)
                sl = round_to_tick(sl, tick_size)
                
            except:
                # Default rounding
                tp1 = round(tp1, 4)
                tp2 = round(tp2, 4)
                tp3 = round(tp3, 4)
                tp4 = round(tp4, 4)
                sl = round(sl, 4)
            
            position_data[symbol]['tp_prices'] = [str(tp1), str(tp2), str(tp3), str(tp4)]
            position_data[symbol]['sl_price'] = str(sl)
            
            print(f"  Calculated TP prices: {position_data[symbol]['tp_prices']}")
            print(f"  Calculated SL price: {position_data[symbol]['sl_price']}")
    
    print("\n=== FIXING MIRROR ACCOUNT ORDERS ===")
    
    for symbol, data in position_data.items():
        print(f"\n{symbol} - Fixing orders...")
        
        try:
            # Get current orders
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
            
            tp_prices = data['tp_prices']
            sl_price = data['sl_price']
            side = data['side']
            
            # Determine order side (opposite of position side)
            order_side = "Sell" if side == "Buy" else "Buy"
            
            # Fix TP orders
            fixed_count = 0
            for i, order in enumerate(tp_orders_sorted):
                if i < len(tp_prices) and float(order.get('triggerPrice', 0)) == 0:
                    order_id = order.get('orderId')
                    qty = order.get('qty')
                    link_id = order.get('orderLinkId', '')
                    
                    print(f"  Fixing TP{i+1} order {order_id[:8]}...")
                    try:
                        # Cancel broken order
                        mirror_client.cancel_order(
                            category="linear",
                            symbol=symbol,
                            orderId=order_id
                        )
                        
                        # Create new order with correct trigger price
                        new_link_id = link_id.replace('_REBAL_', '_FIXED_')
                        
                        mirror_client.place_order(
                            category="linear",
                            symbol=symbol,
                            side=order_side,
                            orderType="Market",
                            qty=qty,
                            triggerPrice=tp_prices[i],
                            triggerDirection=1 if side == "Buy" else 2,
                            triggerBy="LastPrice",
                            reduceOnly=True,
                            orderLinkId=new_link_id,
                            stopOrderType="TakeProfit"
                        )
                        print(f"  ✅ TP{i+1} fixed @ {tp_prices[i]}")
                        fixed_count += 1
                    except Exception as e:
                        print(f"  ❌ Error fixing TP{i+1}: {e}")
            
            # Fix SL order
            for order in sl_orders:
                if float(order.get('triggerPrice', 0)) == 0:
                    order_id = order.get('orderId')
                    qty = order.get('qty')
                    link_id = order.get('orderLinkId', '')
                    
                    print(f"  Fixing SL order {order_id[:8]}...")
                    try:
                        # Cancel broken order
                        mirror_client.cancel_order(
                            category="linear",
                            symbol=symbol,
                            orderId=order_id
                        )
                        
                        # Create new order
                        new_link_id = link_id.replace('_REBAL_', '_FIXED_')
                        
                        mirror_client.place_order(
                            category="linear",
                            symbol=symbol,
                            side=order_side,
                            orderType="Market",
                            qty=qty,
                            triggerPrice=sl_price,
                            triggerDirection=2 if side == "Buy" else 1,
                            triggerBy="LastPrice",
                            reduceOnly=True,
                            orderLinkId=new_link_id,
                            stopOrderType="StopLoss"
                        )
                        print(f"  ✅ SL fixed @ {sl_price}")
                        fixed_count += 1
                    except Exception as e:
                        print(f"  ❌ Error fixing SL: {e}")
            
            print(f"  Fixed {fixed_count} orders for {symbol}")
            
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
    
    # Verify the fixes
    print("\n=== VERIFYING FIXED ORDERS ===")
    
    for symbol in position_data.keys():
        try:
            response = mirror_client.get_open_orders(category="linear", symbol=symbol)
            orders = response.get('result', {}).get('list', [])
            
            print(f"\n{symbol} - Current orders:")
            
            for order in orders:
                order_type = order.get('stopOrderType', 'Limit')
                if order_type in ['TakeProfit', 'StopLoss']:
                    trigger_price = order.get('triggerPrice', 0)
                    qty = order.get('qty', 0)
                    print(f"  {order_type}: {trigger_price} (Qty: {qty})")
                    
        except Exception as e:
            print(f"Error verifying {symbol}: {e}")
    
    print("\n✅ Mirror order fix complete!")
    print("\n⚠️ IMPORTANT: Now you need to restart the bot to activate monitoring for these positions!")

asyncio.run(fix_mirror_orders_with_calculation())