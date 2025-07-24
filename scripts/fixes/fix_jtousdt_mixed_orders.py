#!/usr/bin/env python3
"""
Fix JTOUSDT mixed Fast/Conservative orders issue.
This script will:
1. Cancel all existing JTOUSDT orders
2. Remove all JTOUSDT monitors 
3. Let the bot recreate proper monitoring
"""
import asyncio
import logging
import pickle
from datetime import datetime
from clients.bybit_client import bybit_client
from clients.bybit_helpers import get_all_positions, get_all_open_orders
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_jtousdt():
    """Fix the mixed orders issue for JTOUSDT"""
    logger.info("🔧 Starting JTOUSDT fix...")
    
    # Step 1: Create backup
    dashboard_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'backup_{timestamp}_jtousdt_fix_{dashboard_file}'
    
    try:
        import shutil
        shutil.copy2(dashboard_file, backup_file)
        logger.info(f"✅ Backup created: {backup_file}")
    except Exception as e:
        logger.error(f"❌ Failed to create backup: {e}")
        return
    
    # Step 2: Get current position and orders
    positions = await get_all_positions()
    orders = await get_all_open_orders()
    
    # Find JTOUSDT position
    jto_position = None
    for pos in positions:
        if pos['symbol'] == 'JTOUSDT' and float(pos.get('size', 0)) > 0:
            jto_position = pos
            break
    
    if not jto_position:
        logger.warning("No active JTOUSDT position found")
        return
    
    # Find JTOUSDT orders
    jto_orders = [o for o in orders if o['symbol'] == 'JTOUSDT']
    logger.info(f"Found {len(jto_orders)} JTOUSDT orders to cancel")
    
    # Step 3: Cancel all JTOUSDT orders
    cancelled_count = 0
    for order in jto_orders:
        try:
            logger.info(f"Cancelling order {order['orderId']} (linkId: {order.get('orderLinkId', '')})")
            bybit_client.cancel_order(
                category="linear",
                symbol="JTOUSDT",
                orderId=order['orderId']
            )
            cancelled_count += 1
            await asyncio.sleep(0.1)  # Small delay between cancellations
        except Exception as e:
            logger.error(f"Failed to cancel order {order['orderId']}: {e}")
    
    logger.info(f"✅ Cancelled {cancelled_count}/{len(jto_orders)} orders")
    
    # Step 4: Cancel mirror orders if enabled
    if is_mirror_trading_enabled():
        logger.info("Checking mirror account...")
        mirror_orders = await get_mirror_orders()
        mirror_jto_orders = [o for o in mirror_orders if o['symbol'] == 'JTOUSDT']
        
        for order in mirror_jto_orders:
            try:
                logger.info(f"Cancelling mirror order {order['orderId']}")
                bybit_client_2.cancel_order(
                    category="linear",
                    symbol="JTOUSDT",
                    orderId=order['orderId']
                )
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Failed to cancel mirror order {order['orderId']}: {e}")
    
    # Step 5: Remove all JTOUSDT monitors from persistence
    try:
        with open(dashboard_file, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        monitor_tasks = bot_data.get('monitor_tasks', {})
        
        # Find and remove JTOUSDT monitors
        monitors_to_remove = []
        for key, info in monitor_tasks.items():
            if isinstance(info, dict) and info.get('symbol') == 'JTOUSDT':
                monitors_to_remove.append(key)
        
        for key in monitors_to_remove:
            del monitor_tasks[key]
            logger.info(f"Removed monitor: {key}")
        
        # Save updated data
        with open(dashboard_file, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"✅ Removed {len(monitors_to_remove)} JTOUSDT monitors")
        
    except Exception as e:
        logger.error(f"Error updating persistence: {e}")
    
    logger.info("\n✅ JTOUSDT fix complete!")
    logger.info("The bot will automatically recreate proper monitoring on next update.")
    logger.info("Please decide whether you want Fast or Conservative approach and place a new trade.")

async def get_mirror_orders():
    """Get orders from mirror account"""
    try:
        from clients.bybit_helpers import api_call_with_retry
        order_response = await api_call_with_retry(
            lambda: bybit_client_2.get_open_orders(
                category="linear",
                settleCoin="USDT"
            ),
            timeout=30
        )
        return order_response.get("result", {}).get("list", []) if order_response and order_response.get("retCode") == 0 else []
    except Exception as e:
        logger.error(f"Error getting mirror orders: {e}")
        return []

if __name__ == "__main__":
    asyncio.run(fix_jtousdt())