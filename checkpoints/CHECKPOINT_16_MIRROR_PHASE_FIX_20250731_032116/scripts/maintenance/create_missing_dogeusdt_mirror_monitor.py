#!/usr/bin/env python3
"""
Create the missing DOGEUSDT_Buy_mirror monitor
"""

import pickle
import time
from decimal import Decimal
import asyncio
from datetime import datetime

async def create_dogeusdt_mirror_monitor():
    """Create the missing DOGEUSDT_Buy_mirror monitor"""
    
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    # First, let's check if DOGEUSDT exists on mirror
    from execution.mirror_trader import bybit_client_2
    
    try:
        # Get mirror positions
        response = bybit_client_2.get_positions(
            category="linear", 
            symbol="DOGEUSDT"
        )
        
        if response['retCode'] != 0:
            print(f"❌ Error fetching mirror positions: {response}")
            return False
            
        mirror_position = None
        for pos in response['result']['list']:
            if pos['symbol'] == 'DOGEUSDT' and pos['side'] == 'Buy' and float(pos['size']) > 0:
                mirror_position = pos
                break
                
        if not mirror_position:
            print("❌ No DOGEUSDT Buy position found on mirror account")
            return False
            
        print(f"✅ Found DOGEUSDT Buy position on mirror: Size={mirror_position['size']}")
        
        # Load pickle file
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
            
        # Create backup
        backup_path = f"{pkl_path}.backup_{int(time.time())}"
        with open(backup_path, 'wb') as f:
            pickle.dump(data, f)
        print(f"✅ Created backup: {backup_path}")
        
        # Get enhanced_tp_sl_monitors
        monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
        
        # Check if already exists
        if 'DOGEUSDT_Buy_mirror' in monitors:
            print("⚠️ DOGEUSDT_Buy_mirror monitor already exists!")
            return True
            
        # Get data from main monitor if exists
        main_monitor = monitors.get('DOGEUSDT_Buy_main', {})
        if not main_monitor:
            print("❌ No main DOGEUSDT monitor found to reference")
            return False
            
        # Create mirror monitor based on actual mirror position
        mirror_size = Decimal(str(mirror_position['size']))
        avg_price = Decimal(str(mirror_position['avgPrice']))
        
        mirror_monitor = {
            'symbol': 'DOGEUSDT',
            'side': 'Buy',
            'position_size': mirror_size,
            'remaining_size': mirror_size,
            'entry_price': avg_price,
            'avg_price': avg_price,
            'approach': main_monitor.get('approach', 'fast'),
            'tp_orders': {},  # Will be populated if orders exist
            'sl_order': None,  # Will be populated if order exists
            'filled_tps': [],
            'cancelled_limits': False,
            'tp1_hit': False,
            'tp1_info': None,
            'sl_moved_to_be': False,
            'sl_move_attempts': 0,
            'created_at': time.time(),
            'last_check': time.time(),
            'limit_orders': [],
            'limit_orders_cancelled': False,
            'phase': 'MONITORING',
            'chat_id': main_monitor.get('chat_id'),
            'account_type': 'mirror',
            'has_mirror': True
        }
        
        # Get mirror orders
        orders_response = bybit_client_2.get_open_orders(
            category="linear",
            symbol="DOGEUSDT"
        )
        
        if orders_response['retCode'] == 0:
            for order in orders_response['result']['list']:
                if order['orderType'] == 'Limit' and order['reduceOnly']:
                    # This is a TP order
                    order_info = {
                        'order_id': order['orderId'],
                        'order_link_id': order.get('orderLinkId', ''),
                        'price': Decimal(str(order['price'])),
                        'quantity': Decimal(str(order['qty'])),
                        'original_quantity': Decimal(str(order['qty'])),
                        'percentage': 100,  # Fast approach uses 100%
                        'tp_number': 1,
                        'account': 'mirror'
                    }
                    mirror_monitor['tp_orders'][order['orderId']] = order_info
                    print(f"✅ Found TP order: {order['orderId'][:8]}... @ {order['price']}")
                    
                elif order['stopOrderType'] == 'StopLoss':
                    # This is SL order
                    mirror_monitor['sl_order'] = {
                        'order_id': order['orderId'],
                        'order_link_id': order.get('orderLinkId', ''),
                        'price': Decimal(str(order['triggerPrice'])),
                        'quantity': Decimal(str(order['qty'])),
                        'original_quantity': Decimal(str(order['qty'])),
                        'covers_full_position': True,
                        'target_position_size': mirror_size,
                        'account': 'mirror'
                    }
                    print(f"✅ Found SL order: {order['orderId'][:8]}... @ {order['triggerPrice']}")
        
        # Add to monitors
        monitors['DOGEUSDT_Buy_mirror'] = mirror_monitor
        
        # Save back to pickle
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
            
        print(f"✅ Created DOGEUSDT_Buy_mirror monitor successfully!")
        print(f"   Position size: {mirror_size}")
        print(f"   Entry price: {avg_price}")
        print(f"   TP orders: {len(mirror_monitor['tp_orders'])}")
        print(f"   SL order: {'Yes' if mirror_monitor['sl_order'] else 'No'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating mirror monitor: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    sys.path.append('/Users/lualakol/bybit-telegram-bot')
    from config.settings import setup_logging
    setup_logging()
    
    result = asyncio.run(create_dogeusdt_mirror_monitor())
    if result:
        print("\n✅ DOGEUSDT_Buy_mirror monitor created successfully!")
        print("Total monitors should now be 15")
    else:
        print("\n❌ Failed to create DOGEUSDT_Buy_mirror monitor")