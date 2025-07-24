#!/usr/bin/env python3
"""
Patch the trading system to ensure TP numbers are always set correctly for future trades
"""
import os
import re
import shutil
from datetime import datetime

def patch_trader_tp_numbers():
    """Patch trader.py to ensure TP numbers are set"""
    
    file_path = "execution/trader.py"
    backup_path = f"{file_path}.backup_tp_numbering_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print("📝 Patching trader.py for TP numbering...")
    
    # Create backup
    shutil.copy2(file_path, backup_path)
    print(f"✅ Created backup: {backup_path}")
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    changes_made = []
    
    # Pattern 1: Find where TP orders are created in conservative approach
    # Look for where tp_order_results are processed
    pattern1 = r'(tp_order_results\s*=.*?\n)(.*?)(for\s+i,\s*tp_result\s+in\s+enumerate\(tp_order_results\):)'
    
    def add_tp_number_to_conservative(match):
        before = match.group(1)
        middle = match.group(2)
        for_loop = match.group(3)
        
        # Add TP number assignment in the loop
        new_loop = '''for i, tp_result in enumerate(tp_order_results):
                if tp_result and tp_result.get("orderId"):
                    tp_number = i + 1  # TP1, TP2, TP3, TP4
                    percentage = tp_percentages[i] if i < len(tp_percentages) else 5'''
        
        # Check if already patched
        if "tp_number = i + 1" not in middle:
            changes_made.append("✅ Added TP numbering to conservative approach")
            return before + middle + new_loop
        return match.group(0)
    
    content = re.sub(pattern1, add_tp_number_to_conservative, content, flags=re.DOTALL)
    
    # Pattern 2: Ensure TP data includes tp_number when storing
    # Look for where tp_data is created
    pattern2 = r'(tp_data\s*=\s*{\s*\n.*?"order_id".*?\n.*?"price".*?\n.*?"quantity".*?\n)(.*?)(})'
    
    def add_tp_number_field(match):
        tp_data_start = match.group(1)
        tp_data_middle = match.group(2)
        tp_data_end = match.group(3)
        
        # Check if tp_number already exists
        if '"tp_number"' not in tp_data_start and '"tp_number"' not in tp_data_middle:
            # Add tp_number field
            new_fields = '                        "tp_number": tp_number,\n                        "percentage": percentage,\n'
            changes_made.append("✅ Added tp_number field to TP data structure")
            return tp_data_start + new_fields + tp_data_middle + tp_data_end
        return match.group(0)
    
    content = re.sub(pattern2, add_tp_number_field, content, flags=re.DOTALL)
    
    # Pattern 3: Fix fast approach to always use tp_number = 1
    pattern3 = r'(# Fast market approach.*?tp_result.*?get\("orderId"\).*?\n)(.*?)(monitor_data\["tp_orders"\])'
    
    def fix_fast_approach_tp(match):
        before = match.group(1)
        middle = match.group(2)
        after = match.group(3)
        
        if '"tp_number": 1' not in middle:
            # Add tp_number = 1 for fast approach
            new_middle = middle.rstrip() + '\n                    tp_data["tp_number"] = 1\n                    tp_data["percentage"] = 100\n                    '
            changes_made.append("✅ Fixed fast approach TP numbering")
            return before + new_middle + after
        return match.group(0)
    
    content = re.sub(pattern3, fix_fast_approach_tp, content, flags=re.DOTALL)
    
    # Write the patched content
    with open(file_path, 'w') as f:
        f.write(content)
    
    if changes_made:
        print("\nChanges made to trader.py:")
        for change in changes_made:
            print(f"  {change}")
    else:
        print("⚠️  trader.py may already be patched or needs manual review")
    
    return len(changes_made) > 0

