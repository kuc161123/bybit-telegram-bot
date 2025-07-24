#!/usr/bin/env python3
"""Fix all imports to use analytics versions"""

import os
import re

def fix_imports_in_file(filepath):
    """Fix imports in a single file"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Track if changes were made
    original_content = content
    
    # Fix various import patterns
    replacements = [
        # Dashboard imports
        (r'from dashboard\.generator_enhanced import', 'from dashboard.generator_analytics_compact import'),
        (r'from dashboard\.generator import', 'from dashboard.generator_analytics_compact import'),
        (r'from dashboard\.keyboards import', 'from dashboard.keyboards_analytics import'),
        (r'from dashboard\.keyboards_v2 import', 'from dashboard.keyboards_analytics import'),
        
        # Handle specific function imports
        (r'build_mobile_dashboard_text as build_dashboard_text_async', 'build_mobile_dashboard_text as build_dashboard_text_async'),
        (r'fetch_all_trades_status, generate_comprehensive_help', '# Removed old imports'),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    # Write back if changed
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Fixed imports in: {filepath}")
        return True
    return False

def main():
    """Fix all Python files with old imports"""
    files_to_fix = [
        'handlers/callbacks.py',
        'handlers/callbacks_enhanced.py',
        'handlers/ai_handlers.py',
        'handlers/analytics_callbacks.py',
        'handlers/test_dashboard.py',
        'test_ultra_dashboard.py',
    ]
    
    fixed_count = 0
    for filepath in files_to_fix:
        full_path = f'/Users/lualakol/bybit-telegram-bot/{filepath}'
        if os.path.exists(full_path):
            if fix_imports_in_file(full_path):
                fixed_count += 1
        else:
            print(f"File not found: {full_path}")
    
    print(f"\nFixed {fixed_count} files")

if __name__ == "__main__":
    main()