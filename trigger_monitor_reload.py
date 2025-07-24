#!/usr/bin/env python3
"""
Trigger monitor reload without restarting the bot
"""
import pickle
import time
from datetime import datetime

def trigger_reload():
    """Create trigger files to force monitor reload"""
    print("="*60)
    print("TRIGGERING MONITOR RELOAD")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Create multiple trigger files to ensure reload
    triggers = [
        'reload_monitors.signal',
        'force_reload.trigger',
        '.reload_enhanced_monitors'
    ]
    
    trigger_content = f"""RELOAD_TIMESTAMP={int(time.time())}
FORCE_RELOAD=true
EXPECTED_MONITORS=10
RELOAD_MIRROR=true
"""
    
    for trigger_file in triggers:
        with open(trigger_file, 'w') as f:
            f.write(trigger_content)
        print(f"✅ Created {trigger_file}")
    
    # Also update the pickle file's bot_data to include a reload flag
    print("\n📝 Adding reload flag to pickle file...")
    
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    # Add reload flag
    if 'bot_data' not in data:
        data['bot_data'] = {}
    
    data['bot_data']['force_monitor_reload'] = True
    data['bot_data']['reload_timestamp'] = time.time()
    data['bot_data']['expected_monitors'] = 10
    
    # Save updated pickle
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    print("✅ Added reload flag to pickle file")
    
    # Verify monitors are in pickle
    monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    print(f"\n📊 Pickle contains {len(monitors)} monitors:")
    for key in monitors.keys():
        print(f"   - {key}")
    
    print("\n" + "="*60)
    print("RELOAD TRIGGERED")
    print("="*60)
    print("✅ Created trigger files")
    print("✅ Updated pickle with reload flag")
    print("\nThe bot should reload monitors on the next cycle (within 5-12 seconds)")
    print("You should see 'Monitoring 10 positions' in the logs")

if __name__ == "__main__":
    trigger_reload()