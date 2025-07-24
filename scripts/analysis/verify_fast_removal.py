#!/usr/bin/env python3
"""Verify that fast approach has been completely removed"""

import os
import re

def verify_removal():
    issues = []
    
    for root, dirs, files in os.walk('.'):
        # Skip certain directories
        if any(skip in root for skip in ['.git', '__pycache__', 'backup_before_fast_removal', 'venv']):
            continue
            
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r') as f:
                        content = f.read()
                        lines = content.split('\n')
                    
                    for i, line in enumerate(lines):
                        # Skip comments and disabled code
                        if line.strip().startswith('#'):
                            continue
                            
                        # Check for fast approach references
                        if re.search(r'approach.*=.*["\']fast["\']', line, re.IGNORECASE):
                            issues.append(f"{filepath}:{i+1} - {line.strip()}")
                        elif 'APPROACH_SELECTION' in line and 'range' in line:
                            issues.append(f"{filepath}:{i+1} - {line.strip()}")
                        elif "'fast'" in line and 'approach' in line.lower():
                            issues.append(f"{filepath}:{i+1} - {line.strip()}")
                        elif '"fast"' in line and 'approach' in line.lower():
                            issues.append(f"{filepath}:{i+1} - {line.strip()}")
                            
                except Exception as e:
                    pass
    
    if issues:
        print("⚠️ Found potential fast approach references:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✅ No active fast approach references found!")
        print("The bot now only supports conservative trading approach.")

if __name__ == "__main__":
    verify_removal()
