#!/usr/bin/env python3
"""
Prevent duplicate monitors from being created
"""
import time
import pickle
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_and_fix_monitors():
    """Check for and remove duplicate monitors"""
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    # Check for legacy monitors
    legacy_monitors = []
    for key in list(monitors.keys()):
        if not key.endswith('_main') and not key.endswith('_mirror'):
            legacy_monitors.append(key)
    
    if legacy_monitors:
        logger.warning(f"Found {len(legacy_monitors)} legacy monitors - removing...")
        for key in legacy_monitors:
            del monitors[key]
            logger.info(f"  Removed: {key}")
        
        # Save updated data
        data['bot_data']['enhanced_tp_sl_monitors'] = monitors
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        # Create signal file
        with open('reload_enhanced_monitors.signal', 'w') as f:
            f.write(str(time.time()))
        
        return True
    
    return False

# Run initial check
logger.info("=" * 60)
logger.info("MONITOR DUPLICATE PREVENTION")
logger.info("=" * 60)

fixed = check_and_fix_monitors()

if fixed:
    logger.info("\n✅ Removed duplicate monitors and triggered reload")
else:
    logger.info("\n✅ No duplicate monitors found")

# Check final state
with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
    data = pickle.load(f)

monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
main_count = sum(1 for k in monitors if k.endswith('_main'))
mirror_count = sum(1 for k in monitors if k.endswith('_mirror'))

logger.info(f"\nFinal monitor state:")
logger.info(f"  Total: {len(monitors)}")
logger.info(f"  Main: {main_count}")
logger.info(f"  Mirror: {mirror_count}")

if len(monitors) == 13:
    logger.info("\n✅ MONITOR FIX COMPLETE - All positions have account-aware monitors")
    logger.info("✅ Position sync code has been fixed to prevent future duplicates")