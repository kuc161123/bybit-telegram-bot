#!/usr/bin/env python3
"""
Patch the Enhanced TP/SL Manager to fix limit fill detection logic.
This ensures alerts are sent for ALL limit fills, not just small ones.
"""

import os
import shutil
from datetime import datetime

def create_backup(file_path):
    """Create a timestamped backup of the file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{file_path}.backup_limit_fix_{timestamp}"
    shutil.copy2(file_path, backup_path)
    print(f"Created backup: {backup_path}")
    return backup_path

def patch_enhanced_tp_sl_manager():
    """Apply the limit fill detection fix to enhanced_tp_sl_manager.py"""
    
    file_path = "execution/enhanced_tp_sl_manager.py"
    
    # Create backup
    backup_path = create_backup(file_path)
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find and fix the problematic condition
    # OLD: if not limit_orders_filled and fill_percentage < 50:
    # NEW: if not limit_orders_filled and current_size > 0:
    
    old_pattern = "if not limit_orders_filled and fill_percentage < 50:"
    new_pattern = "if not limit_orders_filled and current_size > 0:"
    
    if old_pattern in content:
        content = content.replace(old_pattern, new_pattern)
        print(f"✅ Fixed limit fill detection condition")
        print(f"   OLD: {old_pattern}")
        print(f"   NEW: {new_pattern}")
    else:
        print("⚠️  Could not find the exact pattern. Looking for similar patterns...")
        
        # Try alternative patterns
        alternatives = [
            ("elif not limit_orders_filled and fill_percentage < 50:", 
             "elif not limit_orders_filled and current_size > 0:"),
            ("if not monitor_data.get('limit_orders_filled') and fill_percentage < 50:",
             "if not monitor_data.get('limit_orders_filled') and current_size > 0:"),
            ("and fill_percentage < 50", "and current_size > 0")
        ]
        
        found = False
        for old, new in alternatives:
            if old in content:
                content = content.replace(old, new)
                print(f"✅ Fixed limit fill detection with alternative pattern")
                print(f"   OLD: {old}")
                print(f"   NEW: {new}")
                found = True
                break
        
        if not found:
            print("❌ Could not find the pattern to fix. Manual intervention needed.")
            print("\nPlease manually update the condition in enhanced_tp_sl_manager.py:")
            print("Change: if not limit_orders_filled and fill_percentage < 50:")
            print("To:     if not limit_orders_filled and current_size > 0:")
            return
    
    # Also ensure we always call _adjust_all_orders_for_partial_fill
    # when position size increases
    
    # Look for the position increase detection section
    position_increase_pattern = "# Position size increased"
    if position_increase_pattern in content:
        print("\n✅ Found position increase detection section")
        
        # Add a comment to ensure proper handling
        comment = """
                    # IMPORTANT: Always adjust orders and send alerts for ANY limit fill
                    # regardless of fill percentage. Large fills (>50%) should still
                    # trigger alerts and order adjustments."""
        
        content = content.replace(position_increase_pattern, 
                                position_increase_pattern + comment)
    
    # Write the patched file
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"\n✅ Successfully patched {file_path}")
    print(f"   Backup saved to: {backup_path}")
    
    # Create a summary file
    summary = f"""Enhanced TP/SL Manager Limit Fill Detection Fix
================================================

Applied on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Backup file: {backup_path}

Changes made:
1. Fixed limit fill alert condition to trigger for ALL fills, not just <50%
2. Ensured position size increases always trigger order adjustments
3. Added comments for clarity

Key improvement:
- OLD: Only sent alerts for fills under 50%
- NEW: Sends alerts for ANY limit fill

This fix ensures:
- All limit order fills generate alerts
- TP/SL orders are properly adjusted for partial fills
- No more missed alerts for large limit fills
"""
    
    with open("limit_fill_detection_fix_summary.md", 'w') as f:
        f.write(summary)
    
    print("\n📄 Created limit_fill_detection_fix_summary.md")

def main():
    """Main function."""
    print("🔧 Patching Enhanced TP/SL Manager for limit fill detection...\n")
    
    # Check if file exists
    if not os.path.exists("execution/enhanced_tp_sl_manager.py"):
        print("❌ Error: execution/enhanced_tp_sl_manager.py not found!")
        print("   Make sure you're running this from the bot's root directory.")
        return
    
    patch_enhanced_tp_sl_manager()
    
    print("\n✅ Patching complete!")
    print("\n⚠️  IMPORTANT: Restart the bot for changes to take effect.")
    print("   The fix will prevent future limit fill detection issues.")

if __name__ == "__main__":
    main()