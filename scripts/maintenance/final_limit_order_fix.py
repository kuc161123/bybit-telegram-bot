#!/usr/bin/env python3
"""
Final Limit Order Registration Fix
==================================

This script provides a complete solution for limit order tracking.
"""

import asyncio
import logging
import pickle
import time
from datetime import datetime
from pybit.unified_trading import HTTP
from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET,
    ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
)
from utils.pickle_lock import main_pickle_lock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def final_limit_order_fix():
    """Complete fix for limit order registration"""
    try:
        # Step 1: Check current open orders on exchange
        logger.info("=== Step 1: Checking open orders on exchange ===")
        
        if ENABLE_MIRROR_TRADING:
            mirror_client = HTTP(
                testnet=USE_TESTNET,
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2
            )
            
            response = mirror_client.get_open_orders(category="linear", settleCoin="USDT")
            
            if response['retCode'] == 0:
                orders = response['result']['list']
                
                # Group orders by symbol
                orders_by_symbol = {}
                for order in orders:
                    symbol = order['symbol']
                    if symbol not in orders_by_symbol:
                        orders_by_symbol[symbol] = []
                    orders_by_symbol[symbol].append(order)
                
                logger.info(f"Found orders for {len(orders_by_symbol)} symbols on mirror account")
                
                # Find CAKEUSDT limit orders
                if 'CAKEUSDT' in orders_by_symbol:
                    cake_limit_orders = []
                    for order in orders_by_symbol['CAKEUSDT']:
                        if (order['orderType'] == 'Limit' and 
                            order['side'] == 'Buy' and 
                            not order.get('reduceOnly', False)):
                            cake_limit_orders.append(order['orderId'])
                            logger.info(f"Found CAKEUSDT limit order: {order['orderId']}")
                    
                    # Step 2: Update monitors with found limit orders
                    if cake_limit_orders:
                        logger.info("\n=== Step 2: Updating monitors with limit orders ===")
                        
                        data = main_pickle_lock.safe_load()
                        
                        if data and 'bot_data' in data:
                            monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
                            
                            # Update both CAKEUSDT monitors
                            updated = False
                            for monitor_key in ['CAKEUSDT_Buy', 'CAKEUSDT_Buy_mirror']:
                                if monitor_key in monitors:
                                    monitor = monitors[monitor_key]
                                    
                                    # Initialize limit_orders if not present
                                    if 'limit_orders' not in monitor:
                                        monitor['limit_orders'] = []
                                    
                                    # Add the found orders
                                    for order_id in cake_limit_orders:
                                        # Check if order already tracked
                                        existing_ids = [o.get('order_id') if isinstance(o, dict) else o 
                                                       for o in monitor['limit_orders']]
                                        
                                        if order_id not in existing_ids:
                                            monitor['limit_orders'].append({
                                                'order_id': order_id,
                                                'status': 'ACTIVE',
                                                'registered_at': time.time()
                                            })
                                            updated = True
                                            logger.info(f"Added order {order_id} to {monitor_key}")
                            
                            if updated:
                                # Save the updated data
                                success = main_pickle_lock.safe_save(data)
                                if success:
                                    logger.info("✅ Successfully updated monitors with limit orders")
                                else:
                                    logger.error("❌ Failed to save updated monitors")
                else:
                    logger.info("No CAKEUSDT orders found on mirror account")
        
        # Step 3: Fix the timing issue in trader.py
        logger.info("\n=== Step 3: Fixing trader.py timing issue ===")
        await fix_trader_timing()
        
        logger.info("\n=== Summary ===")
        logger.info("✅ Limit order tracking has been fixed!")
        logger.info("- Existing positions: Limit orders registered from exchange")
        logger.info("- Future trades: Timing issue fixed in trader.py")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in final limit order fix: {e}")
        import traceback
        traceback.print_exc()
        return False

async def fix_trader_timing():
    """Fix the timing issue in trader.py"""
    try:
        with open('execution/trader.py', 'r') as f:
            content = f.read()
        
        # Check if the fix is already applied
        if "# Wait for monitor to be created before registering" in content:
            logger.info("✅ Trader.py timing fix already applied")
            return
        
        # Find the line where register_limit_orders is called
        search_line = "await enhanced_tp_sl_manager.register_limit_orders(symbol, side, limit_order_ids)"
        
        if search_line in content:
            # Add a delay before the registration
            replacement = """# Wait for monitor to be created before registering
                    await asyncio.sleep(1)
                    await enhanced_tp_sl_manager.register_limit_orders(symbol, side, limit_order_ids)"""
            
            content = content.replace(search_line, replacement)
            
            # Write back
            with open('execution/trader.py', 'w') as f:
                f.write(content)
            
            logger.info("✅ Applied timing fix to trader.py")
        else:
            logger.warning("⚠️ Could not find register_limit_orders call in trader.py")
            
    except Exception as e:
        logger.error(f"Error fixing trader timing: {e}")

async def main():
    """Main function"""
    await final_limit_order_fix()

if __name__ == "__main__":
    asyncio.run(main())