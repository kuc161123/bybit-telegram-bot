#!/usr/bin/env python3
"""
Script to manually trigger limit order checking for all monitors.
This will help verify that the fix is working.
"""
import asyncio
import sys
import os
import pickle
import logging
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def trigger_limit_order_check():
    """Manually trigger limit order checking"""
    try:
        # Load monitors from pickle
        logger.info("📊 Loading monitors from persistence...")
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        persisted_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        # Load monitors into manager
        for monitor_key, monitor_data in persisted_monitors.items():
            if monitor_key.endswith('_main') or monitor_key.endswith('_mirror'):
                enhanced_tp_sl_manager.position_monitors[monitor_key] = monitor_data
        
        logger.info(f"📊 Loaded {len(enhanced_tp_sl_manager.position_monitors)} monitors")
        
        # Check monitors with limit orders
        monitors_to_check = []
        for monitor_key, monitor_data in enhanced_tp_sl_manager.position_monitors.items():
            if monitor_data.get('limit_orders'):
                monitors_to_check.append((monitor_key, monitor_data))
        
        logger.info(f"📊 Found {len(monitors_to_check)} monitors with limit orders")
        
        # Manually trigger monitoring for each
        for monitor_key, monitor_data in monitors_to_check:
            symbol = monitor_data.get('symbol')
            side = monitor_data.get('side')
            account_type = monitor_data.get('account_type', 'main')
            
            logger.info(f"\n🔄 Triggering check for {monitor_key}")
            logger.info(f"   Approach: {monitor_data.get('approach', 'UNKNOWN')}")
            logger.info(f"   Limit Orders: {len(monitor_data.get('limit_orders', []))}")
            
            try:
                # Call monitor_and_adjust_orders
                await enhanced_tp_sl_manager.monitor_and_adjust_orders(symbol, side, account_type)
                logger.info(f"   ✅ Check completed")
            except Exception as e:
                logger.error(f"   ❌ Error: {e}")
        
        logger.info("\n✅ Done! Check the logs above to see if limit order checking was triggered.")
        logger.info("Look for messages like:")
        logger.info("   - '🔍 Checking limit orders for...'")
        logger.info("   - '⚠️ Monitor ... has X limit orders but approach is...'")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(trigger_limit_order_check())