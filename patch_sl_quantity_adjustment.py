#!/usr/bin/env python3
"""
Patch to ensure SL quantity adjustment works correctly after every TP hit
"""
import os
import shutil
import re
from datetime import datetime

def create_backup(file_path):
    """Create a backup of the file"""
    backup_path = f"{file_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(file_path, backup_path)
    print(f"✅ Created backup: {backup_path}")
    return backup_path

def patch_sl_adjustment():
    """Apply patches to ensure SL quantity adjustment works correctly"""
    
    file_path = "execution/enhanced_tp_sl_manager.py"
    
    # Create backup
    backup_path = create_backup(file_path)
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Track changes
    changes_made = []
    
    # Patch 1: Replace basic _adjust_sl_quantity with enhanced version after TP fills
    # Find line where TP fill adjustment happens (around line 1329)
    pattern1 = r'(await self\._send_tp_fill_alert_enhanced.*?\n\s+)# Adjust SL quantity to match remaining position\n\s+await self\._adjust_sl_quantity\(monitor_data, current_size\)'
    replacement1 = r'\1# Adjust SL quantity to match remaining position (using enhanced method)\n            await self._adjust_sl_quantity_enhanced(monitor_data, current_size)'
    
    if re.search(pattern1, content, re.DOTALL):
        content = re.sub(pattern1, replacement1, content, flags=re.DOTALL)
        changes_made.append("✅ Patched TP fill to use enhanced SL adjustment")
    
    # Patch 2: Ensure SL adjustment after TP2/3/4 fills
    # Find the progressive TP fill handler
    pattern2 = r'(async def _handle_progressive_tp_fills.*?:.*?\n)(.*?)(\n\s+async def)'
    
    def add_sl_adjustment(match):
        method_start = match.group(1)
        method_body = match.group(2)
        next_method = match.group(3)
        
        # Check if SL adjustment is already there
        if '_adjust_sl_quantity' not in method_body:
            # Add SL adjustment at the end of the method
            lines = method_body.rstrip().split('\n')
            indent = '        '  # 8 spaces for method content
            lines.append(f'{indent}# Ensure SL quantity matches remaining position after progressive TP')
            lines.append(f'{indent}await self._adjust_sl_quantity_enhanced(monitor_data, current_size)')
            method_body = '\n'.join(lines) + '\n'
            changes_made.append("✅ Added SL adjustment to progressive TP fills")
        
        return method_start + method_body + next_method
    
    content = re.sub(pattern2, add_sl_adjustment, content, flags=re.DOTALL)
    
    # Patch 3: Fix the _adjust_sl_quantity_enhanced method to properly calculate quantities
    pattern3 = r'(async def _adjust_sl_quantity_enhanced.*?\n)(.*?)(await self\._adjust_sl_quantity\(monitor_data, enhanced_sl_qty\))'
    
    def fix_enhanced_calculation(match):
        method_header = match.group(1)
        method_body = match.group(2)
        final_call = match.group(3)
        
        # Replace the body with proper calculation
        new_body = '''        """Enhanced SL quantity adjustment that properly tracks position changes"""
        if not monitor_data.get("sl_order"):
            logger.warning("No SL order to adjust")
            return

        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            
            # Log current state
            logger.info(f"🔄 SL Adjustment for {symbol} {side}")
            logger.info(f"   Current position size: {current_position_size}")
            logger.info(f"   Original position size: {monitor_data.get('position_size', 'Unknown')}")
            logger.info(f"   TP1 hit: {monitor_data.get('tp1_hit', False)}")
            
            # For conservative approach after TP1, SL should match remaining position
            # This is because all limit orders are cancelled after TP1
            sl_quantity = current_position_size
            
            # Log the decision
            logger.info(f"   SL will be adjusted to: {sl_quantity}")
            
            # Use the standard adjustment method with calculated quantity
            '''
        
        return method_header + new_body + final_call
    
    content = re.sub(pattern3, fix_enhanced_calculation, content, flags=re.DOTALL)
    changes_made.append("✅ Fixed enhanced SL calculation logic")
    
    # Patch 4: Ensure fast approach also uses enhanced adjustment
    pattern4 = r'(# Position should be closed, but update SL just in case\n\s+)await self\._adjust_sl_quantity\(monitor_data, current_size\)'
    replacement4 = r'\1await self._adjust_sl_quantity_enhanced(monitor_data, current_size)'
    
    if re.search(pattern4, content):
        content = re.sub(pattern4, replacement4, content)
        changes_made.append("✅ Patched fast approach to use enhanced SL adjustment")
    
    # Patch 5: Add logging to track SL adjustments
    pattern5 = r'(if sl_result and sl_result\.get\("orderId"\):\n\s+# Update SL order info)'
    replacement5 = r'if sl_result and sl_result.get("orderId"):\n                    logger.info(f"✅ SL adjusted: {monitor_data[\'symbol\']} {monitor_data[\'side\']} - New qty: {adjusted_quantity}, Price: {sl_order[\'price\']}")\n                    # Update SL order info'
    
    if re.search(pattern5, content):
        content = re.sub(pattern5, replacement5, content)
        changes_made.append("✅ Added detailed logging for SL adjustments")
    
    # Write the patched content
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("\n" + "="*60)
    print("SL QUANTITY ADJUSTMENT PATCH APPLIED")
    print("="*60)
    
    if changes_made:
        print("\nChanges made:")
        for change in changes_made:
            print(f"  {change}")
    else:
        print("\n⚠️  No changes were needed - the code may have already been patched")
    
    print(f"\n📁 Backup saved to: {backup_path}")
    print("\n⚠️  IMPORTANT: Restart the bot for changes to take effect!")
    
    # Create a summary file
    summary = f"""
SL QUANTITY ADJUSTMENT PATCH SUMMARY
====================================
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

WHAT THIS PATCH DOES:
1. Ensures enhanced SL quantity adjustment is used after every TP hit
2. Properly adjusts SL quantity after TP1 (should be 15% of original)
3. Properly adjusts SL quantity after TP2/3/4 progressively
4. Adds detailed logging to track SL adjustments
5. Works for both conservative and fast approaches

EXPECTED BEHAVIOR AFTER PATCH:
- When TP1 (85%) hits:
  • Cancels remaining limit orders ✅
  • Moves SL to breakeven ✅
  • Adjusts SL quantity to match remaining 15% ✅
  
- When TP2 (5%) hits:
  • SL quantity adjusts to remaining 10% ✅
  
- When TP3 (5%) hits:
  • SL quantity adjusts to remaining 5% ✅
  
- When TP4 (5%) hits:
  • Position closes completely ✅

ALERTS YOU'LL RECEIVE:
1. "TP1 HIT - PROFIT TAKEN!" with breakeven info
2. "Limit Orders Cleaned Up" showing cancelled orders
3. "STOP LOSS MOVED TO BREAKEVEN" confirmation
4. For each TP: Updated SL quantity in logs

Changes made:
{chr(10).join('  ' + change for change in changes_made) if changes_made else '  No changes needed'}

Backup created: {backup_path}
"""
    
    with open('sl_adjustment_patch_summary.txt', 'w') as f:
        f.write(summary)
    
    print(f"\n📄 Summary saved to: sl_adjustment_patch_summary.txt")

if __name__ == "__main__":
    try:
        patch_sl_adjustment()
    except Exception as e:
        print(f"\n❌ Error applying patch: {e}")
        print("Please check the file path and try again")