#!/usr/bin/env python3
"""
Monitor TP1 Events in Real-Time
This script monitors for TP1 hits and verifies limit order cancellation
"""

import asyncio
import logging
import sys
import os
import pickle
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def monitor_tp1_events():
    """Monitor for TP1 events and track behavior"""
    from config.settings import CANCEL_LIMITS_ON_TP1
    
    logger.info("🔍 Monitoring TP1 Events")
    logger.info(f"   CANCEL_LIMITS_ON_TP1: {CANCEL_LIMITS_ON_TP1}")
    logger.info("   Press Ctrl+C to stop monitoring")
    logger.info("=" * 80)
    
    last_check = {}
    
    while True:
        try:
            # Load current monitors
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
                data = pickle.load(f)
            
            monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
            
            # Check for new TP1 hits
            for key, monitor in monitors.items():
                if monitor.get('tp1_hit'):
                    # Check if this is a new TP1 hit
                    if key not in last_check or not last_check[key].get('tp1_hit'):
                        symbol = monitor.get('symbol')
                        side = monitor.get('side')
                        account = monitor.get('account_type', 'main')
                        
                        logger.info(f"\n🎯 NEW TP1 HIT DETECTED!")
                        logger.info(f"   Symbol: {symbol} {side}")
                        logger.info(f"   Account: {account}")
                        logger.info(f"   Limit orders cancelled: {monitor.get('limit_orders_cancelled', False)}")
                        logger.info(f"   SL moved to BE: {monitor.get('sl_moved_to_be', False)}")
                        
                        # Check for limit orders
                        limit_orders = monitor.get('limit_orders', [])
                        logger.info(f"   Limit orders in monitor: {len(limit_orders)}")
                        
                        if CANCEL_LIMITS_ON_TP1 and limit_orders and not monitor.get('limit_orders_cancelled'):
                            logger.warning(f"   ⚠️ Expected limit cancellation but flag not set!")
            
            # Update last check
            last_check = {k: {'tp1_hit': v.get('tp1_hit', False)} for k, v in monitors.items()}
            
            # Wait before next check
            await asyncio.sleep(5)
            
        except KeyboardInterrupt:
            logger.info("\n👋 Monitoring stopped by user")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(monitor_tp1_events())
