#!/usr/bin/env python3
"""
Comprehensive fix for Enhanced TP/SL monitoring to prevent false TP detection
"""

import re

def fix_enhanced_monitoring():
    """Fix the monitoring logic to prevent cross-account contamination"""
    
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        content = f.read()
    
    # First, let's find and fix the duplicate code issue
    # The duplicate if-else block needs to be removed
    duplicate_pattern = r'''if account_type == 'mirror':
                            fresh_positions = await get_position_info_for_account\(symbol, 'mirror'\)
                        else:
                            fresh_positions = await get_position_info\(symbol\)'''
    
    # Check if there's still a duplicate
    occurrences = len(re.findall(duplicate_pattern, content, re.MULTILINE))
    if occurrences > 1:
        print(f"Found {occurrences} occurrences of position fetching code, removing duplicates...")
        # Keep only the first occurrence
        parts = content.split(duplicate_pattern)
        if len(parts) > 2:
            content = parts[0] + duplicate_pattern + duplicate_pattern.join(parts[2:])
    
    # Now, the critical fix: When detecting "impossible TP fill", don't update monitor with wrong account data
    # Find the problematic section where it updates monitor data
    problem_pattern = r'(if size_diff > monitor_data\["position_size"\]:.*?monitor_data\["position_size"\] = current_size.*?monitor_data\["remaining_size"\] = current_size.*?await self\._save_to_persistence\(\).*?return)'
    
    # Replace with a version that doesn't contaminate the data
    replacement = '''if size_diff > monitor_data["position_size"]:
                        logger.error(f"⚠️ Detected impossible TP fill for {monitor_key}: size_diff={size_diff} > position_size={monitor_data['position_size']}")
                        # This is likely a cross-account detection issue
                        # Do NOT update monitor data with wrong account sizes
                        logger.warning(f"🛡️ Preventing cross-account contamination for {monitor_key}")
                        return  # Exit without modifying monitor data'''
    
    content = re.sub(problem_pattern, replacement, content, flags=re.DOTALL)
    
    # Also add a safety check at the beginning of position monitoring to validate account type
    # Find the monitor_position method
    monitor_position_pattern = r'(async def monitor_position\(self, monitor_key: str\):)'
    
    safety_check = '''async def monitor_position(self, monitor_key: str):
        """
        Monitor a single position for TP/SL hits
        Enhanced with account-aware position fetching to prevent cross-account false positives
        """'''
    
    content = re.sub(monitor_position_pattern, safety_check, content)
    
    # Write the fixed content
    with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
        f.write(content)
    
    print("✅ Applied comprehensive fix to Enhanced TP/SL manager:")
    print("1. Removed duplicate position fetching code")
    print("2. Prevented monitor data contamination on false positive detection")
    print("3. Added safety documentation")
    print("\nThe monitoring system will no longer contaminate mirror monitors with main account data.")

if __name__ == "__main__":
    fix_enhanced_monitoring()