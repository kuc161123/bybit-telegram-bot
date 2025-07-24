#!/usr/bin/env python3
"""
Check actual monitor keys in pickle file vs expected format
"""
import pickle
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

async def check_monitor_keys():
    """Check monitor key formats and actual coverage"""
    try:
        # Load pickle file
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        print("🔍 MONITOR KEY ANALYSIS")
        print("=" * 60)
        
        print(f"\n📊 Total Enhanced TP/SL Monitors: {len(enhanced_monitors)}")
        print("\n📋 Actual monitor keys in pickle:")
        
        main_monitors = []
        mirror_monitors = []
        
        for key in sorted(enhanced_monitors.keys()):
            monitor = enhanced_monitors[key]
            symbol = monitor.get('symbol', 'UNKNOWN')
            side = monitor.get('side', 'UNKNOWN')
            remaining = monitor.get('remaining_size', 0)
            
            if key.endswith('_mirror'):
                mirror_monitors.append(key)
                print(f"  🪞 {key}: {symbol} {side} (remaining: {remaining})")
            elif key.endswith('_main'):
                main_monitors.append(key)
                print(f"  📈 {key}: {symbol} {side} (remaining: {remaining})")
            else:
                print(f"  ❓ {key}: {symbol} {side} (remaining: {remaining})")
        
        print(f"\n📊 Monitor Breakdown:")
        print(f"  Main monitors (_main suffix): {len(main_monitors)}")
        print(f"  Mirror monitors (_mirror suffix): {len(mirror_monitors)}")
        
        # Now get actual positions from API
        from dotenv import load_dotenv
        load_dotenv()
        
        from clients.bybit_client import BybitClient
        bybit_client = BybitClient()
        
        # Get positions
        main_positions = bybit_client.get_open_positions()
        main_open = [p for p in main_positions if float(p.get('size', 0)) > 0]
        
        mirror_positions = bybit_client.get_open_positions(account_type="mirror")
        mirror_open = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
        
        print(f"\n📊 Actual Positions:")
        print(f"  Main account: {len(main_open)} positions")
        print(f"  Mirror account: {len(mirror_open)} positions")
        
        # Check coverage with correct key format
        print(f"\n🔍 COVERAGE ANALYSIS (using actual key format):")
        
        # Check main positions
        print("\n📈 Main Account Coverage:")
        main_covered = 0
        for pos in main_open:
            symbol = pos.get('symbol')
            side = pos.get('side')
            expected_key = f"{symbol}_{side}_main"
            
            if expected_key in enhanced_monitors:
                print(f"  ✅ {symbol} {side}: Monitor exists")
                main_covered += 1
            else:
                print(f"  ❌ {symbol} {side}: No monitor found (expected key: {expected_key})")
        
        # Check mirror positions
        print("\n🪞 Mirror Account Coverage:")
        mirror_covered = 0
        for pos in mirror_open:
            symbol = pos.get('symbol')
            side = pos.get('side')
            expected_key = f"{symbol}_{side}_mirror"
            
            if expected_key in enhanced_monitors:
                print(f"  ✅ {symbol} {side}: Monitor exists")
                mirror_covered += 1
            else:
                print(f"  ❌ {symbol} {side}: No monitor found (expected key: {expected_key})")
        
        print(f"\n📊 SUMMARY:")
        print(f"  Main positions: {len(main_open)} total, {main_covered} have monitors ({main_covered/len(main_open)*100:.1f}%)")
        print(f"  Mirror positions: {len(mirror_open)} total, {mirror_covered} have monitors ({mirror_covered/len(mirror_open)*100:.1f}%)")
        print(f"  Total monitors: {len(enhanced_monitors)} (should be {len(main_open) + len(mirror_open)})")
        
        if main_covered + mirror_covered == len(main_open) + len(mirror_open):
            print(f"\n✅ All positions have monitors! The find_missing_monitors script has incorrect key format expectations.")
        else:
            missing_count = (len(main_open) - main_covered) + (len(mirror_open) - mirror_covered)
            print(f"\n⚠️ Actually missing {missing_count} monitors")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_monitor_keys())