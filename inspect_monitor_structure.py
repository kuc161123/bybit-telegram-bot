#!/usr/bin/env python3
"""
Inspect monitor structure to understand why chat_id updates aren't persisting.
"""

import pickle
import json
from datetime import datetime
from typing import Dict, Any, List

def inspect_monitor_structure():
    """Inspect the structure of monitors in the pickle file."""
    
    print("=" * 80)
    print("MONITOR STRUCTURE INSPECTION")
    print("=" * 80)
    
    # Load pickle file
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    try:
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        print(f"✓ Successfully loaded {pickle_file}")
    except Exception as e:
        print(f"✗ Error loading pickle file: {e}")
        return
    
    # Define problematic monitors to inspect
    problematic_monitors = [
        'AUCTIONUSDT_Buy_main',
        'NTRNUSDT_Buy_main',
        'AAVEUSDT_Buy_main',
        'THETAUSDT_Buy_main',
        'FIOUSDT_Buy_main'
    ]
    
    print(f"\n📊 Inspecting {len(problematic_monitors)} problematic monitors...")
    
    # Check bot_data structure
    bot_data = data.get('bot_data', {})
    print(f"\n🔍 bot_data keys: {list(bot_data.keys())}")
    
    # 1. Check enhanced_tp_sl_monitors
    enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
    print(f"\n📌 Enhanced TP/SL Monitors: {len(enhanced_monitors)} total")
    
    for monitor_key in problematic_monitors[:2]:  # Inspect first 2 in detail
        if monitor_key in enhanced_monitors:
            monitor = enhanced_monitors[monitor_key]
            print(f"\n🔍 Monitor: {monitor_key}")
            print(f"   Type: {type(monitor)}")
            
            # Print all fields
            if isinstance(monitor, dict):
                for field, value in monitor.items():
                    value_type = type(value).__name__
                    if field == 'chat_id':
                        print(f"   📍 {field}: {value} (type: {value_type}) {'⚠️ NONE!' if value is None else ''}")
                    else:
                        # Truncate long values
                        value_str = str(value)
                        if len(value_str) > 50:
                            value_str = value_str[:47] + "..."
                        print(f"   - {field}: {value_str} (type: {value_type})")
            else:
                print(f"   ⚠️ Monitor is not a dict! Type: {type(monitor)}")
        else:
            print(f"\n❌ Monitor {monitor_key} NOT FOUND in enhanced_tp_sl_monitors")
    
    # 2. Check monitor_tasks
    monitor_tasks = bot_data.get('monitor_tasks', {})
    print(f"\n📌 Dashboard Monitor Tasks: {len(monitor_tasks)} total")
    
    # Find monitors in monitor_tasks
    for monitor_key in problematic_monitors[:2]:
        found_in_tasks = False
        for task_key, task_data in monitor_tasks.items():
            if monitor_key in str(task_key) or monitor_key in str(task_data):
                print(f"\n🔍 Found {monitor_key} in monitor_tasks:")
                print(f"   Task key: {task_key}")
                if isinstance(task_data, dict):
                    for field, value in task_data.items():
                        if field == 'chat_id':
                            print(f"   📍 {field}: {value} (type: {type(value).__name__})")
                        else:
                            value_str = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                            print(f"   - {field}: {value_str}")
                found_in_tasks = True
                break
        
        if not found_in_tasks:
            print(f"\n❌ Monitor {monitor_key} NOT FOUND in monitor_tasks")
    
    # 3. Check user_data for positions
    print(f"\n📌 Checking user_data for related positions...")
    user_data = data.get('user_data', {})
    
    for chat_id, user_info in user_data.items():
        if isinstance(user_info, dict):
            positions = user_info.get('positions', {})
            for monitor_key in problematic_monitors[:2]:
                # Extract symbol from monitor key
                symbol = monitor_key.split('_')[0]
                if symbol in positions:
                    print(f"\n✓ Found position {symbol} for chat_id {chat_id}")
                    pos = positions[symbol]
                    if isinstance(pos, dict):
                        print(f"   - Side: {pos.get('side')}")
                        print(f"   - Size: {pos.get('size')}")
                        print(f"   - Account: {'main' if monitor_key.endswith('_main') else 'mirror'}")
    
    # 4. Check pickle file metadata
    print(f"\n📌 Pickle file metadata:")
    import os
    file_stats = os.stat(pickle_file)
    print(f"   - Size: {file_stats.st_size:,} bytes")
    print(f"   - Modified: {datetime.fromtimestamp(file_stats.st_mtime)}")
    
    # 5. Check for any other occurrences of these monitors
    print(f"\n📌 Searching for monitor keys in entire pickle structure...")
    
    def search_dict(d, search_key, path=""):
        """Recursively search for a key in nested dictionaries."""
        results = []
        if isinstance(d, dict):
            for k, v in d.items():
                new_path = f"{path}.{k}" if path else k
                if search_key in str(k):
                    results.append((new_path, k, type(v).__name__))
                if isinstance(v, (dict, list)):
                    results.extend(search_dict(v, search_key, new_path))
        elif isinstance(d, list):
            for i, item in enumerate(d):
                new_path = f"{path}[{i}]"
                if isinstance(item, (dict, list)):
                    results.extend(search_dict(item, search_key, new_path))
        return results
    
    # Search for first problematic monitor
    search_key = problematic_monitors[0]
    print(f"\n🔍 Searching for '{search_key}' in entire structure...")
    occurrences = search_dict(data, search_key)
    
    if occurrences:
        print(f"   Found {len(occurrences)} occurrence(s):")
        for path, key, value_type in occurrences:
            print(f"   - {path} (value type: {value_type})")
    else:
        print(f"   ❌ No occurrences found!")
    
    # 6. Check if monitors have consistent structure
    print(f"\n📌 Checking monitor structure consistency...")
    
    # Get all enhanced monitor keys
    all_monitor_keys = list(enhanced_monitors.keys())
    
    # Check field consistency
    if all_monitor_keys:
        # Get fields from first monitor
        first_monitor = enhanced_monitors.get(all_monitor_keys[0], {})
        if isinstance(first_monitor, dict):
            expected_fields = set(first_monitor.keys())
            
            # Check a sample of monitors
            sample_size = min(10, len(all_monitor_keys))
            inconsistent_monitors = []
            
            for key in all_monitor_keys[:sample_size]:
                monitor = enhanced_monitors.get(key, {})
                if isinstance(monitor, dict):
                    monitor_fields = set(monitor.keys())
                    if monitor_fields != expected_fields:
                        inconsistent_monitors.append({
                            'key': key,
                            'missing': expected_fields - monitor_fields,
                            'extra': monitor_fields - expected_fields
                        })
            
            if inconsistent_monitors:
                print(f"   ⚠️ Found {len(inconsistent_monitors)} monitors with inconsistent fields:")
                for m in inconsistent_monitors[:3]:  # Show first 3
                    print(f"   - {m['key']}")
                    if m['missing']:
                        print(f"     Missing: {m['missing']}")
                    if m['extra']:
                        print(f"     Extra: {m['extra']}")
            else:
                print(f"   ✓ All sampled monitors have consistent fields")
                print(f"   Expected fields: {sorted(expected_fields)}")
    
    # 7. Special check for chat_id field
    print(f"\n📌 Analyzing chat_id field across all enhanced monitors...")
    
    chat_id_stats = {
        'total': len(enhanced_monitors),
        'with_chat_id': 0,
        'chat_id_none': 0,
        'missing_chat_id': 0,
        'chat_id_values': set()
    }
    
    for key, monitor in enhanced_monitors.items():
        if isinstance(monitor, dict):
            if 'chat_id' in monitor:
                chat_id_stats['with_chat_id'] += 1
                if monitor['chat_id'] is None:
                    chat_id_stats['chat_id_none'] += 1
                else:
                    chat_id_stats['chat_id_values'].add(monitor['chat_id'])
            else:
                chat_id_stats['missing_chat_id'] += 1
    
    print(f"   - Total monitors: {chat_id_stats['total']}")
    print(f"   - With chat_id field: {chat_id_stats['with_chat_id']}")
    print(f"   - chat_id is None: {chat_id_stats['chat_id_none']}")
    print(f"   - Missing chat_id field: {chat_id_stats['missing_chat_id']}")
    print(f"   - Unique chat_id values: {chat_id_stats['chat_id_values']}")
    
    print("\n" + "=" * 80)
    print("INSPECTION COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    inspect_monitor_structure()