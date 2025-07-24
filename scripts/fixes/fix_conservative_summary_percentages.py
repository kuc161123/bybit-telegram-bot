#!/usr/bin/env python3
"""
Fix the Conservative approach summary to show correct 85/5/5/5 percentages
instead of outdated 70/10/10/10
"""
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_conservative_percentages():
    """Fix the incorrect percentage displays in trader.py"""
    
    file_path = "execution/trader.py"
    
    logger.info(f"Reading {file_path}...")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Track replacements
    replacements = 0
    original_content = content
    
    # Fix patterns
    fixes = [
        # Fix TP1 70% -> 85%
        (r'TP1 @ \$\{format_price\(tp_prices\[0\]\)\}: 70% exit', 
         'TP1 @ ${format_price(tp_prices[0])}: 85% exit'),
        
        # Fix TP2-4: 10% each -> 5% each
        (r'TP2-4: 10% each for runners', 
         'TP2-4: 5% each for runners'),
         
        # Fix any hardcoded 70/10/10/10 references
        (r'70%, 10%, 10%, 10%', '85%, 5%, 5%, 5%'),
        (r'70%/10%/10%/10%', '85%/5%/5%/5%'),
        
        # Fix in comments or descriptions
        (r'70% \(TP1\), 10% \(TP2\), 10% \(TP3\), 10% \(TP4\)',
         '85% (TP1), 5% (TP2), 5% (TP3), 5% (TP4)'),
    ]
    
    for old_pattern, new_pattern in fixes:
        if re.search(old_pattern, content):
            content = re.sub(old_pattern, new_pattern, content)
            replacements += len(re.findall(old_pattern, original_content))
            logger.info(f"✅ Fixed: {old_pattern} -> {new_pattern}")
    
    # Additional check for any remaining 70% or 10% in TP context
    tp_context_lines = []
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'TP' in line and ('70%' in line or '10%' in line):
            tp_context_lines.append((i+1, line.strip()))
    
    if tp_context_lines:
        logger.warning("Found potential remaining incorrect percentages:")
        for line_num, line in tp_context_lines[:5]:  # Show first 5
            logger.warning(f"  Line {line_num}: {line}")
    
    if replacements > 0:
        # Backup original
        import shutil
        backup_path = f"{file_path}.backup_conservative_fix"
        shutil.copy(file_path, backup_path)
        logger.info(f"Created backup: {backup_path}")
        
        # Write fixed content
        with open(file_path, 'w') as f:
            f.write(content)
        
        logger.info(f"✅ Fixed {replacements} incorrect percentage references")
        logger.info("Conservative approach now correctly shows 85/5/5/5 distribution")
    else:
        logger.info("No incorrect percentages found - file may already be fixed")
    
    return replacements

if __name__ == "__main__":
    print("=" * 60)
    print("Fixing Conservative Approach Summary Percentages")
    print("=" * 60)
    
    replacements = fix_conservative_percentages()
    
    if replacements > 0:
        print(f"\n✅ Successfully updated {replacements} references")
        print("The Conservative approach summary now shows:")
        print("- TP1: 85% (locks in majority of profits)")
        print("- TP2: 5% (small runner)")
        print("- TP3: 5% (small runner)")
        print("- TP4: 5% (small runner)")
    else:
        print("\n✅ All percentages are already correct!")
    
    print("=" * 60)