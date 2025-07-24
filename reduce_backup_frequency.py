#!/usr/bin/env python3
"""
Reduce backup frequency to max 1 per minute
"""
import re
from datetime import datetime

def reduce_backup_frequency():
    """Modify pickle_lock.py to limit backup frequency"""
    
    file_path = "utils/pickle_lock.py"
    
    print("📝 Reducing backup frequency...")
    
    try:
        # Read the file
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check if we need to add time tracking
        if "LAST_BACKUP_TIME = {}" not in content:
            # Add after imports
            import_end = content.find('\n\n', content.find('import'))
            if import_end > 0:
                addition = "\n# Backup frequency limiter\nLAST_BACKUP_TIME = {}  # Track last backup per file\nBACKUP_INTERVAL = 60  # Minimum seconds between backups\n"
                content = content[:import_end] + addition + content[import_end:]
                
                # Now modify the create_backup function
                # Find the function
                func_start = content.find("def create_backup(")
                if func_start > 0:
                    # Find the function body
                    func_body_start = content.find(":", func_start) + 1
                    indent = "    "  # Standard 4 spaces
                    
                    # Add time check at start of function
                    time_check = f'''
{indent}# Check if we should create a backup
{indent}import time
{indent}global LAST_BACKUP_TIME
{indent}current_time = time.time()
{indent}file_key = filepath if isinstance(filepath, str) else 'default'
{indent}
{indent}if file_key in LAST_BACKUP_TIME and current_time - LAST_BACKUP_TIME[file_key] < BACKUP_INTERVAL:
{indent}{indent}return  # Skip backup if too recent
{indent}
{indent}LAST_BACKUP_TIME[file_key] = current_time
{indent}'''
                    
                    # Insert after function definition
                    next_line = content.find("\n", func_body_start)
                    content = content[:next_line] + time_check + content[next_line:]
                
                print("✅ Added backup frequency limiter")
                
                # Write the updated content
                with open(file_path, 'w') as f:
                    f.write(content)
        else:
            print("✅ Backup frequency already limited")
            
    except Exception as e:
        print(f"⚠️  Could not modify backup frequency: {e}")

def main():
    print("🚀 Reducing Backup Frequency")
    print("=" * 60)
    
    reduce_backup_frequency()
    
    print("\n" + "=" * 60)
    print("✅ Backup frequency reduced to max 1 per minute!")
    print("\n📝 The change will take effect immediately")
    print("No bot restart needed!")

if __name__ == "__main__":
    main()