#!/usr/bin/env python3
"""
Fix the tp_orders list/dict format issue in enhanced_tp_sl_manager.py
"""

import re

def fix_tp_orders_format():
    """Add type checking and conversion for tp_orders in monitor methods"""
    
    print("\n🔧 FIXING TP_ORDERS FORMAT ISSUE")
    print("=" * 60)
    
    file_path = "execution/enhanced_tp_sl_manager.py"
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Create the type conversion helper
    type_converter = '''
    def _ensure_tp_orders_dict(self, monitor_data: Dict):
        """Ensure tp_orders is in dict format for backward compatibility"""
        tp_orders = monitor_data.get("tp_orders", {})
        if isinstance(tp_orders, list):
            # Convert list to dict using order_id as key
            tp_dict = {}
            for order in tp_orders:
                if isinstance(order, dict) and "order_id" in order:
                    tp_dict[order["order_id"]] = order
            monitor_data["tp_orders"] = tp_dict
            return tp_dict
        return tp_orders
'''
    
    # Add the helper method after the __init__ method
    init_pattern = r'(def __init__\(self\):.*?self\._init_mirror_support\(\)\n)'
    content = re.sub(init_pattern, r'\1' + type_converter, content, flags=re.DOTALL)
    
    # Pattern to find all occurrences of tp_orders access
    patterns_to_fix = [
        # Pattern 1: for loops over tp_orders
        (r'for order_id, tp_order in monitor_data\.get\("tp_orders", \{\}\)\.items\(\):',
         '''# Ensure tp_orders is dict format
            tp_orders = self._ensure_tp_orders_dict(monitor_data)
            for order_id, tp_order in tp_orders.items():'''),
        
        # Pattern 2: Direct access to tp_orders
        (r'tp_orders = monitor_data\.get\("tp_orders", \{\}\)',
         'tp_orders = self._ensure_tp_orders_dict(monitor_data)'),
         
        # Pattern 3: Check length/iteration over tp_orders when expecting list
        (r'for tp in monitor_data\.get\("tp_orders", \[\]\)',
         '''# Handle both list and dict formats
            tp_orders_raw = monitor_data.get("tp_orders", [])
            if isinstance(tp_orders_raw, dict):
                tp_orders_list = list(tp_orders_raw.values())
            else:
                tp_orders_list = tp_orders_raw
            for tp in tp_orders_list'''),
    ]
    
    # Apply fixes
    for pattern, replacement in patterns_to_fix:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    # Write the fixed content
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed tp_orders format handling in {file_path}")
    
    # Also fix the immediate issue in mirror_enhanced_tp_sl.py
    mirror_file = "execution/mirror_enhanced_tp_sl.py"
    
    with open(mirror_file, 'r') as f:
        mirror_content = f.read()
    
    # Ensure monitor data is created with tp_orders as dict from the start
    mirror_content = mirror_content.replace(
        '"tp_orders": {},',
        '"tp_orders": {},  # Always use dict format for consistency'
    )
    
    # Ensure the conversion happens immediately after setup_tp_sl_from_monitor
    fix_after_setup = '''            # Use enhanced sync method to place orders
            result = await self.enhanced_mirror.setup_tp_sl_from_monitor(monitor_data, mirror_position, tp_prices, tp_percentages, sl_price_decimal)
            
            # Ensure tp_orders is in dict format immediately after setup
            if result and isinstance(result, dict) and "tp_orders" in result:
                if isinstance(result["tp_orders"], list):
                    # Convert to dict format
                    tp_dict = {}
                    for order in result["tp_orders"]:
                        if isinstance(order, dict) and "order_id" in order:
                            tp_dict[order["order_id"]] = order
                    result["tp_orders"] = tp_dict
                    # Also update monitor_data
                    if self.main_manager and monitor_key in self.main_manager.position_monitors:
                        self.main_manager.position_monitors[monitor_key]["tp_orders"] = tp_dict'''
    
    mirror_content = mirror_content.replace(
        '            # Use enhanced sync method to place orders\n            result = await self.enhanced_mirror.setup_tp_sl_from_monitor(monitor_data, mirror_position, tp_prices, tp_percentages, sl_price_decimal)',
        fix_after_setup
    )
    
    with open(mirror_file, 'w') as f:
        f.write(mirror_content)
    
    print(f"✅ Fixed mirror TP/SL manager to use dict format")
    
    print("\n✅ All fixes applied!")
    print("\nThe monitoring error should now be resolved.")
    print("The bot will handle both list and dict formats for tp_orders.")
    
    return True

if __name__ == "__main__":
    fix_tp_orders_format()