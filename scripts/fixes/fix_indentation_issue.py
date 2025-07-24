#!/usr/bin/env python3
"""
Fix the indentation issue in enhanced_tp_sl_manager.py
"""

import re

# Read the file
with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
    lines = f.readlines()

# Find the problematic section and fix indentation
in_fix_block = False
fixed_lines = []
indent_level = None

for i, line in enumerate(lines):
    if 'if last_processed_size != current_size:' in line:
        in_fix_block = True
        indent_level = len(line) - len(line.lstrip()) + 4  # Get proper indent level
        fixed_lines.append(line)
    elif in_fix_block and line.strip() and not line.strip().startswith('#'):
        # Check if we've reached the end of the block
        if 'elif current_size >' in line:
            in_fix_block = False
            fixed_lines.append(line)
        else:
            # Add proper indentation
            current_indent = len(line) - len(line.lstrip())
            if current_indent < indent_level:
                # This line needs more indentation
                fixed_lines.append(' ' * indent_level + line.lstrip())
            else:
                fixed_lines.append(line)
    else:
        fixed_lines.append(line)

# Write back
with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
    f.writelines(fixed_lines)

print("✅ Fixed indentation issue")