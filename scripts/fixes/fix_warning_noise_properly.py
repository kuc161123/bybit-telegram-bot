#!/usr/bin/env python3
"""
Fix warning noise by adding once-per-session warning logic
"""

import re

def fix_warning_noise():
    """Apply the warning noise reduction fix properly"""
    
    # Read the file
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        content = f.read()
    
    # First, add the warned_positions set to __init__
    # Find the __init__ method and add it after other instance variables
    init_pattern = r'(self\.mirror_sync_locks = \{\}.*?\n)'
    init_replacement = r'\1        # Track positions that have shown cross-account warnings\n        self.warned_positions = set()\n'
    
    content = re.sub(init_pattern, init_replacement, content, flags=re.DOTALL)
    
    # Now fix the error logging section
    # Look for the specific error log line
    error_line = 'logger.error(f"⚠️ Detected impossible TP fill for {monitor_key}: size_diff={size_diff} > position_size={monitor_data[\'position_size\']}")'
    
    # Replace with conditional logging
    error_replacement = '''if monitor_key not in self.warned_positions:
                            self.warned_positions.add(monitor_key)
                            logger.error(f"⚠️ Detected impossible TP fill for {monitor_key}: size_diff={size_diff} > position_size={monitor_data['position_size']}")
                        else:
                            logger.debug(f"Known impossible fill for {monitor_key}: size_diff={size_diff}")'''
    
    content = content.replace(error_line, error_replacement)
    
    # Fix the warning logging section
    warning_line = 'logger.warning(f"🛡️ Preventing cross-account contamination for {monitor_key}")'
    
    warning_replacement = '''if monitor_key not in self.warned_positions:
                            self.warned_positions.add(monitor_key)
                            logger.warning(f"🛡️ Preventing cross-account contamination for {monitor_key}")
                        else:
                            logger.debug(f"🛡️ Contamination prevention active for {monitor_key}")'''
    
    content = content.replace(warning_line, warning_replacement)
    
    # Also fix the 66% detection warning if it exists
    if "Suspicious reduction detected" in content:
        suspicious_line = 'logger.warning(f"⚠️ Suspicious reduction detected for {monitor_key}: {diff_percentage:.2f}% - possible cross-account detection")'
        suspicious_replacement = '''if monitor_key not in self.warned_positions:
                            self.warned_positions.add(monitor_key)
                            logger.warning(f"⚠️ Suspicious reduction detected for {monitor_key}: {diff_percentage:.2f}% - possible cross-account detection")
                        else:
                            logger.debug(f"Known false positive for {monitor_key}: {diff_percentage:.2f}% reduction")'''
        content = content.replace(suspicious_line, suspicious_replacement)
    
    # Write the fixed content
    with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
        f.write(content)
    
    print("✅ Applied warning noise reduction fix:")
    print("1. Added self.warned_positions set to track warned positions")
    print("2. Modified error logging to show only once per position")
    print("3. Modified warning logging to show only once per position")
    print("4. Subsequent occurrences use DEBUG level")
    print("\nRestart the bot for changes to take effect.")

if __name__ == "__main__":
    fix_warning_noise()