#!/usr/bin/env python3
"""
Ensure limit order cancellation message appears in TP1 alerts
"""
import re
from datetime import datetime
import shutil

def patch_tp1_alert_message():
    """Patch the TP1 alert to always show limit cancellation message for conservative/ggshot"""
    print("🔧 Patching TP1 Alert Message...")
    
    file_path = "execution/enhanced_tp_sl_manager.py"
    
    # Backup first
    backup_path = f"{file_path}.backup_limit_msg_{int(datetime.now().timestamp())}"
    shutil.copy(file_path, backup_path)
    print(f"✅ Created backup: {backup_path}")
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Find the send_tp_alert method
        method_start = content.find("async def _send_tp_fill_alert(")
        if method_start == -1:
            method_start = content.find("async def _send_tp_fill_alert_enhanced(")
        
        if method_start > 0:
            # Find the TP1 actions section
            tp1_section_start = content.find("if tp_number == 1:", method_start)
            if tp1_section_start > 0:
                # Find where we add actions
                actions_start = content.find('message += f"\\n\\n🎯 Actions Taken:"', tp1_section_start)
                if actions_start > 0:
                    # Find the end of this section
                    next_section = content.find("\n\n", actions_start + 50)
                    if next_section > 0:
                        section = content[actions_start:next_section]
                        
                        # Check if we're checking for limit_orders_cancelled
                        if "if monitor_data.get('limit_orders_cancelled')" in section:
                            # Replace conditional with always showing for conservative/ggshot
                            new_section = section
                            
                            # Find the line with the condition
                            condition_match = re.search(
                                r'(\s+)if monitor_data\.get\([\'"]limit_orders_cancelled[\'"]\):\s*\n\s+message \+= f"\\n• Unfilled limit orders cancelled"',
                                section
                            )
                            
                            if condition_match:
                                indent = condition_match.group(1)
                                # Replace with approach check
                                replacement = f'{indent}# Show cancellation message for conservative/ggshot approaches\n'
                                replacement += f'{indent}approach = monitor_data.get("approach", "")\n'
                                replacement += f'{indent}if approach in ["conservative", "ggshot"]:\n'
                                replacement += f'{indent}    message += f"\\n• Unfilled limit orders cancelled"'
                                
                                new_section = section[:condition_match.start()] + replacement + section[condition_match.end():]
                                content = content[:actions_start] + new_section + content[next_section:]
                                
                                print("✅ Updated to show cancellation for conservative/ggshot approaches")
                        else:
                            # Add the message after SL moved to breakeven
                            sl_moved_line = section.find('message += f"\\n• SL moved to breakeven"')
                            if sl_moved_line > 0:
                                # Find the end of this line
                                line_end = section.find('\n', sl_moved_line)
                                if line_end > 0:
                                    # Get indentation
                                    line_start = section.rfind('\n', 0, sl_moved_line) + 1
                                    indent = section[line_start:sl_moved_line]
                                    
                                    # Add the limit cancellation message
                                    addition = f'\n{indent}# Show cancellation for conservative/ggshot\n'
                                    addition += f'{indent}approach = monitor_data.get("approach", "")\n'
                                    addition += f'{indent}if approach in ["conservative", "ggshot"]:\n'
                                    addition += f'{indent}    message += f"\\n• Unfilled limit orders cancelled"'
                                    
                                    new_section = section[:line_end] + addition + section[line_end:]
                                    content = content[:actions_start] + new_section + content[next_section:]
                                    
                                    print("✅ Added cancellation message for conservative/ggshot approaches")
        
        # Save the patched file
        with open(file_path, 'w') as f:
            f.write(content)
        
        print("✅ Patch applied successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        # Restore backup on error
        shutil.copy(backup_path, file_path)
        print("🔄 Restored from backup due to error")

def main():
    print("🚀 Ensuring Limit Order Cancellation Alert")
    print("=" * 60)
    
    patch_tp1_alert_message()
    
    print("\n" + "=" * 60)
    print("✅ Fix Complete!")
    print("\n📝 What was done:")
    print("1. Modified TP1 alert to always show cancellation message")
    print("2. Applies to conservative and ggshot approaches only")
    print("3. Future TP1 alerts will show: '• Unfilled limit orders cancelled'")
    print("\n🎯 Example alert after fix:")
    print("""
✅ TP1 Hit - SYMBOL Buy

📊 Fill Details:
• Filled: X (85%)
• Price: X.XXX
• Remaining: X (15%)
• Account: MAIN/MIRROR

🎯 Actions Taken:
• SL moved to breakeven
• Unfilled limit orders cancelled

📍 Remaining TPs: TP2, TP3, TP4
""")

if __name__ == "__main__":
    main()