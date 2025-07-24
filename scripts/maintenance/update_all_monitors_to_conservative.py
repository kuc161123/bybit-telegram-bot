#!/usr/bin/env python3
"""
Update all monitors to Conservative approach
This will ensure limit orders are properly tracked and cancelled when TP1 hits
"""

import pickle
import logging
import time
from datetime import datetime
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def update_monitors_to_conservative():
    """Update all monitors to conservative approach"""
    
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    # Create backup first
    backup_path = f"{pkl_path}.backup_approach_fix_{int(time.time())}"
    shutil.copy2(pkl_path, backup_path)
    logger.info(f"✅ Created backup: {backup_path}")
    
    # Load pickle file
    try:
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        logger.error(f"Error loading pickle file: {e}")
        return False
    
    # Get Enhanced TP/SL monitors
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    logger.info(f"\n{'='*60}")
    logger.info(f"🔧 UPDATING ALL MONITORS TO CONSERVATIVE APPROACH")
    logger.info(f"{'='*60}")
    
    updated_count = 0
    already_conservative = 0
    
    # Update each monitor
    for key, monitor in enhanced_monitors.items():
        symbol = monitor.get('symbol')
        side = monitor.get('side')
        current_approach = monitor.get('approach', 'Unknown')
        account = 'Mirror' if key.endswith('_mirror') else 'Main'
        
        if current_approach == 'conservative':
            already_conservative += 1
            logger.info(f"✅ {symbol} {side} ({account}) - Already Conservative")
        else:
            # Update to conservative
            monitor['approach'] = 'conservative'
            
            # Initialize limit_orders array if not present
            if 'limit_orders' not in monitor:
                monitor['limit_orders'] = []
            
            # Ensure other conservative-specific fields are present
            if 'limit_orders_cancelled' not in monitor:
                monitor['limit_orders_cancelled'] = False
                
            # Update phase if needed - conservative positions start in BUILDING phase
            if monitor.get('phase') == 'MONITORING' and not monitor.get('tp1_hit'):
                monitor['phase'] = 'BUILDING'
                logger.info(f"   📝 Changed phase from MONITORING to BUILDING")
            
            updated_count += 1
            logger.info(f"🔄 {symbol} {side} ({account}) - Updated from {current_approach} to Conservative")
            logger.info(f"   Phase: {monitor.get('phase')}")
            logger.info(f"   TP1 Hit: {monitor.get('tp1_hit', False)}")
    
    # Update the data back
    data['bot_data']['enhanced_tp_sl_monitors'] = enhanced_monitors
    
    # Save the updated pickle file
    try:
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"\n✅ Successfully saved updated monitors")
    except Exception as e:
        logger.error(f"Error saving pickle file: {e}")
        return False
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 UPDATE SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total monitors: {len(enhanced_monitors)}")
    logger.info(f"Already Conservative: {already_conservative}")
    logger.info(f"Updated to Conservative: {updated_count}")
    logger.info(f"Main account monitors: {len([k for k in enhanced_monitors.keys() if not k.endswith('_mirror')])}")
    logger.info(f"Mirror account monitors: {len([k for k in enhanced_monitors.keys() if k.endswith('_mirror')])}")
    
    # Important notes
    logger.info(f"\n💡 IMPORTANT NOTES:")
    logger.info(f"1. All monitors now use Conservative approach")
    logger.info(f"2. Limit orders will be tracked and cancelled when TP1 hits")
    logger.info(f"3. Positions without TP1 hit are in BUILDING phase")
    logger.info(f"4. The bot will now properly manage limit order cancellation")
    
    # Check for positions that already hit TP1
    tp1_hit_positions = []
    for key, monitor in enhanced_monitors.items():
        if monitor.get('tp1_hit'):
            tp1_hit_positions.append(f"{monitor['symbol']} {monitor['side']} ({'Mirror' if key.endswith('_mirror') else 'Main'})")
    
    if tp1_hit_positions:
        logger.info(f"\n⚠️ Positions that already hit TP1:")
        for pos in tp1_hit_positions:
            logger.info(f"   - {pos}")
        logger.info(f"   These should already have their limit orders cancelled")
    
    return True

def main():
    """Main execution"""
    success = update_monitors_to_conservative()
    
    if success:
        logger.info(f"\n✅ All monitors successfully updated to Conservative approach!")
        logger.info(f"🔄 The bot will now properly track and cancel limit orders when TP1 hits")
    else:
        logger.error(f"\n❌ Failed to update monitors")

if __name__ == "__main__":
    main()