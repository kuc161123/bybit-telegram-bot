#!/usr/bin/env python3
"""
Verify all Enhanced TP/SL monitors are active and running
"""
import asyncio
import logging
import pickle
from datetime import datetime
from typing import Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def check_monitors_status():
    """Check the status of all Enhanced TP/SL monitors"""
    # Load pickle data
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)
    
    bot_data = data.get('bot_data', {})
    enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
    monitor_tasks = bot_data.get('monitor_tasks', {})
    
    logger.info("=" * 60)
    logger.info("ENHANCED TP/SL MONITORS STATUS")
    logger.info("=" * 60)
    
    # Check Enhanced monitors
    logger.info(f"\nTotal Enhanced Monitors: {len(enhanced_monitors)}")
    
    active_count = 0
    for key, monitor in enhanced_monitors.items():
        symbol = monitor.get('symbol')
        side = monitor.get('side')
        chat_id = monitor.get('chat_id')
        account_type = monitor.get('account_type', 'main')
        phase = monitor.get('phase', 'UNKNOWN')
        last_check = monitor.get('last_check', 0)
        
        # Calculate time since last check
        if last_check:
            time_since = datetime.now().timestamp() - last_check
            time_str = f"{int(time_since)}s ago"
        else:
            time_str = "Never"
        
        status = "✅ ACTIVE" if phase == "MONITORING" else "❌ INACTIVE"
        chat_status = "✅" if chat_id else "❌ NO CHAT_ID"
        
        logger.info(f"\n{key}:")
        logger.info(f"  Symbol: {symbol} {side}")
        logger.info(f"  Account: {account_type}")
        logger.info(f"  Status: {status}")
        logger.info(f"  Phase: {phase}")
        logger.info(f"  Chat ID: {chat_id} {chat_status}")
        logger.info(f"  Last Check: {time_str}")
        
        if phase == "MONITORING":
            active_count += 1
    
    # Check Dashboard monitor tasks
    logger.info(f"\n\nTotal Dashboard Monitor Tasks: {len(monitor_tasks)}")
    
    dashboard_active = 0
    for key, task in monitor_tasks.items():
        if task.get('active'):
            dashboard_active += 1
            logger.info(f"\n{key}:")
            logger.info(f"  Symbol: {task.get('symbol')}")
            logger.info(f"  System: {task.get('system_type')}")
            logger.info(f"  Active: ✅")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Enhanced Monitors: {active_count}/{len(enhanced_monitors)} active")
    logger.info(f"Dashboard Tasks: {dashboard_active}/{len(monitor_tasks)} active")
    
    if active_count == len(enhanced_monitors):
        logger.info("\n✅ All Enhanced TP/SL monitors are ACTIVE and ready!")
    else:
        logger.warning(f"\n⚠️ Only {active_count} out of {len(enhanced_monitors)} monitors are active")
    
    # Check if bot is running
    logger.info("\n" + "=" * 60)
    logger.info("BOT RUNTIME CHECK")
    logger.info("=" * 60)
    
    import os
    import subprocess
    
    try:
        # Check if main.py is running
        result = subprocess.run(['pgrep', '-f', 'main.py'], capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            logger.info(f"✅ Bot is running! Process IDs: {', '.join(pids)}")
            logger.info("\nThe Enhanced TP/SL monitors are actively monitoring your positions.")
        else:
            logger.warning("⚠️ Bot is not running! Start the bot to activate monitoring:")
            logger.warning("   python main.py")
    except Exception as e:
        logger.error(f"Could not check bot status: {e}")

async def main():
    await check_monitors_status()

if __name__ == "__main__":
    asyncio.run(main())