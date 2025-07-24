#!/usr/bin/env python3
"""
Force Trigger All Monitors
=========================

This script forces the bot to recognize all 8 monitors by:
1. Killing any running bot processes
2. Clearing stale monitor data
3. Loading the updated monitors from our sync
4. Starting monitoring tasks for all positions
"""

import pickle
import subprocess
import time
import logging
import os
import signal
from decimal import Decimal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def kill_bot_processes():
    """Kill any running bot processes"""
    try:
        # Find bot processes
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'main.py' in line and 'python' in line:
                parts = line.split()
                pid = int(parts[1])
                logger.info(f"Killing bot process: PID {pid}")
                os.kill(pid, signal.SIGTERM)
                time.sleep(1)
        logger.info("✅ All bot processes killed")
    except Exception as e:
        logger.error(f"Error killing processes: {e}")

def rebuild_monitors():
    """Rebuild monitor data from sync results"""
    try:
        # First, let's verify what we have
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        # Get the monitors created by sync
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        logger.info(f"\n📊 Current state:")
        logger.info(f"Enhanced monitors in pickle: {len(enhanced_monitors)}")
        logger.info(f"Monitor keys: {list(enhanced_monitors.keys())}")
        
        # Check if we have all 8 monitors
        expected_monitors = [
            'CAKEUSDT_Buy_main', 'SNXUSDT_Buy_main', '1INCHUSDT_Buy_main', 'SUSHIUSDT_Buy_main',
            'CAKEUSDT_Buy_mirror', 'SNXUSDT_Buy_mirror', '1INCHUSDT_Buy_mirror', 'SUSHIUSDT_Buy_mirror'
        ]
        
        missing_monitors = []
        for expected in expected_monitors:
            if expected not in enhanced_monitors:
                missing_monitors.append(expected)
        
        if missing_monitors:
            logger.warning(f"⚠️ Missing monitors: {missing_monitors}")
            logger.info("Running sync again...")
            
            # Import and run sync
            from sync_all_positions_to_monitors import PositionMonitorSynchronizer
            import asyncio
            
            synchronizer = PositionMonitorSynchronizer()
            asyncio.run(synchronizer.run())
            
            # Reload data
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
                data = pickle.load(f)
            enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        # Ensure bot_data structure is complete
        if 'bot_data' not in data:
            data['bot_data'] = {}
        
        # Clear any old monitor tasks
        data['bot_data']['monitor_tasks'] = {}
        data['bot_data']['active_monitors'] = {}
        
        # Update enhanced_tp_sl_monitors
        data['bot_data']['enhanced_tp_sl_monitors'] = enhanced_monitors
        
        # Save the updated data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"\n✅ Pickle file updated with {len(enhanced_monitors)} monitors")
        
        # Display summary
        logger.info("\n📊 Monitor Summary:")
        for key, monitor in enhanced_monitors.items():
            logger.info(f"  {key}: size={monitor['position_size']}, account={monitor.get('account_type')}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error rebuilding monitors: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main execution"""
    logger.info("🔄 Starting force trigger for all monitors...")
    
    # Step 1: Kill bot processes
    logger.info("\n1️⃣ Killing bot processes...")
    kill_bot_processes()
    time.sleep(2)
    
    # Step 2: Rebuild monitors
    logger.info("\n2️⃣ Rebuilding monitor data...")
    if not rebuild_monitors():
        logger.error("Failed to rebuild monitors")
        return
    
    # Step 3: Start the bot
    logger.info("\n3️⃣ Starting bot with updated monitors...")
    logger.info("Run: python3 main.py")
    logger.info("\n✅ Force trigger complete!")
    logger.info("The bot should now load all 8 monitors")

if __name__ == "__main__":
    main()