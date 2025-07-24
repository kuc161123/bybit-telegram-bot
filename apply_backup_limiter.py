#!/usr/bin/env python3
"""
Apply backup frequency limiter to all files that create backups
"""
import os
import re
import glob

def find_and_patch_backup_creation():
    """Find all files creating backups and patch them"""
    print("🔍 Finding all backup creation code...")
    
    # Common patterns for backup creation
    patterns_to_find = [
        r"backup.*=.*f['\"].*backup.*['\"]",
        r"shutil\.copy.*backup",
        r"logger\.info.*Created backup",
        r"print.*Created backup"
    ]
    
    files_to_patch = set()
    
    # Search Python files
    for py_file in glob.glob("**/*.py", recursive=True):
        if 'venv' in py_file or '__pycache__' in py_file or '.backup' in py_file:
            continue
            
        try:
            with open(py_file, 'r') as f:
                content = f.read()
                
            for pattern in patterns_to_find:
                if re.search(pattern, content, re.IGNORECASE):
                    files_to_patch.add(py_file)
                    break
        except:
            pass
    
    print(f"\n📋 Found {len(files_to_patch)} files with backup code:")
    for f in sorted(files_to_patch):
        print(f"   - {f}")
    
    # Patch each file
    patched = 0
    for file_path in files_to_patch:
        if patch_file(file_path):
            patched += 1
    
    print(f"\n✅ Patched {patched} files")

def patch_file(file_path):
    """Patch a single file to add backup limiting"""
    print(f"\n🔧 Patching {file_path}...")
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Skip if already has our limiter
        if "should_create_backup" in content or "LAST_BACKUP_TIME" in content:
            print("   ✓ Already has backup limiting")
            return False
        
        modified = False
        
        # Find lines that create backups
        lines = content.split('\n')
        new_lines = []
        
        # Add import at top if needed
        added_import = False
        
        for i, line in enumerate(lines):
            # Add our import after other imports
            if not added_import and line.strip() and not line.startswith('import') and not line.startswith('from'):
                if i > 10:  # We're past the import section
                    new_lines.append("from utils import should_create_backup")
                    new_lines.append("")
                    added_import = True
            
            # Check if this line creates a backup
            if re.search(r"backup.*=.*['\"].*backup.*['\"]", line) or "shutil.copy" in line and "backup" in line:
                # Get indentation
                indent = len(line) - len(line.lstrip())
                indent_str = " " * indent
                
                # Add check before backup
                new_lines.append(f"{indent_str}# Check if backup is needed")
                new_lines.append(f"{indent_str}if should_create_backup('{file_path}'):")
                new_lines.append(f"    {line}")  # Add extra indent
                modified = True
            else:
                new_lines.append(line)
        
        if modified:
            # Save patched file
            with open(file_path, 'w') as f:
                f.write('\n'.join(new_lines))
            print("   ✅ Patched successfully")
            return True
        else:
            print("   ℹ️  No backup creation found")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def create_global_limiter():
    """Ensure the global limiter exists in utils/__init__.py"""
    print("\n🔧 Ensuring global backup limiter exists...")
    
    init_file = "utils/__init__.py"
    
    try:
        if os.path.exists(init_file):
            with open(init_file, 'r') as f:
                content = f.read()
        else:
            content = ""
        
        if "should_create_backup" not in content:
            # Add the limiter
            limiter_code = '''

# Global backup frequency limiter
import time
import os

_BACKUP_TIMES = {}
_BACKUP_INTERVAL = 300  # 5 minutes

def should_create_backup(filepath: str = "main") -> bool:
    """Check if enough time has passed to create a backup"""
    global _BACKUP_TIMES, _BACKUP_INTERVAL
    current_time = time.time()
    
    if filepath in _BACKUP_TIMES:
        if current_time - _BACKUP_TIMES[filepath] < _BACKUP_INTERVAL:
            return False
    
    _BACKUP_TIMES[filepath] = current_time
    return True
'''
            
            with open(init_file, 'w') as f:
                f.write(content + limiter_code)
            
            print("✅ Added global backup limiter")
        else:
            print("✅ Global limiter already exists")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    print("🚀 Applying Backup Frequency Limiter")
    print("=" * 60)
    
    # First ensure we have the global limiter
    create_global_limiter()
    
    # Then patch all files
    find_and_patch_backup_creation()
    
    print("\n" + "=" * 60)
    print("✅ Backup limiting applied!")
    print("\n📝 Changes will take effect after restarting the bot")
    print("⏰ Backups now limited to once every 5 minutes per file")

if __name__ == "__main__":
    main()