#!/usr/bin/env python3
"""
Clean up duplicate monitors - remove legacy monitors that have account-specific equivalents
"""

import pickle
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def cleanup_duplicate_monitors():
    """Remove legacy monitors that have account-specific versions"""
    try:
        # Load pickle file
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
        
        # Find legacy monitors (without _main or _mirror suffix)
        legacy_monitors = []
        account_specific_monitors = []
        
        for key in monitors:
            if key.endswith('_main') or key.endswith('_mirror'):
                account_specific_monitors.append(key)
            else:
                # Check if it has a number of underscores that suggests it's legacy
                parts = key.split('_')
                if len(parts) == 2:  # symbol_side format
                    legacy_monitors.append(key)
        
        logger.info(f"Found {len(legacy_monitors)} legacy monitors")
        logger.info(f"Found {len(account_specific_monitors)} account-specific monitors")
        
        # Check which legacy monitors have account-specific equivalents
        removed_count = 0
        for legacy_key in legacy_monitors:
            symbol, side = legacy_key.split('_')
            main_key = f"{symbol}_{side}_main"
            mirror_key = f"{symbol}_{side}_mirror"
            
            # If we have an account-specific version, remove the legacy one
            if main_key in monitors or mirror_key in monitors:
                logger.info(f"Removing duplicate legacy monitor: {legacy_key}")
                del monitors[legacy_key]
                removed_count += 1
            else:
                logger.info(f"Keeping legacy monitor (no account-specific version): {legacy_key}")
        
        if removed_count > 0:
            # Save updated data
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"✅ Removed {removed_count} duplicate monitors")
            logger.info(f"📊 Remaining monitors: {len(monitors)}")
            
            # Show remaining monitors
            logger.info("\nRemaining monitors:")
            for key in sorted(monitors.keys()):
                monitor = monitors[key]
                logger.info(f"  {key}: {monitor['symbol']} {monitor['side']} ({monitor.get('account_type', 'unknown')})")
        else:
            logger.info("✅ No duplicate monitors found")
            
    except Exception as e:
        logger.error(f"Error cleaning up monitors: {e}")

if __name__ == "__main__":
    cleanup_duplicate_monitors()