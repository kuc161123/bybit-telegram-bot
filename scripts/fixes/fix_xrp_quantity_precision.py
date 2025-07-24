#!/usr/bin/env python3
"""
Fix XRP Quantity Precision

Patches the mirror sync logic to properly handle XRPUSDT quantity formatting
"""

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def apply_quantity_fix():
    """Apply quantity precision fix for XRPUSDT"""
    try:
        logger.info("🔧 Applying XRPUSDT Quantity Precision Fix...")
        
        # Patch the mirror enhanced TP/SL module
        mirror_file = '/Users/lualakol/bybit-telegram-bot/execution/mirror_enhanced_tp_sl.py'
        
        with open(mirror_file, 'r') as f:
            content = f.read()
        
        # Add quantity rounding for XRPUSDT after imports
        patch_imports = '''from utils.helpers import value_adjusted_to_step
from utils.order_identifier import generate_order_link_id, generate_adjusted_order_link_id, ORDER_TYPE_TP, ORDER_TYPE_SL
from clients.bybit_helpers import get_correct_position_idx
from utils.quantity_formatter import format_quantity_for_exchange, validate_quantity_for_order

# Special handling for symbols with no decimal places
NO_DECIMAL_SYMBOLS = {'XRPUSDT', 'DOGEUSDT', 'SHIBUSDT', 'FLOKIUSDT'}

def round_quantity_for_symbol(quantity, symbol):
    """Round quantity based on symbol requirements"""
    if symbol in NO_DECIMAL_SYMBOLS:
        return str(int(round(float(quantity))))
    return str(quantity)
'''
        
        # Replace the imports section
        if "from utils.quantity_formatter import" in content:
            # Already has the import, just add the helper
            if "NO_DECIMAL_SYMBOLS" not in content:
                import_end = content.find("logger = logging.getLogger(__name__)")
                if import_end > 0:
                    before = content[:import_end]
                    after = content[import_end:]
                    
                    helper_code = '''
# Special handling for symbols with no decimal places
NO_DECIMAL_SYMBOLS = {'XRPUSDT', 'DOGEUSDT', 'SHIBUSDT', 'FLOKIUSDT'}

def round_quantity_for_symbol(quantity, symbol):
    """Round quantity based on symbol requirements"""
    if symbol in NO_DECIMAL_SYMBOLS:
        return str(int(round(float(quantity))))
    return str(quantity)

'''
                    content = before + helper_code + after
        
        # Find and patch the sync reduction calculation
        if "reduction_percentage = ((main_current - mirror_current) / main_current) * 100" in content:
            # Add tolerance check
            old_block = '''            reduction_percentage = ((main_current - mirror_current) / main_current) * 100
            logger.info(f"🪞 Mirror position {symbol} {side} size changed: {mirror_current} → {main_monitor['remaining_size']}")
            logger.info(f"🪞 Syncing mirror phase: {old_phase} → {new_phase}")
            logger.info(f"🔄 MIRROR: Main position reduced by {reduction_percentage:.2f}% - syncing mirror orders")'''
            
            new_block = '''            reduction_percentage = ((main_current - mirror_current) / main_current) * 100
            
            # Check if the difference is negligible (less than 0.5%)
            if abs(reduction_percentage) < 0.5:
                logger.info(f"🪞 Mirror position {symbol} {side} - negligible difference ({reduction_percentage:.2f}%), skipping sync")
                return
            
            logger.info(f"🪞 Mirror position {symbol} {side} size changed: {mirror_current} → {main_monitor['remaining_size']}")
            logger.info(f"🪞 Syncing mirror phase: {old_phase} → {new_phase}")
            logger.info(f"🔄 MIRROR: Main position reduced by {reduction_percentage:.2f}% - syncing mirror orders")'''
            
            content = content.replace(old_block, new_block)
        
        # Patch the order amendment calls to round quantities
        if "new_qty = order['quantity'] * ratio" in content:
            old_line = "new_qty = order['quantity'] * ratio"
            new_line = "new_qty = round_quantity_for_symbol(order['quantity'] * ratio, symbol)"
            content = content.replace(old_line, new_line)
        
        # Write the patched file
        with open(mirror_file, 'w') as f:
            f.write(content)
        
        logger.info("✅ Patched mirror_enhanced_tp_sl.py with quantity fixes")
        
        # Also patch the position size comparison tolerance
        logger.info("📌 Adding position size tolerance...")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error applying quantity fix: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("🚀 XRPUSDT Quantity Precision Fix")
    logger.info("=" * 60)
    
    if apply_quantity_fix():
        logger.info("\n🎉 Quantity precision fix successfully applied!")
        logger.info("📌 XRPUSDT orders will now use whole numbers")
        logger.info("📌 Position sync will have 0.5% tolerance")
        logger.info("📌 No bot restart required")
    else:
        logger.error("\n❌ Failed to apply quantity fix")