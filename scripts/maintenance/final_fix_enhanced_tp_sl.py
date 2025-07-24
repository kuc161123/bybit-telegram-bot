#!/usr/bin/env python3
"""
Final fix for enhanced_tp_sl_manager.py - properly handle all account-aware position fetching
"""

import shutil
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def final_fix():
    """Manually fix all position fetching to be account-aware"""
    
    file_path = "execution/enhanced_tp_sl_manager.py"
    backup_path = f"{file_path}.backup_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Create backup
    shutil.copy2(file_path, backup_path)
    logger.info(f"Created backup: {backup_path}")
    
    # Read the file
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Fix line by line
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Fix line 952 which has two statements on one line
        if i == 951 and 'if account_type == \'mirror\':' in line and 'positions = await' in line:
            # Split the line
            new_lines.append('            if account_type == \'mirror\':\n')
            new_lines.append('                positions = await get_position_info_for_account(symbol, \'mirror\')\n')
            i += 1
            continue
        
        # Skip duplicate account type checks
        if i > 950 and i < 970 and '# Get position for the correct account type' in line:
            # Skip the duplicate check section (lines 955-960)
            while i < len(lines) and 'logger.debug(f"🔍 Fetching MAIN position' not in lines[i]:
                i += 1
            continue
        
        new_lines.append(line)
        i += 1
    
    # Write the fixed content
    with open(file_path, 'w') as f:
        f.writelines(new_lines)
    
    logger.info("✅ Fixed enhanced_tp_sl_manager.py")
    
    # Now let's properly implement the account-aware fix throughout the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace all instances where we need account-aware fetching
    # This is a more targeted approach
    replacements = [
        # Fix for line ~1010 (false positive verification)
        ('fresh_positions = await get_position_info(symbol)\n', 
         '''if account_type == 'mirror':
                            fresh_positions = await get_position_info_for_account(symbol, 'mirror')
                        else:
                            fresh_positions = await get_position_info(symbol)
'''),
        
        # Fix for line ~1074 (limit order fill detection)
        ('positions = await get_position_info(symbol)\n',
         '''if monitor_data.get("account_type", "main") == 'mirror':
                    positions = await get_position_info_for_account(symbol, 'mirror')
                else:
                    positions = await get_position_info(symbol)
'''),
        
        # Fix for line ~1181
        ('positions = await get_position_info(monitor_data["symbol"])\n',
         '''if monitor_data.get("account_type", "main") == 'mirror':
                    positions = await get_position_info_for_account(monitor_data["symbol"], 'mirror')
                else:
                    positions = await get_position_info(monitor_data["symbol"])
'''),
    ]
    
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new, 1)  # Replace only first occurrence
            logger.info(f"✅ Applied fix for: {old.strip()}")
    
    # Write final content
    with open(file_path, 'w') as f:
        f.write(content)
    
    logger.info("\n✅ Final fix complete!")
    logger.info("🎯 All position fetches should now be account-aware")

if __name__ == "__main__":
    final_fix()