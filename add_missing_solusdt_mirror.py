#!/usr/bin/env python3
"""
Add missing SOLUSDT_Buy_mirror monitor to pickle file
"""

import pickle
import os
import logging
from decimal import Decimal
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_solusdt_mirror_monitor():
    """Add the missing SOLUSDT_Buy_mirror monitor"""
    try:
        pickle_file = "/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl"
        
        # Backup first
        backup_file = f"{pickle_file}.backup_{int(time.time())}"
        os.system(f"cp {pickle_file} {backup_file}")
        logger.info(f"✅ Created backup: {backup_file}")
        
        # Read current data
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        logger.info(f"📊 Current monitors: {list(monitors.keys())}")
        
        # Check if SOLUSDT_Buy_main exists to copy data
        if "SOLUSDT_Buy_main" in monitors:
            main_monitor = monitors["SOLUSDT_Buy_main"]
            logger.info(f"✅ Found SOLUSDT_Buy_main monitor to use as template")
            
            # Create mirror monitor with proportional sizing
            # Mirror typically uses ~33% of main position size
            main_size = main_monitor.get('position_size', Decimal('32.7'))
            mirror_size = main_size * Decimal('0.383')  # Approximate ratio based on margin differences
            
            mirror_monitor = {
                "symbol": "SOLUSDT",
                "side": "Buy",
                "account_type": "mirror",
                "position_size": mirror_size,
                "remaining_size": mirror_size,
                "entry_price": main_monitor.get('entry_price', Decimal('0')),
                "phase": "MONITORING",  # Mirror typically in MONITORING phase
                "tp_orders": [],  # Will be populated by bot
                "sl_order": None,  # Will be populated by bot
                "limit_orders": [],  # Will be populated by bot
                "created_at": time.time(),
                "last_updated": time.time(),
                "chat_id": main_monitor.get('chat_id'),
                "approach": main_monitor.get('approach', 'conservative'),
                "close_detections": 0  # Reset any close detections
            }
            
            # Add to monitors
            monitors["SOLUSDT_Buy_mirror"] = mirror_monitor
            
            # Save back to pickle
            with open(pickle_file, 'wb') as f:
                pickle.dump(data, f)
                
            logger.info(f"✅ Added SOLUSDT_Buy_mirror monitor with size: {mirror_size}")
            logger.info(f"📊 Total monitors now: {len(monitors)}")
            logger.info(f"📊 All monitors: {list(monitors.keys())}")
            
            return True
            
        else:
            logger.error("❌ SOLUSDT_Buy_main monitor not found - cannot create mirror")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error adding mirror monitor: {e}")
        return False

def verify_monitors():
    """Verify all expected monitors exist"""
    try:
        pickle_file = "/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl"
        
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        expected_monitors = [
            "SNXUSDT_Buy_main",
            "SNXUSDT_Buy_mirror", 
            "ONTUSDT_Buy_main",
            "ONTUSDT_Buy_mirror",
            "SOLUSDT_Buy_main",
            "SOLUSDT_Buy_mirror"
        ]
        
        logger.info("🔍 Verifying monitors...")
        all_good = True
        
        for monitor_key in expected_monitors:
            if monitor_key in monitors:
                monitor = monitors[monitor_key]
                size = monitor.get('position_size', 'Unknown')
                phase = monitor.get('phase', 'Unknown')
                logger.info(f"✅ {monitor_key}: Size={size}, Phase={phase}")
            else:
                logger.warning(f"❌ {monitor_key}: MISSING")
                all_good = False
                
        if all_good:
            logger.info(f"✅ All {len(expected_monitors)} monitors present!")
        else:
            logger.warning(f"⚠️ Some monitors missing")
            
        return all_good
        
    except Exception as e:
        logger.error(f"❌ Error verifying monitors: {e}")
        return False

if __name__ == "__main__":
    logger.info("🔧 Adding missing SOLUSDT_Buy_mirror monitor...")
    logger.info("=" * 50)
    
    # Add the missing monitor
    success = add_solusdt_mirror_monitor()
    
    if success:
        logger.info("✅ Successfully added SOLUSDT_Buy_mirror monitor")
        
        # Verify all monitors
        logger.info("\n🔍 Verifying all monitors...")
        verify_monitors()
        
        # Create signal for reload
        signal_file = "/Users/lualakol/bybit-telegram-bot/.force_load_all_monitors"
        with open(signal_file, 'w') as f:
            f.write("1")
        logger.info(f"\n✅ Created reload signal - bot will load all 6 monitors on next cycle")
        
    else:
        logger.error("❌ Failed to add mirror monitor")
    
    logger.info("=" * 50)
    logger.info("🎯 Complete!")