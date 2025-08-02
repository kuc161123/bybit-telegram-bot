#!/usr/bin/env python3
"""
Reduce false TP detection warning noise by implementing once-per-session logging
"""

import re

def reduce_warning_noise():
    """Modify enhanced_tp_sl_manager.py to log warnings only once per position"""
    
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        content = f.read()
    
    # First, add a class variable to track warned positions
    class_init_pattern = r'(class EnhancedTPSLManager:.*?def __init__\(self[^)]*\):)'
    
    class_init_replacement = r'\1\n        # Track positions that have shown cross-account warnings\n        self.warned_positions = set()'
    
    content = re.sub(class_init_pattern, class_init_replacement, content, flags=re.DOTALL)
    
    # Now modify the warning section to check if we've already warned
    warning_section = r'(# If reduction is exactly ~66%, it\'s likely a cross-account false positive\s*if 65 <= diff_percentage <= 68:)'
    
    warning_replacement = '''# If reduction is exactly ~66%, it's likely a cross-account false positive
                    if 65 <= diff_percentage <= 68:
                        # Only warn once per position per session
                        if monitor_key not in self.warned_positions:
                            self.warned_positions.add(monitor_key)'''
    
    content = re.sub(warning_section, warning_replacement, content)
    
    # Update the warning logging to check if already warned
    warning_log_pattern = r'(logger\.warning\(f"⚠️ Suspicious reduction detected for {monitor_key}:.*?\))'
    
    warning_log_replacement = '''if monitor_key not in self.warned_positions:
                            logger.warning(f"⚠️ Suspicious reduction detected for {monitor_key}: {diff_percentage:.2f}% - possible cross-account detection")
                        else:
                            logger.debug(f"Known false positive for {monitor_key}: {diff_percentage:.2f}% reduction")'''
    
    content = re.sub(warning_log_pattern, warning_log_replacement, content)
    
    # Also update the error logging
    error_pattern = r'(logger\.error\(f"⚠️ Detected impossible TP fill for {monitor_key}:.*?\))'
    
    error_replacement = '''if monitor_key not in self.warned_positions:
                        logger.error(f"⚠️ Detected impossible TP fill for {monitor_key}: size_diff={size_diff} > position_size={monitor_data['position_size']}")
                    else:
                        logger.debug(f"Known impossible fill for {monitor_key}: size_diff={size_diff}")'''
    
    content = re.sub(error_pattern, error_replacement, content)
    
    # Update the contamination warning to also check
    contamination_pattern = r'(logger\.warning\(f"🛡️ Preventing cross-account contamination for {monitor_key}"\))'
    
    contamination_replacement = '''if monitor_key not in self.warned_positions:
                        logger.warning(f"🛡️ Preventing cross-account contamination for {monitor_key}")
                    else:
                        logger.debug(f"🛡️ Contamination prevention active for {monitor_key}")'''
    
    content = re.sub(contamination_pattern, contamination_replacement, content)
    
    # Write the modified content
    with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
        f.write(content)
    
    print("✅ Modified Enhanced TP/SL manager to reduce warning noise:")
    print("1. Added warned_positions set to track positions")
    print("2. Warnings now shown only once per position per session")
    print("3. Subsequent occurrences use DEBUG level logging")
    print("\nThe bot will now be much quieter about known false positives.")

if __name__ == "__main__":
    reduce_warning_noise()