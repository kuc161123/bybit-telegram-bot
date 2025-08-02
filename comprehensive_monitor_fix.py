#!/usr/bin/env python3
"""
Comprehensive fix for both monitor issues:
1. Fix order counting (3 registered → 2 found)
2. Clean up stale monitors (28 monitors → actual count)
"""
import pickle
import asyncio
import sys
import os
import json
from datetime import datetime

async def comprehensive_fix():
    """Apply comprehensive fixes to all monitor issues"""
    
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    # Kill any remaining processes first
    os.system("pkill -f 'python.*main.py' 2>/dev/null || true")
    os.system("pkill -f 'bybit.*bot' 2>/dev/null || true")
    
    if not os.path.exists(pickle_file):
        print(f"❌ Pickle file not found: {pickle_file}")
        return
    
    # Create timestamped backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{pickle_file}.backup_comprehensive_fix_{timestamp}"
    try:
        import shutil
        shutil.copy2(pickle_file, backup_file)
        print(f"🔒 Created backup: {backup_file}")
    except Exception as e:
        print(f"⚠️ Could not create backup: {e}")
    
    # Load data with error handling
    try:
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        print("✅ Loaded bot data successfully")
    except Exception as e:
        print(f"❌ Failed to load pickle data: {e}")
        return
    
    bot_data = data.get('bot_data', {})
    monitor_tasks = bot_data.get('monitor_tasks', {})
    
    print(f"📊 Initial monitors: {len(monitor_tasks)}")
    
    # COMPREHENSIVE FIX 1: Clean up ALL invalid order entries
    total_order_fixes = 0
    monitors_with_orders = 0
    
    for monitor_key, monitor_data in list(monitor_tasks.items()):
        if 'limit_orders' in monitor_data and monitor_data['limit_orders']:
            monitors_with_orders += 1
            original_orders = monitor_data['limit_orders']
            valid_orders = []
            
            # More thorough validation
            for order in original_orders:
                if (isinstance(order, dict) and 
                    order.get("order_id") and 
                    isinstance(order.get("order_id"), str) and 
                    len(order.get("order_id", "")) > 0):
                    valid_orders.append(order)
                else:
                    print(f"🗑️ Removing invalid order from {monitor_key}: {type(order)} - {order}")
            
            if len(valid_orders) != len(original_orders):
                print(f"🧹 Fixed orders in {monitor_key}: {len(original_orders)} → {len(valid_orders)}")
                monitor_data['limit_orders'] = valid_orders
                total_order_fixes += 1
                
                # If no valid orders remain, clean up the empty array
                if not valid_orders:
                    monitor_data['limit_orders'] = []
    
    print(f"🔧 Order fixes applied: {total_order_fixes} monitors")
    print(f"📊 Monitors with orders: {monitors_with_orders}")
    
    # COMPREHENSIVE FIX 2: Remove ALL stale monitors
    print("\n🔍 Comprehensive stale monitor cleanup...")
    
    # Import position checking functions
    sys.path.append('.')
    try:
        from clients.bybit_client import bybit_client  
        from execution.mirror_trader import bybit_client_2
        from clients.bybit_helpers import get_all_positions
        
        # Get all positions from both accounts
        print("📡 Fetching current positions from exchange...")
        try:
            main_positions = await get_all_positions()
            print(f"✅ Main account positions: {len(main_positions)}")
        except Exception as e:
            print(f"⚠️ Could not fetch main positions: {e}")
            main_positions = []
        
        try:
            mirror_positions = await get_all_positions(client=bybit_client_2) if bybit_client_2 else []
            print(f"✅ Mirror account positions: {len(mirror_positions)}")
        except Exception as e:
            print(f"⚠️ Could not fetch mirror positions: {e}")
            mirror_positions = []
        
        # Create comprehensive set of active position keys
        active_position_keys = set()
        
        # Process main positions
        for pos in main_positions:
            size = float(pos.get('size', 0))
            if size > 0:
                symbol = pos['symbol']
                side = pos['side']
                key = f"{symbol}_{side}_main"
                active_position_keys.add(key)
                print(f"✅ Active main position: {key} (size: {size})")
        
        # Process mirror positions  
        for pos in mirror_positions:
            size = float(pos.get('size', 0))
            if size > 0:
                symbol = pos['symbol']
                side = pos['side']
                key = f"{symbol}_{side}_mirror"
                active_position_keys.add(key)
                print(f"✅ Active mirror position: {key} (size: {size})")
        
        print(f"📊 Total active positions found: {len(active_position_keys)}")
        
        # Alternative key formats to check
        alternative_keys = set()
        for key in active_position_keys:
            parts = key.split('_')
            if len(parts) >= 3:
                symbol, side, account = parts[0], parts[1], parts[2]
                # Add chat_id prefix variants
                alternative_keys.add(f"*_{symbol}_{side}_{account}")
                # Add conservative suffix variants
                alternative_keys.add(f"*_{symbol}_CONSERVATIVE_{account}")
        
        # Remove stale monitors with comprehensive key matching
        stale_monitors = []
        for monitor_key in list(monitor_tasks.keys()):
            is_active = False
            
            # Direct key match
            if monitor_key in active_position_keys:
                is_active = True
            else:
                # Check alternative formats
                for active_key in active_position_keys:
                    if (active_key.split('_')[0] in monitor_key and  # Symbol match
                        active_key.split('_')[1] in monitor_key and  # Side match  
                        active_key.split('_')[2] in monitor_key):    # Account match
                        is_active = True
                        break
            
            if not is_active:
                stale_monitors.append(monitor_key)
        
        # Remove stale monitors
        for monitor_key in stale_monitors:
            del monitor_tasks[monitor_key]
            print(f"🗑️ Removed stale monitor: {monitor_key}")
        
        print(f"\n🧹 Stale monitor cleanup results:")
        print(f"  - Removed: {len(stale_monitors)} stale monitors")
        print(f"  - Remaining: {len(monitor_tasks)} active monitors")
        
        # Verify remaining monitors
        print(f"\n✅ Remaining active monitors:")
        for monitor_key in monitor_tasks.keys():
            limit_count = len(monitor_tasks[monitor_key].get('limit_orders', []))
            print(f"  - {monitor_key} ({limit_count} limit orders)")
        
    except Exception as e:
        print(f"⚠️ Could not perform position-based cleanup: {e}")
        print("📊 Continuing with order fixes only...")
    
    # Save the comprehensively fixed data
    try:
        # Use atomic write for safety
        temp_file = f"{pickle_file}.tmp_{timestamp}"
        with open(temp_file, 'wb') as f:
            pickle.dump(data, f)
        
        # Verify the file
        with open(temp_file, 'rb') as f:
            pickle.load(f)
        
        # Atomic replace
        os.rename(temp_file, pickle_file)
        
        print(f"\n✅ Comprehensive fixes saved successfully!")
        print(f"🔧 Order fixes: {total_order_fixes} monitors")
        print(f"🗑️ Stale monitors removed: {len(stale_monitors) if 'stale_monitors' in locals() else 'N/A'}")
        print(f"📊 Final monitor count: {len(monitor_tasks)}")
        
    except Exception as e:
        print(f"❌ Failed to save fixed data: {e}")
        return
    
    print("\n🎉 Comprehensive monitor fixes complete!")
    print("🔄 Please restart the bot to see the corrected counts.")

if __name__ == "__main__":
    asyncio.run(comprehensive_fix())