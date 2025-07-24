#!/usr/bin/env python3
"""
Fix the tp_orders iteration error in enhanced_tp_sl_manager.py
"""

import re

def fix_tp_orders_iteration():
    """Fix the iteration over tp_orders dictionary"""
    
    file_path = 'execution/enhanced_tp_sl_manager.py'
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the problematic line
    old_pattern = r'for tp_order in monitor_data\.get\("tp_orders", \[\]\):'
    new_code = 'for order_id, tp_order in monitor_data.get("tp_orders", {}).items():'
    
    # Check if pattern exists
    if re.search(old_pattern, content):
        print("✅ Found the problematic iteration pattern")
        
        # Replace it
        content = re.sub(old_pattern, new_code, content)
        
        # Also need to remove the line that gets order_id since we now have it from iteration
        # Find and comment out: order_id = tp_order["order_id"]
        content = re.sub(
            r'(\s+)order_id = tp_order\["order_id"\]',
            r'\1# order_id = tp_order["order_id"]  # Now comes from iteration',
            content
        )
        
        # Write back
        with open(file_path, 'w') as f:
            f.write(content)
        
        print("✅ Fixed the iteration to handle dictionary properly")
        print("📝 Changes made:")
        print("   - Changed iteration to: for order_id, tp_order in monitor_data.get('tp_orders', {}).items()")
        print("   - Commented out redundant order_id extraction")
        
        return True
    else:
        print("❌ Could not find the exact pattern")
        print("🔍 Looking for alternative patterns...")
        
        # Look for the function
        if '_enhanced_fill_detection' in content:
            print("✅ Found _enhanced_fill_detection function")
            
            # Extract the function
            start = content.find('async def _enhanced_fill_detection')
            if start != -1:
                # Find the problematic section
                section_start = content.find('# Check TP orders for fills', start)
                section_end = content.find('# Check for any other order changes', start)
                
                if section_start != -1 and section_end != -1:
                    problem_section = content[section_start:section_end]
                    print("\n📋 Current code section:")
                    print(problem_section[:200] + "...")
                    
                    print("\n💡 The issue: tp_orders is a dict, not a list")
                    print("   Current structure: {'order_id': {...order_data...}}")
                    print("   Need to iterate over .items() to get both key and value")
        
        return False

if __name__ == "__main__":
    print("🔧 Fixing tp_orders iteration error...")
    
    if fix_tp_orders_iteration():
        print("\n✅ Fix applied successfully!")
        print("🚀 The bot should no longer show 'string indices must be integers' errors")
    else:
        print("\n⚠️ Manual fix needed")
        print("📝 In execution/enhanced_tp_sl_manager.py, find:")
        print("   for tp_order in monitor_data.get('tp_orders', []):")
        print("   And replace with:")
        print("   for order_id, tp_order in monitor_data.get('tp_orders', {}).items():")