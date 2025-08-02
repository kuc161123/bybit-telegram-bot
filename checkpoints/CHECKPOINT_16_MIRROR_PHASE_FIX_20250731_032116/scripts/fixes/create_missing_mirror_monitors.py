#!/usr/bin/env python3
"""
Create Missing Mirror Monitors
Creates Enhanced TP/SL monitors for positions that are missing them
"""

import asyncio
import logging
import pickle
import sys
import os
from decimal import Decimal
from datetime import datetime
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from clients.bybit_client import bybit_client
from clients.bybit_helpers import get_all_positions
from execution.mirror_trader import bybit_client_2

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Missing mirror positions identified from the investigation
MISSING_MONITORS = [
    {"symbol": "AUCTIONUSDT", "side": "Buy", "account": "mirror"},
    {"symbol": "CRVUSDT", "side": "Buy", "account": "mirror"},
    {"symbol": "SEIUSDT", "side": "Buy", "account": "mirror"},
    {"symbol": "ARBUSDT", "side": "Buy", "account": "mirror"},
    {"symbol": "IDUSDT", "side": "Buy", "account": "mirror"}
]

async def create_monitor_entry(position_data: dict, account: str) -> dict:
    """Create a monitor entry for Enhanced TP/SL system"""
    
    symbol = position_data['symbol']
    side = position_data['side']
    size = Decimal(str(position_data['size']))
    avg_price = Decimal(str(position_data['avgPrice']))
    
    # Create monitor key
    monitor_key = f"{symbol}_{side}_{account}"
    
    # Create monitor data structure
    monitor_data = {
        'symbol': symbol,
        'side': side,
        'size': size,
        'account': account,
        'avg_entry_price': avg_price,
        'tp_orders': {},
        'sl_order': None,
        'status': 'active',
        'created_at': datetime.now().isoformat(),
        'tp1_hit': False,
        'tp2_hit': False,
        'tp3_hit': False,
        'breakeven_moved': False,
        'last_check': time.time(),
        'monitoring_active': True,
        'sl_moved_to_breakeven': False,
        'initial_size': size,
        'remaining_size': size,
        'filled_size': Decimal('0'),
        'actual_entry_prices': [(avg_price, size)],  # Track actual fills
        'weighted_avg_entry': avg_price,
        'limit_orders_cancelled': False,
        'chat_id': None  # Will be resolved from pickle data
    }
    
    return monitor_key, monitor_data

async def main():
    logger.info("🔧 Creating Missing Mirror Monitors")
    logger.info("=" * 80)
    
    try:
        # Load current pickle file
        pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        # Create backup
        backup_file = f"{pickle_file}.backup_missing_monitors_{int(time.time())}"
        if os.path.exists(pickle_file):
            import shutil
            shutil.copy2(pickle_file, backup_file)
            logger.info(f"✅ Created backup: {backup_file}")
        
        # Load data
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        # Get current monitors
        enhanced_monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
        logger.info(f"📊 Current Enhanced TP/SL monitors: {len(enhanced_monitors)}")
        
        # Get all mirror positions
        mirror_positions = await get_all_positions(client=bybit_client_2)
        logger.info(f"📊 Total mirror positions: {len(mirror_positions)}")
        
        # Find chat_id from user data
        chat_id = None
        for uid, user_data in data.get('user_data', {}).items():
            if user_data.get('positions'):
                chat_id = uid
                break
        
        if not chat_id:
            logger.warning("⚠️ No chat_id found in user data")
        
        # Create monitors for missing positions
        created_count = 0
        
        for missing in MISSING_MONITORS:
            symbol = missing['symbol']
            side = missing['side']
            account = missing['account']
            monitor_key = f"{symbol}_{side}_{account}"
            
            # Check if monitor already exists
            if monitor_key in enhanced_monitors:
                logger.info(f"ℹ️ Monitor already exists for {monitor_key}")
                continue
            
            # Find position data
            position = None
            for pos in mirror_positions:
                if pos['symbol'] == symbol and pos['side'] == side:
                    position = pos
                    break
            
            if not position:
                logger.warning(f"⚠️ Position not found for {symbol} {side}")
                continue
            
            # Create monitor entry
            _, monitor_data = await create_monitor_entry(position, account)
            monitor_data['chat_id'] = chat_id
            
            # Add to monitors
            enhanced_monitors[monitor_key] = monitor_data
            created_count += 1
            
            logger.info(f"✅ Created monitor for {monitor_key}")
            logger.info(f"   Size: {monitor_data['size']}")
            logger.info(f"   Avg Price: {monitor_data['avg_entry_price']}")
        
        # Update pickle file
        data['bot_data']['enhanced_tp_sl_monitors'] = enhanced_monitors
        
        # Save updated data
        with open(pickle_file, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"\n✅ Created {created_count} new monitors")
        logger.info(f"📊 Total Enhanced TP/SL monitors now: {len(enhanced_monitors)}")
        
        # List all monitors
        logger.info("\n📋 All Enhanced TP/SL Monitors:")
        main_count = 0
        mirror_count = 0
        
        for key in sorted(enhanced_monitors.keys()):
            monitor = enhanced_monitors[key]
            account_type = monitor.get('account', 'main')
            if account_type == 'main':
                main_count += 1
            else:
                mirror_count += 1
            logger.info(f"   {key} - Size: {monitor.get('size', 'N/A')}")
        
        logger.info(f"\n📊 Summary:")
        logger.info(f"   Main account monitors: {main_count}")
        logger.info(f"   Mirror account monitors: {mirror_count}")
        logger.info(f"   Total monitors: {len(enhanced_monitors)}")
        
        # Create reload signal
        signal_file = 'reload_monitors.signal'
        with open(signal_file, 'w') as f:
            f.write(str(time.time()))
        logger.info(f"\n🔄 Created reload signal: {signal_file}")
        
    except Exception as e:
        logger.error(f"❌ Error creating monitors: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())