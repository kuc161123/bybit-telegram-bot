#!/usr/bin/env python3
"""
Fix limit fill detection logic in enhanced_tp_sl_manager.py
This ensures alerts and rebalancing happen for every limit fill, not just the first one
"""
import shutil
from datetime import datetime

def fix_limit_fill_detection():
    """Apply fix to enhanced_tp_sl_manager.py"""
    
    # Create backup
    source_file = "execution/enhanced_tp_sl_manager.py"
    backup_file = f"execution/enhanced_tp_sl_manager.py.backup_limit_detection_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy(source_file, backup_file)
    print(f"✅ Created backup: {backup_file}")
    
    # Read the file
    with open(source_file, 'r') as f:
        content = f.read()
    
    # Fix 1: Replace the simple boolean check with position size tracking
    old_check = '''        # Check if limit orders have already been filled
        limit_orders_filled = monitor_data.get("limit_orders_filled", False)'''
    
    new_check = '''        # Enhanced limit fill detection - track actual position sizes
        limit_orders_filled = monitor_data.get("limit_orders_filled", False)
        last_known_size = monitor_data.get("last_known_size", Decimal("0"))
        
        # Detect any position size increase (indicates limit fill)
        position_increased = current_size > last_known_size if last_known_size > 0 else False'''
    
    content = content.replace(old_check, new_check)
    
    # Fix 2: Update the limit fill detection logic
    old_logic = '''        # If no TP was filled, check for limit order fills
        elif not limit_orders_filled and current_size > 0:
            logger.info(f"📊 Conservative approach: Limit orders filling ({fill_percentage:.2f}% filled)")

            # Mark that limit orders have been filled
            monitor_data["limit_orders_filled"] = True

            # Send limit fill alert
            await self._send_limit_fill_alert(monitor_data, fill_percentage)

            # For limit order fills, we need to adjust TP/SL quantities proportionally
            await self._adjust_all_orders_for_partial_fill(monitor_data, current_size)'''
    
    new_logic = '''        # Enhanced: Check for any position increase (limit fills)
        elif position_increased or (not limit_orders_filled and current_size > 0):
            size_diff = current_size - last_known_size if last_known_size > 0 else current_size
            logger.info(f"📊 Conservative approach: Limit order detected - size increased by {size_diff}")
            logger.info(f"📊 Position: {last_known_size} → {current_size} ({fill_percentage:.2f}% filled)")
            
            # Update tracking data
            monitor_data["limit_orders_filled"] = True
            monitor_data["last_known_size"] = current_size
            monitor_data["last_limit_fill_time"] = time.time()
            
            # Count filled limits for accurate alert
            filled_limits = self._count_filled_limit_orders(monitor_data)
            monitor_data["filled_limit_count"] = filled_limits
            
            # Send limit fill alert with accurate count
            await self._send_limit_fill_alert(monitor_data, fill_percentage)
            
            # Rebalance all TP/SL orders for new position size
            await self._adjust_all_orders_for_partial_fill(monitor_data, current_size)
            
            # Save state immediately
            self.save_monitors_to_persistence()'''
    
    content = content.replace(old_logic, new_logic)
    
    # Fix 3: Add helper method to count filled limit orders
    helper_method = '''
    def _count_filled_limit_orders(self, monitor_data: Dict) -> int:
        """Count how many limit orders have been filled"""
        limit_orders = monitor_data.get("limit_orders", [])
        filled_count = 0
        
        for order in limit_orders:
            if isinstance(order, dict) and order.get("status") == "FILLED":
                filled_count += 1
        
        return filled_count
'''
    
    # Insert helper method after _handle_conservative_position_change
    insert_position = content.find("    async def _handle_fast_position_change")
    if insert_position > 0:
        content = content[:insert_position] + helper_method + "\n" + content[insert_position:]
    
    # Fix 4: Update position size tracking in monitor creation
    old_monitor_init = '''            "limit_orders_filled": False,'''
    
    new_monitor_init = '''            "limit_orders_filled": False,
            "last_known_size": position_size,  # Track for size change detection
            "filled_limit_count": 0,  # Track number of filled limits
            "last_limit_fill_time": 0,  # Track when last limit filled'''
    
    content = content.replace(old_monitor_init, new_monitor_init)
    
    # Fix 5: Ensure position size is always updated
    position_update = '''                # Always update last known size for change detection
                monitor_data["last_known_size"] = current_size'''
    
    # Add this after position size checks
    check_position = "if current_size != monitor_data.get(\"remaining_size\", monitor_data[\"position_size\"]):"
    pos = content.find(check_position)
    if pos > 0:
        # Find the end of this if block
        end_pos = content.find("\n\n", pos)
        if end_pos > 0:
            content = content[:end_pos] + "\n" + position_update + content[end_pos:]
    
    # Write the fixed content
    with open(source_file, 'w') as f:
        f.write(content)
    
    print("✅ Applied limit fill detection fixes:")
    print("  1. Enhanced position size tracking with last_known_size")
    print("  2. Detect any position increase as potential limit fill")
    print("  3. Added filled limit order counter")
    print("  4. Improved state persistence after limit fills")
    print("  5. Always update position size for accurate tracking")
    print("\n📝 The monitor will now:")
    print("  - Detect ALL limit fills, not just the first one")
    print("  - Send alerts for every limit fill with accurate count")
    print("  - Rebalance TPs after every limit fill")
    print("  - Track position size changes continuously")

if __name__ == "__main__":
    fix_limit_fill_detection()