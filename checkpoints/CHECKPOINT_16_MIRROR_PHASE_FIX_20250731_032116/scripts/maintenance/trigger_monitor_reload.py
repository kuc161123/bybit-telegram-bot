#!/usr/bin/env python3
"""
Trigger Monitor Reload and Check Count
Force the background task to reload monitors and see the result
"""
import asyncio
import sys
import os
import time

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

async def trigger_monitor_reload():
    """Trigger monitor reload and check the count"""
    try:
        print("🔍 TRIGGERING MONITOR RELOAD TO CHECK COUNT")
        print("=" * 60)
        
        # 1. Check current state
        print("\n📊 STEP 1: CHECKING CURRENT STATE")
        print("-" * 40)
        
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        
        print(f"📊 Current runtime monitors: {len(enhanced_tp_sl_manager.position_monitors)}")
        
        # 2. Create signal file to trigger reload
        print("\n📊 STEP 2: TRIGGERING RELOAD")
        print("-" * 30)
        
        signal_file = '/Users/lualakol/bybit-telegram-bot/reload_enhanced_monitors.signal'
        
        # Create the signal file
        with open(signal_file, 'w') as f:
            f.write('reload_monitors')
        
        print(f"📡 Signal file created: {signal_file}")
        print("⏳ Waiting 10 seconds for background task to process...")
        
        # Wait for the background task to process
        await asyncio.sleep(10)
        
        # 3. Check after reload
        print("\n📊 STEP 3: CHECKING AFTER RELOAD")
        print("-" * 40)
        
        print(f"📊 Runtime monitors after reload: {len(enhanced_tp_sl_manager.position_monitors)}")
        
        if len(enhanced_tp_sl_manager.position_monitors) > 0:
            print(f"✅ Monitors loaded! Listing first 5:")
            for i, (key, data) in enumerate(list(enhanced_tp_sl_manager.position_monitors.items())[:5]):
                symbol = data.get('symbol', 'UNKNOWN')
                side = data.get('side', 'UNKNOWN')
                account = 'MIRROR' if 'MIRROR' in key else 'MAIN'
                print(f"  📋 {key}: {symbol} {side} {account}")
            
            if len(enhanced_tp_sl_manager.position_monitors) == 26:
                print(f"\n🎯 FOUND THE 26! Enhanced TP/SL Manager now has exactly 26 monitors")
                
                # Count by account
                main_count = sum(1 for key in enhanced_tp_sl_manager.position_monitors.keys() if 'MIRROR' not in key)
                mirror_count = sum(1 for key in enhanced_tp_sl_manager.position_monitors.keys() if 'MIRROR' in key)
                
                print(f"📊 Account breakdown:")
                print(f"  Main account monitors: {main_count}")
                print(f"  Mirror account monitors: {mirror_count}")
                print(f"  Total: {main_count + mirror_count}")
                
                if main_count + mirror_count == 26:
                    print(f"🔧 Analysis: {main_count} main + {mirror_count} mirror = 26 total")
                    
                    # Check if this matches position count
                    expected_positions = 24  # From our earlier verification
                    if main_count + mirror_count > expected_positions:
                        extra_monitors = (main_count + mirror_count) - expected_positions
                        print(f"⚠️ Found {extra_monitors} extra monitors compared to actual positions")
            
            elif len(enhanced_tp_sl_manager.position_monitors) == 24:
                print(f"📊 Monitor count matches pickle file (24)")
            else:
                print(f"❓ Unexpected monitor count: {len(enhanced_tp_sl_manager.position_monitors)}")
        else:
            print(f"❌ No monitors loaded after reload")
        
        # 4. Check if signal file was removed
        print(f"\n📊 STEP 4: CHECKING SIGNAL FILE STATUS")
        print("-" * 40)
        
        if os.path.exists(signal_file):
            print(f"📡 Signal file still exists - background task may not have processed it yet")
        else:
            print(f"✅ Signal file removed - background task processed the reload")
        
        print(f"\n" + "=" * 60)
        print(f"🔍 MONITOR RELOAD TRIGGER COMPLETE")
        
    except Exception as e:
        print(f"❌ Error during reload trigger: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(trigger_monitor_reload())