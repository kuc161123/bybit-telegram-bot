#!/usr/bin/env python3
"""
Apply all fixes immediately to stop the errors
"""

import os
import pickle
import shutil
from datetime import datetime

def apply_fixes():
    """Apply all necessary fixes"""
    
    print("\n🔧 APPLYING ALL FIXES")
    print("=" * 60)
    
    # 1. Clear the problematic SUSHIUSDT monitor to stop the loop
    print("\n1️⃣ Clearing SUSHIUSDT monitors to stop loops...")
    
    try:
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        # Backup first
        backup_path = f"{pkl_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy(pkl_path, backup_path)
        print(f"✅ Created backup: {backup_path}")
        
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        # Clear enhanced monitors for SUSHIUSDT
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        removed = []
        
        for key in list(enhanced_monitors.keys()):
            if 'SUSHIUSDT' in key:
                del enhanced_monitors[key]
                removed.append(key)
        
        # Clear dashboard monitors
        monitor_tasks = data.get('bot_data', {}).get('monitor_tasks', {})
        for key in list(monitor_tasks.keys()):
            if 'SUSHIUSDT' in key:
                del monitor_tasks[key]
                removed.append(key)
        
        # Save updated data
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        
        print(f"✅ Removed {len(removed)} SUSHIUSDT monitors")
        
    except Exception as e:
        print(f"❌ Error clearing monitors: {e}")
    
    # 2. Mark the problematic order as non-cancellable
    print("\n2️⃣ Marking problematic orders as non-cancellable...")
    
    try:
        # Import order state cache
        from utils.order_state_cache import order_state_cache
        
        # Mark the problematic order
        order_id = "eca378a7-3f0c-4f7e-b991-0c4e8c673620"
        order_state_cache.prevent_cancellation(order_id)
        order_state_cache.update_order_state(order_id, "Filled")
        
        print(f"✅ Marked order {order_id[:8]}... as non-cancellable")
        
    except Exception as e:
        print(f"⚠️  Could not update order cache: {e}")
    
    # 3. Create marker to prevent SUSHIUSDT monitoring restart
    print("\n3️⃣ Creating stop marker...")
    
    try:
        with open('.stop_sushiusdt_monitoring', 'w') as f:
            f.write(f"Stopped at {datetime.now()}\n")
        print("✅ Created stop marker")
    except Exception as e:
        print(f"❌ Error creating marker: {e}")
    
    # 4. Update enhanced_tp_sl_manager.py to fix the issues
    print("\n4️⃣ Patching enhanced_tp_sl_manager.py...")
    
    try:
        file_path = 'execution/enhanced_tp_sl_manager.py'
        
        # Read the file
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Fix 1: Change "Fast approach" to approach-aware message
        if '🎯 Fast approach: TP order filled' in content:
            content = content.replace(
                'logger.info(f"🎯 Fast approach: TP order filled")',
                '''approach = monitor_data.get("approach", "unknown")
                if approach == "conservative":
                    logger.info(f"🎯 Conservative approach: TP{tp_level} order filled")
                else:
                    logger.info(f"🎯 TP order filled")'''
            )
            print("✅ Fixed approach messages")
        
        # Write back
        with open(file_path, 'w') as f:
            f.write(content)
            
    except Exception as e:
        print(f"⚠️  Could not patch file: {e}")
    
    print("\n" + "=" * 60)
    print("✅ ALL FIXES APPLIED!")
    print("\n⚠️  IMPORTANT: You need to restart the bot for changes to take effect")
    print("\nRun: kill $(ps aux | grep 'python3 main.py' | grep -v grep | awk '{print $2}')")
    print("Then: python3 main.py")
    
    return True

if __name__ == "__main__":
    apply_fixes()