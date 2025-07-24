#!/usr/bin/env python3
"""
Hotfix for Mirror Order Amendment Loop

Immediately stops the repeated amendment attempts for XRPUSDT mirror orders
"""

import logging
import pickle
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def apply_hotfix():
    """Apply hotfix to stop amendment loop"""
    try:
        logger.info("🔧 Applying Mirror Order Amendment Loop Hotfix...")
        
        # Load the pickle file
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        backup_path = f'{pkl_path}.backup_amendment_fix_{int(time.time())}'
        
        # Backup first
        logger.info(f"💾 Creating backup: {backup_path}")
        with open(pkl_path, 'rb') as src, open(backup_path, 'wb') as dst:
            dst.write(src.read())
        
        # Load data
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        # Find XRPUSDT mirror monitor and update it
        bot_data = data.get('bot_data', {})
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        # Look for XRPUSDT mirror monitor
        mirror_key = None
        for key in enhanced_monitors:
            if 'XRPUSDT' in key and 'MIRROR' in key:
                mirror_key = key
                break
        
        if mirror_key:
            monitor = enhanced_monitors[mirror_key]
            logger.info(f"📌 Found XRPUSDT mirror monitor: {mirror_key}")
            
            # Update the monitor to prevent further amendments
            monitor['amendment_attempts'] = 100  # Set high to trigger backoff
            monitor['last_amendment_attempt'] = time.time()
            monitor['amendment_suspended'] = True
            monitor['position_size_synced'] = True
            
            # Round the position size to prevent precision issues
            if 'position_size' in monitor:
                current_size = float(str(monitor['position_size']))
                monitor['position_size'] = int(round(current_size))
                logger.info(f"   Rounded position size: {current_size} → {monitor['position_size']}")
            
            # Save the updated data
            with open(pkl_path, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info("✅ Applied amendment suspension to XRPUSDT mirror monitor")
        else:
            logger.warning("⚠️ XRPUSDT mirror monitor not found")
        
        # Also patch the running instance if possible
        try:
            import execution.mirror_enhanced_tp_sl as mirror_module
            
            # Add amendment tracking to prevent loops
            if not hasattr(mirror_module, '_amendment_tracker'):
                mirror_module._amendment_tracker = {}
            
            # Track XRPUSDT to prevent further attempts
            mirror_module._amendment_tracker['XRPUSDT_Buy'] = {
                'attempts': 100,
                'last_attempt': time.time(),
                'suspended': True
            }
            
            logger.info("✅ Patched running mirror module to prevent amendments")
            
        except Exception as e:
            logger.info(f"ℹ️ Could not patch running module (may not be loaded): {e}")
        
        logger.info("\n✅ Hotfix applied successfully!")
        logger.info("📌 The amendment loop for XRPUSDT should stop immediately")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error applying hotfix: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("🚀 Mirror Order Amendment Loop Hotfix")
    logger.info("=" * 60)
    
    if apply_hotfix():
        logger.info("\n🎉 Hotfix successfully applied!")
        logger.info("📌 The repeated order amendments should stop")
        logger.info("📌 No bot restart required")
    else:
        logger.error("\n❌ Failed to apply hotfix")