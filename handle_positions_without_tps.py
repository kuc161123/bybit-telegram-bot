#!/usr/bin/env python3
"""
Handle positions without TP orders (where all TPs may have been hit)
These need special handling to ensure they can still be closed properly
"""

import pickle
import time
import shutil

def handle_positions_without_tps():
    """Mark positions without TPs as having all TPs filled"""
    
    print("=" * 80)
    print("HANDLING POSITIONS WITHOUT TP ORDERS")
    print("=" * 80)
    
    # Create backup
    backup_file = f"bybit_bot_dashboard_v4.1_enhanced.pkl.backup_no_tps_{int(time.time())}"
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
    
    positions_without_tps = []
    
    for monitor_key, monitor_data in enhanced_monitors.items():
        # Check if monitor has no final_tp_order_id
        if not monitor_data.get('final_tp_order_id'):
            symbol = monitor_data.get('symbol', 'Unknown')
            side = monitor_data.get('side', 'Unknown')
            account = monitor_data.get('account_type', 'main')
            
            # Check if it has no TP orders at all
            has_tp_orders = False
            
            if 'tp_orders' in monitor_data and monitor_data['tp_orders']:
                has_tp_orders = True
            elif 'take_profits' in monitor_data and monitor_data['take_profits']:
                has_tp_orders = True
            
            if not has_tp_orders:
                positions_without_tps.append({
                    'key': monitor_key,
                    'symbol': symbol,
                    'side': side,
                    'account': account,
                    'filled_tps': len(monitor_data.get('filled_tps', [])),
                    'position_size': monitor_data.get('position_size', 0),
                    'remaining_size': monitor_data.get('remaining_size', 0)
                })
    
    print(f"\n📊 Found {len(positions_without_tps)} positions without TP orders")
    
    if positions_without_tps:
        print("\n📋 Positions without TPs:")
        for pos in positions_without_tps:
            print(f"\n  • {pos['symbol']} {pos['side']} ({pos['account']})")
            print(f"    Filled TPs: {pos['filled_tps']}")
            print(f"    Position size: {pos['position_size']}")
            print(f"    Remaining size: {pos['remaining_size']}")
        
        # Mark these as having all TPs filled
        print("\n🔧 Marking these positions as 'all TPs filled'...")
        
        updated_count = 0
        for pos in positions_without_tps:
            monitor = enhanced_monitors[pos['key']]
            
            # Set special markers
            monitor['final_tp_order_id'] = 'NO_TPS_CONFIGURED'
            monitor['all_tps_filled'] = True
            
            # Ensure these fields exist
            if 'tp_orders' not in monitor:
                monitor['tp_orders'] = {}
            if 'filled_tps' not in monitor:
                monitor['filled_tps'] = []
            
            updated_count += 1
        
        # Save updated data
        try:
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
                pickle.dump(data, f)
            
            print(f"\n✅ Updated {updated_count} monitors")
            print("\n💡 These positions will now:")
            print("   • Be eligible for manual closure")
            print("   • Not wait for TP fills (since there are no TPs)")
            print("   • Can be closed via dashboard or commands")
            
        except Exception as e:
            print(f"\n❌ Error saving data: {e}")
    else:
        print("\n✅ All positions have TP tracking configured!")

if __name__ == "__main__":
    handle_positions_without_tps()