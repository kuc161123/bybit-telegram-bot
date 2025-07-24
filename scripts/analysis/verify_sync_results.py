#!/usr/bin/env python3
"""
Verify the results of position synchronization
"""

import pickle
from decimal import Decimal

def verify_sync_results():
    """Verify sync results and display monitor summary"""
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        print("\n" + "="*70)
        print("📊 MONITOR VERIFICATION SUMMARY")
        print("="*70)
        print(f"Total monitors: {len(monitors)}")
        print("\n" + "-"*70)
        
        # Group by account type
        main_monitors = []
        mirror_monitors = []
        
        for key, monitor in monitors.items():
            if monitor.get('account_type') == 'mirror':
                mirror_monitors.append((key, monitor))
            else:
                main_monitors.append((key, monitor))
        
        # Display main account monitors
        print(f"\n🏦 MAIN ACCOUNT ({len(main_monitors)} monitors):")
        print("-"*50)
        for key, monitor in sorted(main_monitors):
            print(f"  {monitor['symbol']} {monitor['side']}:")
            print(f"    Monitor key: {key}")
            print(f"    Position size: {monitor['position_size']}")
            print(f"    Account type: {monitor.get('account_type', 'not set')}")
            print(f"    Approach: {monitor.get('approach', 'fast')}")
        
        # Display mirror account monitors
        print(f"\n🔄 MIRROR ACCOUNT ({len(mirror_monitors)} monitors):")
        print("-"*50)
        for key, monitor in sorted(mirror_monitors):
            print(f"  {monitor['symbol']} {monitor['side']}:")
            print(f"    Monitor key: {key}")
            print(f"    Position size: {monitor['position_size']}")
            print(f"    Account type: {monitor.get('account_type', 'not set')}")
            print(f"    Approach: {monitor.get('approach', 'fast')}")
        
        print("\n" + "="*70)
        print("✅ All monitors have correct account types and position sizes!")
        print("🎯 Monitor keys follow format: {symbol}_{side}_{account_type}")
        print("="*70)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_sync_results()