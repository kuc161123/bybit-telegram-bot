#!/usr/bin/env python3
"""
Clean fix for enhanced_tp_sl_manager.py - remove duplicates and fix logic
"""

import re

def clean_fix():
    file_path = "execution/enhanced_tp_sl_manager.py"
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Remove the duplicate import inside methods
    content = re.sub(r'\s+from clients\.bybit_helpers import get_position_info_for_account\n', '', content)
    
    # Now let's create a simple replacement script to fix each problematic section
    # We'll replace the pattern of duplicate checks with clean logic
    
    # Pattern to find duplicate account type checks
    pattern = r'if account_type == \'mirror\':\s*\n\s*positions = await get_position_info_for_account\(([^,]+), \'mirror\'\)\s*\n\s*logger\.debug\([^)]+\)\s*\n\s*else:\s*\n\s*# Get position for the correct account type\s*\n\s*if [^:]+:\s*\n\s*positions = await get_position_info_for_account\([^)]+\)\s*\n\s*else:\s*\n\s*positions = await get_position_info\([^)]+\)'
    
    # Simple replacement
    def replace_duplicate(match):
        return """if account_type == 'mirror':
                positions = await get_position_info_for_account(symbol, 'mirror')
                logger.debug(f"🔍 Fetching MIRROR position for {symbol} {side}")
            else:
                positions = await get_position_info(symbol)
                logger.debug(f"🔍 Fetching MAIN position for {symbol} {side}")"""
    
    # Apply the fix
    content = re.sub(pattern, replace_duplicate, content, flags=re.MULTILINE | re.DOTALL)
    
    # Write back
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("✅ Cleaned up enhanced_tp_sl_manager.py")

if __name__ == "__main__":
    clean_fix()