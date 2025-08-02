#!/usr/bin/env python3
"""
Patch the monitor logic to properly filter positions by account type
"""

import shutil
import logging
import re

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def patch_enhanced_tp_sl_manager():
    """Add proper account filtering to prevent cross-account false positives"""
    
    file_path = "execution/enhanced_tp_sl_manager.py"
    backup_path = f"{file_path}.backup_proper_fix"
    
    # Create backup
    shutil.copy2(file_path, backup_path)
    logger.info(f"Created backup: {backup_path}")
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the monitor_and_adjust_orders method
    method_pattern = r'async def monitor_and_adjust_orders\(self, symbol: str, side: str, account_type: str = "main"\):'
    
    if re.search(method_pattern, content):
        logger.info("Found monitor_and_adjust_orders method")
        
        # Add a check at the beginning of the method
        insert_code = '''
        # Construct the monitor key based on account type
        monitor_key = f"{symbol}_{side}_{account_type}"
        
        # Verify we have the correct monitor for this account
        if monitor_key not in self.position_monitors:
            logger.debug(f"No monitor found for {monitor_key}")
            return
            
        # Double-check account type matches
        monitor_data = self.position_monitors[monitor_key]
        if monitor_data.get('account_type') != account_type:
            logger.warning(f"Account type mismatch for {monitor_key}: monitor has {monitor_data.get('account_type')}, called with {account_type}")
            return
'''
        
        # Find where to insert (after the method definition)
        lines = content.split('\n')
        new_lines = []
        inserted = False
        
        for i, line in enumerate(lines):
            new_lines.append(line)
            
            if 'async def monitor_and_adjust_orders' in line and not inserted:
                # Find the next line that's not a docstring
                j = i + 1
                while j < len(lines) and (lines[j].strip().startswith('"""') or lines[j].strip().startswith("'''")):
                    new_lines.append(lines[j])
                    j += 1
                
                # Skip any existing docstring
                if j < len(lines) and lines[j].strip() == '"""':
                    while j < len(lines) and lines[j].strip() != '"""':
                        new_lines.append(lines[j])
                        j += 1
                    if j < len(lines):
                        new_lines.append(lines[j])  # closing """
                        j += 1
                
                # Insert our code with proper indentation
                indent = "        "  # 8 spaces for method body
                for code_line in insert_code.strip().split('\n'):
                    if code_line:
                        new_lines.append(indent + code_line)
                    else:
                        new_lines.append('')
                
                # Add remaining lines
                for k in range(j, len(lines)):
                    new_lines.append(lines[k])
                
                inserted = True
                break
        
        if inserted:
            # Write back
            with open(file_path, 'w') as f:
                f.write('\n'.join(new_lines))
            
            logger.info("✅ Patched monitor_and_adjust_orders to validate account type")
        else:
            logger.warning("Could not insert the patch")
    else:
        logger.error("Could not find monitor_and_adjust_orders method")

if __name__ == "__main__":
    patch_enhanced_tp_sl_manager()