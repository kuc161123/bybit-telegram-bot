#!/usr/bin/env python3
"""
Trace Monitor Loading Process
Monitor what happens when Enhanced TP/SL Manager loads from pickle
"""
import asyncio
import sys
import os
import pickle
from decimal import Decimal

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

async def trace_monitor_loading():
    """Trace the exact loading process to find where 26 comes from"""
    try:
        print("🔍 TRACING MONITOR LOADING PROCESS")
        print("=" * 60)
        
        # 1. Check what's currently in pickle file
        print("\n📊 STEP 1: EXAMINING PICKLE FILE CONTENT")
        print("-" * 50)
        
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        print(f"📊 Pickle data keys: {list(data.keys())}")
        
        bot_data = data.get('bot_data', {})
        print(f"📊 bot_data keys: {list(bot_data.keys())}")
        
        # Check enhanced_tp_sl_monitors
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        print(f"📊 enhanced_tp_sl_monitors: {len(enhanced_monitors)} monitors")
        
        # Check if there are other monitor collections
        monitor_related_keys = [key for key in bot_data.keys() if 'monitor' in key.lower()]
        print(f"📊 Monitor-related keys in bot_data: {monitor_related_keys}")
        
        for key in monitor_related_keys:
            data_item = bot_data[key]
            if isinstance(data_item, dict):
                print(f"  📋 {key}: {len(data_item)} items")
                if key != 'enhanced_tp_sl_monitors' and len(data_item) > 0:
                    print(f"    Sample keys: {list(data_item.keys())[:3]}")
        
        # 2. Simulate the loading process step by step
        print(f"\n📊 STEP 2: SIMULATING LOADING PROCESS")
        print("-" * 50)
        
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        
        # Use the singleton instance
        test_manager = enhanced_tp_sl_manager
        print(f"📊 Fresh manager has {len(test_manager.position_monitors)} monitors")
        
        # Load the same way background_tasks.py does
        persisted_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        print(f"📊 Found {len(persisted_monitors)} persisted monitors to load")
        
        # Clear and load
        test_manager.position_monitors.clear()
        test_manager.position_monitors.update(persisted_monitors)
        
        print(f"📊 After loading: {len(test_manager.position_monitors)} monitors")
        
        # 3. Check if there are additional monitors being added elsewhere
        print(f"\n📊 STEP 3: CHECKING FOR ADDITIONAL MONITOR SOURCES")
        print("-" * 50)
        
        # Check if there are any other monitor collections that might be merged
        monitor_tasks = bot_data.get('monitor_tasks', {})
        print(f"📊 monitor_tasks: {len(monitor_tasks)} items")
        
        if monitor_tasks:
            print(f"  Sample monitor_tasks keys: {list(monitor_tasks.keys())[:5]}")
            
            # Check if any monitor_tasks relate to Enhanced TP/SL
            enhanced_related = []
            for key, task_data in monitor_tasks.items():
                if isinstance(task_data, dict):
                    approach = task_data.get('approach', '')
                    if approach == 'CONSERVATIVE' or 'enhanced' in str(task_data).lower():
                        enhanced_related.append(key)
            
            print(f"📊 Enhanced TP/SL related monitor_tasks: {len(enhanced_related)}")
            if enhanced_related:
                print(f"  Sample keys: {enhanced_related[:5]}")
        
        # 4. Check if there might be duplicate loading
        print(f"\n📊 STEP 4: CHECKING FOR POTENTIAL DUPLICATION SOURCES")
        print("-" * 50)
        
        # Look for any backup or temporary monitor data
        backup_keys = [key for key in bot_data.keys() if 'backup' in key.lower() or 'temp' in key.lower()]
        print(f"📊 Backup/temp keys: {backup_keys}")
        
        # Check if there are monitors with different structures
        unique_monitor_structures = set()
        for key, monitor_data in enhanced_monitors.items():
            if isinstance(monitor_data, dict):
                structure = tuple(sorted(monitor_data.keys()))
                unique_monitor_structures.add(structure)
        
        print(f"📊 Unique monitor data structures: {len(unique_monitor_structures)}")
        for i, structure in enumerate(unique_monitor_structures):
            print(f"  Structure {i+1}: {len(structure)} fields")
        
        # 5. Check for runtime monitor additions
        print(f"\n📊 STEP 5: CHECKING RUNTIME BEHAVIOR")
        print("-" * 50)
        
        # Look at the actual enhanced_tp_sl_manager that's running
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        print(f"📊 Running enhanced_tp_sl_manager has {len(enhanced_tp_sl_manager.position_monitors)} monitors")
        
        # Check if there's a difference between our test and the running instance
        if len(enhanced_tp_sl_manager.position_monitors) != len(test_manager.position_monitors):
            print(f"⚠️ DISCREPANCY FOUND!")
            print(f"  Test manager: {len(test_manager.position_monitors)}")
            print(f"  Running manager: {len(enhanced_tp_sl_manager.position_monitors)}")
            
            # Find the difference
            running_keys = set(enhanced_tp_sl_manager.position_monitors.keys())
            test_keys = set(test_manager.position_monitors.keys())
            
            extra_in_running = running_keys - test_keys
            missing_in_running = test_keys - running_keys
            
            print(f"  Extra in running: {len(extra_in_running)} - {list(extra_in_running)}")
            print(f"  Missing in running: {len(missing_in_running)} - {list(missing_in_running)}")
        
        # 6. Final analysis
        print(f"\n📊 FINAL ANALYSIS")
        print("-" * 30)
        
        total_potential_monitors = (
            len(enhanced_monitors) + 
            (len([k for k in monitor_tasks.keys() if 'enhanced' in str(k).lower()]) if monitor_tasks else 0)
        )
        
        print(f"📊 Potential monitor sources:")
        print(f"  enhanced_tp_sl_monitors: {len(enhanced_monitors)}")
        print(f"  monitor_tasks (enhanced): {len([k for k in monitor_tasks.keys() if 'enhanced' in str(k).lower()]) if monitor_tasks else 0}")
        print(f"  Running manager: {len(enhanced_tp_sl_manager.position_monitors)}")
        
        if len(enhanced_tp_sl_manager.position_monitors) == 26:
            print(f"\n✅ FOUND THE 26! Running manager has exactly 26 monitors")
            print(f"🔧 This suggests monitors are being added at runtime")
        elif len(enhanced_monitors) + 2 == 26:
            print(f"\n💡 POTENTIAL THEORY: 24 pickle + 2 runtime additions = 26")
        
        print(f"\n" + "=" * 60)
        print(f"🔍 MONITOR LOADING TRACE COMPLETE")
        
    except Exception as e:
        print(f"❌ Error during trace: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(trace_monitor_loading())