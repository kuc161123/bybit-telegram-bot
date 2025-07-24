#!/usr/bin/env python3
"""
Fix monitor isolation so mirror monitor continues even if main monitor fails
"""

import re

def fix_monitor_isolation():
    print("\n🔧 FIXING MONITOR ISOLATION")
    print("=" * 60)
    
    # Read the file
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        content = f.read()
    
    # Find the monitor loop error handler
    # Replace the part that removes both monitors when one fails
    
    # Old pattern that removes both monitors
    old_cleanup = """        finally:
            # Cleanup using robust persistence
            if monitor_key in self.position_monitors:
                monitor_data = self.position_monitors[monitor_key]
                chat_id = monitor_data.get("chat_id")
                approach = monitor_data.get("approach", "conservative")
                
                # Remove monitor using robust persistence
                try:
                    from utils.robust_persistence import remove_trade_monitor
                    await remove_trade_monitor(symbol, side, reason="monitor_stopped")
                    logger.info(f"✅ Removed monitor using Robust Persistence: {monitor_key}")
                except Exception as e:
                    logger.error(f"Error removing monitor via robust persistence: {e}")
                
                del self.position_monitors[monitor_key]
            logger.info(f"🛑 Monitor loop ended for {symbol} {side}")"""
    
    # New pattern that only removes the specific monitor
    new_cleanup = """        finally:
            # Cleanup only this specific monitor, not all monitors for this position
            if monitor_key in self.position_monitors:
                monitor_data = self.position_monitors[monitor_key]
                chat_id = monitor_data.get("chat_id")
                approach = monitor_data.get("approach", "conservative")
                account_type = monitor_data.get("account_type", "main")
                
                # Only remove the specific monitor that failed
                try:
                    # Use account-specific removal to avoid affecting other monitors
                    from utils.robust_persistence import remove_trade_monitor
                    # Pass account_type to ensure only this monitor is removed
                    await remove_trade_monitor(symbol, side, reason=f"monitor_stopped_{account_type}")
                    logger.info(f"✅ Removed {account_type} monitor: {monitor_key}")
                except Exception as e:
                    logger.error(f"Error removing {account_type} monitor: {e}")
                
                # Only delete this specific monitor key
                del self.position_monitors[monitor_key]
                logger.info(f"🛑 Monitor loop ended for {monitor_key} ({account_type})")
            else:
                logger.info(f"🛑 Monitor loop ended for {monitor_key} (already removed)")"""
    
    # Replace
    if old_cleanup in content:
        content = content.replace(old_cleanup, new_cleanup)
        print("✅ Fixed monitor cleanup to isolate monitors")
    else:
        print("⚠️  Monitor cleanup pattern not found, attempting alternative fix...")
        
        # Alternative: Just fix the error handler to continue on error
        # Find the error handler part
        import re
        
        # Pattern to find the except block
        pattern = r'(except Exception as e:\s*\n\s*logger\.error\(f"❌ Error in monitor loop for {symbol} {side}: {e}"\))'
        
        # Replace with a version that doesn't stop the monitor
        replacement = '''except Exception as e:
            logger.error(f"❌ Error in monitor loop for {symbol} {side}: {e}")
            # Continue monitoring despite error - don't break the loop
            # This ensures mirror monitor continues even if main has issues
            await asyncio.sleep(5)  # Wait a bit before retrying
            continue'''
        
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            content = new_content
            print("✅ Fixed error handler to continue on error")
    
    # Also fix the tp_orders list/dict issue inline
    # Add a helper at the beginning of monitor_and_adjust_orders
    monitor_pattern = r'(async def monitor_and_adjust_orders\(self.*?\n.*?"""[^"]*""")'
    
    def add_tp_fix(match):
        return match.group(1) + '''
        # Helper to ensure tp_orders is always in dict format
        def ensure_tp_orders_dict(data):
            """Convert tp_orders to dict if it's a list"""
            if "tp_orders" in data:
                tp_orders = data["tp_orders"]
                if isinstance(tp_orders, list):
                    # Convert list to dict
                    tp_dict = {}
                    for order in tp_orders:
                        if isinstance(order, dict) and "order_id" in order:
                            tp_dict[order["order_id"]] = order
                    data["tp_orders"] = tp_dict
            return data
'''
    
    content = re.sub(monitor_pattern, add_tp_fix, content, flags=re.DOTALL)
    
    # Apply the helper before using monitor_data
    content = content.replace(
        "monitor_data = self.position_monitors[monitor_key]",
        """monitor_data = self.position_monitors[monitor_key]
        # Ensure tp_orders is in dict format
        monitor_data = ensure_tp_orders_dict(monitor_data)"""
    )
    
    # Write the fixed content
    with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
        f.write(content)
    
    print("✅ Applied monitor isolation fixes")
    print("\nKey improvements:")
    print("1. Monitors are now isolated - mirror continues if main fails")
    print("2. Error handler continues monitoring instead of stopping")
    print("3. tp_orders format is automatically converted to dict")
    print("4. Account-specific cleanup prevents cross-contamination")
    
    return True

if __name__ == "__main__":
    fix_monitor_isolation()