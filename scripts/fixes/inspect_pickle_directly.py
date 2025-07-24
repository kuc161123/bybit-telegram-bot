#!/usr/bin/env python3
"""
Direct Pickle Inspection
========================

Directly inspect the pickle file to understand the JASMY monitor structure.
"""
import pickle
import json

def inspect_pickle():
    """Inspect pickle file directly"""
    print("🔍 Direct pickle inspection...")
    
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        print("✅ Pickle loaded successfully")
        
        # Check top-level structure
        print(f"\n📊 Top-level keys: {list(data.keys())}")
        
        if 'bot_data' in data:
            bot_data = data['bot_data']
            print(f"📊 bot_data keys: {list(bot_data.keys())}")
            
            if 'enhanced_tp_sl_monitors' in bot_data:
                monitors = bot_data['enhanced_tp_sl_monitors']
                print(f"📊 Enhanced monitors count: {len(monitors)}")
                
                # Find JASMY monitors
                jasmy_monitors = {}
                for key, monitor in monitors.items():
                    if monitor.get('symbol') == 'JASMYUSDT':
                        jasmy_monitors[key] = monitor
                
                print(f"🎯 JASMY monitors found: {len(jasmy_monitors)}")
                
                for key, monitor in jasmy_monitors.items():
                    print(f"\n{'='*60}")
                    print(f"🎯 Monitor: {key}")
                    print(f"{'='*60}")
                    
                    # Key fields
                    important_fields = [
                        'symbol', 'account_type', 'position_size', 'remaining_size',
                        'tp1_hit', 'phase', 'filled_tps', 'sl_moved_to_be', 
                        'limit_orders_cancelled', 'phase_transition_time'
                    ]
                    
                    for field in important_fields:
                        value = monitor.get(field, 'NOT_SET')
                        print(f"   {field}: {value}")
                    
                    # Check TP orders
                    tp_orders = monitor.get('tp_orders', {})
                    print(f"   tp_orders_count: {len(tp_orders)}")
                    
                    # Check if there's tp1_info
                    tp1_info = monitor.get('tp1_info')
                    if tp1_info:
                        print(f"   tp1_info: {tp1_info}")
                    else:
                        print(f"   tp1_info: NOT_SET")
        
        # Check if there are other potential locations
        print(f"\n🔍 Searching for other JASMY references...")
        jasmy_refs = find_jasmy_references(data)
        print(f"📊 Total JASMY references found: {len(jasmy_refs)}")
        
    except Exception as e:
        print(f"❌ Inspection failed: {e}")

def find_jasmy_references(obj, path="root"):
    """Recursively find all JASMY references"""
    refs = []
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            new_path = f"{path}.{key}"
            if 'JASMY' in str(key).upper() or 'JASMY' in str(value).upper():
                refs.append((new_path, key, value))
            refs.extend(find_jasmy_references(value, new_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            new_path = f"{path}[{i}]"
            if 'JASMY' in str(item).upper():
                refs.append((new_path, i, item))
            refs.extend(find_jasmy_references(item, new_path))
    elif isinstance(obj, str) and 'JASMY' in obj.upper():
        refs.append((path, "string_value", obj))
    
    return refs

if __name__ == "__main__":
    inspect_pickle()