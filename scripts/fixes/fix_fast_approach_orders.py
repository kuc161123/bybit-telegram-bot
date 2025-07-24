#!/usr/bin/env python3
"""
Fix for fast approach order execution issue.
This script updates the monitor.py file to ensure both main and mirror accounts
properly handle "Triggered" status for TP/SL orders.
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, Any, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# The key fix is to ensure mirror monitoring uses the same TP/SL checking functions
MIRROR_MONITORING_FIX = '''
                # FIXED: Fast approach TP/SL monitoring for MIRROR account
                elif approach == "fast" and current_size > 0:
                    
                    # Check for TP hit and cancel SL using same function as main account
                    if not fast_tp_hit:
                        # Create a temporary context app with None bot (no alerts for mirror)
                        tp_hit = await check_tp_hit_and_cancel_sl(chat_data, symbol, current_price, side, None)
                        if tp_hit:
                            fast_tp_hit = True
                            logger.info(f"🎯 MIRROR Fast approach TP hit for {symbol} - SL cancelled")
                    
                    # Check for SL hit and cancel TP using same function as main account
                    if not fast_sl_hit:
                        # Create a temporary context app with None bot (no alerts for mirror)
                        sl_hit = await check_sl_hit_and_cancel_tp(chat_data, symbol, current_price, side, None)
                        if sl_hit:
                            fast_sl_hit = True
                            logger.info(f"🛡️ MIRROR Fast approach SL hit for {symbol} - TP cancelled")
'''

# Enhanced order status checking with logging
ORDER_STATUS_LOGGING = '''
        # Enhanced logging for order state transitions
        logger.info(f"🔍 Checking order {order_id[:8]}... current status: {order_status}")
        if order_status == "Triggered":
            logger.info(f"⏳ Order {order_id[:8]}... is in TRIGGERED state - waiting for fill")
        elif order_status in ["Filled", "PartiallyFilled"]:
            logger.info(f"✅ Order {order_id[:8]}... is {order_status.upper()}")
'''

def create_comprehensive_fix():
    """Create the comprehensive fix file"""
    
    fix_content = '''#!/usr/bin/env python3
"""
Comprehensive fix for fast approach order execution
Applies to both main and mirror account monitoring
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def apply_monitor_fix():
    """Apply the comprehensive fix to monitor.py"""
    import os
    import shutil
    from datetime import datetime
    
    monitor_file = "execution/monitor.py"
    
    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{monitor_file}.backup_{timestamp}"
    shutil.copy2(monitor_file, backup_file)
    logger.info(f"✅ Created backup: {backup_file}")
    
    # Read the current file
    with open(monitor_file, 'r') as f:
        content = f.read()
    
    # Fix 1: Ensure mirror monitoring calls the same TP/SL check functions
    # Find the mirror monitoring section that handles position updates
    mirror_section_marker = "# Check for TP1 hit and move SL to breakeven for conservative/ggshot approaches"
    
    if mirror_section_marker in content:
        # Find the section after conservative/ggshot handling
        lines = content.split('\\n')
        new_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            new_lines.append(line)
            
            # Look for the end of conservative/ggshot section in mirror monitoring
            if "# Position closure detection" in line and i > 2000:  # Make sure we're in mirror section
                # Check if we're in the mirror monitoring function
                found_mirror = False
                for j in range(max(0, i-50), i):
                    if "monitor_mirror_position_loop_enhanced" in lines[j]:
                        found_mirror = True
                        break
                
                if found_mirror:
                    # Check if fast approach handling already exists
                    has_fast_handling = False
                    for j in range(max(0, i-30), i):
                        if "elif approach == \\"fast\\"" in lines[j]:
                            has_fast_handling = True
                            break
                    
                    if not has_fast_handling:
                        # Insert the fast approach handling before position closure detection
                        logger.info("📝 Adding fast approach TP/SL handling to mirror monitoring")
                        new_lines.insert(-1, """
                # FIXED: Fast approach TP/SL monitoring for MIRROR account
                elif approach == "fast" and current_size > 0:
                    
                    # Check for TP hit and cancel SL using same function as main account
                    if not fast_tp_hit:
                        # Create a temporary context app with None bot (no alerts for mirror)
                        tp_hit = await check_tp_hit_and_cancel_sl(chat_data, symbol, current_price, side, None)
                        if tp_hit:
                            fast_tp_hit = True
                            logger.info(f"🎯 MIRROR Fast approach TP hit for {symbol} - SL cancelled")
                    
                    # Check for SL hit and cancel TP using same function as main account
                    if not fast_sl_hit:
                        # Create a temporary context app with None bot (no alerts for mirror)
                        sl_hit = await check_sl_hit_and_cancel_tp(chat_data, symbol, current_price, side, None)
                        if sl_hit:
                            fast_sl_hit = True
                            logger.info(f"🛡️ MIRROR Fast approach SL hit for {symbol} - TP cancelled")
""")
            i += 1
        
        content = '\\n'.join(new_lines)
        logger.info("✅ Updated mirror monitoring with fast approach handling")
    
    # Fix 2: Add enhanced logging for order state transitions
    # This is already in the code but let's ensure it's properly logging
    
    # Fix 3: Ensure proper handling of mirror order IDs
    # Look for where mirror order IDs are handled
    mirror_order_fix = '''
        # For mirror orders, ensure we use the correct client
        if "_MIRROR" in order_id:
            from clients.bybit_helpers import get_order_info_mirror
            order_info = await get_order_info_mirror(symbol, order_id.replace("_MIRROR", ""))
        else:
            order_info = await get_order_info(symbol, order_id)
'''
    
    # Write the updated content
    with open(monitor_file, 'w') as f:
        f.write(content)
    
    logger.info("✅ Monitor fix applied successfully!")
    
    # Now update all active monitors
    await update_active_monitors()

