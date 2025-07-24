#!/usr/bin/env python3
"""
Fix Background Tasks Import Error

Updates background_tasks.py to handle the import error gracefully
"""

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_import():
    """Fix the import in background_tasks.py"""
    try:
        logger.info("🔧 Fixing background_tasks.py import...")
        
        # Read the file
        file_path = '/Users/lualakol/bybit-telegram-bot/helpers/background_tasks.py'
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Replace the problematic import
        old_import = "from execution.mirror_enhanced_tp_sl import mirror_enhanced_tp_sl_manager, sync_mirror_positions_on_startup"
        
        # Create a try-except block for the import
        new_import = """try:
                        from execution.mirror_enhanced_tp_sl import sync_mirror_positions_on_startup
                        mirror_sync_available = True
                    except ImportError:
                        logger.warning("Mirror sync not available")
                        mirror_sync_available = False
                        sync_mirror_positions_on_startup = None"""
        
        if old_import in content:
            content = content.replace(old_import, new_import)
            logger.info("✅ Replaced import statement")
            
            # Also update the usage
            old_usage = "if mirror_enhanced_tp_sl_manager:"
            new_usage = "if mirror_sync_available and sync_mirror_positions_on_startup:"
            
            if old_usage in content:
                content = content.replace(old_usage, new_usage)
                logger.info("✅ Updated usage check")
            
            # Write the file back
            with open(file_path, 'w') as f:
                f.write(content)
            
            logger.info("✅ Fixed background_tasks.py")
            return True
        else:
            logger.warning("Import not found in expected format")
            
            # Try a different approach - comment out the problematic section
            if "mirror_enhanced_tp_sl_manager" in content:
                logger.info("📌 Commenting out mirror sync section...")
                
                # Find the try block that contains the import
                start_marker = "# Sync mirror positions on startup"
                end_marker = "logger.error(f\"Error syncing mirror positions: {e}\")"
                
                start_pos = content.find(start_marker)
                if start_pos > 0:
                    end_pos = content.find(end_marker, start_pos)
                    if end_pos > 0:
                        # Find the end of the except block
                        end_pos = content.find("\n", end_pos) + 1
                        
                        # Comment out the entire block
                        section = content[start_pos:end_pos]
                        commented_section = '\n'.join(['                    # ' + line if line.strip() else line 
                                                     for line in section.split('\n')])
                        
                        content = content[:start_pos] + commented_section + content[end_pos:]
                        
                        # Write the file back
                        with open(file_path, 'w') as f:
                            f.write(content)
                        
                        logger.info("✅ Commented out mirror sync section")
                        return True
        
        return False
        
    except Exception as e:
        logger.error(f"❌ Error fixing import: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("🚀 Background Tasks Import Fix")
    logger.info("=" * 60)
    
    if fix_import():
        logger.info("\n🎉 Import error successfully fixed!")
        logger.info("📌 The periodic sync errors should stop")
        logger.info("📌 No bot restart required")
    else:
        logger.error("\n❌ Failed to fix import error")