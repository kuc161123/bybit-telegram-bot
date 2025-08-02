#!/usr/bin/env python3
"""
Comprehensive fix for all syntax errors
"""

def comprehensive_fix():
    print("\n🔧 COMPREHENSIVE SYNTAX FIX")
    print("=" * 60)
    
    # Read the file
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        content = f.read()
    
    # Fix 1: Replace all occurrences of the corrupted pattern
    import re
    
    # Pattern 1: Fix broken list comprehensions with inserted conversion code
    pattern1 = r'len\(\[tp # Handle both list and dict formats\s*\n\s*else:\s*\n\s*tp_orders_list = tp_orders_raw\s*\n\s*for tp in tp_orders_list'
    replacement1 = 'len([tp for tp in monitor_data.get("tp_orders", [])'
    content = re.sub(pattern1, replacement1, content, flags=re.MULTILINE | re.DOTALL)
    
    # Pattern 2: Fix broken any() statements
    pattern2 = r'any\(tp\["order_id"\] == order_id # Handle both list and dict formats.*?for tp in tp_orders_list\)'
    replacement2 = 'any(tp["order_id"] == order_id for tp in monitor_data.get("tp_orders", []))'
    content = re.sub(pattern2, replacement2, content, flags=re.MULTILINE | re.DOTALL)
    
    # Pattern 3: Remove standalone tp_orders_raw declarations that are out of place
    pattern3 = r'\n\s*tp_orders_raw = monitor_data\.get\("tp_orders", \[\]\)\s*\n\s*if isinstance\(tp_orders_raw, dict\):\s*\n\s*tp_orders_list = list\(tp_orders_raw\.values\(\)\)\s*\n\s*else:\s*\n\s*tp_orders_list = tp_orders_raw\s*\n'
    content = re.sub(pattern3, '\n', content, flags=re.MULTILINE)
    
    # Pattern 4: Fix specific line 3430 issue
    # Find and fix the specific corrupted list comprehension
    lines = content.split('\n')
    fixed_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check for the specific pattern around line 3430
        if 'active_tps = len([tp # Handle both list and dict formats' in line:
            # Fix this line
            fixed_lines.append('            active_tps = len([tp for tp in monitor_data.get("tp_orders", []) if tp.get("status") != "FILLED"])')
            # Skip the corrupted following lines
            i += 1
            while i < len(lines) and ('else:' in lines[i] or 'tp_orders_list' in lines[i] or 'for tp in tp_orders_list' in lines[i]):
                i += 1
            continue
        
        # Check for other corrupted patterns
        elif '# Handle both list and dict formats' in line and not line.strip().startswith('#'):
            # This is a corrupted line, try to fix it
            if 'len([' in line:
                # Fix list comprehension
                base = line.split('# Handle both list and dict formats')[0]
                fixed_lines.append(base + 'for tp in monitor_data.get("tp_orders", [])])')
                # Skip following corrupted lines
                i += 1
                while i < len(lines) and ('tp_orders' in lines[i] or 'for tp in' in lines[i]):
                    i += 1
                continue
        
        fixed_lines.append(line)
        i += 1
    
    # Join back
    content = '\n'.join(fixed_lines)
    
    # Final cleanup: Remove any remaining standalone conversion blocks
    content = re.sub(r'\n\s*# Handle both list and dict formats\s*\n', '\n', content)
    
    # Write the fixed content
    with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
        f.write(content)
    
    print("✅ Applied comprehensive fixes")
    
    # Verify the fix
    try:
        import ast
        ast.parse(content)
        print("✅ Python syntax is now valid!")
        print("\n🎉 ALL SYNTAX ERRORS FIXED!")
    except SyntaxError as e:
        print(f"\n⚠️  Still has syntax error at line {e.lineno}")
        print(f"   Error: {e.msg}")
        # Try to show the problematic line
        lines = content.split('\n')
        if e.lineno and e.lineno <= len(lines):
            print(f"   Line {e.lineno}: {lines[e.lineno-1]}")
            print(f"   Previous line: {lines[e.lineno-2] if e.lineno > 1 else 'N/A'}")
    
    return True

if __name__ == "__main__":
    comprehensive_fix()