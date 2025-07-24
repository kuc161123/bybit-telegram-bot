import asyncio
import os
from pybit.unified_trading import HTTP
import json

async def fix_mirror_orders_properly():
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
            size = float(pos.get('size', 0))
            
            position_data[symbol] = {
                'side': side,
                'avg_price': avg_price,
                'size': size
            }
            
            print(f"\n{symbol}:")
            print(f"  Side: {side}")
            print(f"  Avg Price: {avg_price}")
            print(f"  Size: {size}")
            
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
    
    print("\n=== CANCELLING BROKEN ORDERS AND CREATING NEW ONES ===")
    
    for symbol, data in position_data.items():
        print(f"\n{symbol} - Processing orders...")
        
        try:
            # Get current orders
            response = mirror_client.get_open_orders(category="linear", symbol=symbol)
            orders = response.get('result', {}).get('list', [])
            
            # Find orders with price 0 that should be TP/SL
            orders_to_cancel = []
            for order in orders:
                price = float(order.get('price', 0))
                link_id = order.get('orderLinkId', '')
                if price == 0 and ('_TP' in link_id or '_SL' in link_id):
                    orders_to_cancel.append(order)
            
            print(f"  Found {len(orders_to_cancel)} broken orders to fix")
            
            # Cancel all broken orders first
            for order in orders_to_cancel:
                order_id = order.get('orderId')
                try:
                    mirror_client.cancel_order(
                        category="linear",
                        symbol=symbol,
                        orderId=order_id
                    )
                    print(f"  ✅ Cancelled order {order_id[:8]}...")
                except Exception as e:
                    print(f"  ❌ Error cancelling order {order_id[:8]}: {e}")
            
            # Now create new conditional orders
            tp_prices = data['tp_prices']
            sl_price = data['sl_price']
            side = data['side']
            total_size = data['size']
            
            # Calculate quantities for conservative approach
            tp1_qty = str(round(total_size * 0.85, 1))
            tp2_qty = str(round(total_size * 0.05, 1))
            tp3_qty = str(round(total_size * 0.05, 1))
            tp4_qty = str(round(total_size * 0.05, 1))
            sl_qty = str(total_size)
            
            # Determine order side (opposite of position side)
            order_side = "Sell" if side == "Buy" else "Buy"
            
            print("\n  Creating new conditional orders...")
            
            # Create TP orders
            tp_quantities = [tp1_qty, tp2_qty, tp3_qty, tp4_qty]
            for i, (tp_price, qty) in enumerate(zip(tp_prices, tp_quantities)):
                try:
                    result = mirror_client.place_order(
                        category="linear",
                        symbol=symbol,
                        side=order_side,
                        orderType="Market",
                        qty=qty,
                        triggerPrice=tp_price,
                        triggerDirection=1 if side == "Buy" else 2,
                        triggerBy="LastPrice",
                        reduceOnly=True,
                        orderLinkId=f"MIRROR_BOT_CONS_TP{i+1}_FIXED_{symbol[:4]}_{str(int(asyncio.get_event_loop().time() * 1000))[-6:]}",
                        stopOrderType="TakeProfit"
                    )
                    print(f"  ✅ Created TP{i+1} @ {tp_price} for {qty} units")
                except Exception as e:
                    print(f"  ❌ Error creating TP{i+1}: {e}")
            
            # Create SL order
            try:
                result = mirror_client.place_order(
                    category="linear",
                    symbol=symbol,
                    side=order_side,
                    orderType="Market",
                    qty=sl_qty,
                    triggerPrice=sl_price,
                    triggerDirection=2 if side == "Buy" else 1,
                    triggerBy="LastPrice",
                    reduceOnly=True,
                    orderLinkId=f"MIRROR_BOT_CONS_SL_FIXED_{symbol[:4]}_{str(int(asyncio.get_event_loop().time() * 1000))[-6:]}",
                    stopOrderType="StopLoss"
                )
                print(f"  ✅ Created SL @ {sl_price} for {sl_qty} units")
            except Exception as e:
                print(f"  ❌ Error creating SL: {e}")
                
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
    
    # Verify the fixes
    print("\n=== VERIFYING FIXED ORDERS ===")
    
    for symbol in position_data.keys():
        try:
            response = mirror_client.get_open_orders(category="linear", symbol=symbol)
            orders = response.get('result', {}).get('list', [])
            
            print(f"\n{symbol} - Current orders:")
            
            tp_count = 0
            sl_count = 0
            limit_count = 0
            
            for order in orders:
                order_type = order.get('stopOrderType', '')
                if order_type == 'TakeProfit':
                    tp_count += 1
                    trigger_price = order.get('triggerPrice', 0)
                    qty = order.get('qty', 0)
                    print(f"  TP @ {trigger_price}: Qty={qty}")
                elif order_type == 'StopLoss':
                    sl_count += 1
                    trigger_price = order.get('triggerPrice', 0)
                    qty = order.get('qty', 0)
                    print(f"  SL @ {trigger_price}: Qty={qty}")
                else:
                    price = order.get('price', 0)
                    if float(price) > 0:  # Only show real limit orders
                        limit_count += 1
            
            print(f"  Summary: {tp_count} TPs, {sl_count} SL, {limit_count} limit orders")
                    
        except Exception as e:
            print(f"Error verifying {symbol}: {e}")
    
    print("\n✅ Mirror order fix complete!")
    print("\n⚠️ IMPORTANT: Now you need to restart the bot to activate monitoring for these positions!")

asyncio.run(fix_mirror_orders_properly())