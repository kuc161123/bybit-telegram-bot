#!/usr/bin/env python3
"""
Safely add missing mirror monitors without overwriting existing ones
"""
import pickle
import time
from decimal import Decimal
from execution.mirror_trader import bybit_client_2

def add_missing_mirror_monitors():
    """Add missing mirror monitors to pickle file directly"""
    
    # First, backup current file
    import shutil
    backup_name = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_before_mirror_fix_{int(time.time())}'
    shutil.copy2('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_name)
    print(f"✅ Created backup: {backup_name}")
    
    # Load current data
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    print(f"Current monitors: {len(enhanced_monitors)} (should be 18+)")
    
    # List of positions that need mirror monitors
    missing_mirror_positions = [
        ('1INCHUSDT', 'Buy'),
        ('AUCTIONUSDT', 'Buy'),
        ('HIGHUSDT', 'Buy'),
        ('NTRNUSDT', 'Buy'),
        ('WOOUSDT', 'Buy'),
        ('ZRXUSDT', 'Buy')
    ]
    
    # Get mirror positions
    try:
        mirror_positions = bybit_client_2.get_positions(category="linear", settleCoin="USDT")
        if mirror_positions['retCode'] != 0:
            print(f"Error getting mirror positions: {mirror_positions.get('retMsg')}")
            return
        
        created_count = 0
        
        for symbol, side in missing_mirror_positions:
            monitor_key = f"{symbol}_{side}_mirror"
            
            # Skip if already exists
            if monitor_key in enhanced_monitors:
                print(f"✅ Monitor already exists for {monitor_key}")
                continue
            
            # Find the position
            position_found = None
            for pos in mirror_positions['result']['list']:
                if pos['symbol'] == symbol and pos['side'] == side and float(pos.get('size', 0)) > 0:
                    position_found = pos
                    break
            
            if not position_found:
                print(f"⚠️  No active position found for {symbol} {side}")
                continue
            
            print(f"🔍 Creating monitor for {symbol} {side}")
            
            size = Decimal(str(position_found['size']))
            avg_price = Decimal(str(position_found.get('avgPrice', 0)))
            
            # Get orders
            orders_response = bybit_client_2.get_open_orders(
                category="linear",
                symbol=symbol
            )
            
            tp_orders = {}
            sl_order = None
            
            if orders_response['retCode'] == 0:
                for order in orders_response['result']['list']:
                    if order.get('stopOrderType') == 'TakeProfit' or (order.get('orderType') == 'Limit' and order.get('reduceOnly')):
                        order_id = order['orderId']
                        tp_orders[order_id] = {
                            'order_id': order_id,
                            'price': Decimal(str(order.get('price', 0))),
                            'quantity': Decimal(str(order.get('qty', 0))),
                            'order_link_id': order.get('orderLinkId', ''),
                            'status': order.get('orderStatus', 'Active')
                        }
                    elif order.get('stopOrderType') == 'StopLoss':
                        sl_order = {
                            'order_id': order['orderId'],
                            'price': Decimal(str(order.get('triggerPrice', 0))),
                            'quantity': Decimal(str(order.get('qty', 0))),
                            'order_link_id': order.get('orderLinkId', ''),
                            'status': order.get('orderStatus', 'Active')
                        }
            
            # Create monitor data
            monitor_data = {
                "symbol": symbol,
                "side": side,
                "position_size": size,
                "remaining_size": size,
                "entry_price": avg_price,
                "avg_price": avg_price,
                "approach": "conservative" if len(tp_orders) > 1 else "fast",
                "tp_orders": tp_orders,
                "sl_order": sl_order,
                "filled_tps": [],
                "cancelled_limits": False,
                "tp1_hit": False,
                "tp1_info": None,
                "sl_moved_to_be": False,
                "sl_move_attempts": 0,
                "created_at": time.time(),
                "last_check": time.time(),
                "limit_orders": [],
                "limit_orders_cancelled": False,
                "phase": "MONITORING",
                "chat_id": None,
                "account_type": "mirror",
                "has_mirror": True
            }
            
            # Add to monitors
            enhanced_monitors[monitor_key] = monitor_data
            created_count += 1
            print(f"✅ Added monitor for {symbol} {side} with {len(tp_orders)} TP orders")
        
        # Save back to file
        data['bot_data']['enhanced_tp_sl_monitors'] = enhanced_monitors
        
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        print(f"\n{'='*50}")
        print(f"Created {created_count} new mirror monitors")
        print(f"Total monitors now: {len(enhanced_monitors)}")
        
        # Verify counts
        main_count = sum(1 for k in enhanced_monitors.keys() if k.endswith('_main'))
        mirror_count = sum(1 for k in enhanced_monitors.keys() if k.endswith('_mirror'))
        print(f"Main monitors: {main_count}")
        print(f"Mirror monitors: {mirror_count}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    add_missing_mirror_monitors()