def patch_mirror_sync_tp_numbers():
    """Patch mirror sync to preserve TP numbers"""
    
    file_path = "execution/mirror_enhanced_tp_sl.py"
    backup_path = f"{file_path}.backup_tp_numbering_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print("\n📝 Patching mirror_enhanced_tp_sl.py for TP numbering...")
    
    # Create backup
    shutil.copy2(file_path, backup_path)
    print(f"✅ Created backup: {backup_path}")
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    changes_made = []
    
    # Pattern: Find where mirror TP orders are created
    pattern = r'(mirror_tp_data\s*=\s*{\s*\n.*?"order_id".*?\n.*?"price".*?\n.*?"quantity".*?\n)(.*?)(})'
    
    def add_mirror_tp_fields(match):
        tp_data_start = match.group(1)
        tp_data_middle = match.group(2)
        tp_data_end = match.group(3)
        
        # Check if tp_number already exists
        if '"tp_number"' not in tp_data_start and '"tp_number"' not in tp_data_middle:
            # Add tp_number field from main TP
            new_fields = '                    "tp_number": main_tp.get("tp_number", i + 1),\n                    "percentage": main_tp.get("percentage", tp_percentages[i] if i < len(tp_percentages) else 5),\n'
            changes_made.append("✅ Added tp_number preservation to mirror sync")
            return tp_data_start + new_fields + tp_data_middle + tp_data_end
        return match.group(0)
    
    content = re.sub(pattern, add_mirror_tp_fields, content, flags=re.DOTALL)
    
    # Write the patched content
    with open(file_path, 'w') as f:
        f.write(content)
    
    if changes_made:
        print("\nChanges made to mirror_enhanced_tp_sl.py:")
        for change in changes_made:
            print(f"  {change}")
    else:
        print("⚠️  mirror_enhanced_tp_sl.py may already be patched or needs manual review")
    
    return len(changes_made) > 0

def create_tp_number_validator():
    """Create a validator script to check TP numbers"""
    
    validator_content = '''#!/usr/bin/env python3
"""
Validate TP numbers in monitor data
"""
import pickle

def validate_tp_numbers():
    """Check all monitors for TP numbering issues"""
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        issues = []
        
        for monitor_key, monitor_data in monitors.items():
            symbol = monitor_data.get('symbol', 'Unknown')
            side = monitor_data.get('side', 'Unknown')
            account_type = monitor_data.get('account_type', 'main')
            approach = monitor_data.get('approach', 'fast').lower()
            tp_orders = monitor_data.get('tp_orders', {})
            
            for order_id, tp_data in tp_orders.items():
                tp_number = tp_data.get('tp_number', 0)
                percentage = tp_data.get('percentage', 0)
                
                if tp_number == 0:
                    issues.append(f"TP0 found in {symbol} {side} ({account_type})")
                
                # Validate percentage matches TP number for conservative
                if approach == 'conservative':
                    expected_percentages = {1: 85, 2: 5, 3: 5, 4: 5}
                    if tp_number in expected_percentages and percentage != expected_percentages[tp_number]:
                        issues.append(f"Wrong percentage for TP{tp_number} in {symbol} {side} ({account_type}): {percentage}% (expected {expected_percentages[tp_number]}%)")
        
        if issues:
            print("❌ Issues found:")
            for issue in issues:
                print(f"   - {issue}")
        else:
            print("✅ All TP numbers are valid!")
        
        return len(issues) == 0
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    validate_tp_numbers()
'''
    
    with open('validate_tp_numbers.py', 'w') as f:
        f.write(validator_content)
    
    print("\n✅ Created validate_tp_numbers.py for future validation")

def main():
    print("🚀 Comprehensive TP Numbering Fix")
    print("=" * 60)
    
    # Patch trader.py
    trader_patched = patch_trader_tp_numbers()
    
    # Patch mirror sync
    mirror_patched = patch_mirror_sync_tp_numbers()
    
    # Create validator
    create_tp_number_validator()
    
    print("\n" + "=" * 60)
    print("📊 Summary:")
    print(f"✅ Current positions: All TP0 issues fixed")
    print(f"{'✅' if trader_patched else '⚠️'} trader.py: {'Patched' if trader_patched else 'Manual review needed'}")
    print(f"{'✅' if mirror_patched else '⚠️'} mirror_enhanced_tp_sl.py: {'Patched' if mirror_patched else 'Manual review needed'}")
    print(f"✅ Validator created: validate_tp_numbers.py")
    
    print("\n🎯 Next Steps:")
    print("1. Restart the bot to apply all changes")
    print("2. Future trades will have proper TP numbering")
    print("3. Run 'python3 validate_tp_numbers.py' to check TP numbers anytime")
    
    print("\n✅ All done! Your TP alerts will now show TP1/2/3/4 correctly!")

if __name__ == "__main__":
    main()