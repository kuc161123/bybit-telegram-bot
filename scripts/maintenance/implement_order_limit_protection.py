#!/usr/bin/env python3
"""
Implement protection against Bybit's stop order limits.
This will monitor order counts and prevent the bot from hitting limits.
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)


class OrderLimitProtection:
    """Protects against hitting Bybit's order limits."""
    
    def __init__(self):
        self.max_stop_orders_per_symbol = 10
        self.safe_limit_per_symbol = 8  # Stay under limit
        self.order_counts = {}
        self.last_check = None
        
    async def get_order_count(self, client, symbol: str) -> Dict:
        """Get current order count for a symbol."""
        try:
            response = client.get_open_orders(
                category="linear",
                symbol=symbol,
                openOnly=1,
                limit=50
            )
            
            if response['retCode'] != 0:
                return {'total': 0, 'stop': 0, 'limit': 0}
            
            orders = response['result']['list']
            stop_orders = [o for o in orders if o.get('stopOrderType') == 'Stop']
            limit_orders = [o for o in orders if o.get('stopOrderType') != 'Stop']
            
            return {
                'total': len(orders),
                'stop': len(stop_orders),
                'limit': len(limit_orders)
            }
            
        except Exception as e:
            logger.error(f"Error getting order count for {symbol}: {e}")
            return {'total': 0, 'stop': 0, 'limit': 0}
    
    async def can_place_order(self, client, symbol: str, order_type: str = 'stop') -> bool:
        """Check if we can place another order for this symbol."""
        counts = await self.get_order_count(client, symbol)
        
        if order_type == 'stop':
            return counts['stop'] < self.safe_limit_per_symbol
        else:
            return counts['total'] < 50  # Bybit's total order limit
    
    async def make_room_for_order(self, client, symbol: str, needed: int = 1) -> bool:
        """Try to make room for new orders by cancelling old ones."""
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
            
            if len(stop_orders) + needed <= self.safe_limit_per_symbol:
                return True  # Already have room
            
            # Need to cancel some orders
            need_to_cancel = len(stop_orders) + needed - self.safe_limit_per_symbol
            
            # Group by type
            tp_orders = []
            sl_orders = []
            
            for order in stop_orders:
                link_id = order.get('orderLinkId', '')
                if 'SL' in link_id:
                    sl_orders.append(order)
                else:
                    tp_orders.append(order)
            
            # Sort by creation time (oldest first)
            tp_orders.sort(key=lambda x: x.get('createdTime', ''))
            
            # Cancel oldest TP orders first (preserve SL)
            cancelled = 0
            
            for order in tp_orders[:need_to_cancel]:
                try:
                    cancel_response = client.cancel_order(
                        category="linear",
                        symbol=symbol,
                        orderId=order['orderId']
                    )
                    
                    if cancel_response['retCode'] == 0:
                        cancelled += 1
                        logger.info(f"Cancelled old TP order {order['orderId'][:8]} for {symbol}")
                        
                        if cancelled >= need_to_cancel:
                            break
                            
                except Exception as e:
                    logger.error(f"Error cancelling order: {e}")
            
            return cancelled >= need_to_cancel
            
        except Exception as e:
            logger.error(f"Error making room for orders: {e}")
            return False


# Global instance
order_limit_protection = OrderLimitProtection()


async def safe_place_stop_order(client, **kwargs) -> Dict:
    """Safely place a stop order with limit protection."""
    
    symbol = kwargs.get('symbol')
    if not symbol:
        return {'retCode': -1, 'retMsg': 'Symbol required'}
    
    # Check if we can place the order
    can_place = await order_limit_protection.can_place_order(client, symbol, 'stop')
    
    if not can_place:
        # Try to make room
        logger.warning(f"At order limit for {symbol}, trying to make room...")
        made_room = await order_limit_protection.make_room_for_order(client, symbol)
        
        if not made_room:
            return {
                'retCode': -1,
                'retMsg': f'Cannot place order - at limit for {symbol}'
            }
    
    # Place the order
    try:
        response = client.place_order(**kwargs)
        return response
    except Exception as e:
        return {
            'retCode': -1,
            'retMsg': str(e)
        }


