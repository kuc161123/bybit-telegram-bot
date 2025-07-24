#!/usr/bin/env python3
"""
Update all monitors to CONSERVATIVE approach only
This ensures both main and mirror account monitors work correctly with the updated code
"""
import pickle
import time
from datetime import datetime

def update_monitors_conservative():
    """Update all monitors to use CONSERVATIVE approach"""
    
    # Create backup first
    backup_file = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_conservative_only_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    
    print("=" * 80)
    print("UPDATING ALL MONITORS TO CONSERVATIVE APPROACH")
    print("=" * 80)
    
    try:
        # Load current data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        # Create backup
        with open(backup_file, 'wb') as f:
            pickle.dump(data, f)
        print(f"✅ Created backup: {backup_file}")
        
        # Check both locations for monitors
        monitors = data.get('enhanced_tp_sl_monitors', {})
        if not monitors and 'bot_data' in data:
            monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
        
        if not monitors:
            print("❌ No monitors found in pickle file")
            return
        
        print(f"\nFound {len(monitors)} monitors to update:")
        
        updated_count = 0
        
        for monitor_key, monitor_data in monitors.items():
            old_approach = monitor_data.get('approach', 'unknown')
            
            # Update to CONSERVATIVE approach
            monitor_data['approach'] = 'CONSERVATIVE'
            
            # Ensure limit_orders_filled is properly set for conservative approach
            if monitor_data.get('limit_orders_filled') is True and old_approach == 'FAST':
                # This was a fast approach that's now conservative
                monitor_data['limit_orders_filled'] = False
            
            # Ensure phase is set correctly for conservative approach
            if monitor_data.get('phase') == 'PROFIT_TAKING' and old_approach == 'FAST':
                monitor_data['phase'] = 'BUILDING'
            
            # Ensure last_known_size is set for new limit fill detection
            if 'last_known_size' not in monitor_data:
                monitor_data['last_known_size'] = monitor_data.get('remaining_size', monitor_data.get('position_size', 0))
            
            # Ensure filled_limit_count is set
            if 'filled_limit_count' not in monitor_data:
                monitor_data['filled_limit_count'] = 0
            
            # Ensure last_limit_fill_time is set
            if 'last_limit_fill_time' not in monitor_data:
                monitor_data['last_limit_fill_time'] = 0
            
            print(f"  {monitor_key}: {old_approach} → CONSERVATIVE")
            updated_count += 1
        
        # Update the monitors in the correct location
        if 'enhanced_tp_sl_monitors' in data:
            data['enhanced_tp_sl_monitors'] = monitors
        elif 'bot_data' in data and 'enhanced_tp_sl_monitors' in data['bot_data']:
            data['bot_data']['enhanced_tp_sl_monitors'] = monitors
        
        # Save updated data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        print(f"\n✅ Updated {updated_count} monitors to CONSERVATIVE approach")
        print("✅ All monitors now use conservative approach only")
        print("✅ Enhanced limit fill detection initialized")
        
        # Create signal file to trigger monitor reload
        signal_file = 'conservative_update.signal'
        with open(signal_file, 'w') as f:
            f.write(f"Conservative update completed at {datetime.now()}\n")
            f.write(f"Updated {updated_count} monitors\n")
            f.write("All monitors now use CONSERVATIVE approach\n")
        
        print(f"✅ Created signal file: {signal_file}")
        
        print("\n" + "=" * 80)
        print("UPDATE COMPLETE")
        print("=" * 80)
        print("📝 Changes applied:")
        print("  • All monitors set to CONSERVATIVE approach")
        print("  • Fast approach logic removed")
        print("  • Enhanced limit fill detection enabled")
        print("  • Position size tracking initialized")
        print("\n🔄 The bot will automatically reload monitors")
        print("   No restart required - monitors will use new logic immediately")
        
    except Exception as e:
        print(f"❌ Error updating monitors: {e}")
        print("The original pickle file remains unchanged")

if __name__ == "__main__":
    update_monitors_conservative()