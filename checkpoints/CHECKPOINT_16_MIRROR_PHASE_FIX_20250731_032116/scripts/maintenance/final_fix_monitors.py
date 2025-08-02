#!/usr/bin/env python3
"""
Final comprehensive fix for mirror monitor sizes
"""

import pickle
import logging
import asyncio
from decimal import Decimal
from datetime import datetime
import os

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def final_fix_monitors():
    """Final comprehensive fix for all monitor issues"""
    try:
        # Get actual positions from exchanges
        logger.info("Fetching actual positions from exchanges...")
        from clients.bybit_helpers import get_all_positions, get_position_info_for_account
        
        # Get main positions
        main_positions = await get_all_positions()
        
        # Get mirror positions for each symbol
        mirror_position_map = {}
        for pos in main_positions:
            symbol = pos['symbol']
            side = pos['side']
            mirror_pos = await get_position_info_for_account(symbol, 'mirror')
            if mirror_pos:
                for mp in mirror_pos:
                    if mp['side'] == side:
                        key = f"{symbol}_{side}"
                        mirror_position_map[key] = Decimal(str(mp['size']))
                        logger.info(f"Mirror position {key}: {mp['size']}")
        
        # Load pickle file
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
        
        logger.info(f"\n=== FIXING ALL MONITORS ===")
        logger.info(f"Total monitors: {len(monitors)}")
        
        fixed_count = 0
        
        # Fix each monitor
        for key, monitor in monitors.items():
            if key.endswith('_mirror'):
                # Extract symbol and side
                parts = key.replace('_mirror', '').split('_')
                if len(parts) >= 2:
                    symbol = parts[0]
                    side = parts[1]
                    pos_key = f"{symbol}_{side}"
                    
                    if pos_key in mirror_position_map:
                        correct_size = mirror_position_map[pos_key]
                        
                        if monitor['position_size'] != correct_size or monitor['remaining_size'] != correct_size:
                            logger.info(f"\nFixing {key}:")
                            logger.info(f"  Old: position_size={monitor['position_size']}, remaining_size={monitor['remaining_size']}")
                            logger.info(f"  New: position_size={correct_size}, remaining_size={correct_size}")
                            
                            monitor['position_size'] = correct_size
                            monitor['remaining_size'] = correct_size
                            fixed_count += 1
                    else:
                        logger.warning(f"No mirror position found for {key}")
            else:
                # For main monitors, ensure position_size equals remaining_size
                if monitor['position_size'] != monitor['remaining_size']:
                    logger.info(f"\nFixing {key} (main):")
                    logger.info(f"  Setting position_size to match remaining_size: {monitor['remaining_size']}")
                    monitor['position_size'] = monitor['remaining_size']
                    fixed_count += 1
        
        # Clear any tracking fields
        for key, monitor in monitors.items():
            if 'cumulative_filled' in monitor:
                del monitor['cumulative_filled']
            if 'total_filled' in monitor:
                del monitor['total_filled']
            monitor['tp1_hit'] = False
            monitor['filled_tps'] = []
        
        # Save updated data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"\n✅ Fixed {fixed_count} monitors")
        
        # Create a good backup
        backup_dir = 'data/persistence_backups'
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"{backup_dir}/backup_write_{timestamp}.pkl"
        
        with open(backup_file, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"✅ Created fresh backup: {backup_file}")
        
        # Verify the fix
        logger.info("\n=== VERIFICATION ===")
        for key in ['ICPUSDT_Sell_mirror', 'IDUSDT_Sell_mirror', 'JUPUSDT_Sell_mirror']:
            if key in monitors:
                monitor = monitors[key]
                logger.info(f"{key}: position_size={monitor['position_size']}, remaining_size={monitor['remaining_size']}")
                
    except Exception as e:
        logger.error(f"Error fixing monitors: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(final_fix_monitors())