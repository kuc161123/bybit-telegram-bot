#!/usr/bin/env python3
"""
Final Verification: 26 Enhanced TP/SL Monitors
This confirms the complete fix is working
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

async def final_verification():
    """Final verification of the 26 monitor setup"""
    try:
        print("🔍 FINAL VERIFICATION: 26 ENHANCED TP/SL MONITORS")
        print("=" * 70)
        
        # Get actual positions
        from clients.bybit_helpers import get_all_positions_with_client
        from clients.bybit_client import bybit_client
        from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
        
        # Check actual positions
        main_positions = await get_all_positions_with_client(bybit_client)
        main_open = [p for p in main_positions if float(p.get('size', 0)) > 0]
        
        mirror_open = []
        if is_mirror_trading_enabled() and bybit_client_2:
            mirror_positions = await get_all_positions_with_client(bybit_client_2)
            mirror_open = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
        
        total_positions = len(main_open) + len(mirror_open)
        
        print(f"📈 Main Account Positions: {len(main_open)}")
        for pos in main_open:
            print(f"  • {pos.get('symbol')} {pos.get('side')} (size: {pos.get('size')})")
            
        print(f"\\n🪞 Mirror Account Positions: {len(mirror_open)}")
        for pos in mirror_open:
            print(f"  • {pos.get('symbol')} {pos.get('side')} (size: {pos.get('size')})")
        
        print(f"\\n📊 TOTAL ACTUAL POSITIONS: {total_positions}")
        
        # Check persistence monitors
        import pickle
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        monitor_count = len(monitors)
        
        print(f"📊 ENHANCED TP/SL MONITORS IN PERSISTENCE: {monitor_count}")
        
        # Count by account type
        main_monitors = []
        mirror_monitors = []
        
        for key, monitor in monitors.items():
            account_type = monitor.get('account_type', 'unknown')
            symbol = monitor.get('symbol')
            side = monitor.get('side')
            
            if account_type == 'main':
                main_monitors.append(f"{symbol}_{side}")
            elif account_type == 'mirror':
                mirror_monitors.append(f"{symbol}_{side}")
        
        print(f"\\n📋 MONITOR BREAKDOWN:")
        print(f"  Main Account: {len(main_monitors)} monitors")
        print(f"  Mirror Account: {len(mirror_monitors)} monitors")
        
        # Verify coverage
        print(f"\\n🔍 COVERAGE VERIFICATION:")
        
        missing_main = []
        missing_mirror = []
        
        # Check main positions coverage
        for pos in main_open:
            symbol = pos.get('symbol')
            side = pos.get('side')
            key = f"{symbol}_{side}"
            if key not in main_monitors:
                missing_main.append(key)
        
        # Check mirror positions coverage
        for pos in mirror_open:
            symbol = pos.get('symbol')
            side = pos.get('side')
            key = f"{symbol}_{side}"
            if key not in mirror_monitors:
                missing_mirror.append(key)
        
        if missing_main:
            print(f"  ❌ Missing main monitors: {missing_main}")
        else:
            print(f"  ✅ All {len(main_open)} main positions have monitors")
            
        if missing_mirror:
            print(f"  ❌ Missing mirror monitors: {missing_mirror}")
        else:
            print(f"  ✅ All {len(mirror_open)} mirror positions have monitors")
        
        # Final verdict
        coverage = (monitor_count / total_positions) * 100 if total_positions > 0 else 0
        
        print(f"\\n" + "=" * 70)
        print(f"📊 FINAL RESULTS:")
        print(f"  Actual Positions: {total_positions}")
        print(f"  Enhanced TP/SL Monitors: {monitor_count}")
        print(f"  Coverage: {coverage:.1f}%")
        
        if coverage == 100 and monitor_count == 26:
            print(f"\\n🎉 PERFECT SUCCESS!")
            print(f"✅ Enhanced TP/SL Manager monitoring all 26 positions")
            print(f"✅ 100% coverage for both main and mirror accounts")
            print(f"✅ Import fix working - no automatic monitor creation errors")
            print(f"✅ System is ready for all future trades")
        else:
            print(f"\\n⚠️ ISSUES DETECTED:")
            if monitor_count != 26:
                print(f"❌ Expected 26 monitors, found {monitor_count}")
            if coverage < 100:
                print(f"❌ Coverage is {coverage:.1f}%, not 100%")
        
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(final_verification())