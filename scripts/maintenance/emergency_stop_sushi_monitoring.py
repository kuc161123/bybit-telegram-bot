#!/usr/bin/env python3
"""
Emergency stop for SUSHIUSDT monitoring loop
"""

import pickle
import os
import asyncio

async def emergency_stop():
    """Stop the SUSHIUSDT monitoring loop"""
    
    print("\n🚨 EMERGENCY STOP - SUSHIUSDT MONITORING")
    print("=" * 60)
    
    # 1. Mark position as fully closed in persistence
    print("\n1️⃣ Marking SUSHIUSDT as fully closed...")
    
    try:
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        # Backup first
        import shutil
        backup_path = f"{pkl_path}.backup_sushi_fix"
        shutil.copy(pkl_path, backup_path)
        print(f"✅ Created backup: {backup_path}")
        
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        # Remove from enhanced monitors
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        removed_enhanced = []
        
        for key in list(enhanced_monitors.keys()):
            if 'SUSHIUSDT' in key:
                del enhanced_monitors[key]
                removed_enhanced.append(key)
        
        # Remove from dashboard monitors
        monitor_tasks = data.get('bot_data', {}).get('monitor_tasks', {})
        removed_dashboard = []
        
        for key in list(monitor_tasks.keys()):
            if 'SUSHIUSDT' in key:
                del monitor_tasks[key]
                removed_dashboard.append(key)
        
        # Clear from user positions
        for user_id in data.get('user_data', {}):
            user_positions = data['user_data'][user_id].get('positions', {})
            if 'SUSHIUSDT_Buy' in user_positions:
                del user_positions['SUSHIUSDT_Buy']
                print(f"✅ Removed SUSHIUSDT_Buy from user {user_id}")
        
        # Save updated data
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        
        print(f"✅ Removed {len(removed_enhanced)} enhanced monitors: {removed_enhanced}")
        print(f"✅ Removed {len(removed_dashboard)} dashboard monitors: {removed_dashboard}")
        
    except Exception as e:
        print(f"❌ Error updating persistence: {e}")
    
    # 2. Create a marker file to prevent restart
    print("\n2️⃣ Creating stop marker...")
    
    try:
        marker_path = '.stop_sushiusdt_monitoring'
        with open(marker_path, 'w') as f:
            f.write("SUSHIUSDT monitoring stopped due to loop\n")
        print(f"✅ Created marker file: {marker_path}")
    except Exception as e:
        print(f"❌ Error creating marker: {e}")
    
    # 3. Clear any cached data
    print("\n3️⃣ Clearing cached data...")
    
    try:
        # Clear order state cache
        from utils.order_state_cache import order_state_cache
        
        # Clear any SUSHI-related entries
        if hasattr(order_state_cache, '_states'):
            for key in list(order_state_cache._states.keys()):
                if 'SUSHI' in str(key):
                    del order_state_cache._states[key]
                    print(f"✅ Cleared cache entry: {key[:8]}...")
        
    except Exception as e:
        print(f"⚠️  Could not clear cache: {e}")
    
    print("\n✅ EMERGENCY STOP COMPLETE")
    print("\nNext steps:")
    print("1. Restart the bot to apply changes")
    print("2. The SUSHIUSDT monitoring will not restart")
    print("3. Check that no more TP alerts are sent")
    
    return True

if __name__ == "__main__":
    asyncio.run(emergency_stop())