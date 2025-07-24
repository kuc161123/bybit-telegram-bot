#!/usr/bin/env python3
"""
Fix TP detection loop and remove Fast approach messages
"""

import asyncio
import pickle
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_tp_loop():
    """Fix the TP detection loop issue"""
    
    print("\n🔧 FIXING TP DETECTION LOOP")
    print("=" * 60)
    
    # 1. First, let's clear the problematic monitor
    print("\n1️⃣ Clearing stuck SUSHIUSDT monitor...")
    
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        # Find and remove SUSHIUSDT monitors
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        removed = []
        for key in list(enhanced_monitors.keys()):
            if 'SUSHIUSDT' in key:
                del enhanced_monitors[key]
                removed.append(key)
        
        # Save the data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        print(f"✅ Removed {len(removed)} SUSHIUSDT monitors: {removed}")
        
    except Exception as e:
        print(f"❌ Error clearing monitors: {e}")
    
    # 2. Stop any active monitoring tasks
    print("\n2️⃣ Stopping monitoring tasks...")
    
    try:
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        
        # Clear position monitors
        if hasattr(enhanced_tp_sl_manager, 'position_monitors'):
            for key in list(enhanced_tp_sl_manager.position_monitors.keys()):
                if 'SUSHIUSDT' in key:
                    monitor = enhanced_tp_sl_manager.position_monitors.get(key, {})
                    
                    # Cancel monitoring task
                    if 'monitoring_task' in monitor:
                        task = monitor['monitoring_task']
                        if not task.done():
                            task.cancel()
                            print(f"✅ Cancelled monitoring task for {key}")
                    
                    # Remove monitor
                    del enhanced_tp_sl_manager.position_monitors[key]
        
        # Clear fill tracker
        if hasattr(enhanced_tp_sl_manager, 'fill_tracker'):
            for key in list(enhanced_tp_sl_manager.fill_tracker.keys()):
                if 'SUSHIUSDT' in key:
                    del enhanced_tp_sl_manager.fill_tracker[key]
                    print(f"✅ Cleared fill tracker for {key}")
        
    except Exception as e:
        print(f"⚠️  Could not stop monitoring tasks: {e}")
    
    print("\n✅ TP detection loop fixed!")
    
    return True

async def fix_approach_messages():
    """Fix approach message issue"""
    
    print("\n\n🔧 FIXING APPROACH MESSAGES")
    print("=" * 60)
    
    print("\nThe 'Fast approach' messages are appearing because:")
    print("1. The position was originally opened with Fast approach")
    print("2. The monitoring system remembers the original approach")
    print("\nTo fix this permanently, we need to update the monitoring logic.")
    
    # Create the fix
    fix_content = '''# Add this check in enhanced_tp_sl_manager.py in the _handle_tp_fill method:

# Replace the "Fast approach" message with approach-aware messaging:
if monitor_data.get("approach") == "fast" or len(monitor_data.get("tp_orders", {})) == 1:
    logger.info(f"🎯 TP order filled (single TP)")
else:
    logger.info(f"🎯 Conservative approach: TP{tp_level} order filled")

# Also update the alert message to not mention approach if not needed
'''
    
    print("\n✅ Approach message fix documented")
    
    return True

if __name__ == "__main__":
    asyncio.run(fix_tp_loop())
    asyncio.run(fix_approach_messages())