#!/usr/bin/env python3
"""
Find Missing Monitors Complete Analysis
Identify all missing Enhanced TP/SL monitors to achieve 28/28 coverage
"""
import asyncio
import sys
import os
import pickle

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

async def find_missing_monitors_complete():
    """Find all missing Enhanced TP/SL monitors"""
    try:
        print("🔍 FINDING MISSING MONITORS - COMPLETE ANALYSIS")
        print("=" * 60)
        
        # Get actual positions
        from clients.bybit_helpers import get_all_positions_with_client
        from clients.bybit_client import bybit_client
        from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
        
        main_positions = await get_all_positions_with_client(bybit_client)
        main_open = [p for p in main_positions if float(p.get('size', 0)) > 0]
        
        mirror_open = []
        if is_mirror_trading_enabled() and bybit_client_2:
            mirror_positions = await get_all_positions_with_client(bybit_client_2)
            mirror_open = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
        
        # Load Enhanced TP/SL monitors
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        print(f"📈 Main Account Positions: {len(main_open)}")
        print(f"🪞 Mirror Account Positions: {len(mirror_open)}")
        print(f"📊 Enhanced TP/SL Monitors: {len(enhanced_monitors)}")
        
        # Analyze missing monitors
        print(f"\\n🔍 ANALYZING MISSING MONITORS:")
        
        # Create expected monitor keys for all positions
        expected_main_monitors = []
        expected_mirror_monitors = []
        
        for pos in main_open:
            symbol = pos.get('symbol')
            side = pos.get('side')
            key = f"{symbol}_{side}"
            expected_main_monitors.append(key)
        
        for pos in mirror_open:
            symbol = pos.get('symbol')
            side = pos.get('side')
            key = f"{symbol}_{side}_MIRROR"
            expected_mirror_monitors.append(key)
        
        # Check which monitors exist
        existing_monitors = list(enhanced_monitors.keys())
        
        print(f"\\n📋 Expected Main Monitors:")
        missing_main = []
        for key in expected_main_monitors:
            exists = key in existing_monitors
            status = "✅" if exists else "❌"
            print(f"  {status} {key}")
            if not exists:
                missing_main.append(key)
        
        print(f"\\n📋 Expected Mirror Monitors:")
        missing_mirror = []
        for key in expected_mirror_monitors:
            exists = key in existing_monitors
            status = "✅" if exists else "❌"
            print(f"  {status} {key}")
            if not exists:
                missing_mirror.append(key)
        
        print(f"\\n❌ MISSING MONITORS:")
        print(f"  Main Account: {missing_main}")
        print(f"  Mirror Account: {missing_mirror}")
        print(f"  Total Missing: {len(missing_main) + len(missing_mirror)}")
        
        # Identify the specific positions for missing monitors
        print(f"\\n📊 MISSING MONITOR DETAILS:")
        
        for key in missing_main:
            symbol_side = key.split('_')
            symbol = symbol_side[0]
            side = symbol_side[1]
            
            # Find the position
            for pos in main_open:
                if pos.get('symbol') == symbol and pos.get('side') == side:
                    print(f"  Main {symbol} {side}: size={pos.get('size')}, avgPrice={pos.get('avgPrice')}")
                    break
        
        for key in missing_mirror:
            symbol_side = key.replace('_MIRROR', '').split('_')
            symbol = symbol_side[0]
            side = symbol_side[1]
            
            # Find the position
            for pos in mirror_open:
                if pos.get('symbol') == symbol and pos.get('side') == side:
                    print(f"  Mirror {symbol} {side}: size={pos.get('size')}, avgPrice={pos.get('avgPrice')}")
                    break
        
        # Summary
        total_expected = len(expected_main_monitors) + len(expected_mirror_monitors)
        total_existing = len(enhanced_monitors)
        total_missing = len(missing_main) + len(missing_mirror)
        
        print(f"\\n" + "=" * 60)
        print(f"📊 SUMMARY:")
        print(f"  Total Expected Monitors: {total_expected}")
        print(f"  Total Existing Monitors: {total_existing}")
        print(f"  Total Missing Monitors: {total_missing}")
        print(f"  Coverage: {(total_existing/total_expected)*100:.1f}%")
        
        if total_missing == 0:
            print(f"\\n🎉 PERFECT! All monitors exist!")
        else:
            print(f"\\n⚠️ Need to add {total_missing} more monitors to achieve 100% coverage")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(find_missing_monitors_complete())