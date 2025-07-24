#!/usr/bin/env python3
"""
Add validation to prevent legacy monitor creation
"""
import re

# Read the enhanced_tp_sl_manager.py file
with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
    content = f.read()

# Add validation method
validation_method = '''
    def _validate_monitor_key(self, monitor_key: str) -> bool:
        """Validate that monitor key uses proper account-aware format"""
        # Monitor key must end with _main or _mirror
        if not (monitor_key.endswith('_main') or monitor_key.endswith('_mirror')):
            logger.warning(f"⚠️ Rejecting legacy monitor key format: {monitor_key}")
            return False
        return True
'''

# Find a good place to insert the validation method (after __init__)
init_pattern = r'(def __init__\(self.*?\n\s+""".*?""".*?\n.*?self\.position_monitors = \{\}.*?\n)'
match = re.search(init_pattern, content, re.DOTALL)

if match:
    # Insert the validation method after the init
    insert_pos = match.end()
    content = content[:insert_pos] + validation_method + '\n' + content[insert_pos:]
    print("✅ Added validation method")
else:
    print("❌ Could not find insertion point for validation method")

# Now add validation checks wherever monitors are added
# Pattern to find where monitors are added to position_monitors
monitor_add_pattern = r'(self\.position_monitors\[([^]]+)\] = )'

replacements = 0
for match in re.finditer(monitor_add_pattern, content):
    key_var = match.group(2)
    # Check if this line already has validation
    start_of_line = content.rfind('\n', 0, match.start()) + 1
    line = content[start_of_line:match.start()]
    
    # Skip if validation already exists
    if '_validate_monitor_key' in line:
        continue
    
    # Add validation before the assignment
    indent = len(line) - len(line.lstrip())
    validation_line = ' ' * indent + f'if not self._validate_monitor_key({key_var}): continue\n'
    
    # Insert validation
    content = content[:start_of_line] + validation_line + content[start_of_line:]
    replacements += 1

print(f"✅ Added {replacements} validation checks")

# Save the updated file
with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
    f.write(content)

print("✅ Updated enhanced_tp_sl_manager.py with monitor key validation")