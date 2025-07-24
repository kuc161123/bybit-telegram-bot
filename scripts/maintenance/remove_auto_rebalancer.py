#!/usr/bin/env python3
"""
Script to safely remove the auto-rebalancer feature from the bot
"""

import os
import pickle
import shutil
import logging
import asyncio
from datetime import datetime
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Files that reference auto-rebalancer
FILES_TO_CHECK = [
    './audit_accounts.py',
    './execution/auto_rebalancer.py',
    './fix_approach_detection.py',
    './handlers/rebalancer_commands.py',
    './helpers/background_tasks.py',
    './main.py',
    './test_dual_approach_fix.py',
    './test_fixes.py',
    './test_trade_logger.py',
    './utils/trade_verifier.py',
    './verify_complete_position_coverage.py'
]

PICKLE_FILE = 'bybit_bot_dashboard_v4.1_enhanced.pkl'


def backup_file(filepath):
    """Create a backup of the file before modification"""
    if not os.path.exists(filepath):
        return None
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{filepath}.backup_{timestamp}"
    shutil.copy2(filepath, backup_path)
    logger.info(f"✅ Created backup: {backup_path}")
    return backup_path


def remove_from_pickle():
    """Remove auto-rebalancer state from pickle file"""
    if not os.path.exists(PICKLE_FILE):
        logger.warning(f"⚠️ Pickle file not found: {PICKLE_FILE}")
        return
        
    # Create backup
    backup_path = backup_file(PICKLE_FILE)
    
    try:
        # Load pickle data
        with open(PICKLE_FILE, 'rb') as f:
            data = pickle.load(f)
        
        # Check if auto_rebalance_state exists
        if 'auto_rebalance_state' in data:
            del data['auto_rebalance_state']
            logger.info("✅ Removed 'auto_rebalance_state' from pickle data")
            
            # Save modified data
            with open(PICKLE_FILE, 'wb') as f:
                pickle.dump(data, f)
            logger.info("✅ Updated pickle file")
        else:
            logger.info("ℹ️ No auto_rebalance_state found in pickle file")
            
    except Exception as e:
        logger.error(f"❌ Error modifying pickle file: {e}")
        if backup_path:
            logger.info(f"💡 You can restore from backup: {backup_path}")


def comment_out_auto_rebalancer_in_main():
    """Comment out auto-rebalancer related code in main.py"""
    main_file = './main.py'
    
    if not os.path.exists(main_file):
        logger.error(f"❌ main.py not found!")
        return
        
    # Create backup
    backup_path = backup_file(main_file)
    
    try:
        with open(main_file, 'r') as f:
            lines = f.readlines()
        
        modified = False
        in_auto_rebalancer_block = False
        
        for i, line in enumerate(lines):
            # Comment out import
            if 'from execution.auto_rebalancer import' in line and not line.strip().startswith('#'):
                lines[i] = '# ' + line
                modified = True
                logger.info(f"✅ Commented out line {i+1}: auto_rebalancer import")
            
            # Comment out start_auto_rebalancer call
            elif 'await start_auto_rebalancer' in line and not line.strip().startswith('#'):
                lines[i] = '# ' + line
                modified = True
                logger.info(f"✅ Commented out line {i+1}: start_auto_rebalancer call")
            
            # Comment out stop_auto_rebalancer in graceful_shutdown
            elif 'stop_auto_rebalancer' in line and not line.strip().startswith('#'):
                lines[i] = '# ' + line
                modified = True
                logger.info(f"✅ Commented out line {i+1}: stop_auto_rebalancer call")
            
            # Comment out is_auto_rebalancer_running check
            elif 'is_auto_rebalancer_running' in line and not line.strip().startswith('#'):
                lines[i] = '# ' + line
                modified = True
                logger.info(f"✅ Commented out line {i+1}: is_auto_rebalancer_running check")
                
            # Look for try block containing auto-rebalancer
            elif line.strip() == "# Start auto-rebalancer":
                in_auto_rebalancer_block = True
                lines[i] = '# ' + line
                modified = True
            elif in_auto_rebalancer_block:
                if line.strip().startswith('try:') or line.strip().startswith('except') or line.strip().startswith('logger'):
                    if 'auto-rebalancer' in line or 'Auto-rebalancer' in line:
                        lines[i] = '# ' + line
                        modified = True
                    elif line.strip() == 'except Exception as e:':
                        lines[i] = '# ' + line
                        in_auto_rebalancer_block = False
                        modified = True
        
        if modified:
            with open(main_file, 'w') as f:
                f.writelines(lines)
            logger.info("✅ Updated main.py")
        else:
            logger.info("ℹ️ No auto-rebalancer references found to comment out in main.py")
            
    except Exception as e:
        logger.error(f"❌ Error modifying main.py: {e}")
        if backup_path:
            logger.info(f"💡 You can restore from backup: {backup_path}")


