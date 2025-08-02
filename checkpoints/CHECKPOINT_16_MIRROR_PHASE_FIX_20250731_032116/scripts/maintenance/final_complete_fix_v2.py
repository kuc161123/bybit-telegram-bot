#!/usr/bin/env python3
"""
Final complete fix for false TP detection - fix both position_size AND remaining_size
"""

import pickle
from decimal import Decimal

def final_fix():
    """Fix all mirror monitor sizes completely"""
    
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    monitors = data['bot_data']['enhanced_tp_sl_monitors']
    
    # Correct mirror position sizes
    fixes = {
        'ICPUSDT_Sell_mirror': Decimal('24.3'),
        'IDUSDT_Sell_mirror': Decimal('391'),
        'JUPUSDT_Sell_mirror': Decimal('1401'),
        'TIAUSDT_Buy_mirror': Decimal('168.2'),
        'LINKUSDT_Buy_mirror': Decimal('10.2'),
        'XRPUSDT_Buy_mirror': Decimal('87')
    }
    
    # Apply fixes
    for key, correct_size in fixes.items():
        if key in monitors:
            print(f"Fixing {key}:")
            print(f"  Old position_size: {monitors[key]['position_size']}")
            print(f"  Old remaining_size: {monitors[key]['remaining_size']}")
            
            # Fix both position_size AND remaining_size
            monitors[key]['position_size'] = correct_size
            monitors[key]['remaining_size'] = correct_size
            
            print(f"  New position_size: {correct_size}")
            print(f"  New remaining_size: {correct_size}")
    
    # Clear the fill tracker completely
    data['bot_data']['fill_tracker'] = {}
    print("\n✅ Cleared fill tracker")
    
    # Save the fixed data
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    print("\n✅ All mirror monitors fixed!")
    print("✅ Both position_size and remaining_size corrected")
    print("✅ Fill tracker cleared")
    print("\nThe bot should now run without false TP detection errors")

if __name__ == "__main__":
    final_fix()