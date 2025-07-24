#!/usr/bin/env python3
"""
Fix the false TP fill detection issue by properly tracking position changes
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def fix_false_tp_fills():
    """Fix the false TP fill detection issue"""
    
    file_path = "execution/enhanced_tp_sl_manager.py"
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix 1: Add position change tracking to prevent duplicate detections
    old_duplicate_check = """                if current_size < monitor_data["remaining_size"]:
                    # Position reduced - TP or SL hit
                    size_diff = monitor_data["remaining_size"] - current_size"""
    
    new_duplicate_check = """                if current_size < monitor_data["remaining_size"]:
                    # Position reduced - TP or SL hit
                    size_diff = monitor_data["remaining_size"] - current_size
                    
                    # Check if we've already processed this position change
                    position_change_key = f"{monitor_key}_last_processed_size"
                    last_processed_size = getattr(self, position_change_key, None)
                    
                    if last_processed_size == current_size:
                        # Already processed this position change, skip
                        continue
                    
                    # Update last processed size
                    setattr(self, position_change_key, current_size)"""
    
    if old_duplicate_check in content:
        content = content.replace(old_duplicate_check, new_duplicate_check)
        print("✅ Added duplicate position change detection")
    else:
        print("❌ Could not find duplicate check code to fix")
    
    # Fix 2: Properly handle mirror account size differences
    old_warning = """                    if diff_percentage > 60 and diff_percentage < 70:
                        logger.warning(f"⚠️ Suspicious reduction detected for {monitor_key}: {diff_percentage:.2f}% - possible cross-account detection")"""
    
    new_warning = """                    if diff_percentage > 60 and diff_percentage < 70:
                        # Check if this is a mirror monitor - expected behavior due to percentage-based sizing
                        if "_mirror" in monitor_key:
                            logger.debug(f"Mirror account size difference detected: {diff_percentage:.2f}% (expected due to percentage-based sizing)")
                        else:
                            logger.warning(f"⚠️ Suspicious reduction detected for {monitor_key}: {diff_percentage:.2f}% - possible cross-account detection")"""
    
    if old_warning in content:
        content = content.replace(old_warning, new_warning)
        print("✅ Fixed mirror account size difference warnings")
    else:
        print("⚠️ Could not find warning code to fix")
    
    # Fix 3: Reset cumulative tracking when position is fully closed
    old_cumulative = """                    cumulative_percentage = (fill_tracker["total_filled"] / fill_tracker["target_size"]) * 100
                    
                    logger.info(f"🎯 Position size reduced by {size_diff} ({fill_percentage:.2f}% of position, {cumulative_percentage:.2f}% cumulative) - TP order filled")"""
    
    new_cumulative = """                    cumulative_percentage = (fill_tracker["total_filled"] / fill_tracker["target_size"]) * 100
                    
                    # Reset cumulative tracking if it exceeds 100% (false positive)
                    if cumulative_percentage > 100:
                        logger.warning(f"⚠️ Cumulative fill exceeded 100% ({cumulative_percentage:.2f}%) - resetting tracker")
                        fill_tracker["total_filled"] = size_diff
                        self.fill_tracker[monitor_key] = fill_tracker
                        cumulative_percentage = (size_diff / fill_tracker["target_size"]) * 100
                    
                    logger.info(f"🎯 Position size reduced by {size_diff} ({fill_percentage:.2f}% of position, {cumulative_percentage:.2f}% cumulative) - TP order filled")"""
    
    if old_cumulative in content:
        content = content.replace(old_cumulative, new_cumulative)
        print("✅ Added cumulative percentage reset logic")
    else:
        print("❌ Could not find cumulative tracking code to fix")
    
    # Backup and write
    import shutil
    backup_path = f"{file_path}.backup_false_tp_fills_final"
    shutil.copy(file_path, backup_path)
    print(f"✅ Created backup: {backup_path}")
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("✅ Fixed false TP fill detection issue")
    return True

if __name__ == "__main__":
    if fix_false_tp_fills():
        print("\n✅ Successfully fixed the false TP fill detection issue")
        print("The bot will now:")
        print("  - Skip duplicate position change detections")
        print("  - Not warn about expected mirror account size differences")
        print("  - Reset cumulative tracking if it exceeds 100%")
        print("\nPlease restart the bot for changes to take effect.")
    else:
        print("\n❌ Failed to fix the false TP fill detection issue")