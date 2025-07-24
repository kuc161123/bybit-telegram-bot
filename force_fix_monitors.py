#!/usr/bin/env python3
"""
Force fix monitor activation - ensuring the change is saved properly
"""

import pickle
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def force_fix_monitors():
    """Force fix monitor activation with verification"""
    try:
        logger.info("=" * 60)
        logger.info("FORCE FIXING MONITOR ACTIVATION")
        logger.info("=" * 60)
        
        # Load pickle data
        logger.info("Loading pickle file...")
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        # Get monitors
        if 'bot_data' not in data:
            data['bot_data'] = {}
        if 'enhanced_tp_sl_monitors' not in data['bot_data']:
            data['bot_data']['enhanced_tp_sl_monitors'] = {}
        
        monitors = data['bot_data']['enhanced_tp_sl_monitors']
        logger.info(f"Found {len(monitors)} monitors")
        
        # Create backup
        backup_filename = f"bybit_bot_dashboard_v4.1_enhanced.pkl.backup_force_fix_{int(datetime.now().timestamp())}"
        import shutil
        shutil.copy('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_filename)
        logger.info(f"📦 Created backup: {backup_filename}")
        
        # Fix ALL monitors
        fixed_count = 0
        for key, monitor in monitors.items():
            if monitor.get('active') != True:
                logger.info(f"Fixing {key}: {monitor.get('active')} -> True")
                monitor['active'] = True
                fixed_count += 1
        
        logger.info(f"Fixed {fixed_count} monitors")
        
        # Save with explicit pickle protocol
        logger.info("Saving updated pickle file...")
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        logger.info("✅ Pickle file saved")
        
        # Immediate verification
        logger.info("Verifying changes...")
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            verify_data = pickle.load(f)
        
        verify_monitors = verify_data['bot_data']['enhanced_tp_sl_monitors']
        active_count = sum(1 for m in verify_monitors.values() if m.get('active') == True)
        
        logger.info(f"✅ Verification: {active_count}/{len(verify_monitors)} monitors now active")
        
        if active_count == len(verify_monitors):
            logger.info("🎉 ALL MONITORS SUCCESSFULLY ACTIVATED!")
        else:
            logger.error(f"❌ Only {active_count} monitors activated out of {len(verify_monitors)}")
            return False
        
        # Show a sample
        sample_key = list(verify_monitors.keys())[0]
        sample_monitor = verify_monitors[sample_key]
        logger.info(f"\n📊 Sample verification - {sample_key}:")
        logger.info(f"   Active: {sample_monitor.get('active')} (type: {type(sample_monitor.get('active'))})")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Force fix failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = force_fix_monitors()
    if success:
        print("\n🎉 Force fix successful! All monitors activated.")
    else:
        print("\n❌ Force fix failed!")
        exit(1)