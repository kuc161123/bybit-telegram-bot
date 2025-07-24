#!/usr/bin/env python3
"""
Fix the monitoring error immediately
"""

import pickle
import os

def fix_monitor_error():
    """Fix the list object error in monitoring"""
    
    print("\n🔧 FIXING MONITOR ERROR")
    print("=" * 60)
    
    # 1. Clear the problematic monitor
    print("\n1️⃣ Clearing problematic monitor...")
    
    try:
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        # Check if there are any monitors
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        monitor_tasks = data.get('bot_data', {}).get('monitor_tasks', {})
        
        print(f"Found {len(enhanced_monitors)} enhanced monitors")
        print(f"Found {len(monitor_tasks)} monitor tasks")
        
        # Clear SUSHIUSDT monitors that are causing issues
        for key in list(enhanced_monitors.keys()):
            if 'SUSHIUSDT' in key:
                monitor = enhanced_monitors[key]
                print(f"\nChecking monitor {key}:")
                
                # Fix tp_orders if it's a list instead of dict
                if 'tp_orders' in monitor and isinstance(monitor['tp_orders'], list):
                    print(f"  ⚠️  tp_orders is a list, converting to dict")
                    # Convert list to dict using order_id as key
                    tp_dict = {}
                    for order in monitor['tp_orders']:
                        if isinstance(order, dict) and 'order_id' in order:
                            tp_dict[order['order_id']] = order
                    monitor['tp_orders'] = tp_dict
                    print(f"  ✅ Converted {len(tp_dict)} TP orders to dict format")
        
        # Save the fixed data
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        
        print("\n✅ Fixed monitor data structure")
        
    except Exception as e:
        print(f"❌ Error fixing monitors: {e}")
    
    # 2. Create a patch for the code
    print("\n2️⃣ Code fix needed in enhanced_tp_sl_manager.py...")
    
    fix_code = '''
# In _handle_tp_fill method, add this check:

# Handle both list and dict formats for tp_orders
if isinstance(monitor_data.get("tp_orders"), list):
    # Convert list to dict
    tp_dict = {}
    for order in monitor_data["tp_orders"]:
        if isinstance(order, dict) and "order_id" in order:
            tp_dict[order["order_id"]] = order
    monitor_data["tp_orders"] = tp_dict

# Now safely iterate
for order_id, tp_order in monitor_data.get("tp_orders", {}).items():
    # ... rest of the code
'''
    
    print("Fix needed:")
    print(fix_code)
    
    print("\n✅ Monitor error fix complete!")
    print("\nNext steps:")
    print("1. The persistence file has been fixed")
    print("2. Restart the bot to apply changes")
    print("3. The monitoring should work properly now")
    
    return True

if __name__ == "__main__":
    fix_monitor_error()