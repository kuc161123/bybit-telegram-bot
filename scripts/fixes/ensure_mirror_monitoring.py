#!/usr/bin/env python3
"""
Ensure proper monitoring for mirror account positions.
This script checks mirror positions and creates monitors if missing.
"""

import asyncio
import os
import logging
from pybit.unified_trading import HTTP
import pickle
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_mirror_positions():
    """Get all active positions from mirror account."""
    try:
        # Get mirror account credentials
        api_key = os.getenv('BYBIT_API_KEY_2')
        api_secret = os.getenv('BYBIT_API_SECRET_2')
        testnet = os.getenv('USE_TESTNET', 'false').lower() == 'true'
        
        if not api_key or not api_secret:
            logger.error("Mirror account credentials not found!")
            return []
        
        # Create client
        client = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret
        )
        
        # Get positions
        response = client.get_positions(category="linear", settleCoin="USDT")
        positions = response.get('result', {}).get('list', [])
        
        active_positions = []
        for pos in positions:
            if float(pos.get('size', 0)) > 0:
                active_positions.append({
                    'symbol': pos.get('symbol'),
                    'side': pos.get('side'),
                    'size': float(pos.get('size', 0)),
                    'avgPrice': float(pos.get('avgPrice', 0)),
                    'unrealisedPnl': float(pos.get('unrealisedPnl', 0)),
                    'positionIdx': pos.get('positionIdx', 0)
                })
        
        return active_positions
        
    except Exception as e:
        logger.error(f"Error getting mirror positions: {e}")
        return []

async def ensure_mirror_orders_have_trigger_prices(symbol: str):
    """Ensure all TP/SL orders for a symbol have proper trigger prices."""
    try:
        # Get mirror account credentials
        api_key = os.getenv('BYBIT_API_KEY_2')
        api_secret = os.getenv('BYBIT_API_SECRET_2')
        testnet = os.getenv('USE_TESTNET', 'false').lower() == 'true'
        
        client = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret
        )
        
        # Get orders
        response = client.get_open_orders(category="linear", symbol=symbol)
        orders = response.get('result', {}).get('list', [])
        
        issues = []
        for order in orders:
            order_type = order.get('stopOrderType', '')
            if order_type in ['TakeProfit', 'StopLoss']:
                trigger_price = float(order.get('triggerPrice', 0))
                if trigger_price == 0:
                    issues.append({
                        'orderId': order.get('orderId'),
                        'type': order_type,
                        'qty': order.get('qty')
                    })
        
        if issues:
            logger.warning(f"⚠️ {symbol} has {len(issues)} orders with 0 trigger price!")
            return False
        else:
            logger.info(f"✅ {symbol} orders have proper trigger prices")
            return True
            
    except Exception as e:
        logger.error(f"Error checking {symbol} orders: {e}")
        return False

async def create_mirror_monitor_entry(position: dict, chat_id: int = 5634913742):
    """Create a monitor entry for a mirror position."""
    try:
        # Load bot data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            bot_data = pickle.load(f)
        
        if 'chat_data' not in bot_data:
            bot_data['chat_data'] = {}
        
        if chat_id not in bot_data['chat_data']:
            bot_data['chat_data'][chat_id] = {}
        
        chat_data = bot_data['chat_data'][chat_id]
        
        # Ensure monitor task data structure exists
        if 'active_monitor_task_data_v2' not in chat_data:
            chat_data['active_monitor_task_data_v2'] = {}
        
        symbol = position['symbol']
        monitor_key = f"{chat_id}_{symbol}_conservative"
        
        # Check if monitor already exists
        if monitor_key in chat_data['active_monitor_task_data_v2']:
            logger.info(f"Monitor already exists for {symbol}")
            return True
        
        # Create monitor entry
        monitor_data = {
            'symbol': symbol,
            'side': position['side'],
            'approach': 'conservative',
            '_chat_id': chat_id,
            'account': 'mirror',
            'position_size': position['size'],
            'avg_price': position['avgPrice'],
            'monitoring_mode': 'MIRROR-BOT-CONSERVATIVE',
            'created_at': datetime.now().isoformat(),
            'active': True
        }
        
        chat_data['active_monitor_task_data_v2'][monitor_key] = monitor_data
        
        # Also add to monitor_tasks if needed
        if 'monitor_tasks' not in bot_data:
            bot_data['monitor_tasks'] = {}
        
        bot_data['monitor_tasks'][monitor_key] = {
            'active': True,
            'symbol': symbol,
            'approach': 'conservative',
            'account': 'mirror'
        }
        
        # Save updated data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(bot_data, f)
        
        logger.info(f"✅ Created monitor entry for mirror position {symbol}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating monitor entry: {e}")
        return False

async def main():
    """Main function to ensure mirror monitoring."""
    logger.info("=== ENSURING MIRROR ACCOUNT MONITORING ===")
    
    # Get mirror positions
    positions = await get_mirror_positions()
    
    if not positions:
        logger.info("No active mirror positions found")
        return
    
    logger.info(f"Found {len(positions)} active mirror positions:")
    
    needs_restart = False
    
    for pos in positions:
        symbol = pos['symbol']
        logger.info(f"\n{symbol}:")
        logger.info(f"  Side: {pos['side']}")
        logger.info(f"  Size: {pos['size']}")
        logger.info(f"  Avg Price: {pos['avgPrice']}")
        logger.info(f"  Unrealized PnL: ${pos['unrealisedPnl']:.2f}")
        
        # Check orders have proper trigger prices
        orders_ok = await ensure_mirror_orders_have_trigger_prices(symbol)
        
        if not orders_ok:
            logger.warning(f"  ⚠️ {symbol} needs order fixes!")
            needs_restart = True
        
        # Ensure monitor exists
        monitor_created = await create_mirror_monitor_entry(pos)
        if monitor_created:
            needs_restart = True
    
    if needs_restart:
        logger.info("\n⚠️ IMPORTANT: Restart the bot to activate monitoring for mirror positions!")
        logger.info("Run: python main.py")
    else:
        logger.info("\n✅ All mirror positions have proper monitoring")

if __name__ == "__main__":
    asyncio.run(main())