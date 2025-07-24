#!/usr/bin/env python3
"""
Enhanced update to add final TP tracking to all monitors
Handles both tp_orders and take_profits fields
"""

import pickle
import time
import shutil
import logging
from typing import Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def find_final_tp_order(monitor_data: Dict) -> Tuple[Optional[str], int]:
    """
    Find the final TP order ID from monitor data
    Returns (order_id, tp_number)
    """
    final_tp_order_id = None
    max_tp_number = 0
    
    # Check tp_orders field (most common)
    if 'tp_orders' in monitor_data and monitor_data['tp_orders']:
        tp_orders = monitor_data['tp_orders']
        
        if isinstance(tp_orders, dict):
            # Dict format - find highest tp_number or tp_level
            for order_id, tp_order in tp_orders.items():
                # Check various fields for TP number
                tp_number = tp_order.get('tp_number') or tp_order.get('tp_level') or 0
                
                # If no explicit number, try to parse from order_link_id
                if tp_number == 0 and 'order_link_id' in tp_order:
                    link_id = tp_order['order_link_id']
                    # Try to extract TP number from link ID (e.g., "TP1_", "TP2_", etc.)
                    for i in range(1, 10):
                        if f"TP{i}" in link_id:
                            tp_number = i
                            break
                
                # If still no number, count position in dict
                if tp_number == 0:
                    tp_number = len(tp_orders)  # Assume last is highest
                
                if tp_number > max_tp_number:
                    max_tp_number = tp_number
                    final_tp_order_id = order_id
        
        elif isinstance(tp_orders, list):
            # List format - last one is final
            for i, tp_order in enumerate(tp_orders):
                tp_number = i + 1
                if tp_number > max_tp_number:
                    max_tp_number = tp_number
                    final_tp_order_id = tp_order.get('order_id')
    
    # Also check take_profits field (some monitors use this)
    elif 'take_profits' in monitor_data and monitor_data['take_profits']:
        tp_orders = monitor_data['take_profits']
        
        if isinstance(tp_orders, list):
            # List format - last one is final
            for i, tp_order in enumerate(tp_orders):
                tp_number = i + 1
                if tp_number > max_tp_number:
                    max_tp_number = tp_number
                    final_tp_order_id = tp_order.get('order_id')
        
        elif isinstance(tp_orders, dict):
            # Dict format
            for order_id, tp_order in tp_orders.items():
                tp_number = tp_order.get('tp_number', len(tp_orders))
                if tp_number > max_tp_number:
                    max_tp_number = tp_number
                    final_tp_order_id = order_id
    
    # If we still don't have a final TP but there are filled_tps, check those
    if not final_tp_order_id and 'filled_tps' in monitor_data and monitor_data['filled_tps']:
        # The monitor might have all TPs filled already
        filled_count = len(monitor_data['filled_tps'])
        if filled_count > 0:
            # Get the last filled TP
            last_filled = monitor_data['filled_tps'][-1]
            if isinstance(last_filled, dict):
                final_tp_order_id = last_filled.get('order_id')
                max_tp_number = last_filled.get('tp_number', filled_count)
            elif isinstance(last_filled, str):
                # Just the order ID
                final_tp_order_id = last_filled
                max_tp_number = filled_count
    
    return final_tp_order_id, max_tp_number


def update_monitors_with_final_tp():
    """Update all monitors to identify their final TP order"""
    
    print("=" * 80)
    print("ENHANCED MONITOR UPDATE WITH FINAL TP TRACKING")
    print("=" * 80)
    
    # Create backup
    backup_file = f"bybit_bot_dashboard_v4.1_enhanced.pkl.backup_final_tp_enhanced_{int(time.time())}"
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
    
    print(f"\n📊 Found {len(enhanced_monitors)} monitors to process")
    
    updated_count = 0
    already_set_count = 0
    no_tp_count = 0
    
    for monitor_key, monitor_data in enhanced_monitors.items():
        # Skip if already has final_tp_order_id
        if monitor_data.get('final_tp_order_id'):
            already_set_count += 1
            continue
        
        # Find the final TP order
        final_tp_order_id, max_tp_number = find_final_tp_order(monitor_data)
        
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
            
            # Show TP structure for verification
            if 'tp_orders' in monitor_data and monitor_data['tp_orders']:
                print(f"   TP Orders: {len(monitor_data['tp_orders'])} (in tp_orders)")
            elif 'take_profits' in monitor_data and monitor_data['take_profits']:
                print(f"   TP Orders: {len(monitor_data['take_profits'])} (in take_profits)")
        else:
            no_tp_count += 1
            # For monitors without TPs, check if they're in a special state
            symbol = monitor_data.get('symbol', 'Unknown')
            side = monitor_data.get('side', 'Unknown')
            account = monitor_data.get('account_type', 'main')
            
            # Check if all TPs were already filled
            if monitor_data.get('filled_tps'):
                print(f"\n⚠️ {symbol} {side} ({account}): All TPs already filled ({len(monitor_data['filled_tps'])} fills)")
                # Set a flag indicating all TPs were filled
                monitor_data['all_tps_filled'] = True
                monitor_data['final_tp_order_id'] = 'ALL_FILLED'
                updated_count += 1
            else:
                print(f"\n❓ {symbol} {side} ({account}): No TP orders found")
    
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
        print(f"   No TPs found: {no_tp_count}")
        print(f"   Total: {len(enhanced_monitors)}")
        
        print("\n💡 Next steps:")
        print("   1. The bot will use final_tp_order_id to track final TP")
        print("   2. When final TP fills, position closes completely")
        print("   3. All remaining orders are cancelled automatically")
        
    except Exception as e:
        print(f"\n❌ Error saving data: {e}")


if __name__ == "__main__":
    update_monitors_with_final_tp()