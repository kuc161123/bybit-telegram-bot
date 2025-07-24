#!/usr/bin/env python3
"""
Direct fix to add INJUSDT limit order IDs to chat_data
"""

import pickle
from datetime import datetime
import os

def main():
    # Load the bot data
    persistence_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    
    try:
        with open(persistence_file, 'rb') as f:
            bot_data = pickle.load(f)
        print("✅ Loaded bot data")
    except Exception as e:
        print(f"❌ Error loading bot data: {e}")
        return
    
    # Get the data
    chat_id = 5634913742
    chat_data_all = bot_data.get('chat_data', {})
    chat_data = chat_data_all.get(chat_id, {})
    
    # Get monitor data
    active_monitors = chat_data.get('active_monitor_task_data_v2', {})
    injusdt_monitor = active_monitors.get(f'{chat_id}_INJUSDT_conservative', {})
    
    # Get the limit order IDs from monitor data
    limit_ids = injusdt_monitor.get('conservative_limit_order_ids', [])
    
    if limit_ids:
        print(f"\n✅ Found {len(limit_ids)} limit order IDs in monitor data:")
        for i, lid in enumerate(limit_ids):
            print(f"   {i+1}. {lid}")
        
        # Add them to chat_data
        from config.constants import LIMIT_ORDER_IDS
        chat_data[LIMIT_ORDER_IDS] = limit_ids
        
        # Update the data
        chat_data_all[chat_id] = chat_data
        bot_data['chat_data'] = chat_data_all
        
        # Create backup
        backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{persistence_file}"
        os.rename(persistence_file, backup_file)
        print(f"\n📦 Created backup: {backup_file}")
        
        # Save updated data
        with open(persistence_file, 'wb') as f:
            pickle.dump(bot_data, f)
        print(f"✅ Saved updated bot data")
        
        print("\n✅ INJUSDT limit order IDs added to chat_data!")
        print("The monitor will now find them on the next check cycle")
    else:
        print("❌ No limit order IDs found in monitor data")

if __name__ == "__main__":
    main()