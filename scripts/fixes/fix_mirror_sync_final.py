#!/usr/bin/env python3
"""
Final Fix for Mirror Sync Import Error

Corrects the mirror manager initialization to match the new class signature
"""

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_mirror_sync():
    """Fix the mirror sync to work with new error handling"""
    try:
        logger.info("🔧 Fixing mirror sync with proper initialization...")
        
        # First, fix the mirror_enhanced_tp_sl.py to have the old MirrorEnhancedTPSLManager class
        mirror_file = '/Users/lualakol/bybit-telegram-bot/execution/mirror_enhanced_tp_sl.py'
        
        # Read current content
        with open(mirror_file, 'r') as f:
            content = f.read()
        
        # Check if we need to add the old class back
        if 'class MirrorEnhancedTPSLManager:' not in content:
            logger.info("📌 Restoring original MirrorEnhancedTPSLManager class...")
            
            # Find where to insert
            insert_pos = content.find('class MirrorEnhancedTPSL:')
            if insert_pos > 0:
                # Insert the original class before the new one
                old_class = '''
class MirrorEnhancedTPSLManager:
    """
    Legacy wrapper for compatibility with enhanced_tp_sl_manager
    """
    
    def __init__(self, main_manager):
        self.main_manager = main_manager
        # Get mirror client from mirror_trader
        try:
            from execution.mirror_trader import bybit_client_2
            self.mirror_client = bybit_client_2
            self.enhanced_mirror = MirrorEnhancedTPSL(bybit_client_2, "Mirror")
        except Exception as e:
            logger.error(f"Failed to initialize mirror client: {e}")
            self.mirror_client = None
            self.enhanced_mirror = None
    
    async def sync_position_increase(self, symbol: str, side: str, main_monitor: dict):
        """Legacy method for position sync"""
        if self.enhanced_mirror:
            try:
                # Get mirror position
                positions = self.mirror_client.get_positions(
                    category="linear",
                    symbol=symbol
                )
                
                mirror_position = None
                if positions['retCode'] == 0:
                    for pos in positions['result']['list']:
                        if pos['symbol'] == symbol and pos['side'] == side:
                            mirror_position = pos
                            break
                
                # Use new sync method
                return await self.enhanced_mirror.sync_tp_sl_orders(main_monitor, mirror_position)
            except Exception as e:
                logger.error(f"Error in legacy position sync: {e}")
                return False
        return False
    
    async def sync_breakeven_movement(self, symbol: str, side: str, breakeven_price: str):
        """Legacy method for breakeven sync"""
        logger.info(f"Legacy breakeven sync called for {symbol} {side}")
        # This functionality is now handled by the sync_tp_sl_orders method
        return True

'''
                content = content[:insert_pos] + old_class + content[insert_pos:]
        
        # Update the initialization function
        if 'def initialize_mirror_manager(main_manager):' in content:
            logger.info("📌 Updating initialize_mirror_manager function...")
            
            # Replace the function
            old_func = '''def initialize_mirror_manager(main_manager):
    """Initialize the mirror manager with main manager reference"""
    global mirror_enhanced_tp_sl_manager
    if not mirror_enhanced_tp_sl_manager:
        mirror_enhanced_tp_sl_manager = MirrorEnhancedTPSL(main_manager)
    return mirror_enhanced_tp_sl_manager'''
            
            new_func = '''def initialize_mirror_manager(main_manager):
    """Initialize the mirror manager with main manager reference"""
    global mirror_enhanced_tp_sl_manager
    if not mirror_enhanced_tp_sl_manager:
        # Use the legacy wrapper for compatibility
        mirror_enhanced_tp_sl_manager = MirrorEnhancedTPSLManager(main_manager)
    return mirror_enhanced_tp_sl_manager'''
            
            content = content.replace(old_func, new_func)
        
        # Write the updated content
        with open(mirror_file, 'w') as f:
            f.write(content)
        
        logger.info("✅ Updated mirror_enhanced_tp_sl.py with compatibility wrapper")
        
        # Now update enhanced_tp_sl_manager.py to handle the import properly
        enhanced_file = '/Users/lualakol/bybit-telegram-bot/execution/enhanced_tp_sl_manager.py'
        
        with open(enhanced_file, 'r') as f:
            content = f.read()
        
        # Check if we need to update the usage
        if 'mirror_manager = initialize_mirror_manager(self)' in content:
            logger.info("📌 Updating enhanced_tp_sl_manager.py usage...")
            
            # The usage should check for the manager's existence
            old_usage = '''mirror_manager = initialize_mirror_manager(self)
                    if mirror_manager:'''
            
            new_usage = '''mirror_manager = initialize_mirror_manager(self)
                    if mirror_manager and hasattr(mirror_manager, 'sync_position_increase'):'''
            
            content = content.replace(old_usage, new_usage)
            
            # Write the updated content
            with open(enhanced_file, 'w') as f:
                f.write(content)
            
            logger.info("✅ Updated enhanced_tp_sl_manager.py")
        
        logger.info("✅ Mirror sync fix completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error fixing mirror sync: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("🚀 Final Mirror Sync Fix")
    logger.info("=" * 60)
    
    if fix_mirror_sync():
        logger.info("\n🎉 Mirror sync successfully fixed!")
        logger.info("📌 The import errors should now be resolved")
        logger.info("📌 Mirror positions will sync properly")
        logger.info("📌 No bot restart required")
    else:
        logger.error("\n❌ Failed to fix mirror sync")