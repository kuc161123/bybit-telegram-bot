#!/usr/bin/env python3
"""
Update existing monitors to track their final TP order ID
This ensures positions close completely when final TP is hit
"""

import pickle
import time
import shutil
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def update_monitors_with_final_tp():
    """Update all monitors to identify their final TP order"""
    
    print("=" * 80)
    print("UPDATING MONITORS WITH FINAL TP TRACKING")
    print("=" * 80)
    
    # Create backup
    backup_file = f"bybit_bot_dashboard_v4.1_enhanced.pkl.backup_final_tp_{int(time.time())}"
    shutil.copy2('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_file)
    print(f"\n📦 Created backup: {backup_file}")
    
    # Load pickle data
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        print(f"❌ Error loading pickle file: {e}")
        return
    
    # Get monitors
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    print(f"\n📊 Found {len(enhanced_monitors)} monitors to update")
    
    updated_count = 0
    already_set_count = 0
    
    for monitor_key, monitor_data in enhanced_monitors.items():
        # Skip if already has final_tp_order_id
        if monitor_data.get('final_tp_order_id'):
            already_set_count += 1
            continue
            
        # Get TP orders
        tp_orders = monitor_data.get('take_profits', [])
        if not tp_orders:
            continue
            
        # Find the TP with highest number (last TP)
        max_tp_number = 0
        final_tp_order = None
        final_tp_order_id = None
        
        # Handle both list and dict formats
        if isinstance(tp_orders, list):
            # For list format, the last one is the final TP
            for i, tp in enumerate(tp_orders):
                tp_number = i + 1
                if tp_number > max_tp_number:
                    max_tp_number = tp_number
                    final_tp_order = tp
                    final_tp_order_id = tp.get('order_id')
        else:
            # For dict format
            for order_id, tp_order in tp_orders.items():
                tp_number = tp_order.get('tp_number', 0)
                if tp_number > max_tp_number:
                    max_tp_number = tp_number
                    final_tp_order = tp_order
                    final_tp_order_id = order_id
        
        if final_tp_order_id:
            # Set the final TP order ID
            monitor_data['final_tp_order_id'] = final_tp_order_id
            
            # Also ensure all_tps_filled flag exists
            if 'all_tps_filled' not in monitor_data:
                monitor_data['all_tps_filled'] = False
            
            updated_count += 1
            
            symbol = monitor_data.get('symbol', 'Unknown')
            side = monitor_data.get('side', 'Unknown')
            account = monitor_data.get('account_type', 'main')
            
            print(f"\n✅ Updated {symbol} {side} ({account}):")
            print(f"   Final TP: TP{max_tp_number}")
            print(f"   Order ID: {final_tp_order_id[:8] if final_tp_order_id else 'None'}...")
            print(f"   Total TPs: {len(tp_orders)}")
    
    # Save updated data
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"\n✅ Successfully updated monitors")
        print(f"   Updated: {updated_count}")
        print(f"   Already set: {already_set_count}")
        print(f"   Total: {len(enhanced_monitors)}")
        
    except Exception as e:
        print(f"\n❌ Error saving data: {e}")


if __name__ == "__main__":
    update_monitors_with_final_tp()