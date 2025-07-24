#!/usr/bin/env python3
"""
Sync ARBUSDT monitor state in pickle file with new TP orders.
"""

import pickle
import time
from datetime import datetime
from decimal import Decimal

def sync_pickle_state():
    """Update pickle file with new ARBUSDT order state."""
    
    print("Syncing ARBUSDT state in pickle file...")
    
    # Load pickle data
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_tp_sync_{timestamp}'
    with open(backup_file, 'wb') as f:
        pickle.dump(data, f)
    print(f"Created backup: {backup_file}")
    
    # Get monitors
    monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    # Update main account monitor
    if 'ARBUSDT_Buy_main' in monitors:
        monitor = monitors['ARBUSDT_Buy_main']
        
        # Update TP orders with new quantities
        tp_orders = monitor.get('tp_orders', {})
        if tp_orders:
            # Update quantities to match what we placed
            tp_list = list(tp_orders.values())
            if len(tp_list) >= 4:
                tp_list[0]['quantity'] = Decimal('1799.9')
                tp_list[0]['original_quantity'] = Decimal('1799.9')
                
                tp_list[1]['quantity'] = Decimal('105.8')
                tp_list[1]['original_quantity'] = Decimal('105.8')
                
                tp_list[2]['quantity'] = Decimal('105.8')
                tp_list[2]['original_quantity'] = Decimal('105.8')
                
                tp_list[3]['quantity'] = Decimal('105.8') 
                tp_list[3]['original_quantity'] = Decimal('105.8')
        
        # Ensure position size is correct
        monitor['position_size'] = Decimal('2117.6')
        monitor['current_size'] = Decimal('2117.6')
        monitor['remaining_size'] = Decimal('2117.6')
        monitor['initial_size'] = Decimal('2117.6')
        monitor['limit_orders_filled'] = True
        
        print("✅ Updated ARBUSDT_Buy_main monitor")
    
    # Update mirror account monitor  
    if 'ARBUSDT_Buy_mirror' in monitors:
        monitor = monitors['ARBUSDT_Buy_mirror']
        
        # Mirror monitor structure is different - ensure basic fields
        monitor['position_size'] = Decimal('699.4')
        monitor['current_size'] = Decimal('699.4')
        monitor['size'] = Decimal('699.4')
        monitor['initial_size'] = Decimal('699.4')
        monitor['remaining_size'] = Decimal('699.4')
        monitor['limit_orders_filled'] = True
        
        print("✅ Updated ARBUSDT_Buy_mirror monitor")
    
    # Save updated data
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    # Create reload signals
    signal_files = [
        'reload_monitors.signal',
        'monitor_reload_trigger.signal', 
        '.reload_enhanced_monitors',
        'force_reload.trigger'
    ]
    
    for signal in signal_files:
        with open(signal, 'w') as f:
            f.write(str(time.time()))
    
    print("✅ Created reload signals")
    print("\n✅ Pickle file sync complete!")
    print("\nThe bot's internal state now matches the exchange orders.")

if __name__ == "__main__":
    sync_pickle_state()