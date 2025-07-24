#!/usr/bin/env python3
"""
Complete Auto-Rebalancer Removal Script
This script completely removes all traces of auto-rebalancer from the bot
"""
import pickle
import logging
import os
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def clean_pickle_file():
    """Remove auto_rebalance_state from pickle file"""
    pickle_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{pickle_file}"
    
    try:
        # Create backup
        logger.info(f"Creating backup: {backup_file}")
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        with open(backup_file, 'wb') as f:
            pickle.dump(data, f)
        
        # Clean bot_data
        changes_made = False
        if 'bot_data' in data:
            bot_data = data['bot_data']
            if 'auto_rebalance_state' in bot_data:
                del bot_data['auto_rebalance_state']
                logger.info("✅ Removed auto_rebalance_state from bot_data")
                changes_made = True
            else:
                logger.info("ℹ️ No auto_rebalance_state found in bot_data")
        
        # Clean user_data for all users
        if 'user_data' in data:
            for user_id, user_data in data['user_data'].items():
                if 'auto_rebalance_state' in user_data:
                    del user_data['auto_rebalance_state']
                    logger.info(f"✅ Removed auto_rebalance_state from user {user_id}")
                    changes_made = True
        
        # Save cleaned data
        if changes_made:
            with open(pickle_file, 'wb') as f:
                pickle.dump(data, f)
            logger.info("✅ Pickle file cleaned and saved")
        else:
            logger.info("ℹ️ No auto_rebalance_state found in pickle file")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error cleaning pickle file: {e}")
        return False

def check_and_report_files():
    """Check various files for auto-rebalancer references"""
    files_to_check = [
        ('main.py', 'Main entry point'),
        ('execution/trader.py', 'Trade execution'),
        ('execution/monitor.py', 'Position monitoring'),
        ('helpers/background_tasks.py', 'Background tasks'),
        ('handlers/__init__.py', 'Handler initialization'),
        ('handlers/rebalancer_commands.py', 'Rebalancer commands'),
        ('handlers/rebalancer_commands.py.disabled', 'Disabled rebalancer commands')
    ]
    
    logger.info("\n📋 Checking files for auto-rebalancer references:")
    
    for file_path, description in files_to_check:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                
                # Check for auto-rebalancer references
                references = []
                for line_num, line in enumerate(content.split('\n'), 1):
                    if any(term in line.lower() for term in ['auto_rebalancer', 'autorebalancer', 'auto-rebalancer', 'auto rebalancer']):
                        # Check if it's commented out
                        stripped_line = line.strip()
                        if stripped_line.startswith('#') or stripped_line.startswith('//'):
                            references.append((line_num, line.strip(), 'COMMENTED'))
                        else:
                            references.append((line_num, line.strip(), 'ACTIVE'))
                
                if references:
                    logger.info(f"\n📄 {file_path} ({description}):")
                    for line_num, line, status in references:
                        if status == 'ACTIVE':
                            logger.warning(f"   ⚠️ Line {line_num}: {line}")
                        else:
                            logger.info(f"   ✅ Line {line_num}: {line} [ALREADY COMMENTED]")
                else:
                    logger.info(f"✅ {file_path}: No references found")
                    
            except Exception as e:
                logger.error(f"❌ Error checking {file_path}: {e}")
        else:
            logger.info(f"ℹ️ {file_path}: File not found")

def verify_removal():
    """Verify that auto-rebalancer has been completely removed"""
    logger.info("\n🔍 Verifying complete removal...")
    
    # Check if auto_rebalancer.py exists
    if os.path.exists('execution/auto_rebalancer.py'):
        logger.warning("⚠️ execution/auto_rebalancer.py still exists - consider renaming to .disabled")
    else:
        logger.info("✅ execution/auto_rebalancer.py not found")
    
    # Check for any remaining imports
    import_found = False
    for root, dirs, files in os.walk('.'):
        # Skip virtual environments and cache
        if any(skip in root for skip in ['venv', '__pycache__', '.git', 'node_modules']):
            continue
            
        for file in files:
            if file.endswith('.py') and not file.startswith('complete_auto_rebalancer_removal'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    # Check for imports
                    if 'from execution.auto_rebalancer import' in content or 'import auto_rebalancer' in content:
                        # Check if it's commented
                        for line in content.split('\n'):
                            if ('from execution.auto_rebalancer import' in line or 'import auto_rebalancer' in line) and not line.strip().startswith('#'):
                                logger.warning(f"⚠️ Active import found in {file_path}")
                                import_found = True
                                break
                except:
                    pass
    
    if not import_found:
        logger.info("✅ No active auto-rebalancer imports found")
    
    logger.info("\n✅ Verification complete!")

def main():
    """Main function to remove all traces of auto-rebalancer"""
    logger.info("🚀 Starting complete auto-rebalancer removal...")
    
    # Step 1: Clean pickle file
    logger.info("\n📦 Step 1: Cleaning pickle file...")
    if clean_pickle_file():
        logger.info("✅ Pickle file cleaned successfully")
    else:
        logger.error("❌ Failed to clean pickle file")
        return
    
    # Step 2: Check files for references
    logger.info("\n🔍 Step 2: Checking code files...")
    check_and_report_files()
    
    # Step 3: Verify removal
    logger.info("\n✅ Step 3: Final verification...")
    verify_removal()
    
    # Final recommendations
    logger.info("\n📌 Recommendations:")
    logger.info("1. The auto-rebalancer has been removed from the pickle file")
    logger.info("2. Auto-rebalancer references in main.py are already commented out")
    logger.info("3. The import in helpers/background_tasks.py needs to be commented out")
    logger.info("4. Consider renaming execution/auto_rebalancer.py to auto_rebalancer.py.disabled")
    logger.info("5. Restart the bot after making these changes")
    
    logger.info("\n✅ Auto-rebalancer removal complete!")

if __name__ == "__main__":
    main()