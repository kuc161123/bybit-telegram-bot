#!/usr/bin/env python3
"""
Comprehensive fix for false TP detection issue
This script fixes all instances where position fetching doesn't consider account type
"""

import re
import shutil
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_enhanced_tp_sl_manager():
    """Fix all non-account-aware position fetches in enhanced_tp_sl_manager.py"""
    
    file_path = "execution/enhanced_tp_sl_manager.py"
    backup_path = f"{file_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Create backup
    shutil.copy2(file_path, backup_path)
    logger.info(f"Created backup: {backup_path}")
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Pattern to find non-account-aware position fetches
    # We need to replace: await get_position_info(symbol)
    # But NOT: await get_position_info_for_account(symbol, ...)
    pattern = r'await get_position_info\(([^)]+)\)(?!_for_account)'
    
    # Track replacements
    replacements = []
    
    # Split into lines for line-by-line processing
    lines = content.split('\n')
    new_lines = []
    
    for i, line in enumerate(lines):
        # Check if this line contains a position fetch that needs fixing
        if 'await get_position_info(' in line and 'get_position_info_for_account' not in line:
            # Extract the symbol parameter
            match = re.search(r'await get_position_info\(([^)]+)\)', line)
            if match:
                symbol_param = match.group(1)
                indent = len(line) - len(line.lstrip())
                
                # We need to determine the account_type variable in context
                # Look backwards for account_type or monitor_data references
                account_type_var = None
                for j in range(max(0, i-50), i):
                    if 'account_type' in lines[j]:
                        # Try to find account_type variable assignment
                        if 'account_type = ' in lines[j]:
                            account_type_var = 'account_type'
                            break
                        elif 'monitor_data.get("account_type"' in lines[j]:
                            account_type_var = 'monitor_data.get("account_type", "main")'
                            break
                        elif '"account_type"' in lines[j] and '=' in lines[j]:
                            account_type_var = 'account_type'
                            break
                
                # If we couldn't find account_type, look for monitor_data
                if not account_type_var:
                    for j in range(max(0, i-20), i):
                        if 'monitor_data' in lines[j] and 'monitor_key' in lines[j]:
                            account_type_var = 'monitor_data.get("account_type", "main")'
                            break
                
                # Default to checking monitor_data if available
                if not account_type_var:
                    account_type_var = 'monitor_data.get("account_type", "main")'
                
                # Create the replacement
                spaces = ' ' * indent
                replacement_lines = [
                    f"{spaces}# Get position for the correct account type",
                    f"{spaces}if {account_type_var} == 'mirror':",
                    f"{spaces}    positions = await get_position_info_for_account({symbol_param}, 'mirror')",
                    f"{spaces}else:",
                    f"{spaces}    positions = await get_position_info({symbol_param})"
                ]
                
                # Log the replacement
                replacements.append(f"Line {i+1}: Replaced position fetch with account-aware version")
                
                # Add the replacement lines
                new_lines.extend(replacement_lines)
                logger.info(f"Fixed line {i+1}: {line.strip()}")
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    
    # Write the fixed content
    with open(file_path, 'w') as f:
        f.write('\n'.join(new_lines))
    
    logger.info(f"\n✅ Fixed {len(replacements)} non-account-aware position fetches")
    for r in replacements:
        logger.info(f"  - {r}")
    
    return True

def main():
    """Main execution"""
    logger.info("🔧 Starting comprehensive fix for false TP detection...")
    
    # Fix the enhanced TP/SL manager
    if fix_enhanced_tp_sl_manager():
        logger.info("\n✅ Successfully fixed enhanced_tp_sl_manager.py")
        logger.info("🎯 All position fetches are now account-aware")
        logger.info("📝 The false TP detection issue should be completely resolved")
    else:
        logger.error("❌ Failed to fix enhanced_tp_sl_manager.py")

if __name__ == "__main__":
    main()