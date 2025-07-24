#!/usr/bin/env python3
"""
Activate LDOUSDT_Sell_mirror monitor without restarting the bot
"""

import asyncio
import pickle
import logging
from decimal import Decimal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def activate_monitor():
    """Activate the LDOUSDT_Sell_mirror monitor"""
    
    # Import the enhanced TP/SL manager
    from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
    
    # Load the monitor data from pickle
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)
    
    monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
    monitor_data = monitors.get('LDOUSDT_Sell_mirror')
    
    if not monitor_data:
        logger.error("❌ LDOUSDT_Sell_mirror monitor not found in pickle")
        return
    
    # Start monitoring for this position
    logger.info("🚀 Activating LDOUSDT_Sell_mirror monitor...")
    
    # Create a monitoring task
    monitor_key = 'LDOUSDT_Sell_mirror'
    
    # Check if already monitoring
    if monitor_key in enhanced_tp_sl_manager.position_monitors:
        logger.warning(f"⚠️ Monitor {monitor_key} is already active")
        return
    
    # Start the monitor
    task = asyncio.create_task(
        enhanced_tp_sl_manager._run_monitor_loop(monitor_key, 'mirror')
    )
    
    # Store the task reference
    enhanced_tp_sl_manager.position_monitors[monitor_key] = {
        'task': task,
        'started_at': asyncio.get_event_loop().time(),
        'account_type': 'mirror'
    }
    
    logger.info(f"✅ Monitor activated for {monitor_key}")
    logger.info(f"   Position: {monitor_data['position_size']} @ {monitor_data['entry_price']}")
    logger.info(f"   TP orders: {len(monitor_data['tp_orders'])}")
    logger.info(f"   SL order: {'Yes' if monitor_data['sl_order'] else 'No'}")
    
    # Also update the monitor_tasks in bot_data for dashboard
    if 'monitor_tasks' not in data['bot_data']:
        data['bot_data']['monitor_tasks'] = {}
    
    # Create dashboard monitor entry
    dashboard_key = f"None_LDOUSDT_conservative_mirror"
    data['bot_data']['monitor_tasks'][dashboard_key] = {
        'chat_id': None,
        'symbol': 'LDOUSDT',
        'approach': 'conservative',
        'monitoring_mode': 'ENHANCED_TP_SL',
        'started_at': asyncio.get_event_loop().time(),
        'active': True,
        'account_type': 'mirror',
        'system_type': 'enhanced_tp_sl',
        'side': 'Sell'
    }
    
    # Save the updated data
    with open(pkl_path, 'wb') as f:
        pickle.dump(data, f)
    
    logger.info("✅ Dashboard monitor task also created")
    
    # Give it a moment to start
    await asyncio.sleep(2)
    
    # Verify it's running
    if monitor_key in enhanced_tp_sl_manager.position_monitors:
        task_info = enhanced_tp_sl_manager.position_monitors[monitor_key]
        if not task_info['task'].done():
            logger.info("✅ Monitor is actively running!")
        else:
            logger.error("❌ Monitor task completed unexpectedly")
    
    # Show all active monitors
    logger.info(f"\n📊 Total active monitors: {len(enhanced_tp_sl_manager.position_monitors)}")
    for key in sorted(enhanced_tp_sl_manager.position_monitors.keys()):
        logger.info(f"   - {key}")

async def main():
    """Main entry point"""
    try:
        await activate_monitor()
    except Exception as e:
        logger.error(f"❌ Error activating monitor: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())