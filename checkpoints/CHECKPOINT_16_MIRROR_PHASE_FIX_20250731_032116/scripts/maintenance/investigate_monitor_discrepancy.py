#!/usr/bin/env python3
"""
Investigate Monitor Count Discrepancy
Find phantom monitors that don't have corresponding positions
"""
import asyncio
import sys
import os
import pickle
from decimal import Decimal

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

async def investigate_monitor_discrepancy():
    """Investigate why Enhanced TP/SL shows 26 monitors but only 24 positions exist"""
    try:
        print("🔍 INVESTIGATING MONITOR COUNT DISCREPANCY")
        print("=" * 60)
        
        # 1. Load pickle file data
        print("\n📊 STEP 1: LOADING PICKLE FILE DATA")
        print("-" * 40)
        
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        print(f"📊 Enhanced TP/SL monitors in pickle: {len(enhanced_monitors)}")
        
        # List all monitors
        monitor_symbols = []
        for monitor_key, monitor_data in enhanced_monitors.items():
            symbol = monitor_data.get('symbol', 'UNKNOWN')
            side = monitor_data.get('side', 'UNKNOWN')
            account = 'MIRROR' if 'MIRROR' in monitor_key else 'MAIN'
            position_size = monitor_data.get('position_size', 0)
            remaining_size = monitor_data.get('remaining_size', 0)
            monitoring_active = monitor_data.get('monitoring_active', False)
            
            monitor_symbols.append(f"{symbol}_{account}")
            print(f"  📋 {monitor_key}: {symbol} {side} {account} (Size: {position_size}, Remaining: {remaining_size}, Active: {monitoring_active})")
        
        # 2. Get actual positions from API
        print("\n📊 STEP 2: GETTING ACTUAL POSITIONS FROM API")
        print("-" * 50)
        
        from clients.bybit_helpers import get_all_positions_with_client
        from clients.bybit_client import bybit_client
        from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
        
        # Get main account positions
        main_positions = await get_all_positions_with_client(bybit_client)
        main_open = [p for p in main_positions if float(p.get('size', 0)) > 0]
        
        # Get mirror account positions
        mirror_open = []
        if is_mirror_trading_enabled() and bybit_client_2:
            mirror_positions = await get_all_positions_with_client(bybit_client_2)
            mirror_open = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
        
        print(f"📊 Actual positions:")
        print(f"  Main account: {len(main_open)} positions")
        print(f"  Mirror account: {len(mirror_open)} positions")
        print(f"  Total: {len(main_open) + len(mirror_open)} positions")
        
        # Create list of actual position symbols
        actual_symbols = []
        
        print(f"\n📋 Main account positions:")
        for pos in main_open:
            symbol = pos.get('symbol', '')
            side = pos.get('side', '')
            size = pos.get('size', 0)
            if symbol:
                actual_symbols.append(f"{symbol}_MAIN")
                print(f"  ✅ {symbol} {side}: {size}")
        
        print(f"\n📋 Mirror account positions:")
        for pos in mirror_open:
            symbol = pos.get('symbol', '')
            side = pos.get('side', '')
            size = pos.get('size', 0)
            if symbol:
                actual_symbols.append(f"{symbol}_MIRROR")
                print(f"  ✅ {symbol} {side}: {size}")
        
        # 3. Compare monitors vs positions
        print("\n📊 STEP 3: COMPARING MONITORS VS POSITIONS")
        print("-" * 50)
        
        # Find phantom monitors (monitors without positions)
        phantom_monitors = []
        for monitor_symbol in monitor_symbols:
            if monitor_symbol not in actual_symbols:
                phantom_monitors.append(monitor_symbol)
        
        # Find missing monitors (positions without monitors)
        missing_monitors = []
        for actual_symbol in actual_symbols:
            if actual_symbol not in monitor_symbols:
                missing_monitors.append(actual_symbol)
        
        print(f"📊 Comparison results:")
        print(f"  Monitors in pickle: {len(monitor_symbols)}")
        print(f"  Actual positions: {len(actual_symbols)}")
        print(f"  Phantom monitors: {len(phantom_monitors)}")
        print(f"  Missing monitors: {len(missing_monitors)}")
        
        if phantom_monitors:
            print(f"\n⚠️ PHANTOM MONITORS (monitors without positions):")
            for phantom in phantom_monitors:
                # Find the actual monitor key for this phantom
                phantom_key = None
                for monitor_key, monitor_data in enhanced_monitors.items():
                    symbol = monitor_data.get('symbol', 'UNKNOWN')
                    account = 'MIRROR' if 'MIRROR' in monitor_key else 'MAIN'
                    if f"{symbol}_{account}" == phantom:
                        phantom_key = monitor_key
                        break
                
                if phantom_key:
                    monitor_data = enhanced_monitors[phantom_key]
                    symbol = monitor_data.get('symbol', 'UNKNOWN')
                    side = monitor_data.get('side', 'UNKNOWN')
                    size = monitor_data.get('position_size', 0)
                    remaining = monitor_data.get('remaining_size', 0)
                    print(f"  👻 {phantom_key}: {symbol} {side} (Size: {size}, Remaining: {remaining})")
        
        if missing_monitors:
            print(f"\n⚠️ MISSING MONITORS (positions without monitors):")
            for missing in missing_monitors:
                print(f"  📭 {missing}")
        
        # 4. Detailed analysis of phantom monitors
        if phantom_monitors:
            print(f"\n📊 STEP 4: DETAILED PHANTOM MONITOR ANALYSIS")
            print("-" * 50)
            
            for phantom in phantom_monitors:
                # Find the monitor details
                for monitor_key, monitor_data in enhanced_monitors.items():
                    symbol = monitor_data.get('symbol', 'UNKNOWN')
                    account = 'MIRROR' if 'MIRROR' in monitor_key else 'MAIN'
                    if f"{symbol}_{account}" == phantom:
                        print(f"\n👻 PHANTOM: {monitor_key}")
                        print(f"  Symbol: {symbol}")
                        print(f"  Side: {monitor_data.get('side', 'UNKNOWN')}")
                        print(f"  Account: {account}")
                        print(f"  Position Size: {monitor_data.get('position_size', 0)}")
                        print(f"  Remaining Size: {monitor_data.get('remaining_size', 0)}")
                        print(f"  Entry Price: {monitor_data.get('entry_price', 0)}")
                        print(f"  Monitoring Active: {monitor_data.get('monitoring_active', False)}")
                        print(f"  Phase: {monitor_data.get('phase', 'UNKNOWN')}")
                        print(f"  TP Orders: {len(monitor_data.get('tp_orders', []))}")
                        print(f"  SL Order: {bool(monitor_data.get('sl_order'))}")
                        print(f"  Chat ID: {monitor_data.get('chat_id', 'UNKNOWN')}")
                        print(f"  Created: {monitor_data.get('created_time', 'UNKNOWN')}")
                        break
        
        # 5. Summary and recommendations
        print(f"\n📊 SUMMARY & RECOMMENDATIONS")
        print("-" * 40)
        
        if len(phantom_monitors) == 2 and len(missing_monitors) == 0:
            print(f"✅ ISSUE IDENTIFIED: Exactly 2 phantom monitors found")
            print(f"📊 This explains the discrepancy: 24 actual + 2 phantom = 26 monitored")
            print(f"\n🔧 RECOMMENDED ACTIONS:")
            print(f"  1. Remove the 2 phantom monitors from pickle file")
            print(f"  2. Improve monitor cleanup logic to prevent future phantoms")
            print(f"  3. Add position validation before monitor creation")
            print(f"  4. Implement periodic phantom monitor detection")
        else:
            print(f"⚠️ UNEXPECTED PATTERN:")
            print(f"  Expected: 2 phantom monitors, 0 missing")
            print(f"  Found: {len(phantom_monitors)} phantom, {len(missing_monitors)} missing")
            print(f"  This may indicate a more complex issue")
        
        print(f"\n" + "=" * 60)
        print(f"🔍 MONITOR DISCREPANCY INVESTIGATION COMPLETE")
        
    except Exception as e:
        print(f"❌ Error during investigation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(investigate_monitor_discrepancy())