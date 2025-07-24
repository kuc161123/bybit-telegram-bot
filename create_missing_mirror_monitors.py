#!/usr/bin/env python3
"""
Create missing mirror monitors for positions without them
"""
import asyncio
import pickle
import time
from decimal import Decimal
from execution.mirror_trader import bybit_client_2
from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
from clients.bybit_helpers import get_open_orders

async def create_missing_mirror_monitors():
    """Create monitors for mirror positions that don't have them"""
    
    # Get mirror positions
    try:
        mirror_positions = bybit_client_2.get_positions(category="linear", settleCoin="USDT")
        if mirror_positions['retCode'] != 0:
            print(f"Error getting mirror positions: {mirror_positions.get('retMsg')}")
            return
            
        # Load current monitors
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        created_count = 0
        
        for pos in mirror_positions['result']['list']:
            if float(pos.get('size', 0)) <= 0:
                continue
                
            symbol = pos['symbol']
            side = pos['side']
            size = Decimal(str(pos['size']))
            avg_price = Decimal(str(pos.get('avgPrice', 0)))
            
            # Check if monitor exists
            monitor_key = f"{symbol}_{side}_mirror"
            if monitor_key in enhanced_monitors:
                print(f"✅ Monitor already exists for {symbol} {side} mirror")
                continue
            
            print(f"🔍 Creating monitor for mirror position: {symbol} {side}")
            
            # Get orders for this position
            orders_response = bybit_client_2.get_open_orders(
                category="linear",
                symbol=symbol
            )
            
            tp_orders = {}
            sl_order = None
            
            if orders_response['retCode'] == 0:
                for order in orders_response['result']['list']:
                    if order.get('stopOrderType') == 'TakeProfit' or order.get('orderType') == 'Limit' and order.get('reduceOnly'):
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
                "chat_id": None,  # Will use DEFAULT_ALERT_CHAT_ID if set
                "account_type": "mirror",
                "has_mirror": True
            }
            
            # Add to enhanced monitors
            enhanced_tp_sl_manager.position_monitors[monitor_key] = monitor_data
            
            # Save to persistence
            await enhanced_tp_sl_manager._save_to_persistence()
            
            # Start monitoring task
            monitor_task = asyncio.create_task(
                enhanced_tp_sl_manager._run_monitor_loop(symbol, side, "mirror")
            )
            
            created_count += 1
            print(f"✅ Created monitor for {symbol} {side} mirror with {len(tp_orders)} TP orders")
            
        print(f"\n{'='*50}")
        print(f"Created {created_count} new mirror monitors")
        print(f"Total monitors now: {len(enhanced_tp_sl_manager.position_monitors)}")
        
    except Exception as e:
        print(f"Error creating mirror monitors: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(create_missing_mirror_monitors())