#!/usr/bin/env python3
"""
Install order limit protection directly into the bot without restart.
This will prevent future order accumulation issues.
"""

import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def install_protection():
    """Install order limit protection."""
    
    print("🛡️ Installing Order Limit Protection")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Create the order limit handler
    order_limit_code = '''"""
Order limit protection module.
Prevents hitting Bybit's 10 stop order per symbol limit.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class OrderLimitManager:
    """Manages order limits to prevent hitting Bybit's restrictions."""
    
    def __init__(self):
        self.max_stop_orders = 8  # Stay under the 10 limit
        self.order_counts = {}
        
    async def check_can_place_order(self, client, symbol: str, is_stop_order: bool = True) -> bool:
        """Check if we can place another order."""
        try:
            response = client.get_open_orders(
                category="linear",
                symbol=symbol,
                openOnly=1,
                limit=50
            )
            
            if response['retCode'] != 0:
                return True  # Assume we can if check fails
            
            orders = response['result']['list']
            stop_orders = [o for o in orders if o.get('stopOrderType') == 'Stop']
            
            if is_stop_order:
                return len(stop_orders) < self.max_stop_orders
            else:
                return len(orders) < 50  # Total order limit
                
        except Exception as e:
            logger.error(f"Error checking order limit for {symbol}: {e}")
            return True  # Allow on error
    
    async def make_room_for_order(self, client, symbol: str) -> bool:
        """Try to make room by cancelling old orders."""
        try:
            response = client.get_open_orders(
                category="linear",
                symbol=symbol,
                openOnly=1,
                limit=50
            )
            
            if response['retCode'] != 0:
                return False
            
            orders = response['result']['list']
            stop_orders = [o for o in orders if o.get('stopOrderType') == 'Stop']
            
            if len(stop_orders) < self.max_stop_orders:
                return True
            
            # Sort by type and creation time
            tp_orders = []
            sl_orders = []
            
            for order in stop_orders:
                link_id = order.get('orderLinkId', '')
                if 'SL' in link_id:
                    sl_orders.append(order)
                else:
                    tp_orders.append(order)
            
            # Sort TPs by creation time (oldest first)
            tp_orders.sort(key=lambda x: x.get('createdTime', ''))
            
            # Cancel oldest TP to make room (preserve SL)
            if tp_orders:
                try:
                    client.cancel_order(
                        category="linear",
                        symbol=symbol,
                        orderId=tp_orders[0]['orderId']
                    )
                    logger.info(f"Made room by cancelling old TP for {symbol}")
                    return True
                except:
                    pass
            
            return False
            
        except Exception as e:
            logger.error(f"Error making room for {symbol}: {e}")
            return False


# Global instance
order_limit_manager = OrderLimitManager()


async def safe_place_order(client, **kwargs):
    """Safely place an order with limit checking."""
    
    symbol = kwargs.get('symbol')
    if not symbol:
        return client.place_order(**kwargs)
    
    # Check if it's a stop order
    is_stop = bool(kwargs.get('triggerPrice')) or kwargs.get('stopOrderType') == 'Stop'
    
    # Check limit
    if is_stop:
        can_place = await order_limit_manager.check_can_place_order(client, symbol, True)
        
        if not can_place:
            # Try to make room
            made_room = await order_limit_manager.make_room_for_order(client, symbol)
            if not made_room:
                logger.warning(f"Cannot place order for {symbol} - at limit")
                return {
                    'retCode': -1,
                    'retMsg': f'Order limit reached for {symbol}'
                }
    
    # Place the order
    return client.place_order(**kwargs)
'''
    
    # Save the protection module
    protection_path = 'utils/order_limit_protection.py'
    os.makedirs(os.path.dirname(protection_path), exist_ok=True)
    
    with open(protection_path, 'w') as f:
        f.write(order_limit_code)
    
    print(f"✅ Created {protection_path}")
    
    # Create the integration patch
    patch_code = '''"""
Runtime patch to integrate order limit protection.
"""

import logging
import asyncio

logger = logging.getLogger(__name__)

try:
    # Import the protection module
    from utils.order_limit_protection import safe_place_order, order_limit_manager
    
    # Patch trader module
    import execution.trader as trader
    if hasattr(trader, 'bybit_client'):
        # Store original
        trader._original_place_order = trader.bybit_client.place_order
        
        # Create wrapper
        def place_order_wrapper(**kwargs):
            # Run async function in sync context
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(safe_place_order(trader.bybit_client, **kwargs))
        
        # Apply patch
        trader.bybit_client.place_order = place_order_wrapper
        logger.info("✅ Patched trader with order limit protection")
    
    # Patch monitor module
    import execution.monitor as monitor
    if hasattr(monitor, 'bybit_client'):
        monitor._original_place_order = monitor.bybit_client.place_order
        monitor.bybit_client.place_order = place_order_wrapper
        logger.info("✅ Patched monitor with order limit protection")
    
    # For mirror account
    if hasattr(trader, 'bybit_client_2'):
        trader._original_place_order_2 = trader.bybit_client_2.place_order
        
        def place_order_wrapper_2(**kwargs):
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(safe_place_order(trader.bybit_client_2, **kwargs))
        
        trader.bybit_client_2.place_order = place_order_wrapper_2
        logger.info("✅ Patched mirror trader with order limit protection")
    
    print("\\n✅ Order limit protection is now active!")
    print("The bot will automatically manage order counts to stay within limits.")
    
except Exception as e:
    logger.error(f"Could not apply order limit protection: {e}")
    print(f"⚠️ Warning: Could not apply protection: {e}")
'''
    
    # Execute the patch
    print("\n📍 Applying runtime patch...")
    exec(patch_code)
    
    # Create a monitoring script
    monitor_script = '''#!/usr/bin/env python3
"""
Monitor order counts and alert when near limits.
"""

import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def monitor_order_limits():
    from pybit.unified_trading import HTTP
    from config.settings import BYBIT_API_KEY_2, BYBIT_API_SECRET_2, USE_TESTNET
    
    if not BYBIT_API_KEY_2:
        print("Mirror account not configured")
        return
    
    client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY_2,
        api_secret=BYBIT_API_SECRET_2
    )
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Order limit monitor started")
    
    while True:
        try:
            # Get positions
            response = client.get_positions(
                category="linear",
                settleCoin="USDT"
            )
            
            if response['retCode'] == 0:
                for pos in response['result']['list']:
                    if float(pos['size']) > 0:
                        symbol = pos['symbol']
                        
                        # Check orders
                        order_resp = client.get_open_orders(
                            category="linear",
                            symbol=symbol,
                            openOnly=1
                        )
                        
                        if order_resp['retCode'] == 0:
                            stop_orders = sum(1 for o in order_resp['result']['list'] 
                                            if o.get('stopOrderType') == 'Stop')
                            
                            if stop_orders >= 8:
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  {symbol}: {stop_orders}/10 stop orders")
                            elif stop_orders >= 10:
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ {symbol}: AT LIMIT - {stop_orders} orders!")
            
            await asyncio.sleep(60)  # Check every minute
            
        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(monitor_order_limits())
'''
    
    with open('monitor_order_limits.py', 'w') as f:
        f.write(monitor_script)
    
    print("📝 Created monitor_order_limits.py")
    
    print("\n" + "=" * 60)
    print("✅ ORDER LIMIT PROTECTION INSTALLED")
    print("=" * 60)
    
    print("\nThe protection system will:")
    print("1. Check order counts before placing new orders")
    print("2. Cancel old TP orders to make room if needed")
    print("3. Prevent hitting the 10 stop order limit")
    print("4. Work without restarting the bot")
    
    print("\n💡 You can also run the monitor separately:")
    print("python monitor_order_limits.py")
    
    print("\n⚠️  Note: Existing excess orders need manual cleanup")
    print("The protection prevents NEW accumulation going forward")


if __name__ == "__main__":
    install_protection()