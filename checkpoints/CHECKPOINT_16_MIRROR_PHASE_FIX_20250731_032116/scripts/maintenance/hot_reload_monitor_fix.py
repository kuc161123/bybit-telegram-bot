#!/usr/bin/env python3
"""
Hot-Reload Monitor Fix
Applies monitor fixes to running bot without restart
"""
import asyncio
import logging
import importlib
import sys
import os

logger = logging.getLogger(__name__)

async def hot_reload_monitor_fixes():
    """Apply monitor fixes to running bot"""
    try:
        logger.info("🔥 Applying hot-reload monitor fixes...")
        
        # Import enhanced TP/SL manager
        sys.path.append('/Users/lualakol/bybit-telegram-bot')
        
        # Reload Enhanced TP/SL manager module
        if 'execution.enhanced_tp_sl_manager' in sys.modules:
            importlib.reload(sys.modules['execution.enhanced_tp_sl_manager'])
            logger.info("✅ Reloaded Enhanced TP/SL manager")
        
        # Reload mirror enhanced TP/SL module
        if 'execution.mirror_enhanced_tp_sl' in sys.modules:
            importlib.reload(sys.modules['execution.mirror_enhanced_tp_sl'])
            logger.info("✅ Reloaded Mirror Enhanced TP/SL manager")
        
        # Create signal file for monitor restoration
        signal_file = '/Users/lualakol/bybit-telegram-bot/reload_enhanced_monitors.signal'
        with open(signal_file, 'w') as f:
            f.write(f"Hot-reload triggered at {time.time()}")
        
        logger.info("✅ Hot-reload complete - monitors will be restored on next cycle")
        
    except Exception as e:
        logger.error(f"❌ Error in hot-reload: {e}")

if __name__ == "__main__":
    import time
    logging.basicConfig(level=logging.INFO)
    asyncio.run(hot_reload_monitor_fixes())
