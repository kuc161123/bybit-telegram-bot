#!/usr/bin/env python3
"""
Fix to ensure all future conservative positions persist order IDs for alerts after restart
"""

import os
import shutil
from datetime import datetime

def apply_monitor_persistence_fix():
    """
    Apply fix to ensure conservative order IDs are stored in active_monitor_task_data_v2
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
    if "# FIX: Store conservative order IDs in monitor data for persistence" in content:
        print("✅ Fix already applied - future conservative positions will persist alerts!")
        return
    
    # Find where we need to insert the fix
    search_text = """    # Store monitoring info WITHOUT the task object (to prevent pickle errors)
    task_info = {
        "chat_id": chat_id,
        "symbol": symbol,
        "approach": approach,
        "active": True,
        "started_at": time.time(),
        "monitoring_mode": monitoring_mode
    }
    
    if ACTIVE_MONITOR_TASK not in chat_data:
        chat_data[ACTIVE_MONITOR_TASK] = {}
    
    chat_data[ACTIVE_MONITOR_TASK] = task_info"""
    
    replacement_text = """    # Store monitoring info WITHOUT the task object (to prevent pickle errors)
    task_info = {
        "chat_id": chat_id,
        "symbol": symbol,
        "approach": approach,
        "active": True,
        "started_at": time.time(),
        "monitoring_mode": monitoring_mode
    }
    
    if ACTIVE_MONITOR_TASK not in chat_data:
        chat_data[ACTIVE_MONITOR_TASK] = {}
    
    chat_data[ACTIVE_MONITOR_TASK] = task_info
    
    # FIX: Store conservative order IDs in monitor data for persistence
    # This ensures alerts work after bot restart for all conservative positions
    if ctx_app and hasattr(ctx_app, 'bot_data'):
        try:
            bot_data = ctx_app.bot_data
            chat_data_all = bot_data.get('chat_data', {})
            
            # Get or create chat data storage
            if chat_id not in chat_data_all:
                chat_data_all[chat_id] = {}
            stored_chat_data = chat_data_all[chat_id]
            
            # Get or create active_monitor_task_data_v2
            if 'active_monitor_task_data_v2' not in stored_chat_data:
                stored_chat_data['active_monitor_task_data_v2'] = {}
            
            # Create monitor key
            monitor_key = f"{chat_id}_{symbol}_{approach}"
            
            # Get or create monitor data
            monitor_data = stored_chat_data['active_monitor_task_data_v2'].get(monitor_key, {})
            monitor_data.update({
                'symbol': symbol,
                'side': chat_data.get(SIDE),
                'approach': approach,
                '_chat_id': chat_id
            })
            
            # Store conservative order IDs if this is a conservative position
            if approach == "conservative":
                # Transfer limit order IDs
                limit_ids = chat_data.get(LIMIT_ORDER_IDS, [])
                if limit_ids:
                    monitor_data['conservative_limit_order_ids'] = limit_ids
                    logger.info(f"✅ Stored {len(limit_ids)} limit order IDs for future persistence")
                
                # Transfer TP order IDs
                tp_ids = chat_data.get(CONSERVATIVE_TP_ORDER_IDS, [])
                if tp_ids:
                    monitor_data['conservative_tp_order_ids'] = tp_ids
                    logger.info(f"✅ Stored {len(tp_ids)} TP order IDs for future persistence")
                
                # Transfer SL order ID
                sl_id = chat_data.get(CONSERVATIVE_SL_ORDER_ID)
                if sl_id:
                    monitor_data['conservative_sl_order_id'] = sl_id
                    logger.info(f"✅ Stored SL order ID for future persistence")
            
            # Store the updated monitor data
            stored_chat_data['active_monitor_task_data_v2'][monitor_key] = monitor_data
            chat_data_all[chat_id] = stored_chat_data
            bot_data['chat_data'] = chat_data_all
            
            logger.info(f"✅ Conservative order IDs stored in active_monitor_task_data_v2 for {symbol}")
        except Exception as e:
            logger.error(f"Error storing conservative order IDs: {e}")"""
    
    if search_text in content:
        content = content.replace(search_text, replacement_text)
        
        # Write the updated content
        with open(monitor_file, 'w') as f:
            f.write(content)
        
        print("✅ Applied fix to monitor.py!")
        print("\n📌 WHAT THIS FIX DOES:")
        print("• Stores conservative order IDs in active_monitor_task_data_v2")
        print("• This data persists in the pickle file across restarts")
        print("• On restart, monitors will have the order IDs to track")
        print("• Alerts will work immediately for all conservative positions")
        print("\n🎉 ALL FUTURE CONSERVATIVE POSITIONS WILL HAVE PERSISTENT ALERTS!")
    else:
        print("❌ Could not find the exact location to apply the fix")
        print("The code structure may have changed")

def main():
    print("🔧 Applying fix for future conservative position persistence...")
    print("="*60)
    
    apply_monitor_persistence_fix()
    
    print("\n📌 IMPORTANT: Restart the bot for this fix to take effect")
    print("After restart, all new conservative positions will:")
    print("  ✅ Store order IDs in persistent storage")
    print("  ✅ Restore monitors with alerts on bot restart")
    print("  ✅ Send alerts for limit fills, TP hits, and SL hits")

if __name__ == "__main__":
    main()