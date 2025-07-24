#!/usr/bin/env python3
"""
Close remaining orphaned monitors
"""

import os
import sys
import pickle
import time
import shutil

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2


def close_remaining_orphans():
    """Close remaining orphaned monitors"""
    
    print("=" * 80)
    print("CLOSING REMAINING ORPHANED MONITORS")
    print("=" * 80)
    
    # Create backup
    backup_file = f"bybit_bot_dashboard_v4.1_enhanced.pkl.backup_final_cleanup_{int(time.time())}"
    shutil.copy2('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_file)
    print(f"\n📦 Created backup: {backup_file}")
    
    # Load orphaned monitors list
    try:
        with open('remaining_orphans.txt', 'r') as f:
            lines = f.readlines()
        
        orphaned_keys = []
        for line in lines[2:]:  # Skip header lines
            key = line.strip()
            if key:
                orphaned_keys.append(key)
                
    except Exception as e:
        print(f"❌ Error reading orphaned monitors list: {e}")
        return
    
    print(f"\n📋 Found {len(orphaned_keys)} orphaned monitor keys to remove")
    
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
    
    for monitor_key in orphaned_keys:
        if monitor_key in enhanced_monitors:
            monitor_data = enhanced_monitors[monitor_key]
            
            symbol = monitor_data.get('symbol', 'Unknown')
            side = monitor_data.get('side', 'Unknown')
            account = monitor_data.get('account_type', 'main')
            
            print(f"\n🗑️  Removing {symbol} {side} ({account})...")
            
            # Try to cancel any remaining orders
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
                        print(f"   ✅ Cancelled SL order")
                    except:
                        pass  # Order might already be cancelled
            
            # Remove the monitor
            del enhanced_monitors[monitor_key]
            removed_count += 1
            print(f"   ✅ Removed monitor: {monitor_key}")
    
    # Save updated data
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        print("\n" + "=" * 80)
        print("FINAL CLEANUP COMPLETE")
        print("=" * 80)
        print(f"\n✅ Removed {removed_count} orphaned monitors")
        
        # Get final counts
        main_count = sum(1 for m in enhanced_monitors.values() if m.get('account_type', 'main') == 'main')
        mirror_count = sum(1 for m in enhanced_monitors.values() if m.get('account_type', 'main') == 'mirror')
        
        print(f"\n📊 Final Monitor Count:")
        print(f"   Main monitors: {main_count}")
        print(f"   Mirror monitors: {mirror_count}")
        print(f"   Total monitors: {len(enhanced_monitors)}")
        
    except Exception as e:
        print(f"\n❌ Error saving data: {e}")


if __name__ == "__main__":
    close_remaining_orphans()