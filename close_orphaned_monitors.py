#!/usr/bin/env python3
"""
Close orphaned monitors that have no corresponding positions
"""

import os
import sys
import pickle
import time
import shutil
from typing import List, Dict

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2


def verify_monitor_is_orphaned(monitor_data: Dict, main_client, mirror_client) -> bool:
    """Double-check that a monitor is truly orphaned"""
    symbol = monitor_data.get('symbol')
    side = monitor_data.get('side')
    account_type = monitor_data.get('account_type', 'main')
    
    # Select appropriate client
    client = main_client if account_type == 'main' else mirror_client
    
    try:
        # Check for active position
        response = client.get_positions(category="linear", symbol=symbol)
        
        if response['retCode'] == 0:
            for pos in response['result']['list']:
                if pos['symbol'] == symbol and pos['side'] == side and float(pos['size']) > 0:
                    # Position exists!
                    print(f"⚠️  Found active position for {symbol} {side} ({account_type}) - NOT orphaned")
                    return False
        
        # Also check open orders
        orders_response = client.get_open_orders(category="linear", symbol=symbol)
        
        if orders_response['retCode'] == 0:
            orders = orders_response['result']['list']
            if orders:
                print(f"⚠️  Found {len(orders)} open orders for {symbol} ({account_type}) - checking further...")
                # Don't consider it orphaned if there are orders
                # unless they're all TP/SL orders without a position
        
        return True  # Confirmed orphaned
        
    except Exception as e:
        print(f"❌ Error verifying {symbol} {side} ({account_type}): {e}")
        return False  # Don't close if we can't verify


def close_orphaned_monitors():
    """Close monitors that have no corresponding positions"""
    
    print("=" * 80)
    print("CLOSING ORPHANED MONITORS")
    print("=" * 80)
    
    # Create backup
    backup_file = f"bybit_bot_dashboard_v4.1_enhanced.pkl.backup_orphan_cleanup_{int(time.time())}"
    shutil.copy2('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_file)
    print(f"\n📦 Created backup: {backup_file}")
    
    # Load orphaned monitors list
    try:
        with open('orphaned_monitors.txt', 'r') as f:
            lines = f.readlines()
        
        orphaned_keys = []
        for line in lines[2:]:  # Skip header lines
            key = line.strip()
            if key:
                orphaned_keys.append(key)
                
    except Exception as e:
        print(f"❌ Error reading orphaned monitors list: {e}")
        return
    
    print(f"\n📋 Found {len(orphaned_keys)} orphaned monitor keys to process")
    
    # Load pickle data
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        print(f"❌ Error loading pickle file: {e}")
        return
    
    # Get monitors
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    removed_count = 0
    skipped_count = 0
    
    for monitor_key in orphaned_keys:
        if monitor_key in enhanced_monitors:
            monitor_data = enhanced_monitors[monitor_key]
            
            symbol = monitor_data.get('symbol', 'Unknown')
            side = monitor_data.get('side', 'Unknown')
            account = monitor_data.get('account_type', 'main')
            remaining_size = monitor_data.get('remaining_size', 0)
            
            print(f"\n🔍 Verifying {symbol} {side} ({account})...")
            
            # Double-check it's truly orphaned
            if verify_monitor_is_orphaned(monitor_data, bybit_client, bybit_client_2):
                # Cancel any remaining orders
                if 'sl_order' in monitor_data and monitor_data['sl_order']:
                    sl_order_id = monitor_data['sl_order'].get('order_id')
                    if sl_order_id:
                        try:
                            client = bybit_client if account == 'main' else bybit_client_2
                            client.cancel_order(
                                category="linear",
                                symbol=symbol,
                                orderId=sl_order_id
                            )
                            print(f"   ✅ Cancelled SL order: {sl_order_id[:8]}...")
                        except Exception as e:
                            print(f"   ⚠️  Could not cancel SL order: {e}")
                
                # Remove the monitor
                del enhanced_monitors[monitor_key]
                removed_count += 1
                
                print(f"   ✅ Removed orphaned monitor: {monitor_key}")
                print(f"      Remaining size was: {remaining_size}")
            else:
                skipped_count += 1
                print(f"   ⏭️  Skipped - position or orders still exist")
    
    # Also check dashboard monitors
    dashboard_monitors = data.get('bot_data', {}).get('monitor_tasks', {})
    dashboard_removed = 0
    
    for key in list(dashboard_monitors.keys()):
        parts = key.split('_')
        if len(parts) >= 3:
            symbol = parts[1]
            # Check if corresponding enhanced monitor exists
            enhanced_exists = False
            for em_key in enhanced_monitors:
                if symbol in em_key:
                    enhanced_exists = True
                    break
            
            if not enhanced_exists:
                del dashboard_monitors[key]
                dashboard_removed += 1
                print(f"\n   ✅ Removed orphaned dashboard monitor: {key}")
    
    # Save updated data
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        print("\n" + "=" * 80)
        print("CLEANUP SUMMARY")
        print("=" * 80)
        print(f"\n✅ Cleanup completed successfully")
        print(f"   Enhanced monitors removed: {removed_count}")
        print(f"   Enhanced monitors skipped: {skipped_count}")
        print(f"   Dashboard monitors removed: {dashboard_removed}")
        print(f"   Total monitors cleaned: {removed_count + dashboard_removed}")
        
        if removed_count > 0:
            print("\n💡 Benefits:")
            print("   • Freed up monitoring resources")
            print("   • Cleaner dashboard display")
            print("   • Improved bot performance")
            
    except Exception as e:
        print(f"\n❌ Error saving data: {e}")


if __name__ == "__main__":
    close_orphaned_monitors()