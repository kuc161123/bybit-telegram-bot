#!/usr/bin/env python3
"""
Permanent fix for monitoring loop and approach messages
"""

import asyncio

async def apply_permanent_fixes():
    """Apply permanent fixes to prevent monitoring loops"""
    
    print("\n🔧 APPLYING PERMANENT FIXES")
    print("=" * 60)
    
    # Fix 1: Update _handle_tp_fill to prevent loops
    fix1 = '''
# In enhanced_tp_sl_manager.py, in _handle_tp_fill method, add:

# Check if position is already closed
current_position = await get_position_info(symbol)
if not current_position or float(current_position.get('size', 0)) == 0:
    logger.info(f"✅ Position {symbol} {side} already closed - stopping monitor")
    # Cancel the monitoring task
    if monitor_key in self.position_monitors:
        monitor = self.position_monitors[monitor_key]
        if 'monitoring_task' in monitor:
            monitor['monitoring_task'].cancel()
        del self.position_monitors[monitor_key]
    return

# Also add a check for repeated fills
if "last_tp_fill_id" in monitor_data and monitor_data["last_tp_fill_id"] == order_id:
    logger.debug(f"TP fill {order_id} already processed - skipping")
    return

# Record this fill
monitor_data["last_tp_fill_id"] = order_id
'''
    
    print("Fix 1: Add position closure check and duplicate fill prevention")
    print(fix1)
    
    # Fix 2: Update approach messages
    fix2 = '''
# Replace "Fast approach" messages with approach-aware ones:

# Instead of:
logger.info(f"🎯 Fast approach: TP order filled")

# Use:
approach = monitor_data.get("approach", "unknown")
if approach == "conservative":
    logger.info(f"🎯 Conservative approach: TP{tp_level} order filled")
elif approach == "fast" or len(monitor_data.get("tp_orders", {})) == 1:
    logger.info(f"🎯 TP order filled")
else:
    logger.info(f"🎯 {approach.title()} approach: TP order filled")
'''
    
    print("\nFix 2: Make approach messages dynamic")
    print(fix2)
    
    # Fix 3: Add monitoring stop condition
    fix3 = '''
# In _run_monitor_loop, add position check:

# At the start of each loop iteration:
position = await get_position_info_for_account(symbol, account_type)
if not position or float(position.get('size', 0)) == 0:
    logger.info(f"✅ Position {symbol} {side} closed - stopping Enhanced TP/SL monitor")
    if monitor_key in self.position_monitors:
        del self.position_monitors[monitor_key]
    break  # Exit the monitoring loop
'''
    
    print("\nFix 3: Add monitoring loop exit condition")
    print(fix3)
    
    print("\n" + "=" * 60)
    print("✅ FIXES DOCUMENTED")
    print("\nTo apply these fixes:")
    print("1. Edit execution/enhanced_tp_sl_manager.py")
    print("2. Add the position checks and duplicate prevention")
    print("3. Update the approach messages")
    print("4. Restart the bot")
    
    return True

if __name__ == "__main__":
    asyncio.run(apply_permanent_fixes())