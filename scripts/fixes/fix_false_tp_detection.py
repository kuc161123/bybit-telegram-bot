#!/usr/bin/env python3
"""
Fix the false TP detection by updating the monitoring logic
"""

import os
import shutil
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_enhanced_tp_sl_manager():
    """Update the enhanced TP/SL manager to prevent false positives"""
    
    file_path = "execution/enhanced_tp_sl_manager.py"
    backup_path = f"{file_path}.backup_false_tp_fix"
    
    # Create backup
    shutil.copy2(file_path, backup_path)
    logger.info(f"Created backup: {backup_path}")
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the section that checks for position reduction
    search_text = """# Enhanced false positive detection:
                    # If reduction is exactly ~66%, it's likely a cross-account false positive"""
    
    replacement_text = """# Enhanced false positive detection:
                    # Skip mirror monitors entirely when checking main positions
                    if monitor_key.endswith('_mirror') and position.get('accountType') != 'mirror':
                        logger.debug(f"Skipping {monitor_key} - mirror monitor vs main position")
                        continue
                    if monitor_key.endswith('_main') and position.get('accountType') == 'mirror':
                        logger.debug(f"Skipping {monitor_key} - main monitor vs mirror position")
                        continue"""
    
    # Replace the content
    if search_text in content:
        content = content.replace(search_text, replacement_text)
        
        # Write back
        with open(file_path, 'w') as f:
            f.write(content)
        
        logger.info("✅ Fixed enhanced TP/SL manager to prevent cross-account false positives")
    else:
        logger.warning("Could not find the target text to replace")
        logger.info("Will search for alternative pattern...")
        
        # Alternative fix - find where positions are checked
        alt_search = "for position in positions:"
        if alt_search in content:
            # Insert account type check right after the for loop
            lines = content.split('\n')
            new_lines = []
            for i, line in enumerate(lines):
                new_lines.append(line)
                if alt_search in line and i < len(lines) - 1:
                    # Get indentation of next line
                    next_line = lines[i + 1]
                    indent = len(next_line) - len(next_line.lstrip())
                    
                    # Insert our check
                    new_lines.append(' ' * indent + "# Skip cross-account comparisons")
                    new_lines.append(' ' * indent + "position_account = 'mirror' if position.get('accountType') == 'mirror' else 'main'")
                    new_lines.append(' ' * indent + "monitor_account = 'mirror' if monitor_key.endswith('_mirror') else 'main'")
                    new_lines.append(' ' * indent + "if position_account != monitor_account:")
                    new_lines.append(' ' * (indent + 4) + "continue")
                    new_lines.append(' ' * indent + "")
            
            content = '\n'.join(new_lines)
            with open(file_path, 'w') as f:
                f.write(content)
            
            logger.info("✅ Applied alternative fix to enhanced TP/SL manager")

if __name__ == "__main__":
    fix_enhanced_tp_sl_manager()