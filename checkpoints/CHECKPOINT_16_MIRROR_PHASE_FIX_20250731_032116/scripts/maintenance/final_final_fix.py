#!/usr/bin/env python3
"""
Final fix - some mirror monitors still have wrong remaining_size
"""

import pickle
from decimal import Decimal

def final_fix():
    """Fix remaining mirror monitor issues"""
    
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    monitors = data['bot_data']['enhanced_tp_sl_monitors']
    
    print("Checking and fixing mirror monitors...")
    fixes_needed = 0
    
    # Check each mirror monitor
    mirror_monitors = {k: v for k, v in monitors.items() if k.endswith('_mirror')}
    
    for key, monitor in mirror_monitors.items():
        pos_size = monitor['position_size']
        rem_size = monitor.get('remaining_size', pos_size)
        
        # For ICPUSDT, IDUSDT - these have been traded, so check if remaining_size is reasonable
        if key in ['ICPUSDT_Sell_mirror', 'IDUSDT_Sell_mirror']:
            # These have active trades, so remaining_size might be different
            # But it should NOT be the main account size
            if key == 'ICPUSDT_Sell_mirror' and float(rem_size) > 100:
                print(f"❌ {key}: remaining_size={rem_size} looks like main account size")
                monitor['remaining_size'] = monitor['position_size']
                fixes_needed += 1
            elif key == 'IDUSDT_Sell_mirror' and float(rem_size) > 2000:
                print(f"❌ {key}: remaining_size={rem_size} looks like main account size")
                monitor['remaining_size'] = monitor['position_size']
                fixes_needed += 1
        else:
            # For other positions, remaining_size should equal position_size
            if rem_size != pos_size:
                print(f"❌ {key}: remaining_size={rem_size} != position_size={pos_size}")
                monitor['remaining_size'] = monitor['position_size']
                fixes_needed += 1
    
    # Clear fill tracker
    data['bot_data']['fill_tracker'] = {}
    
    # Save
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    if fixes_needed > 0:
        print(f"\n✅ Fixed {fixes_needed} monitors")
    else:
        print("\n✅ All monitors already correct")
    
    # Verify
    print("\nFinal verification:")
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    monitors = data['bot_data']['enhanced_tp_sl_monitors']
    for key in sorted(monitors.keys()):
        if key.endswith('_mirror'):
            mon = monitors[key]
            print(f"{key}: pos={mon['position_size']}, rem={mon.get('remaining_size', 'NOT SET')}")

if __name__ == "__main__":
    final_fix()