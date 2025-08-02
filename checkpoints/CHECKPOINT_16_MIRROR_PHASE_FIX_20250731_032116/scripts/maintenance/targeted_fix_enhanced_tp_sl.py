#!/usr/bin/env python3
"""
Targeted fix for enhanced_tp_sl_manager.py - only fix the specific lines that need account-aware fetching
"""

import re

def targeted_fix():
    file_path = "execution/enhanced_tp_sl_manager.py"
    
    # Read the file
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # First, ensure the import is added
    import_added = False
    for i, line in enumerate(lines):
        if 'from clients.bybit_helpers import' in line and not import_added:
            # Check if get_position_info_for_account is already imported
            if 'get_position_info_for_account' not in line:
                # Add it to the import
                lines[i] = line.rstrip().rstrip(')') + ', get_position_info_for_account)\n'
                import_added = True
                break
    
    # Now fix specific problematic lines
    fixes_applied = 0
    
    # Fix 1: Around line 1010 - false positive verification
    for i in range(1000, min(1020, len(lines))):
        if 'fresh_positions = await get_position_info(symbol)' in lines[i]:
            indent = len(lines[i]) - len(lines[i].lstrip())
            lines[i] = ' ' * indent + '# Double-check by re-fetching position for this specific account\n'
            lines.insert(i + 1, ' ' * indent + 'if account_type == \'mirror\':\n')
            lines.insert(i + 2, ' ' * (indent + 4) + 'fresh_positions = await get_position_info_for_account(symbol, \'mirror\')\n')
            lines.insert(i + 3, ' ' * indent + 'else:\n')
            lines.insert(i + 4, ' ' * (indent + 4) + 'fresh_positions = await get_position_info(symbol)\n')
            fixes_applied += 1
            break
    
    # Fix 2: Around line 1074 - limit order fill detection
    for i in range(1060, min(1090, len(lines))):
        if 'positions = await get_position_info(symbol)' in lines[i] and 'Check if any limit orders' in ''.join(lines[max(0, i-10):i]):
            indent = len(lines[i]) - len(lines[i].lstrip())
            lines[i] = ' ' * indent + '# Get positions for the correct account\n'
            lines.insert(i + 1, ' ' * indent + 'if monitor_data.get("account_type", "main") == \'mirror\':\n')
            lines.insert(i + 2, ' ' * (indent + 4) + 'positions = await get_position_info_for_account(symbol, \'mirror\')\n')
            lines.insert(i + 3, ' ' * indent + 'else:\n')
            lines.insert(i + 4, ' ' * (indent + 4) + 'positions = await get_position_info(symbol)\n')
            fixes_applied += 1
            break
    
    # Fix 3: Around line 1735 - _handle_fast_position_change
    for i in range(1720, min(1750, len(lines))):
        if 'positions = await get_position_info(symbol)' in lines[i] and '_handle_fast_position_change' in ''.join(lines[max(0, i-20):i]):
            indent = len(lines[i]) - len(lines[i].lstrip())
            account_type_line = None
            # Look for account_type in the method parameters
            for j in range(max(0, i-20), i):
                if 'account_type' in lines[j] and 'def' in lines[j]:
                    account_type_line = j
                    break
            
            if account_type_line:
                lines[i] = ' ' * indent + '# Get positions for the correct account\n'
                lines.insert(i + 1, ' ' * indent + 'if account_type == \'mirror\':\n')
                lines.insert(i + 2, ' ' * (indent + 4) + 'positions = await get_position_info_for_account(symbol, \'mirror\')\n')
                lines.insert(i + 3, ' ' * indent + 'else:\n')
                lines.insert(i + 4, ' ' * (indent + 4) + 'positions = await get_position_info(symbol)\n')
                fixes_applied += 1
            break
    
    # Write the fixed content
    with open(file_path, 'w') as f:
        f.writelines(lines)
    
    print(f"✅ Applied {fixes_applied} targeted fixes to enhanced_tp_sl_manager.py")
    print("🎯 Key position fetches are now account-aware")

if __name__ == "__main__":
    targeted_fix()