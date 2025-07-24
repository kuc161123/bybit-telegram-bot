#!/usr/bin/env python3
"""
Fix the syntax error in enhanced_tp_sl_manager.py
"""

def fix_syntax_error():
    print("\n🔧 FIXING SYNTAX ERROR")
    print("=" * 60)
    
    # Read the file
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        content = f.read()
    
    # Fix the syntax error around line 2821
    # The problem is a malformed line that was incorrectly split
    
    # Replace the problematic section
    problematic = '''already_tracked = any(tp["order_id"] == order_id # Handle both list and dict formats
            tp_orders_raw = monitor_data.get("tp_orders", [])
            if isinstance(tp_orders_raw, dict):
                tp_orders_list = list(tp_orders_raw.values())
            else:
                tp_orders_list = tp_orders_raw
            for tp in tp_orders_list)'''
    
    # Correct version
    correct = '''already_tracked = any(tp["order_id"] == order_id for tp in monitor_data.get("tp_orders", []))'''
    
    # Replace
    content = content.replace(problematic, correct)
    
    # Also check for other similar patterns
    # Fix any other occurrences where the conversion was incorrectly inserted
    import re
    
    # Pattern to find incorrectly split any() statements
    pattern = r'any\([^)]+# Handle both list and dict formats\s*\n\s*tp_orders_raw[^)]+\)'
    
    # Replace with simpler version
    def fix_any_statement(match):
        # Extract the comparison part
        text = match.group(0)
        if 'tp["order_id"] == order_id' in text:
            return 'any(tp["order_id"] == order_id for tp in monitor_data.get("tp_orders", []))'
        else:
            # Generic fix
            return 'any(tp in monitor_data.get("tp_orders", []))'
    
    content = re.sub(pattern, fix_any_statement, content, flags=re.DOTALL)
    
    # Write the fixed content
    with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
        f.write(content)
    
    print("✅ Fixed syntax error")
    
    # Verify the fix
    try:
        import ast
        ast.parse(content)
        print("✅ Python syntax is valid")
    except SyntaxError as e:
        print(f"⚠️  There may still be syntax errors: {e}")
        print(f"   Line {e.lineno}: {e.text}")
    
    print("\n✅ Syntax error should be fixed now!")
    print("You can start the bot with: ./start_bot_clean.sh")
    
    return True

if __name__ == "__main__":
    fix_syntax_error()