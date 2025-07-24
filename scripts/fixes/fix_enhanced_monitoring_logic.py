#!/usr/bin/env python3
"""
Fix the Enhanced TP/SL monitoring logic to properly handle mirror accounts
"""

import re

def fix_monitoring_logic():
    """Fix the duplicate code and ensure proper account-aware position fetching"""
    
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        content = f.read()
    
    # Find the problematic section with duplicate code
    # Lines 1007-1014 have duplicate if/else blocks
    pattern = r'(if account_type == \'mirror\':\s+fresh_positions = await get_position_info_for_account\(symbol, \'mirror\'\)\s+else:\s+# Double-check by re-fetching position for this specific account\s+if account_type == \'mirror\':\s+fresh_positions = await get_position_info_for_account\(symbol, \'mirror\'\)\s+else:\s+fresh_positions = await get_position_info\(symbol\))'
    
    replacement = '''if account_type == 'mirror':
                            fresh_positions = await get_position_info_for_account(symbol, 'mirror')
                        else:
                            fresh_positions = await get_position_info(symbol)'''
    
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Also fix the position fetching at the beginning of monitor_position
    # Make sure it uses account_type properly
    
    # Find where positions are initially fetched
    pattern2 = r'positions = await get_position_info\(symbol\)'
    
    # Check if this needs to be account-aware
    if 'positions = await get_position_info(symbol)' in content:
        # Find the context to ensure we're in the right place
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'positions = await get_position_info(symbol)' in line:
                # Look for account_type in nearby lines
                context_start = max(0, i - 20)
                context_end = min(len(lines), i + 5)
                context = '\n'.join(lines[context_start:context_end])
                
                if 'account_type = monitor_data.get("account_type", "main")' in context:
                    # Replace with account-aware fetching
                    lines[i] = line.replace(
                        'positions = await get_position_info(symbol)',
                        'positions = await get_position_info_for_account(symbol, account_type)'
                    )
        
        content = '\n'.join(lines)
    
    # Write the fixed content
    with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
        f.write(content)
    
    print("✅ Fixed Enhanced TP/SL monitoring logic:")
    print("1. Removed duplicate if/else blocks")
    print("2. Ensured account-aware position fetching")
    print("\nThe monitoring system will now properly fetch positions for the correct account.")

if __name__ == "__main__":
    fix_monitoring_logic()