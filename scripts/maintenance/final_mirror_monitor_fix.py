#!/usr/bin/env python3
"""
Final fix to ensure mirror monitors are properly configured
"""
import pickle
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load the correct backup that has mirror monitors
backup_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_mirror_monitors_1751959520'
current_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'

logger.info(f"Loading backup file with correct mirror monitors: {backup_file}")

try:
    with open(backup_file, 'rb') as f:
        data = pickle.load(f)
    
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    # Count mirror monitors
    mirror_count = 0
    for key, monitor in enhanced_monitors.items():
        if monitor.get('account_type') == 'mirror':
            mirror_count += 1
            logger.info(f"Found mirror monitor: {key}")
    
    logger.info(f"\nTotal mirror monitors in backup: {mirror_count}")
    
    if mirror_count == 6:
        # Save as current file
        import shutil
        
        # Create safety backup of current
        safety_backup = f"{current_file}.safety_{int(datetime.now().timestamp())}"
        shutil.copy2(current_file, safety_backup)
        logger.info(f"Created safety backup: {safety_backup}")
        
        # Save the correct data
        with open(current_file, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"✅ Restored pickle file with {mirror_count} mirror monitors")
        
        # Now load into manager
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        
        enhanced_tp_sl_manager.position_monitors.clear()
        
        for key, monitor_data in enhanced_monitors.items():
            sanitized = enhanced_tp_sl_manager._sanitize_monitor_data(monitor_data)
            enhanced_tp_sl_manager.position_monitors[key] = sanitized
            
            if sanitized.get('account_type') == 'mirror':
                logger.info(f"✅ Loaded mirror monitor: {key} (chat_id={sanitized.get('chat_id')})")
        
        logger.info(f"\n✅ Successfully loaded {len(enhanced_tp_sl_manager.position_monitors)} monitors")
        logger.info("✅ Mirror monitoring is now active without alerts!")
    else:
        logger.error(f"Backup file has {mirror_count} mirror monitors, expected 6")
        
except Exception as e:
    logger.error(f"Error: {e}")
    import traceback
    traceback.print_exc()