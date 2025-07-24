#!/usr/bin/env python3
"""
Fix the enhanced fill detection error in enhanced_tp_sl_manager.py
The issue is that tp_orders is sometimes a list and sometimes expected as a dict
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def fix_enhanced_fill_detection():
    """Fix the enhanced fill detection to handle tp_orders as both list and dict"""
    
    file_path = "execution/enhanced_tp_sl_manager.py"
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix the enhanced fill detection method to handle both list and dict
    old_code = """            # Check TP orders for fills
            for order_id, tp_order in monitor_data.get("tp_orders", {}).items():
                # order_id = tp_order["order_id"]  # Now comes from iteration"""
    
    new_code = """            # Check TP orders for fills
            tp_orders = monitor_data.get("tp_orders", {})
            
            # Handle both list and dict formats
            if isinstance(tp_orders, list):
                # Convert list to dict using order_id as key
                tp_orders_dict = {}
                for tp_order in tp_orders:
                    if isinstance(tp_order, dict) and "order_id" in tp_order:
                        tp_orders_dict[tp_order["order_id"]] = tp_order
                tp_orders = tp_orders_dict
            
            for order_id, tp_order in tp_orders.items():
                # order_id = tp_order["order_id"]  # Now comes from iteration"""
    
    if old_code in content:
        content = content.replace(old_code, new_code)
        print("✅ Fixed enhanced fill detection to handle both list and dict formats")
    else:
        print("❌ Could not find the exact code to fix")
        return False
    
    # Backup and write
    import shutil
    backup_path = f"{file_path}.backup_fill_detection_fix"
    shutil.copy(file_path, backup_path)
    print(f"✅ Created backup: {backup_path}")
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("✅ Fixed enhanced fill detection issue")
    return True

if __name__ == "__main__":
    if fix_enhanced_fill_detection():
        print("\n✅ Successfully fixed the enhanced fill detection error")
        print("The bot will now properly handle TP order tracking without repeated false alerts")
    else:
        print("\n❌ Failed to fix the enhanced fill detection error")