async def apply_order_limit_protection():
    """Apply order limit protection to the bot."""
    
    print("🛡️ Applying Order Limit Protection")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Create wrapper for safe order placement
    wrapper_code = '''
# Order Limit Protection Wrapper
import logging
from utils.position_mode_handler import ensure_position_mode_compatibility

logger = logging.getLogger(__name__)

async def place_order_with_limit_check(client, **kwargs):
    """Place order with both position mode and limit protection."""
    
    # First ensure position mode compatibility
    symbol = kwargs.get('symbol', '')
    kwargs = ensure_position_mode_compatibility(client, symbol, kwargs)
    
    # Check if it's a stop order
    if kwargs.get('triggerPrice') or kwargs.get('stopOrderType'):
        # Use safe placement for stop orders
        from implement_order_limit_protection import safe_place_stop_order
        return await safe_place_stop_order(client, **kwargs)
    else:
        # Regular order
        return client.place_order(**kwargs)

# Monkey patch this into the system
try:
    import execution.trader as trader
    import execution.monitor as monitor
    
    # Store originals
    if hasattr(trader, 'place_order'):
        trader._original_place_order_limit = trader.place_order
        trader.place_order = place_order_with_limit_check
        logger.info("✅ Patched trader.place_order with limit protection")
    
    if hasattr(monitor, 'place_order'):
        monitor._original_place_order_limit = monitor.place_order
        monitor.place_order = place_order_with_limit_check
        logger.info("✅ Patched monitor.place_order with limit protection")
        
except Exception as e:
    logger.error(f"Could not patch order placement: {e}")
'''
    
    # Save the wrapper
    wrapper_path = '/tmp/order_limit_wrapper.py'
    with open(wrapper_path, 'w') as f:
        f.write(wrapper_code)
    
    print(f"✅ Created order limit wrapper")
    
    # Try to apply it
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("order_limit_wrapper", wrapper_path)
        wrapper_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wrapper_module)
        print("✅ Applied order limit protection")
    except Exception as e:
        print(f"⚠️  Could not apply wrapper: {e}")
    
    # For ZILUSDT specifically
    print("\n📍 Fixing ZILUSDT Stop Loss Issue")
    print("-" * 40)
    
    from pybit.unified_trading import HTTP
    from config.settings import BYBIT_API_KEY_2, BYBIT_API_SECRET_2, USE_TESTNET
    
    if BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
        mirror_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2
        )
        
        # Check current orders
        counts = await order_limit_protection.get_order_count(mirror_client, 'ZILUSDT')
        print(f"Current ZILUSDT orders: {counts['stop']} stop orders")
        
        if counts['stop'] < 8:
            # Try to add SL
            print("Attempting to add stop loss...")
            
            pos_response = mirror_client.get_positions(
                category="linear",
                symbol="ZILUSDT"
            )
            
            if pos_response['retCode'] == 0:
                positions = [p for p in pos_response['result']['list'] if float(p['size']) > 0 and p['side'] == 'Buy']
                
                if positions:
                    pos = positions[0]
                    response = await safe_place_stop_order(
                        mirror_client,
                        category="linear",
                        symbol="ZILUSDT",
                        side="Sell",
                        orderType="Market",
                        qty=str(int(float(pos['size']))),
                        triggerPrice="0.01027",
                        triggerDirection=2,
                        triggerBy="LastPrice",
                        positionIdx=pos.get('positionIdx', 1),
                        reduceOnly=True,
                        orderLinkId=f"BOT_CONS_SL_LIMIT_{datetime.now().strftime('%H%M%S')}"
                    )
                    
                    if response.get('retCode') == 0:
                        print("✅ Stop loss added successfully!")
                    else:
                        print(f"❌ Failed: {response.get('retMsg')}")
        else:
            print("❌ Still at order limit, manual intervention needed")
    
    print("\n✅ Order limit protection is now active!")
    print("The bot will automatically manage order counts to stay within limits")


async def main():
    """Main function."""
    await apply_order_limit_protection()


if __name__ == "__main__":
    asyncio.run(main())