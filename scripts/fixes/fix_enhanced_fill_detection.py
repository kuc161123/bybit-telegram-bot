#!/usr/bin/env python3
"""
Fix the enhanced fill detection error in the bot
"""

import re

def fix_enhanced_fill_detection():
    """Fix the string indices error in enhanced fill detection"""
    
    # Read the enhanced_tp_sl_manager.py file
    file_path = 'execution/enhanced_tp_sl_manager.py'
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the enhanced fill detection section
    # Look for the error-prone code
    if 'enhanced fill detection' in content:
        print("✅ Found enhanced fill detection code")
        
        # The error "string indices must be integers" usually means
        # we're trying to access a string like a dictionary
        # Let's find where this might be happening
        
        # Common patterns that cause this error:
        # 1. Trying to access result['key'] when result is a string
        # 2. Iterating over a string expecting dict items
        
        # Search for the specific function
        pattern = r'def.*enhanced.*fill.*detection.*\(.*\):|enhanced fill detection'
        matches = re.finditer(pattern, content, re.IGNORECASE)
        
        for match in matches:
            start = match.start()
            # Find the function context
            lines = content[:start].split('\n')
            line_num = len(lines)
            print(f"📍 Found enhanced fill detection reference at line {line_num}")
        
        # Create a patch to add type checking
        patch = '''
# Add this type checking to prevent string indices error
if isinstance(result, str):
    logger.debug(f"Result is string, not dict: {result[:100]}")
    return
elif not isinstance(result, dict):
    logger.debug(f"Result is unexpected type: {type(result)}")
    return
'''
        
        print("\n💡 To fix this error, we need to:")
        print("1. Add type checking before accessing dict keys")
        print("2. Ensure API responses are properly parsed")
        print("3. Handle edge cases where responses might be strings")
        
        return True
    else:
        print("❌ Could not find enhanced fill detection code")
        return False

def check_error_location():
    """Try to pinpoint where the error occurs"""
    
    print("\n🔍 Checking for potential error locations...")
    
    # Common places where this error occurs
    locations = [
        ('execution/enhanced_tp_sl_manager.py', '_check_enhanced_fills'),
        ('execution/enhanced_tp_sl_manager.py', '_detect_filled_orders'),
        ('execution/enhanced_tp_sl_manager.py', 'monitor_and_adjust_orders'),
    ]
    
    for file_path, function_name in locations:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                if function_name in content:
                    print(f"✅ Found {function_name} in {file_path}")
                    
                    # Look for dictionary access patterns
                    pattern = r"(\w+)\['[^']+'\]"
                    matches = re.findall(pattern, content)
                    
                    # Find unique variable names that are accessed like dicts
                    vars_accessed = set(matches)
                    if vars_accessed:
                        print(f"   Variables accessed as dicts: {', '.join(list(vars_accessed)[:5])}")
        except Exception as e:
            print(f"❌ Error checking {file_path}: {e}")

if __name__ == "__main__":
    print("🔧 Analyzing enhanced fill detection error...")
    fix_enhanced_fill_detection()
    check_error_location()
    
    print("\n📋 Quick fix to apply:")
    print("1. Find where the error occurs in enhanced_tp_sl_manager.py")
    print("2. Add type checking before accessing dictionary keys")
    print("3. Log the actual type when it's not a dict")
    print("\n⚡ The error likely occurs when processing order fills or API responses")