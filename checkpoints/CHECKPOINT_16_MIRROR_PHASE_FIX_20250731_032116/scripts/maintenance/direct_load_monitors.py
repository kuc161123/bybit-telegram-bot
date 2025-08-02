#!/usr/bin/env python3
"""
Directly load monitors into Enhanced TP/SL Manager
This bypasses the background loop and loads monitors immediately
"""
import asyncio
import sys
import os
import pickle
import logging

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def direct_load_monitors():
    """Directly load monitors into Enhanced TP/SL Manager"""
    try:
        logger.info("🚀 DIRECT LOADING ENHANCED TP/SL MONITORS")
        logger.info("=" * 50)
        
        # Import Enhanced TP/SL Manager
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        
        # Check current state
        logger.info(f"📊 Current monitors in manager: {len(enhanced_tp_sl_manager.position_monitors)}")
        
        # Load from persistence
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        persisted_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        logger.info(f"📊 Found {len(persisted_monitors)} monitors in persistence")
        
        if persisted_monitors:
            # Clear existing monitors and load from persistence
            enhanced_tp_sl_manager.position_monitors.clear()
            enhanced_tp_sl_manager.position_monitors.update(persisted_monitors)
            
            logger.info(f"✅ Loaded {len(persisted_monitors)} monitors into Enhanced TP/SL Manager")
            logger.info(f"📊 Manager now has {len(enhanced_tp_sl_manager.position_monitors)} monitors")
            
            # Show loaded monitors
            logger.info("📋 Loaded monitors:")
            for key, monitor in enhanced_tp_sl_manager.position_monitors.items():
                symbol = monitor.get('symbol')
                side = monitor.get('side')
                account = monitor.get('account_type', 'unknown')
                logger.info(f"  • {key}: {symbol} {side} ({account})")
            
            logger.info("=" * 50)
            logger.info("🎉 MONITORS LOADED SUCCESSFULLY!")
            logger.info("The Enhanced TP/SL Manager should now be monitoring all positions")
            
        else:
            logger.warning("❌ No monitors found in persistence file")
            
    except Exception as e:
        logger.error(f"❌ Error loading monitors: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(direct_load_monitors())