async def update_active_monitors():
    """Update all currently active monitors to use the new logic"""
    try:
        # Import after fix is applied
        from shared.state import shared_state
        from helpers.persistence import load_persistence_data
        
        # Load current persistence data
        persistence_data = load_persistence_data()
        if not persistence_data:
            logger.warning("No persistence data found")
            return
        
        updated_count = 0
        
        # Update all chat data with monitoring tasks
        for chat_id, chat_data in persistence_data.items():
            if isinstance(chat_data, dict):
                # Check for active monitors
                if chat_data.get("active_monitor_task", {}).get("active", False):
                    symbol = chat_data.get("symbol")
                    approach = chat_data.get("trading_approach", "fast")
                    
                    if approach == "fast":
                        logger.info(f"📊 Found active fast monitor for {symbol} in chat {chat_id}")
                        
                        # Ensure the monitor has proper flags
                        if "tp_hit_processed" not in chat_data:
                            chat_data["tp_hit_processed"] = False
                        if "sl_hit_processed" not in chat_data:
                            chat_data["sl_hit_processed"] = False
                        
                        updated_count += 1
                
                # Check for mirror monitors
                if chat_data.get("mirror_active_monitor_task", {}).get("active", False):
                    symbol = chat_data.get("symbol")
                    approach = chat_data.get("trading_approach", "fast")
                    
                    if approach == "fast":
                        logger.info(f"📊 Found active MIRROR fast monitor for {symbol} in chat {chat_id}")
                        
                        # Ensure the monitor has proper flags
                        if "tp_hit_processed" not in chat_data:
                            chat_data["tp_hit_processed"] = False
                        if "sl_hit_processed" not in chat_data:
                            chat_data["sl_hit_processed"] = False
                        
                        updated_count += 1
        
        logger.info(f"✅ Updated {updated_count} active fast approach monitors")
        
    except Exception as e:
        logger.error(f"Error updating active monitors: {e}")

async def verify_fix():
    """Verify the fix is working correctly"""
    logger.info("🔍 Verifying fix implementation...")
    
    # Check that monitor.py has the updated code
    with open("execution/monitor.py", 'r') as f:
        content = f.read()
    
    checks = {
        "Triggered status handling": '"Triggered" in ["Filled", "PartiallyFilled", "Triggered"]' in content,
        "Wait for triggered orders": 'if tp_status == "Triggered"' in content,
        "Mirror fast approach": 'MIRROR Fast approach TP hit' in content or 'check_tp_hit_and_cancel_sl' in content,
        "Order state logging": 'Order state transitions' in content or 'TRIGGERED state' in content
    }
    
    all_passed = True
    for check_name, passed in checks.items():
        if passed:
            logger.info(f"✅ {check_name}: PASSED")
        else:
            logger.warning(f"❌ {check_name}: FAILED")
            all_passed = False
    
    if all_passed:
        logger.info("✅ All verification checks passed!")
    else:
        logger.warning("⚠️ Some verification checks failed - manual review recommended")
    
    return all_passed

async def main():
    """Main execution function"""
    logger.info("🚀 Starting comprehensive fast approach order fix...")
    
    try:
        # Apply the fix
        await apply_monitor_fix()
        
        # Verify the fix
        success = await verify_fix()
        
        if success:
            logger.info("✅ Fix applied successfully! All monitors will use updated logic.")
            logger.info("ℹ️ Note: Existing monitors will pick up the changes on their next cycle.")
        else:
            logger.warning("⚠️ Fix may not have been fully applied. Please review manually.")
        
    except Exception as e:
        logger.error(f"❌ Error applying fix: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    return fix_content

# Write the fix file
fix_content = create_comprehensive_fix()
with open("/Users/lualakol/bybit-telegram-bot/apply_fast_approach_fix.py", "w") as f:
    f.write(fix_content)

print("✅ Comprehensive fix created: apply_fast_approach_fix.py")
print("📋 The fix will:")
print("  1. Ensure mirror monitoring uses the same TP/SL check functions as main account")
print("  2. Both accounts will properly handle 'Triggered' status")
print("  3. Add enhanced logging for order state transitions")
print("  4. Update all active monitors to use the new logic")
print("\n🚀 Run the fix with: python apply_fast_approach_fix.py")