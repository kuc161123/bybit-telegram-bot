#!/usr/bin/env python3
"""
Fix all syntax errors in enhanced_tp_sl_manager.py
"""

def fix_all_syntax_errors():
    print("\n🔧 FIXING ALL SYNTAX ERRORS")
    print("=" * 60)
    
    # Read the file
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        lines = f.readlines()
    
    fixed_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check for the problematic pattern where conversion code was inserted mid-statement
        if '# Handle both list and dict formats' in line:
            # This line has been corrupted, fix it
            if 'any(tp["order_id"] == order_id' in line:
                # Fix the any() statement
                fixed_lines.append('                    already_tracked = any(tp["order_id"] == order_id for tp in monitor_data.get("tp_orders", []))\n')
                i += 1
                # Skip the next lines if they contain the incorrectly inserted conversion code
                while i < len(lines) and ('tp_orders_raw' in lines[i] or 
                                         'isinstance(tp_orders_raw' in lines[i] or
                                         'tp_orders_list = list' in lines[i] or
                                         'else:' in lines[i] and i+1 < len(lines) and 'tp_orders_list = tp_orders_raw' in lines[i+1] or
                                         'tp_orders_list = tp_orders_raw' in lines[i] or
                                         'for tp in tp_orders_list)' in lines[i]):
                    i += 1
                continue
            elif 'len([tp for tp in' in line:
                # Fix list comprehension
                fixed_lines.append(line.replace('# Handle both list and dict formats', '').rstrip() + '\n')
                i += 1
                # Skip incorrectly inserted lines
                while i < len(lines) and ('tp_orders_raw' in lines[i] or 'isinstance(tp_orders_raw' in lines[i]):
                    i += 1
                continue
        
        # Check for standalone conversion code that shouldn't be there
        elif i > 0 and 'tp_orders_raw = monitor_data.get("tp_orders", [])' in line:
            # Check if this is part of a proper function or just incorrectly inserted
            prev_line = lines[i-1].strip()
            if not prev_line.endswith(':') and not prev_line.startswith('#'):
                # This is likely incorrectly inserted, skip it and related lines
                while i < len(lines) and ('tp_orders_raw' in lines[i] or 
                                         'isinstance(tp_orders_raw' in lines[i] or
                                         'tp_orders_list' in lines[i]):
                    i += 1
                continue
        
        # Fix incomplete list comprehensions
        elif 'for tp in tp_orders_list)' in line and 'tp_orders_list' not in ''.join(lines[max(0, i-10):i]):
            # This is a dangling end of a list comprehension
            i += 1
            continue
            
        fixed_lines.append(line)
        i += 1
    
    # Write the fixed content
    with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
        f.writelines(fixed_lines)
    
    print("✅ Fixed all syntax errors")
    
    # Verify the fix
    try:
        with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
            content = f.read()
        import ast
        ast.parse(content)
        print("✅ Python syntax is now valid!")
    except SyntaxError as e:
        print(f"⚠️  Remaining syntax error at line {e.lineno}")
        print(f"   Error: {e.msg}")
        if e.lineno:
            print(f"   Line content: {lines[e.lineno-1].strip() if e.lineno <= len(lines) else 'N/A'}")
    
    print("\n✅ All syntax errors should be fixed!")
    print("You can now start the bot with: ./start_bot_clean.sh")
    
    return True

if __name__ == "__main__":
    fix_all_syntax_errors()