#!/usr/bin/env python3
"""
Simple check of current pickle data and potential monitor restoration
"""

import pickle
import os
import logging
from decimal import Decimal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_pickle_data():
    """Check what monitors are in the pickle file"""
    try:
        pickle_file = "/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl"
        
        if not os.path.exists(pickle_file):
            logger.error(f"Pickle file not found: {pickle_file}")
            return
            
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        logger.info(f"📊 Found {len(monitors)} monitors in pickle file:")
        for monitor_key, monitor_data in monitors.items():
            symbol = monitor_data.get('symbol', 'Unknown')
            side = monitor_data.get('side', 'Unknown')
            account_type = monitor_data.get('account_type', 'Unknown')
            position_size = monitor_data.get('position_size', 'Unknown')
            phase = monitor_data.get('phase', 'Unknown')
            
            logger.info(f"   {monitor_key}: {symbol} {side} ({account_type}) - Size: {position_size}, Phase: {phase}")
        
        # Check if SOLUSDT monitor exists
        solusdt_main = "SOLUSDT_Buy_main"
        solusdt_mirror = "SOLUSDT_Buy_mirror"
        
        if solusdt_main in monitors:
            logger.info(f"✅ SOLUSDT main monitor exists in pickle")
        else:
            logger.warning(f"⚠️ SOLUSDT main monitor missing from pickle")
            
        if solusdt_mirror in monitors:
            logger.info(f"✅ SOLUSDT mirror monitor exists in pickle")
        else:
            logger.warning(f"⚠️ SOLUSDT mirror monitor missing from pickle")
            
        return monitors
        
    except Exception as e:
        logger.error(f"❌ Error reading pickle file: {e}")
        return {}

def create_signal_file():
    """Create a signal file to trigger monitor reload"""
    signal_file = "/Users/lualakol/bybit-telegram-bot/.force_load_all_monitors"
    
    try:
        with open(signal_file, 'w') as f:
            f.write("1")
        logger.info(f"✅ Created signal file: {signal_file}")
        logger.info("🔄 Bot will reload all monitors from pickle on next cycle")
        return True
    except Exception as e:
        logger.error(f"❌ Error creating signal file: {e}")
        return False

if __name__ == "__main__":
    logger.info("🔍 Checking pickle data and monitor status...")
    
    monitors = check_pickle_data()
    
    if monitors:
        logger.info("📊 Pickle data looks good")
        
        # Create signal to force reload
        if create_signal_file():
            logger.info("✅ Signal file created - monitors will be reloaded")
            logger.info("⏰ Check your bot logs in the next few seconds for reload activity")
        else:
            logger.error("❌ Failed to create signal file")
    else:
        logger.error("❌ No monitors found in pickle file")
    
    logger.info("🎯 Check complete!")