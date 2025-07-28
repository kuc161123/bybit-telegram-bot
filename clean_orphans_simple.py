#!/usr/bin/env python3
"""
Simple orphaned monitor cleanup that works around client issues
"""
import pickle
import time
import os
import sys

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_helpers import get_all_positions

async def clean_orphaned_monitors_simple():
    """Remove monitors for positions that no longer exist"""
    
    # Backup first
    timestamp = int(time.time())
    backup_name = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_orphan_cleanup_{timestamp}'
    
    try:
        import shutil
        shutil.copy2('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_name)
        print(f"✅ Created backup: {backup_name}")
    except Exception as e:
        print(f"⚠️ Could not create backup: {e}")
    
    # Get actual positions from main account only (avoiding mirror client issue)
    print("\n🔍 Getting actual positions from main account...")
    
    try:
        main_positions = await get_all_positions()
        main_active_symbols = set()
        
        for pos in main_positions:
            if float(pos.get('size', 0)) > 0:
                main_active_symbols.add(pos['symbol'])
        
        print(f"📊 Main account has {len(main_active_symbols)} active positions")
        
    except Exception as e:
        print(f"❌ Error getting positions: {e}")
        return False
    
    # Load pickle data
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        print(f"❌ Error loading pickle data: {e}")
        return False
    
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    print(f"📊 Current monitors: {len(enhanced_monitors)}")
    
    # Find monitors to remove
    monitors_to_remove = []
    main_monitors_to_remove = []
    mirror_monitors_to_remove = []
    
    for key, monitor in enhanced_monitors.items():
        symbol = monitor.get('symbol', '')
        account = monitor.get('account_type', 'unknown')
        
        # For main account monitors, check if position exists
        if key.endswith('_main') or account == 'main':
            if symbol not in main_active_symbols:
                monitors_to_remove.append(key)
                main_monitors_to_remove.append(symbol)
                print(f"  🗑️ Will remove main monitor: {symbol}")
        
        # For mirror monitors, we'll be more conservative and only remove obvious orphans
        elif key.endswith('_mirror') or account == 'mirror':
            # Only remove if the main account also doesn't have this position
            if symbol not in main_active_symbols:
                monitors_to_remove.append(key)
                mirror_monitors_to_remove.append(symbol)
                print(f"  🗑️ Will remove mirror monitor: {symbol} (main account has no position)")
    
    # Remove orphaned monitors
    for key in monitors_to_remove:
        del enhanced_monitors[key]
    
    print(f"\n🧹 Removed {len(monitors_to_remove)} orphaned monitors:")
    print(f"   • Main account: {len(main_monitors_to_remove)}")
    print(f"   • Mirror account: {len(mirror_monitors_to_remove)}")
    
    # Save updated data
    try:
        data['bot_data']['enhanced_tp_sl_monitors'] = enhanced_monitors
        
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        print("✅ Updated pickle file saved")
        
    except Exception as e:
        print(f"❌ Error saving updated data: {e}")
        return False
    
    # Final count
    main_count = sum(1 for k in enhanced_monitors.keys() if k.endswith('_main'))
    mirror_count = sum(1 for k in enhanced_monitors.keys() if k.endswith('_mirror'))
    
    print(f"\n📊 Final monitor count:")
    print(f"   • Main: {main_count} monitors (for {len(main_active_symbols)} positions)")
    print(f"   • Mirror: {mirror_count} monitors")
    print(f"   • Total: {len(enhanced_monitors)} monitors")
    
    # Show remaining monitors by symbol
    remaining_symbols = set()
    for key, monitor in enhanced_monitors.items():
        remaining_symbols.add(monitor.get('symbol', 'unknown'))
    
    print(f"\n📋 Remaining monitored symbols: {len(remaining_symbols)}")
    if len(remaining_symbols) <= 10:  # Show if not too many
        for symbol in sorted(remaining_symbols):
            print(f"   • {symbol}")
    
    if len(monitors_to_remove) > 0:
        print(f"\n✅ Successfully cleaned up {len(monitors_to_remove)} orphaned monitors!")
        print("   The bot should now run more efficiently.")
    else:
        print(f"\n✅ No orphaned monitors found - system is clean!")
    
    return True

if __name__ == "__main__":
    import asyncio
    asyncio.run(clean_orphaned_monitors_simple())