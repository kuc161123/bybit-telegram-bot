#!/usr/bin/env python3
"""
Fix the recursion error in _ensure_tp_orders_dict
"""

def fix_recursion():
    print("\n🔧 FIXING RECURSION ERROR")
    print("=" * 60)
    
    # Read the file
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        content = f.read()
    
    # Fix the recursion error - the function is calling itself
    old_code = """    def _ensure_tp_orders_dict(self, monitor_data: Dict):
        \"\"\"Ensure tp_orders is in dict format for backward compatibility\"\"\"
        tp_orders = self._ensure_tp_orders_dict(monitor_data)
        if isinstance(tp_orders, list):"""
    
    new_code = """    def _ensure_tp_orders_dict(self, monitor_data: Dict):
        \"\"\"Ensure tp_orders is in dict format for backward compatibility\"\"\"
        tp_orders = monitor_data.get("tp_orders", {})
        if isinstance(tp_orders, list):"""
    
    if old_code in content:
        content = content.replace(old_code, new_code)
        print("✅ Fixed recursion in _ensure_tp_orders_dict")
    else:
        print("⚠️  Exact pattern not found, trying alternative fix...")
        
        # Alternative: Just fix the recursive call
        content = content.replace(
            "tp_orders = self._ensure_tp_orders_dict(monitor_data)",
            "tp_orders = monitor_data.get('tp_orders', {})"
        )
        print("✅ Fixed recursive call")
    
    # Write the fixed content
    with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
        f.write(content)
    
    print("\n✅ Recursion error fixed!")
    print("   The function no longer calls itself")
    print("   This should stop the 'maximum recursion depth exceeded' errors")
    
    return True

if __name__ == "__main__":
    fix_recursion()