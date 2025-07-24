#!/usr/bin/env python3
"""
Fix the monitor account matching to prevent cross-account false positives
"""

import shutil
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_enhanced_tp_sl_manager():
    """Add proper account matching to enhanced TP/SL manager"""
    
    file_path = "execution/enhanced_tp_sl_manager.py"
    backup_path = f"{file_path}.backup_account_fix"
    
    # Create backup
    shutil.copy2(file_path, backup_path)
    logger.info(f"Created backup: {backup_path}")
    
    # Read the file
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Find the line where we check monitors
    new_lines = []
    for i, line in enumerate(lines):
        # Add the line first
        new_lines.append(line)
        
        # Look for the start of monitor checking
        if "async def _monitor_position(" in line:
            # Find the next few lines to insert our check after getting monitor_data
            j = i + 1
            while j < len(lines):
                new_lines.append(lines[j])
                if "monitor_data = self.position_monitors.get(monitor_key)" in lines[j]:
                    # Insert account check right after
                    indent = "        "  # 8 spaces based on method indentation
                    new_lines.append(f"{indent}# Ensure we're checking the right account type\n")
                    new_lines.append(f"{indent}expected_account = 'mirror' if monitor_key.endswith('_mirror') else 'main'\n")
                    new_lines.append(f"{indent}if account_type != expected_account:\n")
                    new_lines.append(f"{indent}    logger.error(f'Account type mismatch for {{monitor_key}}: expected={{expected_account}}, got={{account_type}}')\n")
                    new_lines.append(f"{indent}    return\n")
                    new_lines.append(f"{indent}\n")
                    # Skip to add rest of lines
                    for k in range(j + 1, len(lines)):
                        new_lines.append(lines[k])
                    break
                j += 1
            break
    
    # Write back
    with open(file_path, 'w') as f:
        f.writelines(new_lines)
    
    logger.info("✅ Fixed enhanced TP/SL manager with account type checking")

if __name__ == "__main__":
    fix_enhanced_tp_sl_manager()