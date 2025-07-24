#!/usr/bin/env python3
"""
Fix Mirror Import Error

Quick fix for the mirror_enhanced_tp_sl_manager import error
"""

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_import_error():
    """Fix the import error by adding the missing instantiation"""
    try:
        logger.info("🔧 Fixing mirror_enhanced_tp_sl_manager import error...")
        
        # Read the current file
        mirror_file = '/Users/lualakol/bybit-telegram-bot/execution/mirror_enhanced_tp_sl.py'
        with open(mirror_file, 'r') as f:
            content = f.read()
        
        # Check if the instantiation is missing
        if 'mirror_enhanced_tp_sl_manager' not in content:
            logger.info("📌 Adding mirror_enhanced_tp_sl_manager instantiation...")
            
            # Add the instantiation before the __all__ export
            new_content = content.replace(
                "# Export the enhanced class\n__all__ = ['MirrorEnhancedTPSL']",
                """# Export the enhanced class
__all__ = ['MirrorEnhancedTPSL']

# Create singleton instance for import
mirror_enhanced_tp_sl_manager = None

def initialize_mirror_manager(main_manager):
    \"\"\"Initialize the mirror manager with main manager reference\"\"\"
    global mirror_enhanced_tp_sl_manager
    if not mirror_enhanced_tp_sl_manager:
        mirror_enhanced_tp_sl_manager = MirrorEnhancedTPSL(main_manager)
    return mirror_enhanced_tp_sl_manager"""
            )
            
            # Write the updated content
            with open(mirror_file, 'w') as f:
                f.write(new_content)
            
            logger.info("✅ Added mirror_enhanced_tp_sl_manager instantiation")
        else:
            logger.info("ℹ️ mirror_enhanced_tp_sl_manager already exists")
        
        # Now fix the import in enhanced_tp_sl_manager.py
        enhanced_file = '/Users/lualakol/bybit-telegram-bot/execution/enhanced_tp_sl_manager.py'
        with open(enhanced_file, 'r') as f:
            content = f.read()
        
        # Replace the problematic import
        old_import = "from execution.mirror_enhanced_tp_sl import mirror_enhanced_tp_sl_manager"
        new_import = "from execution.mirror_enhanced_tp_sl import initialize_mirror_manager"
        
        if old_import in content:
            logger.info("📌 Updating import in enhanced_tp_sl_manager.py...")
            content = content.replace(old_import, new_import)
            
            # Also update the usage
            content = content.replace(
                "if mirror_enhanced_tp_sl_manager:",
                "mirror_manager = initialize_mirror_manager(self)\n                    if mirror_manager:"
            )
            
            # Write the updated content
            with open(enhanced_file, 'w') as f:
                f.write(content)
            
            logger.info("✅ Updated import in enhanced_tp_sl_manager.py")
        
        logger.info("✅ Import error fix completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error fixing import: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("🚀 Mirror Import Error Fix")
    logger.info("=" * 60)
    
    if fix_import_error():
        logger.info("\n🎉 Import error successfully fixed!")
        logger.info("📌 The bot should now sync mirror positions without errors")
        logger.info("📌 No restart required - the fix will take effect on next sync")
    else:
        logger.error("\n❌ Failed to fix import error")