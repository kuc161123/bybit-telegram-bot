#!/usr/bin/env python3
"""
Simple direct fix for the tp_orders list/dict issue
"""

import re

def simple_fix():
    """Apply a simple fix directly to the locations causing the error"""
    
    print("\n🔧 APPLYING SIMPLE TP_ORDERS FIX")
    print("=" * 60)
    
    # Read enhanced_tp_sl_manager.py
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        content = f.read()
    
    # Find and fix all occurrences where tp_orders is expected to be a dict
    # This is a more targeted fix for the specific error locations
    
    # Pattern 1: Fix line 1867 and similar
    pattern1 = r'(\s+)for order_id, tp_order in monitor_data\.get\("tp_orders", \{\}\)\.items\(\):'
    replacement1 = r'''\1# Handle both list and dict formats for tp_orders
\1tp_orders = monitor_data.get("tp_orders", {})
\1if isinstance(tp_orders, list):
\1    # Convert list to dict using order_id as key
\1    tp_dict = {}
\1    for order in tp_orders:
\1        if isinstance(order, dict) and "order_id" in order:
\1            tp_dict[order["order_id"]] = order
\1    monitor_data["tp_orders"] = tp_dict
\1    tp_orders = tp_dict
\1for order_id, tp_order in tp_orders.items():'''
    
    content = re.sub(pattern1, replacement1, content, flags=re.MULTILINE)
    
    # Pattern 2: Fix places where tp_orders is accessed directly
    pattern2 = r'(\s+)tp_orders = monitor_data\.get\("tp_orders", \{\}\)'
    replacement2 = r'''\1# Handle both list and dict formats for tp_orders
\1tp_orders = monitor_data.get("tp_orders", {})
\1if isinstance(tp_orders, list):
\1    # Convert list to dict
\1    tp_dict = {}
\1    for order in tp_orders:
\1        if isinstance(order, dict) and "order_id" in order:
\1            tp_dict[order["order_id"]] = order
\1    monitor_data["tp_orders"] = tp_dict
\1    tp_orders = tp_dict'''
    
    content = re.sub(pattern2, replacement2, content, flags=re.MULTILINE)
    
    # Write the fixed content back
    with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
        f.write(content)
    
    print("✅ Applied simple fixes to enhanced_tp_sl_manager.py")
    
    # Now add a sanitize method specifically for this
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        content = f.read()
    
    # Add the sanitize method if not already present
    if '_sanitize_monitor_data' not in content:
        sanitize_method = '''
    def _sanitize_monitor_data(self, monitor_data: Dict) -> Dict:
        """Sanitize monitor data to ensure all fields are in expected format"""
        # Ensure tp_orders is dict format
        if "tp_orders" in monitor_data and isinstance(monitor_data["tp_orders"], list):
            tp_dict = {}
            for order in monitor_data["tp_orders"]:
                if isinstance(order, dict) and "order_id" in order:
                    tp_dict[order["order_id"]] = order
            monitor_data["tp_orders"] = tp_dict
        
        # Ensure numeric fields are Decimal
        from decimal import Decimal
        for field in ["position_size", "remaining_size", "entry_price", "avg_price"]:
            if field in monitor_data and monitor_data[field] is not None:
                monitor_data[field] = Decimal(str(monitor_data[field]))
        
        return monitor_data
'''
        # Insert after __init__ method
        init_end = content.find('self._init_mirror_support()')
        if init_end > 0:
            end_of_line = content.find('\n', init_end)
            content = content[:end_of_line + 1] + sanitize_method + content[end_of_line + 1:]
            
            with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
                f.write(content)
            
            print("✅ Added _sanitize_monitor_data method")
    else:
        print("✅ _sanitize_monitor_data method already exists")
    
    print("\n✅ Simple fix complete!")
    print("The bot should now handle both list and dict formats for tp_orders.")
    
    return True

if __name__ == "__main__":
    simple_fix()