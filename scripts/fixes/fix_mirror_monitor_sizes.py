#!/usr/bin/env python3
"""
Fix mirror monitor position sizes in persistence file
The mirror monitors currently have main account position sizes stored,
which causes false TP fill detections
"""

import pickle
import logging
import asyncio
from decimal import Decimal
from datetime import datetime
import shutil

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def get_actual_positions():
    """Get actual positions from both accounts"""
    from clients.bybit_helpers import get_all_positions, get_position_info_for_account
    
    # Get main positions
    main_positions = await get_all_positions()
    
    # Get mirror positions
    mirror_positions = []
    for pos in main_positions:
        mirror_pos = await get_position_info_for_account(pos['symbol'], 'mirror')
        if mirror_pos:
            mirror_positions.extend(mirror_pos)
    
    return main_positions, mirror_positions

def create_position_map(positions):
    """Create a map of symbol_side -> position data"""
    pos_map = {}
    for pos in positions:
        key = f"{pos['symbol']}_{pos['side']}"
        pos_map[key] = pos
    return pos_map

async def fix_mirror_monitors():
    """Fix all mirror monitor position sizes"""
    try:
        # Create backup
        backup_file = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_mirror_fix_{int(datetime.now().timestamp())}'
        shutil.copy('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_file)
        logger.info(f"Created backup: {backup_file}")
        
        # Load pickle file
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
        
        # Get actual positions
        logger.info("Fetching actual positions from exchanges...")
        main_positions, mirror_positions = await get_actual_positions()
        
        # Create position maps
        main_pos_map = create_position_map(main_positions)
        mirror_pos_map = create_position_map(mirror_positions)
        
        logger.info(f"Found {len(main_positions)} main positions, {len(mirror_positions)} mirror positions")
        
        # Fix each mirror monitor
        fixed_count = 0
        for key, monitor in monitors.items():
            if key.endswith('_mirror'):
                symbol = monitor['symbol']
                side = monitor['side']
                pos_key = f"{symbol}_{side}"
                
                if pos_key in mirror_pos_map:
                    actual_size = Decimal(str(mirror_pos_map[pos_key]['size']))
                    
                    # Check if size needs fixing
                    if monitor['position_size'] != actual_size or monitor['remaining_size'] != actual_size:
                        logger.info(f"Fixing {key}:")
                        logger.info(f"  Old: position_size={monitor['position_size']}, remaining_size={monitor['remaining_size']}")
                        logger.info(f"  New: position_size={actual_size}, remaining_size={actual_size}")
                        
                        monitor['position_size'] = actual_size
                        monitor['remaining_size'] = actual_size
                        fixed_count += 1
                else:
                    logger.warning(f"No mirror position found for {key}")
        
        if fixed_count > 0:
            # Save updated data
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"✅ Fixed {fixed_count} mirror monitors")
            
            # Verify the fixes
            logger.info("\n=== VERIFICATION ===")
            for key, monitor in monitors.items():
                if key.endswith('_mirror') and monitor['symbol'] in ['ICPUSDT', 'IDUSDT', 'JUPUSDT']:
                    logger.info(f"{key}: position_size={monitor['position_size']}, remaining_size={monitor['remaining_size']}")
        else:
            logger.info("✅ All mirror monitors already have correct sizes")
            
    except Exception as e:
        logger.error(f"Error fixing mirror monitors: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(fix_mirror_monitors())