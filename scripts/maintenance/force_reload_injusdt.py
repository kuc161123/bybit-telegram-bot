#!/usr/bin/env python3
"""
Force reload INJUSDT monitoring with limit order IDs
"""

import pickle
import os
from datetime import datetime

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
    
    chat_id = 5634913742
    chat_data_all = bot_data.get('chat_data', {})
    chat_data = chat_data_all.get(chat_id, {})
    
    # Import constants
    from config.constants import (
        LIMIT_ORDER_IDS, CONSERVATIVE_TP_ORDER_IDS, CONSERVATIVE_SL_ORDER_ID,
        SYMBOL, SIDE, TRADING_APPROACH, CONSERVATIVE_LIMITS_FILLED
    )
    
    # Set up INJUSDT data properly
    print("\n📝 Setting up INJUSDT monitoring data...")
    
    # Set the basic data
    chat_data[SYMBOL] = "INJUSDT"
    chat_data[SIDE] = "Sell"
    chat_data[TRADING_APPROACH] = "conservative"
    
    # Set the limit order IDs
    limit_ids = ['441610a4-2cc3-47d6-bc7c-f328496121bc', 'b6199247-4d7d-4a0f-9fd7-30d9a4a4afcc']
    chat_data[LIMIT_ORDER_IDS] = limit_ids
    chat_data['limit_order_ids'] = limit_ids  # Also set lowercase version
    
    # Set TP order IDs
    tp_ids = ['394487f7-50d5-4a2b-9f77-9f5b99811b5e', '4a11a8dd-975f-4175-bc53-defa56154d04', 
              '56330b0d-3f64-49b0-ad37-372df47d6187', '9fcf44f8-60b2-4631-b0bd-17767e2a04a7']
    chat_data[CONSERVATIVE_TP_ORDER_IDS] = tp_ids
    
    # Set SL order ID
    sl_id = '132723ba-5eb2-4fe2-a9e5-ac9b6cb5efac'
    chat_data[CONSERVATIVE_SL_ORDER_ID] = sl_id
    
    # Initialize filled limits tracking
    chat_data[CONSERVATIVE_LIMITS_FILLED] = []
    
    # Also update position-specific data
    position_key = f"position_INJUSDT_Sell_conservative"
    if position_key not in chat_data:
        chat_data[position_key] = {}
    
    position_data = chat_data[position_key]
    position_data.update({
        'symbol': 'INJUSDT',
        'side': 'Sell',
        'approach': 'conservative',
        LIMIT_ORDER_IDS: limit_ids,
        'limit_order_ids': limit_ids,
        CONSERVATIVE_TP_ORDER_IDS: tp_ids,
        CONSERVATIVE_SL_ORDER_ID: sl_id
    })
    
    # Update monitor task data
    active_monitors = chat_data.get('active_monitor_task_data_v2', {})
    monitor_key = f"{chat_id}_INJUSDT_conservative"
    
    if monitor_key in active_monitors:
        monitor_data = active_monitors[monitor_key]
        monitor_data['conservative_limit_order_ids'] = limit_ids
        monitor_data['conservative_tp_order_ids'] = tp_ids
        monitor_data['conservative_sl_order_id'] = sl_id
        print("✅ Updated monitor data with order IDs")
    
    # Save everything
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
    
    print("\n" + "="*60)
    print("✅ INJUSDT MONITORING DATA FULLY UPDATED!")
    print("="*60)
    print("\n📌 The following has been set:")
    print(f"   • {len(limit_ids)} limit order IDs in chat_data")
    print(f"   • {len(tp_ids)} TP order IDs")
    print(f"   • 1 SL order ID")
    print(f"   • Conservative approach confirmed")
    print(f"   • Both main and position-specific data updated")
    
    print("\n⚠️  IMPORTANT: You may need to restart the bot for this to take effect")
    print("   The monitor is running in a separate process and may have cached the data")

if __name__ == "__main__":
    main()