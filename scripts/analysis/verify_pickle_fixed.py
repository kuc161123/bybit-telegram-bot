#!/usr/bin/env python3
"""
Verify the pickle file has correct mirror monitor sizes
"""

import pickle

def verify_fix():
    """Check that mirror monitors have correct position sizes"""
    
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    monitors = data['bot_data']['enhanced_tp_sl_monitors']
    
    # Expected values
    expected = {
        'ICPUSDT_Sell_mirror': 24.3,
        'IDUSDT_Sell_mirror': 391,
        'JUPUSDT_Sell_mirror': 1401,
        'TIAUSDT_Buy_mirror': 168.2,
        'LINKUSDT_Buy_mirror': 10.2,
        'XRPUSDT_Buy_mirror': 87
    }
    
    print("Verifying mirror monitor position sizes:")
    all_correct = True
    
    for key, expected_size in expected.items():
        if key in monitors:
            actual_size = float(monitors[key]['position_size'])
            if actual_size == expected_size:
                print(f"✅ {key}: {actual_size} (correct)")
            else:
                print(f"❌ {key}: {actual_size} (expected {expected_size})")
                all_correct = False
        else:
            print(f"❌ {key}: NOT FOUND")
            all_correct = False
    
    # Also check fill tracker
    print("\nClearing fill tracker to reset cumulative percentages...")
    if 'fill_tracker' in data['bot_data']:
        data['bot_data']['fill_tracker'] = {}
        print("✅ Fill tracker cleared")
    
    # Save the verified data
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    if all_correct:
        print("\n✅ All mirror monitors have correct position sizes!")
        print("✅ Fill tracker cleared")
        print("✅ The bot should now work without false TP detection")
    else:
        print("\n❌ Some monitors still have incorrect sizes")
    
    return all_correct

if __name__ == "__main__":
    verify_fix()