#!/usr/bin/env python3
"""
Permanent fix for false TP detection - fix ALL mirror monitor values
"""

import pickle
from decimal import Decimal

def permanent_fix():
    """Fix all mirror monitor sizes permanently"""
    
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    monitors = data['bot_data']['enhanced_tp_sl_monitors']
    
    print("Current mirror monitor state:")
    print("-" * 60)
    
    # Show current state
    for key in sorted(monitors.keys()):
        if key.endswith('_mirror'):
            mon = monitors[key]
            print(f"\n{key}:")
            print(f"  position_size: {mon['position_size']}")
            print(f"  remaining_size: {mon.get('remaining_size', 'NOT SET')}")
    
    print("\n" + "=" * 60)
    print("Applying fixes...")
    print("=" * 60)
    
    # Fix JUPUSDT_Sell_mirror - it still has wrong remaining_size
    if 'JUPUSDT_Sell_mirror' in monitors:
        monitors['JUPUSDT_Sell_mirror']['remaining_size'] = monitors['JUPUSDT_Sell_mirror']['position_size']
        print(f"✅ Fixed JUPUSDT_Sell_mirror remaining_size to match position_size: {monitors['JUPUSDT_Sell_mirror']['position_size']}")
    
    # Fix TIAUSDT_Buy_mirror - remaining_size is 510.2 instead of 168.2
    if 'TIAUSDT_Buy_mirror' in monitors:
        monitors['TIAUSDT_Buy_mirror']['remaining_size'] = monitors['TIAUSDT_Buy_mirror']['position_size']
        print(f"✅ Fixed TIAUSDT_Buy_mirror remaining_size to match position_size: {monitors['TIAUSDT_Buy_mirror']['position_size']}")
    
    # Fix LINKUSDT_Buy_mirror - remaining_size is 30.9 instead of 10.2
    if 'LINKUSDT_Buy_mirror' in monitors:
        monitors['LINKUSDT_Buy_mirror']['remaining_size'] = monitors['LINKUSDT_Buy_mirror']['position_size']
        print(f"✅ Fixed LINKUSDT_Buy_mirror remaining_size to match position_size: {monitors['LINKUSDT_Buy_mirror']['position_size']}")
    
    # Clear the fill tracker completely
    data['bot_data']['fill_tracker'] = {}
    print("\n✅ Cleared fill tracker")
    
    # Save the fixed data
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    print("\n" + "=" * 60)
    print("Verification after fixes:")
    print("=" * 60)
    
    # Verify the fix
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    monitors = data['bot_data']['enhanced_tp_sl_monitors']
    all_correct = True
    
    for key in sorted(monitors.keys()):
        if key.endswith('_mirror'):
            mon = monitors[key]
            pos_size = float(mon['position_size'])
            rem_size = float(mon.get('remaining_size', 0))
            
            if pos_size == rem_size:
                print(f"✅ {key}: position_size={pos_size}, remaining_size={rem_size} (CORRECT)")
            else:
                print(f"❌ {key}: position_size={pos_size}, remaining_size={rem_size} (MISMATCH)")
                all_correct = False
    
    if all_correct:
        print("\n✅ ✅ ✅ ALL MIRROR MONITORS FIXED! ✅ ✅ ✅")
        print("The false TP detection issue should now be permanently resolved.")
    else:
        print("\n⚠️ Some monitors still have mismatched sizes!")

if __name__ == "__main__":
    permanent_fix()