#!/usr/bin/env python3
"""
Fix Limit Order Registration
============================

This script ensures that limit orders are properly registered and tracked
in the Enhanced TP/SL monitoring system.
"""

import asyncio
import logging
from typing import Dict, List
from pybit.unified_trading import HTTP
from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET,
    ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
)
from clients.bybit_helpers import get_open_orders
from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_limit_order_registration():
    """Fix limit order registration for all positions"""
    try:
        # Get all monitors
        monitors = enhanced_tp_sl_manager.position_monitors
        logger.info(f"Found {len(monitors)} monitors to check")
        
        fixed_count = 0
        
        for monitor_key, monitor in monitors.items():
            symbol = monitor.get('symbol')
            side = monitor.get('side')
            approach = monitor.get('approach', 'unknown')
            account_type = monitor.get('account_type', 'main')
            
            logger.info(f"\nChecking {symbol} {side} ({account_type}) - {approach}")
            
            # Skip if not conservative approach
            if approach != 'conservative':
                logger.info("  - Skipping (not conservative)")
                continue
            
            # Check if limit orders are already tracked
            limit_orders = monitor.get('limit_orders', [])
            if limit_orders:
                logger.info(f"  - Already tracking {len(limit_orders)} limit orders")
                continue
            
            # Get the appropriate client
            if account_type == 'mirror' and ENABLE_MIRROR_TRADING:
                client = HTTP(
                    testnet=USE_TESTNET,
                    api_key=BYBIT_API_KEY_2,
                    api_secret=BYBIT_API_SECRET_2
                )
            else:
                client = HTTP(
                    testnet=USE_TESTNET,
                    api_key=BYBIT_API_KEY,
                    api_secret=BYBIT_API_SECRET
                )
            
            # Get open orders for this symbol
            orders = await get_open_orders(client, symbol)
            
            # Find limit orders for this position
            position_limit_orders = []
            for order in orders:
                if (order.get('orderType') == 'Limit' and 
                    order.get('side') == side and
                    not order.get('reduceOnly', False)):  # Entry orders, not TP/SL
                    
                    order_id = order.get('orderId')
                    if order_id:
                        position_limit_orders.append({
                            'order_id': order_id,
                            'status': 'ACTIVE',
                            'registered_at': asyncio.get_event_loop().time()
                        })
                        logger.info(f"  - Found limit order: {order_id}")
            
            if position_limit_orders:
                # Update the monitor with limit orders
                monitor['limit_orders'] = position_limit_orders
                
                # Save to persistence
                await enhanced_tp_sl_manager.save_monitors_to_persistence()
                
                logger.info(f"  ✅ Registered {len(position_limit_orders)} limit orders")
                fixed_count += 1
            else:
                logger.warning(f"  ⚠️ No limit orders found on exchange")
        
        logger.info(f"\n✅ Fixed {fixed_count} monitors")
        
        # Also fix the limit order registration in trader.py for future trades
        await fix_trader_timing_issue()
        
    except Exception as e:
        logger.error(f"Error fixing limit order registration: {e}")
        import traceback
        traceback.print_exc()

async def fix_trader_timing_issue():
    """Fix the timing issue in trader.py"""
    try:
        # Read trader.py
        with open('execution/trader.py', 'r') as f:
            content = f.read()
        
        # Check if the fix is already applied
        if 'await asyncio.sleep(1)  # Give monitor time to initialize' in content:
            logger.info("✅ Trader timing fix already applied")
            return
        
        # Find the limit order registration section
        search_text = """                    # Register limit orders with Enhanced TP/SL manager
                    if ENABLE_ENHANCED_TP_SL and hasattr(enhanced_tp_sl_manager, 'register_limit_orders'):
                        enhanced_tp_sl_manager.register_limit_orders(symbol, side, limit_order_ids)"""
        
        if search_text in content:
            # Add a delay before registration
            replacement = """                    # Register limit orders with Enhanced TP/SL manager
                    if ENABLE_ENHANCED_TP_SL and hasattr(enhanced_tp_sl_manager, 'register_limit_orders'):
                        # Wait for monitor to be created
                        await asyncio.sleep(1)  # Give monitor time to initialize
                        enhanced_tp_sl_manager.register_limit_orders(symbol, side, limit_order_ids)"""
            
            content = content.replace(search_text, replacement)
            
            # Write back
            with open('execution/trader.py', 'w') as f:
                f.write(content)
            
            logger.info("✅ Applied timing fix to trader.py")
        else:
            logger.warning("⚠️ Could not find limit order registration code in trader.py")
            
    except Exception as e:
        logger.error(f"Error fixing trader timing issue: {e}")

async def main():
    """Main function"""
    await fix_limit_order_registration()

if __name__ == "__main__":
    asyncio.run(main())