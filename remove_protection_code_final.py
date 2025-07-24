#!/usr/bin/env python3
"""
Complete External Order Protection Removal
Run this script when ready to permanently remove the code (requires bot restart)
Generated: 20250712_110804
"""

import os
import shutil
from datetime import datetime

def remove_external_order_protection_code():
    """Remove all external order protection code from the codebase"""
    
    print("🗑️ Removing External Order Protection Code...")
    print("=" * 80)
    
    # Files to delete
    files_to_delete = [
        'utils/external_order_protection.py',
        'utils/external_order_protection_enhanced.py',
        'scripts/fixes/disable_external_order_protection.py',
        'scripts/fixes/restore_external_order_protection.py',
        'scripts/fixes/set_external_protection_env.py',
        'scripts/maintenance/emergency_monitoring_fix.py',
        'scripts/maintenance/hotfix_external_order_protection.py',
    ]
    
    # Backup directory
    backup_dir = f'backups/external_order_protection_20250712_110804'
    os.makedirs(backup_dir, exist_ok=True)
    
    # Backup and delete files
    for file_path in files_to_delete:
        if os.path.exists(file_path):
            backup_path = os.path.join(backup_dir, os.path.basename(file_path))
            shutil.copy2(file_path, backup_path)
            os.remove(file_path)
            print(f"✅ Removed: {file_path} (backed up)")
        else:
            print(f"ℹ️ Not found: {file_path}")
    
    print(f"\n✅ Files backed up to: {backup_dir}")
    print("\n⚠️ Manual steps required:")
    print("1. Edit clients/bybit_helpers.py - remove import and protection checks")
    print("2. Edit execution/monitor.py - remove import and protection check")
    print("3. Edit config/settings.py - remove BOT_ORDER_PREFIX_STRICT")
    print("4. Update .env.example - remove EXTERNAL_ORDER_PROTECTION and BOT_ORDER_PREFIX_STRICT")
    print("5. Restart the bot for changes to take effect")

if __name__ == "__main__":
    remove_external_order_protection_code()
