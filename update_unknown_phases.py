#!/usr/bin/env python3
"""
Update monitors with Unknown phase to MONITORING phase
"""

import pickle
import shutil
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

PICKLE_FILE = 'bybit_bot_dashboard_v4.1_enhanced.pkl'

def update_unknown_phases():
    """Update monitors with Unknown phase to MONITORING"""
    
    # Create backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f"{PICKLE_FILE}.backup_phase_update_{timestamp}"
    shutil.copy(PICKLE_FILE, backup_file)
    logger.info(f"✅ Created backup: {backup_file}")
    
    # Load pickle data
    with open(PICKLE_FILE, 'rb') as f:
        data = pickle.load(f)
    
    monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    updates_made = []
    
    logger.info("\n📊 Updating monitors with Unknown phase...\n")
    
    for monitor_key, monitor in monitors.items():
        phase = monitor.get('phase', 'Unknown')
        
        if phase == 'Unknown':
            symbol = monitor.get('symbol', '')
            side = monitor.get('side', '')
            account = monitor.get('account_type', monitor.get('account', ''))
            position_size = monitor.get('position_size', 0)
            remaining_size = monitor.get('remaining_size', 0)
            
            # Update to MONITORING phase
            monitor['phase'] = 'MONITORING'
            monitor['phase_transition_time'] = datetime.now().timestamp()
            
            updates_made.append({
                'monitor': monitor_key,
                'symbol': symbol,
                'side': side,
                'account': account,
                'position_size': position_size,
                'remaining_size': remaining_size
            })
            
            logger.info(f"✅ Updated {monitor_key} from Unknown → MONITORING")
    
    # Save updated data
    with open(PICKLE_FILE, 'wb') as f:
        pickle.dump(data, f)
    
    logger.info(f"\n✅ Updated {len(updates_made)} monitors")
    
    if updates_made:
        logger.info("\n📋 UPDATES SUMMARY:")
        logger.info("-" * 60)
        for update in updates_made:
            logger.info(f"{update['monitor']} - Position: {update['position_size']}, Remaining: {update['remaining_size']}")
    
    # Create signal file to reload monitors
    with open('.reload_enhanced_monitors.signal', 'w') as f:
        f.write(str(datetime.now().timestamp()))
    logger.info("\n✅ Created reload signal for enhanced monitors")
    
    return updates_made

if __name__ == "__main__":
    update_unknown_phases()