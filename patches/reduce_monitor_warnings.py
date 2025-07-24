#!/usr/bin/env python3
"""
Patch to reduce frequency of "No monitors found" warnings
"""

import os
import sys

def apply_patch():
    """Apply patch to reduce monitor warning frequency"""
    
    # Read the background_tasks.py file
    file_path = "helpers/background_tasks.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace the warning message with less frequent logging
    old_code = '''else:
                        logger.warning("🔍 No persisted monitors found")'''
    
    new_code = '''else:
                        # Only log this warning once every 5 minutes to reduce spam
                        if not hasattr(enhanced_tp_sl_monitoring_loop, '_last_no_persist_log'):
                            enhanced_tp_sl_monitoring_loop._last_no_persist_log = 0
                        
                        import time
                        current_time = time.time()
                        if current_time - enhanced_tp_sl_monitoring_loop._last_no_persist_log > 300:  # 5 minutes
                            logger.warning("🔍 No persisted monitors found")
                            enhanced_tp_sl_monitoring_loop._last_no_persist_log = current_time'''
    
    if old_code in content:
        content = content.replace(old_code, new_code)
        
        # Write back
        with open(file_path, 'w') as f:
            f.write(content)
        
        print("✅ Patched background_tasks.py to reduce monitor warning frequency")
        return True
    else:
        print("⚠️ Could not find target code to patch in background_tasks.py")
        return False

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    apply_patch()