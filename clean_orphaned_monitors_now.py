#!/usr/bin/env python3
"""
Clean orphaned monitors that don't have active positions
"""
import pickle
import time
from clients.bybit_helpers import bybit_client
from execution.mirror_trader import bybit_client_2

def clean_orphaned_monitors():
    """Remove monitors for positions that no longer exist"""
    
    # Backup first
    import shutil
    backup_name = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_before_cleanup_{int(time.time())}'
    shutil.copy2('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_name)
    print(f"✅ Created backup: {backup_name}")
    
    # Get actual positions
    print("\nGetting actual positions from exchange...")
    
    # Main account
    main_positions = bybit_client.get_positions(category='linear', settleCoin='USDT')
    main_active_symbols = set()
    
    if main_positions['retCode'] == 0:
        for pos in main_positions['result']['list']:
            if float(pos.get('size', 0)) > 0:
                main_active_symbols.add(pos['symbol'])
    
    print(f"Main account has {len(main_active_symbols)} active positions")
    
    # Mirror account
    mirror_positions = bybit_client_2.get_positions(category='linear', settleCoin='USDT')
    mirror_active_symbols = set()
    
    if mirror_positions['retCode'] == 0:
        for pos in mirror_positions['result']['list']:
            if float(pos.get('size', 0)) > 0:
                mirror_active_symbols.add(pos['symbol'])
    
    print(f"Mirror account has {len(mirror_active_symbols)} active positions")
    
    # Load pickle data
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    print(f"\nCurrent monitors: {len(enhanced_monitors)}")
    
    # Find monitors to remove
    monitors_to_remove = []
    
    for key, monitor in enhanced_monitors.items():
        symbol = monitor['symbol']
        
        if key.endswith('_main') and symbol not in main_active_symbols:
            monitors_to_remove.append(key)
            print(f"  Will remove main monitor: {symbol}")
        elif key.endswith('_mirror') and symbol not in mirror_active_symbols:
            monitors_to_remove.append(key)
            print(f"  Will remove mirror monitor: {symbol}")
    
    # Remove orphaned monitors
    for key in monitors_to_remove:
        del enhanced_monitors[key]
    
    print(f"\nRemoved {len(monitors_to_remove)} orphaned monitors")
    
    # Save updated data
    data['bot_data']['enhanced_tp_sl_monitors'] = enhanced_monitors
    
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    # Final count
    main_count = sum(1 for k in enhanced_monitors.keys() if k.endswith('_main'))
    mirror_count = sum(1 for k in enhanced_monitors.keys() if k.endswith('_mirror'))
    
    print(f"\nFinal monitor count:")
    print(f"  Main: {main_count} (should be {len(main_active_symbols)})")
    print(f"  Mirror: {mirror_count} (should be {len(mirror_active_symbols)})")
    print(f"  Total: {len(enhanced_monitors)} (should be {len(main_active_symbols) + len(mirror_active_symbols)})")
    
    if main_count == len(main_active_symbols) and mirror_count == len(mirror_active_symbols):
        print("\n✅ All monitors now match actual positions!")
    else:
        print("\n⚠️  Monitor count still doesn't match positions")

if __name__ == "__main__":
    clean_orphaned_monitors()