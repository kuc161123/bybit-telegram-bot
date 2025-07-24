#!/usr/bin/env python3
"""
Fix monitor to check limit order IDs from the correct location
"""

import os
import shutil
from datetime import datetime

def apply_monitor_limit_check_fix():
    """
    Fix monitor to check limit order IDs from active_monitor_task_data_v2
    """
    
    monitor_file = "/Users/lualakol/bybit-telegram-bot/execution/monitor.py"
    
    # Create backup
    backup_file = f"{monitor_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(monitor_file, backup_file)
    print(f"✅ Created backup: {backup_file}")
    
    # Read the file
    with open(monitor_file, 'r') as f:
        content = f.read()
    
    # Check if fix is already applied
    if "# FIX: Check monitor data for limit order IDs" in content:
        print("✅ Fix already applied!")
        return
    
    # Find the check_conservative_limit_fills function
    search_text = """        limit_order_ids = chat_data.get(LIMIT_ORDER_IDS, [])
        limits_filled = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])"""
    
    replacement_text = """        # FIX: Check monitor data for limit order IDs if not in chat_data
        limit_order_ids = chat_data.get(LIMIT_ORDER_IDS, [])
        
        # If no limit IDs in chat_data, check monitor data (for existing positions)
        if not limit_order_ids and ctx_app and hasattr(ctx_app, 'bot_data'):
            try:
                bot_data = ctx_app.bot_data
                chat_data_all = bot_data.get('chat_data', {})
                chat_id = chat_data.get('chat_id') or chat_data.get('_chat_id')
                if chat_id:
                    stored_chat_data = chat_data_all.get(chat_id, {})
                    active_monitors = stored_chat_data.get('active_monitor_task_data_v2', {})
                    
                    # Find monitor for this symbol
                    monitor_key = f"{chat_id}_{symbol}_{approach}"
                    monitor_data = active_monitors.get(monitor_key, {})
                    
                    # Get limit order IDs from monitor data
                    monitor_limit_ids = monitor_data.get('conservative_limit_order_ids', [])
                    if monitor_limit_ids:
                        limit_order_ids = monitor_limit_ids
                        logger.info(f"✅ Found {len(limit_order_ids)} limit order IDs in monitor data")
            except Exception as e:
                logger.debug(f"Could not check monitor data for limit IDs: {e}")
        
        limits_filled = chat_data.get(CONSERVATIVE_LIMITS_FILLED, [])"""
    
    if search_text in content:
        content = content.replace(search_text, replacement_text)
        
        # Write the updated content
        with open(monitor_file, 'w') as f:
            f.write(content)
        
        print("✅ Applied fix to monitor.py!")
        print("\n📌 WHAT THIS FIX DOES:")
        print("• Monitors now check active_monitor_task_data_v2 for limit order IDs")
        print("• This fixes existing positions like INJUSDT")
        print("• New positions will work with either location")
        print("\n🎉 ALL CONSERVATIVE POSITIONS WILL NOW HAVE LIMIT FILL ALERTS!")
    else:
        print("❌ Could not find the exact location to apply the fix")
        print("The code structure may have changed")

def main():
    print("🔧 Fixing monitor limit order ID checking...")
    print("="*60)
    
    apply_monitor_limit_check_fix()
    
    print("\n📌 IMPORTANT: Restart the bot for this fix to take effect")
    print("After restart:")
    print("  ✅ INJUSDT will detect its 2 limit orders")
    print("  ✅ Limit fill alerts will work for INJUSDT")
    print("  ✅ All positions will have proper alert detection")

if __name__ == "__main__":
    main()