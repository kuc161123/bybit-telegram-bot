#!/usr/bin/env python3
"""
Trace monitoring to understand false TP fills
"""

import pickle
from decimal import Decimal

# Load pickle file
with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
    data = pickle.load(f)

monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})

print("\n=== POSITION SIZE ANALYSIS ===")

# Analyze the position sizes to understand the 66% pattern
for symbol in ['ICPUSDT', 'IDUSDT', 'JUPUSDT', 'TIAUSDT', 'LINKUSDT', 'XRPUSDT']:
    main_key = f"{symbol}_Sell_main" if symbol in ['ICPUSDT', 'IDUSDT', 'JUPUSDT'] else f"{symbol}_Buy_main"
    mirror_key = f"{symbol}_Sell_mirror" if symbol in ['ICPUSDT', 'IDUSDT', 'JUPUSDT'] else f"{symbol}_Buy_mirror"
    
    if main_key in monitors and mirror_key in monitors:
        main_size = monitors[main_key]['position_size']
        mirror_size = monitors[mirror_key]['position_size']
        
        # Calculate what percentage mirror is of main
        percentage = (mirror_size / main_size) * 100
        
        # Calculate what the "reduction" would be if comparing mirror to main
        fake_reduction = main_size - mirror_size
        fake_percentage = (fake_reduction / main_size) * 100
        
        print(f"\n{symbol}:")
        print(f"  Main size: {main_size}")
        print(f"  Mirror size: {mirror_size}")
        print(f"  Mirror/Main ratio: {percentage:.2f}%")
        print(f"  If comparing mirror to main, 'reduction': {fake_reduction} ({fake_percentage:.2f}%)")
        
        # Check if this matches the log percentages
        if abs(fake_percentage - 66.39) < 1 or abs(fake_percentage - 66.44) < 1 or abs(fake_percentage - 66.32) < 1:
            print(f"  ⚠️ THIS MATCHES THE FALSE TP FILL PERCENTAGE!")