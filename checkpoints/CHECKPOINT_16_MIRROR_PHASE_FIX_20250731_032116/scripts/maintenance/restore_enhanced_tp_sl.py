#!/usr/bin/env python3
"""
Restore enhanced_tp_sl_manager.py from backup
"""

import shutil
import os

# Find the most recent backup
backups = [
    'execution/enhanced_tp_sl_manager.py.backup_false_tp_fills_final',
    'execution/enhanced_tp_sl_manager.py.backup_fill_detection_fix',
    'execution/enhanced_tp_sl_manager.py.backup_false_tp_fix',
    'execution/enhanced_tp_sl_manager.py.backup_final_20250708_135340',
    'execution/enhanced_tp_sl_manager.py.backup_20250708_134838'
]

# Find the first existing backup
backup_file = None
for backup in backups:
    if os.path.exists(backup):
        backup_file = backup
        break

if backup_file:
    # Restore from backup
    shutil.copy(backup_file, 'execution/enhanced_tp_sl_manager.py')
    print(f"✅ Restored from {backup_file}")
    
    # Now apply only the essential fixes
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        content = f.read()
    
    # Fix 1: Handle tp_orders as both list and dict
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
        print("✅ Applied fix for tp_orders list/dict handling")
    
    # Fix 2: Add cumulative reset logic
    old_cumulative = """                    cumulative_percentage = (fill_tracker["total_filled"] / fill_tracker["target_size"]) * 100
                    
                    logger.info(f"🎯 Position size reduced by {size_diff} ({fill_percentage:.2f}% of position, {cumulative_percentage:.2f}% cumulative) - TP order filled")"""
    
    new_cumulative = """                    cumulative_percentage = (fill_tracker["total_filled"] / fill_tracker["target_size"]) * 100
                    
                    # Reset cumulative tracking if it exceeds 100% (false positive)
                    if cumulative_percentage > 100:
                        logger.warning(f"⚠️ Cumulative fill exceeded 100% ({cumulative_percentage:.2f}%) - resetting tracker")
                        fill_tracker["total_filled"] = size_diff
                        self.fill_tracker[monitor_key] = fill_tracker
                        cumulative_percentage = (size_diff / fill_tracker["target_size"]) * 100
                    
                    logger.info(f"🎯 Position size reduced by {size_diff} ({fill_percentage:.2f}% of position, {cumulative_percentage:.2f}% cumulative) - TP order filled")"""
    
    if old_cumulative in content:
        content = content.replace(old_cumulative, new_cumulative)
        print("✅ Applied cumulative reset logic")
    
    # Write back
    with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
        f.write(content)
    
    print("✅ Enhanced TP/SL manager restored and fixed")
else:
    print("❌ No backup file found")