def list_files_to_cleanup():
    """List all files that reference auto-rebalancer for manual cleanup"""
    logger.info("\n📋 Files that reference auto-rebalancer (may need manual cleanup):")
    
    for filepath in FILES_TO_CHECK:
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                    
                # Count references
                import_count = len(re.findall(r'from.*auto_rebalancer.*import|import.*auto_rebalancer', content))
                usage_count = len(re.findall(r'auto_rebalancer|AutoRebalancer|rebalancer', content, re.IGNORECASE))
                
                if import_count > 0 or usage_count > 0:
                    logger.info(f"  - {filepath}")
                    logger.info(f"    Imports: {import_count}, Usages: {usage_count}")
                    
            except Exception as e:
                logger.error(f"  - Error reading {filepath}: {e}")


async def check_if_running():
    """Check if auto-rebalancer is currently running"""
    try:
        # Try to import and check status
        from execution.auto_rebalancer import is_auto_rebalancer_running, stop_auto_rebalancer
        
        if is_auto_rebalancer_running():
            logger.info("🔄 Auto-rebalancer is currently running. Stopping it...")
            await stop_auto_rebalancer()
            logger.info("✅ Auto-rebalancer stopped")
        else:
            logger.info("ℹ️ Auto-rebalancer is not running")
            
    except ImportError:
        logger.info("ℹ️ Auto-rebalancer module not found or already removed")
    except Exception as e:
        logger.error(f"❌ Error checking auto-rebalancer status: {e}")


def create_removal_summary():
    """Create a summary of what was removed"""
    summary = """
📋 AUTO-REBALANCER REMOVAL SUMMARY
================================

The following actions were taken:

1. ✅ Removed auto_rebalance_state from pickle file
2. ✅ Commented out auto-rebalancer imports and calls in main.py
3. ✅ Created backups of all modified files

Files that may still need manual cleanup:
- handlers/rebalancer_commands.py (contains /rebalancer commands)
- execution/auto_rebalancer.py (the main module - can be deleted)
- Various test files that reference the rebalancer

To complete the removal:
1. Delete execution/auto_rebalancer.py if you want to fully remove it
2. Remove or comment out rebalancer commands in handlers/rebalancer_commands.py
3. Clean up any test files that reference the auto-rebalancer

The bot will continue to function normally without the auto-rebalancer.
All other features (trading, monitoring, etc.) remain intact.
"""
    
    with open('auto_rebalancer_removal_summary.txt', 'w') as f:
        f.write(summary)
    
    logger.info(summary)


async def main():
    """Main removal process"""
    logger.info("🚀 Starting Auto-Rebalancer Removal Process...")
    
    # Step 1: Check if running and stop it
    await check_if_running()
    
    # Step 2: Remove from pickle file
    logger.info("\n📦 Step 2: Removing from pickle file...")
    remove_from_pickle()
    
    # Step 3: Comment out in main.py
    logger.info("\n📝 Step 3: Commenting out in main.py...")
    comment_out_auto_rebalancer_in_main()
    
    # Step 4: List files for manual cleanup
    logger.info("\n🔍 Step 4: Identifying files for cleanup...")
    list_files_to_cleanup()
    
    # Step 5: Create summary
    logger.info("\n📄 Step 5: Creating removal summary...")
    create_removal_summary()
    
    logger.info("\n✅ Auto-Rebalancer removal process completed!")
    logger.info("💡 Check 'auto_rebalancer_removal_summary.txt' for details")


if __name__ == "__main__":
    asyncio.run(main())