#!/usr/bin/env python3
"""
Add Missing Monitors - Simple Version
Uses robust persistence to add missing monitors without restart
"""

import asyncio
import logging
import json
import sys
import os
from decimal import Decimal
from datetime import datetime
import time
import pickle

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.robust_persistence import robust_persistence

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Missing monitors data from analysis
MISSING_MONITORS = [
    {
        "monitor_key": "AUCTIONUSDT_Buy_mirror",
        "symbol": "AUCTIONUSDT",
        "side": "Buy",
        "account": "mirror",
        "size": "7.1",
        "avgPrice": "9.816"
    },
    {
        "monitor_key": "CRVUSDT_Buy_mirror",
        "symbol": "CRVUSDT",
        "side": "Buy",
        "account": "mirror",
        "size": "225.5",
        "avgPrice": "0.6408"
    },
    {
        "monitor_key": "SEIUSDT_Buy_mirror",
        "symbol": "SEIUSDT",
        "side": "Buy",
        "account": "mirror",
        "size": "429",
        "avgPrice": "0.3418"
    },
    {
        "monitor_key": "ARBUSDT_Buy_mirror",
        "symbol": "ARBUSDT",
        "side": "Buy",
        "account": "mirror",
        "size": "349.7",
        "avgPrice": "0.41181092"
    },
    {
        "monitor_key": "IDUSDT_Buy_mirror",
        "symbol": "IDUSDT",
        "side": "Buy",
        "account": "mirror",
        "size": "77",
        "avgPrice": "0.172"
    }
]

async def add_missing_monitors():
    """Add missing monitors using robust persistence"""
    logger.info("🔧 Adding Missing Monitors Using Robust Persistence")
    logger.info("=" * 80)
    
    try:
        # Get chat_id from existing data
        chat_id = None
        data = await robust_persistence.read_data()
        for uid, user_data in data.get('user_data', {}).items():
            if user_data.get('positions'):
                chat_id = uid
                break
        
        if not chat_id:
            logger.warning("⚠️ No chat_id found, monitors may not send alerts")
        else:
            logger.info(f"✅ Found chat_id: {chat_id}")
        
        # Add each missing monitor
        added_count = 0
        
        for monitor_info in MISSING_MONITORS:
            monitor_key = monitor_info['monitor_key']
            symbol = monitor_info['symbol']
            side = monitor_info['side']
            account = monitor_info['account']
            size = Decimal(str(monitor_info['size']))
            avg_price = Decimal(str(monitor_info['avgPrice']))
            
            logger.info(f"\n📍 Adding monitor: {monitor_key}")
            
            # Create monitor data
            monitor_data = {
                'symbol': symbol,
                'side': side,
                'size': size,
                'position_size': size,
                'initial_size': size,
                'remaining_size': size,
                'filled_size': Decimal('0'),
                'account': account,
                'account_type': account,
                'avg_entry_price': avg_price,
                'entry_price': avg_price,
                'weighted_avg_entry': avg_price,
                'actual_entry_prices': [(avg_price, size)],
                'tp_orders': {},
                'sl_order': None,
                'approach': 'conservative',
                'status': 'active',
                'created_at': datetime.now().isoformat(),
                'last_check': time.time(),
                'monitoring_active': True,
                'tp1_hit': False,
                'tp2_hit': False,
                'tp3_hit': False,
                'tp4_hit': False,
                'breakeven_moved': False,
                'sl_moved_to_breakeven': False,
                'limit_orders_cancelled': False,
                'chat_id': chat_id,
                'position_idx': 0,
                'dashboard_key': monitor_key,
                'stop_loss': None,
                'take_profits': []
            }
            
            # Position data for lifecycle tracking
            position_data = {
                'symbol': symbol,
                'side': side,
                'size': str(size),
                'avgPrice': str(avg_price),
                'account': account
            }
            
            # Add monitor using robust persistence
            await robust_persistence.add_monitor(monitor_key, monitor_data, position_data)
            added_count += 1
            
            logger.info(f"   ✅ Added successfully")
            logger.info(f"   Size: {size}")
            logger.info(f"   Entry: {avg_price}")
        
        logger.info(f"\n✅ Added {added_count} monitors to persistence")
        
        # Get updated stats
        stats = await robust_persistence.get_stats()
        logger.info(f"\n📊 Persistence Stats:")
        logger.info(f"   Total monitors: {stats.get('total_monitors')}")
        logger.info(f"   Total dashboard monitors: {stats.get('total_dashboard_monitors')}")
        logger.info(f"   File size: {stats.get('file_size_mb', 0):.2f} MB")
        
        # Create reload signal
        signal_file = 'reload_enhanced_monitors.signal'
        with open(signal_file, 'w') as f:
            f.write(str(time.time()))
        logger.info(f"\n🔄 Created reload signal: {signal_file}")
        logger.info("   The bot will reload monitors within 5 seconds")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error adding monitors: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main function"""
    success = await add_missing_monitors()
    
    if success:
        logger.info("\n" + "=" * 80)
        logger.info("✅ SUCCESSFULLY ADDED MISSING MONITORS")
        logger.info("   The bot will start monitoring all 25 positions")
        logger.info("   No restart required!")
    else:
        logger.error("\n❌ Failed to add monitors")

if __name__ == "__main__":
    asyncio.run(main())