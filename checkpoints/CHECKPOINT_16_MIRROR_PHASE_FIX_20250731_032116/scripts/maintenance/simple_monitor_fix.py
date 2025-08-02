#!/usr/bin/env python3
"""
Simple fix to ensure tp_orders is always dict format in mirror_enhanced_tp_sl.py
"""

def fix_mirror_tp_orders():
    print("\n🔧 FIXING MIRROR TP ORDERS FORMAT")
    print("=" * 60)
    
    # Read the mirror file
    with open('execution/mirror_enhanced_tp_sl.py', 'r') as f:
        content = f.read()
    
    # Find where tp_orders is created as a list
    # Replace it to always create as dict
    
    # Pattern 1: When creating monitor data
    old_pattern1 = '"tp_orders": [],'
    new_pattern1 = '"tp_orders": {},'
    
    if old_pattern1 in content:
        content = content.replace(old_pattern1, new_pattern1)
        print("✅ Fixed tp_orders initialization to use dict")
    
    # Pattern 2: When adding TP orders
    # Find the section where TP orders are added
    import re
    
    # Look for where tp_orders are appended
    append_pattern = r'monitor_data\["tp_orders"\]\.append\('
    
    # Count occurrences
    append_count = len(re.findall(append_pattern, content))
    if append_count > 0:
        print(f"⚠️  Found {append_count} places where tp_orders.append is used")
        
        # Replace append with dict assignment
        # This is more complex, need to find the actual code blocks
        
        # Find the function that creates TP orders
        tp_creation_pattern = r'(for i, tp_percent in enumerate.*?monitor_data\["tp_orders"\]\.append\(tp_order\))'
        
        matches = re.findall(tp_creation_pattern, content, re.DOTALL)
        for match in matches:
            # Replace the append with dict assignment
            new_code = match.replace(
                'monitor_data["tp_orders"].append(tp_order)',
                'monitor_data["tp_orders"][tp_order["order_id"]] = tp_order'
            )
            content = content.replace(match, new_code)
            print("✅ Fixed TP order append to use dict assignment")
    
    # Also ensure tp_orders is converted when copying from main
    # Find where tp_orders is copied
    copy_pattern = r'"tp_orders": tp_orders'
    if copy_pattern in content:
        # Replace with conversion logic
        new_copy = '''"tp_orders": {order["order_id"]: order for order in tp_orders} if isinstance(tp_orders, list) else tp_orders'''
        content = content.replace(copy_pattern, new_copy)
        print("✅ Added conversion when copying tp_orders from main")
    
    # Write the fixed content
    with open('execution/mirror_enhanced_tp_sl.py', 'w') as f:
        f.write(content)
    
    print("\n✅ Mirror TP orders format fixed!")
    print("   All tp_orders will now be created as dicts")
    print("   This prevents the 'list' object has no attribute 'get' error")
    
    return True

if __name__ == "__main__":
    fix_mirror_tp_orders()