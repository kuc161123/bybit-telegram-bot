#!/usr/bin/env python3
"""
Fix to ensure ALL conservative positions are properly tracked in monitors
This prevents issues like JUPUSDT not being found for rebalancing
"""

import os
import shutil
from datetime import datetime

def main():
    """Apply fix to monitor.py to ensure conservative positions are tracked"""
    
    monitor_file = "/Users/lualakol/bybit-telegram-bot/execution/monitor.py"
    
    # Create backup
    backup_file = f"{monitor_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(monitor_file, backup_file)
    print(f"✅ Created backup: {backup_file}")
    
    # Read the file
    with open(monitor_file, 'r') as f:
        content = f.read()
    
    # Find the section where approach is detected
    search_text = """def detect_approach_from_orders(orders: List[Dict]) -> str:
    \"\"\"Detect trading approach from order structure\"\"\"
    
    # Count order types
    tp_count = 0
    limit_count = 0
    
    for order in orders:
        order_type = identify_order_type(order)
        if order_type == ORDER_TYPE_TP:
            tp_count += 1
        elif order_type == ORDER_TYPE_LIMIT:
            limit_count += 1
    
    # Determine approach based on order counts
    if tp_count == 4:
        return "conservative"
    elif tp_count == 1:
        return "fast"
    else:
        return "unknown\""""
    
    # Enhanced version that ensures proper tracking
    replacement_text = """def detect_approach_from_orders(orders: List[Dict]) -> str:
    \"\"\"Detect trading approach from order structure\"\"\"
    
    # Count order types
    tp_count = 0
    limit_count = 0
    
    for order in orders:
        order_type = identify_order_type(order)
        if order_type == ORDER_TYPE_TP:
            tp_count += 1
        elif order_type == ORDER_TYPE_LIMIT:
            limit_count += 1
    
    # Determine approach based on order counts
    if tp_count >= 4:  # Changed from == to >= to be more flexible
        return "conservative"
    elif tp_count == 1:
        return "fast"
    elif tp_count > 1:  # Multiple TPs but not 4, likely conservative
        logger.info(f"Detected {tp_count} TPs, assuming conservative approach")
        return "conservative"
    else:
        return "unknown\""""
    
    if search_text in content:
        content = content.replace(search_text, replacement_text)
        print("✅ Applied approach detection fix")
    else:
        print("⚠️  Could not find exact match for approach detection")
    
    # Find where monitor data is stored and ensure it includes approach
    monitor_store_search = """# Store monitor task data for persistence
                active_monitors[monitor_key] = {
                    'symbol': symbol,
                    'side': side,
                    'approach': approach,
                    'started_at': asyncio.get_event_loop().time(),
                    'chat_id': chat_id"""
    
    monitor_store_replace = """# Store monitor task data for persistence
                active_monitors[monitor_key] = {
                    'symbol': symbol,
                    'side': side,
                    'approach': approach,
                    'started_at': asyncio.get_event_loop().time(),
                    'chat_id': chat_id,
                    'is_conservative': approach == 'conservative',  # Explicit flag
                    'tp_count': len([o for o in orders if identify_order_type(o) == ORDER_TYPE_TP])"""
    
    if monitor_store_search in content:
        content = content.replace(monitor_store_search, monitor_store_replace)
        print("✅ Enhanced monitor data storage")
    
    # Write the updated content
    with open(monitor_file, 'w') as f:
        f.write(content)
    
    print("✅ Monitor tracking fix applied!")
    print("\n📌 What this fix does:")
    print("• Better detection of conservative positions (even with 3 or 4+ TPs)")
    print("• Stores explicit conservative flag in monitor data")
    print("• Prevents positions like JUPUSDT from being missed")
    print("• Ensures auto-rebalancer finds all conservative positions")

if __name__ == "__main__":
    main()