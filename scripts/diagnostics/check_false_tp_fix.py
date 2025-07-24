#!/usr/bin/env python3
"""Auto-check for false TP fix integrity"""
import pickle
import sys

def check_fix():
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
    
    # Check JUPUSDT_Sell_mirror as a canary
    if 'JUPUSDT_Sell_mirror' in monitors:
        rem_size = float(monitors['JUPUSDT_Sell_mirror'].get('remaining_size', 0))
        if rem_size > 2000:  # Main account size
            print("❌ FALSE TP FIX REVERTED! Run: python robust_permanent_fix.py")
            sys.exit(1)
    
    print("✅ False TP fix still intact")

if __name__ == "__main__":
    check_fix()
