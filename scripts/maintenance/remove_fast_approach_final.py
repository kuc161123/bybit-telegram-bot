#!/usr/bin/env python3
"""
Final Phase: Complete Fast Approach Cleanup
==========================================

This script ensures all fast approach references are removed and 
the bot only supports conservative trading.
"""

import os
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def final_cleanup():
    """Final cleanup of fast approach references"""
    
    # 1. Update main.py if needed
    logger.info("Checking main.py...")
    try:
        with open('main.py', 'r') as f:
            content = f.read()
        
        if 'fast' in content.lower():
            content = re.sub(r'approach.*fast', 'approach = "conservative"', content, flags=re.IGNORECASE)
            with open('main.py', 'w') as f:
                f.write(content)
            logger.info("✅ Updated main.py")
    except Exception as e:
        logger.error(f"Error checking main.py: {e}")
    
    # 2. Update the ConversationHandler setup
    logger.info("Fixing ConversationHandler in main.py...")
    try:
        with open('main.py', 'r') as f:
            content = f.read()
        
        # Remove APPROACH_SELECTION state from ConversationHandler
        content = re.sub(
            r'APPROACH_SELECTION:\s*\[.*?\],?\s*\n',
            '',
            content,
            flags=re.MULTILINE | re.DOTALL
        )
        
        with open('main.py', 'w') as f:
            f.write(content)
        logger.info("✅ Fixed ConversationHandler")
    except Exception as e:
        logger.error(f"Error fixing ConversationHandler: {e}")
    
    # 3. Update screenshot analyzer to default to conservative
    logger.info("Updating screenshot analyzer...")
    try:
        with open('utils/screenshot_analyzer.py', 'r') as f:
            content = f.read()
        
        # Default to conservative approach
        content = re.sub(
            r'approach\s*=\s*extracted_data\.get\(["\']approach["\']\s*,\s*["\']fast["\']\)',
            'approach = "conservative"  # Only conservative approach',
            content
        )
        
        with open('utils/screenshot_analyzer.py', 'w') as f:
            f.write(content)
        logger.info("✅ Updated screenshot analyzer")
    except Exception as e:
        logger.error(f"Error updating screenshot analyzer: {e}")
    
    # 4. Clean up any approach selection UI
    logger.info("Cleaning up UI references...")
    ui_files = [
        'dashboard/keyboards_v2.py',
        'dashboard/keyboards_analytics.py',
        'handlers/mobile_handlers.py'
    ]
    
    for ui_file in ui_files:
        if os.path.exists(ui_file):
            try:
                with open(ui_file, 'r') as f:
                    content = f.read()
                
                # Remove fast approach buttons
                content = re.sub(
                    r'InlineKeyboardButton\(["\'].*Fast.*["\'],.*?\)',
                    '',
                    content
                )
                
                # Update approach references
                content = re.sub(r'approach.*fast', 'approach = "conservative"', content, flags=re.IGNORECASE)
                
                with open(ui_file, 'w') as f:
                    f.write(content)
                logger.info(f"✅ Cleaned {ui_file}")
            except Exception as e:
                logger.error(f"Error cleaning {ui_file}: {e}")
    
    # 5. Update any monitoring files
    logger.info("Updating monitoring files...")
    try:
        with open('execution/monitor.py', 'r') as f:
            content = f.read()
        
        content = re.sub(r'approach\s*==\s*["\']fast["\']', 'False', content)
        content = re.sub(r'monitor\[["\']approach["\']\]\s*==\s*["\']fast["\']', 'False', content)
        
        with open('execution/monitor.py', 'w') as f:
            f.write(content)
        logger.info("✅ Updated monitor.py")
    except Exception as e:
        logger.error(f"Error updating monitor.py: {e}")
    
    # 6. Create a verification script
    logger.info("Creating verification script...")
    verification_script = '''#!/usr/bin/env python3
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
                        lines = content.split('\\n')
                    
                    for i, line in enumerate(lines):
                        # Skip comments and disabled code
                        if line.strip().startswith('#'):
                            continue
                            
                        # Check for fast approach references
                        if re.search(r'approach.*=.*["\']fast["\']', line, re.IGNORECASE):
                            issues.append(f"{filepath}:{i+1} - {line.strip()}")
                        elif 'APPROACH_SELECTION' in line and 'range' in line:
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
'''
    
    with open('verify_fast_removal.py', 'w') as f:
        f.write(verification_script)
    
    logger.info("✅ Created verification script")
    
    # 7. Update the pickle file to remove fast approach monitors
    logger.info("Cleaning up pickle file...")
    try:
        from utils.pickle_lock import main_pickle_lock
        
        data = main_pickle_lock.safe_load()
        if data and 'bot_data' in data:
            monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
            
            # Update all monitors to conservative
            updated = False
            for monitor_key, monitor in monitors.items():
                if monitor.get('approach') == 'fast':
                    monitor['approach'] = 'conservative'
                    updated = True
                    logger.info(f"Updated monitor {monitor_key} to conservative")
            
            if updated:
                main_pickle_lock.safe_save(data)
                logger.info("✅ Updated pickle file")
        
    except Exception as e:
        logger.error(f"Error updating pickle file: {e}")
    
    logger.info("\n✅ Final cleanup complete!")
    logger.info("Run 'python3 verify_fast_removal.py' to verify all changes.")

if __name__ == "__main__":
    final_cleanup()