#!/usr/bin/env python3
"""
Fix Conservative Trade Summary Messages
Updates all references from old 70/10/10/10 to new 85/5/5/5 distribution
"""

import re
import os

def fix_conservative_messages():
    """Update all conservative trade summary messages to show correct TP distribution"""
    
    file_path = "execution/trader.py"
    
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found")
        return
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Track changes
    changes_made = []
    
    # Fix 1: Update the TP1 percentage display in logical breakdown (line ~2078)
    old_pattern1 = r'logical_breakdown \+= f"  - TP1 @ \$\{format_price\(tp_prices\[0\]\)\}: 70% exit\\n"'
    new_pattern1 = 'logical_breakdown += f"  - TP1 @ ${format_price(tp_prices[0])}: 85% exit\\n"'
    if old_pattern1 in content:
        content = content.replace(
            'logical_breakdown += f"  - TP1 @ ${format_price(tp_prices[0])}: 70% exit\\n"',
            'logical_breakdown += f"  - TP1 @ ${format_price(tp_prices[0])}: 85% exit\\n"'
        )
        changes_made.append("Updated TP1 from 70% to 85% in logical breakdown")
    
    # Fix 2: Update the TP2-4 percentage display (line ~2079)
    old_pattern2 = 'logical_breakdown += f"  - TP2-4: 10% each for runners\\n"'
    new_pattern2 = 'logical_breakdown += f"  - TP2-4: 5% each for runners\\n"'
    if old_pattern2 in content:
        content = content.replace(old_pattern2, new_pattern2)
        changes_made.append("Updated TP2-4 from 10% each to 5% each")
    
    # Fix 3: Update merge message TP1 display (line ~3657)
    if 'logical_breakdown += f"  - TP1 @ ${format_price(tp[\'price\'])}: 70% exit (primary)\\n"' in content:
        content = content.replace(
            'logical_breakdown += f"  - TP1 @ ${format_price(tp[\'price\'])}: 70% exit (primary)\\n"',
            'logical_breakdown += f"  - TP1 @ ${format_price(tp[\'price\'])}: 85% exit (primary)\\n"'
        )
        changes_made.append("Updated merge TP1 from 70% to 85%")
    
    # Fix 4: Update merge message TP2-4 display (line ~3659)
    old_tp_other = 'logical_breakdown += f"  - TP{i} @ ${format_price(tp[\'price\'])}: 10% exit (runner)\\n"'
    new_tp_other = 'logical_breakdown += f"  - TP{i} @ ${format_price(tp[\'price\'])}: 5% exit (runner)\\n"'
    if old_tp_other in content:
        content = content.replace(old_tp_other, new_tp_other)
        changes_made.append("Updated merge TP2-4 from 10% to 5%")
    
    # Fix 5: Update gradual profit taking description (line ~3680)
    old_gradual = 'logical_breakdown += f"  - Gradual profit taking (70/10/10/10)\\n"'
    new_gradual = 'logical_breakdown += f"  - Gradual profit taking (85/5/5/5)\\n"'
    if old_gradual in content:
        content = content.replace(old_gradual, new_gradual)
        changes_made.append("Updated gradual profit taking from 70/10/10/10 to 85/5/5/5")
    
    # Fix 6: Update preserved TP levels message (line ~3721)
    old_preserved = 'message += "• Multiple TP levels preserved (70/10/10/10%)\\n"'
    new_preserved = 'message += "• Multiple TP levels preserved (85/5/5/5%)\\n"'
    if old_preserved in content:
        content = content.replace(old_preserved, new_preserved)
        changes_made.append("Updated preserved TP levels from 70/10/10/10 to 85/5/5/5")
    
    # Fix 7: Update the hardcoded TP percentage in position merge (line ~3039)
    # This needs to be updated to use the actual percentages
    old_tp_dict = "{'price': tp_prices[0], 'percentage': 70}"
    new_tp_dict = "{'price': tp_prices[0], 'percentage': 85}"
    if old_tp_dict in content:
        content = content.replace(old_tp_dict, new_tp_dict)
        changes_made.append("Updated TP1 percentage in merge from 70 to 85")
    
    # Fix 8: Add actual TP percentages to the position details display
    # Look for where tp_details are being formatted and ensure they show correct percentages
    
    # Write the updated content back
    if changes_made:
        # Backup original file
        with open(file_path + '.backup', 'w') as f:
            with open(file_path, 'r') as original:
                f.write(original.read())
        
        # Write updated content
        with open(file_path, 'w') as f:
            f.write(content)
        
        print(f"✅ Successfully updated {file_path}")
        print(f"\nChanges made ({len(changes_made)}):")
        for change in changes_made:
            print(f"  • {change}")
        print(f"\n📁 Backup saved to: {file_path}.backup")
    else:
        print("❌ No changes needed - patterns not found or already updated")
    
    # Additional recommendation
    print("\n💡 Recommendation:")
    print("Consider using the enhanced summary function from enhanced_conservative_summary.py")
    print("for a more comprehensive and accurate trade summary display.")


def check_current_values():
    """Check current TP percentage values in the code"""
    
    file_path = "execution/trader.py"
    
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found")
        return
    
    print("🔍 Checking current TP percentage references...\n")
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Find all references to TP percentages
    for i, line in enumerate(lines, 1):
        if any(pattern in line for pattern in ['70%', '10%', '85%', '5%', 'tp_percentages']):
            if 'tp_percentages = [0.85, 0.05, 0.05, 0.05]' in line:
                print(f"✅ Line {i}: Correct implementation - {line.strip()}")
            elif '70' in line or '10%' in line:
                print(f"❌ Line {i}: Outdated reference - {line.strip()}")
            elif '85' in line or '5%' in line:
                print(f"✅ Line {i}: Updated reference - {line.strip()}")


if __name__ == "__main__":
    print("Conservative Trade Summary Message Fixer")
    print("=" * 50)
    
    # First check current values
    check_current_values()
    
    print("\n" + "=" * 50)
    print("\n🔧 Applying fixes...\n")
    
    # Apply fixes
    fix_conservative_messages()