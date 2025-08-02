#!/usr/bin/env python3
"""
Trigger the bot to load all 8 monitors
"""

import pickle
import logging
import os
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def trigger_reload():
    """Trigger monitor reload by temporarily clearing monitors"""
    try:
        # Create force load signal
        signal_file = '.force_load_all_monitors'
        with open(signal_file, 'w') as f:
            f.write("# Force load signal\n")
        logger.info(f"✅ Created {signal_file}")
        
        # Also create the regular reload signal
        reload_signal = 'reload_enhanced_monitors.signal'
        with open(reload_signal, 'w') as f:
            f.write("reload")
        logger.info(f"✅ Created {reload_signal}")
        
        # Load pickle and temporarily clear monitors to trigger reload
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        # Store original monitors
        original_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        logger.info(f"📊 Original monitors: {len(original_monitors)}")
        
        # Clear monitors temporarily
        data['bot_data']['enhanced_tp_sl_monitors'] = {}
        
        # Save without monitors
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        logger.info("⏳ Cleared monitors temporarily - bot will reload from backup...")
        time.sleep(2)
        
        # Restore monitors
        data['bot_data']['enhanced_tp_sl_monitors'] = original_monitors
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        logger.info("✅ Monitors restored - bot should now load all 8")
        logger.info("📊 The bot will detect empty monitors and trigger reload with force load signal")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    trigger_reload()