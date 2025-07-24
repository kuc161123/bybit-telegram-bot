#!/usr/bin/env python3
"""
Absolutely final fix - check current state and fix any remaining issues
"""

import pickle
from decimal import Decimal

def check_and_fix():
    """Check current state and apply final fixes"""
    
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    monitors = data['bot_data']['enhanced_tp_sl_monitors']
    
    print("Current mirror monitor state:")
    mirror_monitors = {k: v for k, v in monitors.items() if k.endswith('_mirror')}
    
    for key, monitor in mirror_monitors.items():
        print(f"\n{key}:")
        print(f"  position_size: {monitor['position_size']}")
        print(f"  remaining_size: {monitor.get('remaining_size', 'NOT SET')}")
    
    # Check for issues
    issues_found = False
    
    # Check ICPUSDT_Sell_mirror
    if 'ICPUSDT_Sell_mirror' in monitors:
        mon = monitors['ICPUSDT_Sell_mirror']
        if float(mon['position_size']) != 24.3 or float(mon.get('remaining_size', 0)) != 24.3:
            print(f"\n❌ ICPUSDT_Sell_mirror has wrong values!")
            issues_found = True
    
    # Check IDUSDT_Sell_mirror  
    if 'IDUSDT_Sell_mirror' in monitors:
        mon = monitors['IDUSDT_Sell_mirror']
        if float(mon['position_size']) != 391 or float(mon.get('remaining_size', 0)) != 391:
            print(f"\n❌ IDUSDT_Sell_mirror has wrong values!")
            issues_found = True
            
    # Check JUPUSDT_Sell_mirror
    if 'JUPUSDT_Sell_mirror' in monitors:
        mon = monitors['JUPUSDT_Sell_mirror']
        if float(mon['position_size']) != 1401 or float(mon.get('remaining_size', 0)) != 1401:
            print(f"\n❌ JUPUSDT_Sell_mirror has wrong values!")
            issues_found = True
    
    if issues_found:
        print("\n⚠️ Issues found! Applying fixes...")
        
        # Apply all fixes
        fixes = {
            'ICPUSDT_Sell_mirror': {'position_size': Decimal('24.3'), 'remaining_size': Decimal('24.3')},
            'IDUSDT_Sell_mirror': {'position_size': Decimal('391'), 'remaining_size': Decimal('391')},
            'JUPUSDT_Sell_mirror': {'position_size': Decimal('1401'), 'remaining_size': Decimal('1401')},
            'TIAUSDT_Buy_mirror': {'position_size': Decimal('168.2'), 'remaining_size': Decimal('168.2')},
            'LINKUSDT_Buy_mirror': {'position_size': Decimal('10.2'), 'remaining_size': Decimal('10.2')},
            'XRPUSDT_Buy_mirror': {'position_size': Decimal('87'), 'remaining_size': Decimal('87')}
        }
        
        for key, values in fixes.items():
            if key in monitors:
                monitors[key]['position_size'] = values['position_size']
                monitors[key]['remaining_size'] = values['remaining_size']
                print(f"✅ Fixed {key}")
        
        # Clear fill tracker
        data['bot_data']['fill_tracker'] = {}
        
        # Save
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
            
        print("\n✅ All fixes applied and saved!")
    else:
        print("\n✅ All mirror monitors already have correct values!")
    
    # Double-check the fix
    print("\nFinal verification:")
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    monitors = data['bot_data']['enhanced_tp_sl_monitors']
    for key in ['ICPUSDT_Sell_mirror', 'IDUSDT_Sell_mirror', 'JUPUSDT_Sell_mirror']:
        if key in monitors:
            print(f"{key}: position_size={monitors[key]['position_size']}, remaining_size={monitors[key].get('remaining_size', 'NOT SET')}")

if __name__ == "__main__":
    check_and_fix()