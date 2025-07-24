#!/usr/bin/env python3
"""
Check if Enhanced TP/SL monitors are properly separated between main and mirror accounts.
"""

import pickle

def analyze_monitor_structure():
    """Analyze the Enhanced TP/SL monitor structure for account confusion."""
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        print("ENHANCED TP/SL MONITORS ANALYSIS")
        print("=" * 80)
        print(f"Total monitors: {len(enhanced_monitors)}")
        print()
        
        # Categorize monitors by account type
        main_monitors = {}
        mirror_monitors = {}
        unknown_monitors = {}
        
        for key, monitor in enhanced_monitors.items():
            account_type = monitor.get('account_type', 'unknown')
            
            if '_main' in key or account_type == 'main':
                main_monitors[key] = monitor
            elif '_mirror' in key or account_type == 'mirror':
                mirror_monitors[key] = monitor
            else:
                unknown_monitors[key] = monitor
        
        # Display main account monitors
        print("MAIN ACCOUNT MONITORS:")
        print("-" * 80)
        for key, monitor in sorted(main_monitors.items()):
            print(f"\nKey: {key}")
            print(f"  Symbol: {monitor.get('symbol')}")
            print(f"  Side: {monitor.get('side')}")
            print(f"  Account Type: {monitor.get('account_type', 'NOT SET')}")
            print(f"  Position Size: {monitor.get('position_size')}")
            print(f"  Remaining Size: {monitor.get('remaining_size')}")
            print(f"  Has Mirror: {monitor.get('has_mirror', False)}")
            
            # Check for inconsistencies
            if '_mirror' in key and monitor.get('account_type') == 'main':
                print("  ⚠️ WARNING: Key contains '_mirror' but account_type is 'main'")
            if '_main' not in key and '_mirror' not in key:
                print("  ⚠️ WARNING: Key doesn't specify account type suffix")
        
        # Display mirror account monitors
        print("\n\nMIRROR ACCOUNT MONITORS:")
        print("-" * 80)
        for key, monitor in sorted(mirror_monitors.items()):
            print(f"\nKey: {key}")
            print(f"  Symbol: {monitor.get('symbol')}")
            print(f"  Side: {monitor.get('side')}")
            print(f"  Account Type: {monitor.get('account_type', 'NOT SET')}")
            print(f"  Position Size: {monitor.get('position_size')}")
            print(f"  Remaining Size: {monitor.get('remaining_size')}")
            print(f"  Has Mirror: {monitor.get('has_mirror', False)}")
            
            # Check for inconsistencies
            if '_main' in key and monitor.get('account_type') == 'mirror':
                print("  ⚠️ WARNING: Key contains '_main' but account_type is 'mirror'")
        
        # Display unknown monitors
        if unknown_monitors:
            print("\n\nUNKNOWN/PROBLEMATIC MONITORS:")
            print("-" * 80)
            for key, monitor in sorted(unknown_monitors.items()):
                print(f"\nKey: {key}")
                print(f"  Symbol: {monitor.get('symbol')}")
                print(f"  Side: {monitor.get('side')}")
                print(f"  Account Type: {monitor.get('account_type', 'NOT SET')}")
                print(f"  Position Size: {monitor.get('position_size')}")
                print(f"  Remaining Size: {monitor.get('remaining_size')}")
                print("  ⚠️ WARNING: Cannot determine account type from key or data")
        
        # Check for duplicate monitoring
        print("\n\nCHECKING FOR DUPLICATE MONITORING:")
        print("-" * 80)
        
        # Group by symbol and side
        position_monitors = {}
        for key, monitor in enhanced_monitors.items():
            symbol = monitor.get('symbol', 'UNKNOWN')
            side = monitor.get('side', 'UNKNOWN')
            pos_key = f"{symbol}_{side}"
            
            if pos_key not in position_monitors:
                position_monitors[pos_key] = []
            position_monitors[pos_key].append({
                'key': key,
                'account_type': monitor.get('account_type', 'unknown'),
                'remaining_size': monitor.get('remaining_size', 0)
            })
        
        # Check for positions with multiple monitors
        for pos_key, monitors in position_monitors.items():
            if len(monitors) > 2:  # More than main + mirror
                print(f"\n⚠️ {pos_key} has {len(monitors)} monitors:")
                for mon in monitors:
                    print(f"  - {mon['key']} ({mon['account_type']}) - remaining: {mon['remaining_size']}")
            elif len(monitors) == 2:
                # Check if it's properly main + mirror
                account_types = [m['account_type'] for m in monitors]
                if 'main' in account_types and 'mirror' in account_types:
                    print(f"✅ {pos_key} has correct main + mirror monitors")
                else:
                    print(f"⚠️ {pos_key} has 2 monitors but not main+mirror: {account_types}")
        
        # Summary
        print("\n\nSUMMARY:")
        print("-" * 80)
        print(f"Main account monitors: {len(main_monitors)}")
        print(f"Mirror account monitors: {len(mirror_monitors)}")
        print(f"Unknown/problematic monitors: {len(unknown_monitors)}")
        
        # Check for key format issues
        print("\n\nKEY FORMAT ANALYSIS:")
        print("-" * 80)
        
        legacy_format_count = 0
        new_format_count = 0
        
        for key in enhanced_monitors.keys():
            parts = key.split('_')
            if len(parts) == 2:  # Legacy format: SYMBOL_SIDE
                legacy_format_count += 1
                print(f"Legacy format: {key}")
            elif len(parts) == 3:  # New format: SYMBOL_SIDE_ACCOUNT
                new_format_count += 1
            else:
                print(f"Unexpected format: {key} ({len(parts)} parts)")
        
        print(f"\nLegacy format keys (SYMBOL_SIDE): {legacy_format_count}")
        print(f"New format keys (SYMBOL_SIDE_ACCOUNT): {new_format_count}")
        
        if legacy_format_count > 0:
            print("\n⚠️ WARNING: Found legacy format keys without account type suffix!")
            print("This could cause confusion between main and mirror monitors.")
        
        return enhanced_monitors
        
    except Exception as e:
        print(f"Error: {e}")
        return {}

if __name__ == "__main__":
    analyze_monitor_structure()