#!/usr/bin/env python3
"""
Reset APTUSDT monitor to correct state after false TP detection
"""

import os
import sys
import pickle
import asyncio
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.pickle_lock import main_pickle_lock
from clients.bybit_helpers import get_position_info

async def reset_aptusdt_monitor():
    """Reset the APTUSDT monitor to correct state"""
    
    symbol = "APTUSDT"
    side = "Buy"
    
    # Get current position from Bybit
    print(f"🔍 Fetching position info for {symbol}...")
    positions = await get_position_info(symbol)
    
    if not positions:
        print(f"❌ No position found for {symbol}")
        return False
    
    # Find the Buy position
    position = None
    for pos in positions:
        if pos.get("side") == side:
            position = pos
            break
    
    if not position:
        print(f"❌ No {side} position found for {symbol}")
        return False
    
    current_size = Decimal(str(position.get("size", "0")))
    avg_price = Decimal(str(position.get("avgPrice", "0")))
    
    print(f"✅ Found position: size={current_size}, avg_price={avg_price}")
    
    # Update the monitor
    def update_monitor(data):
        if 'bot_data' not in data:
            data['bot_data'] = {}
        
        monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
        
        updated = False
        
        # Update main account monitor
        main_key = f"{symbol}_{side}_main"
        if main_key in monitors:
            monitor = monitors[main_key]
            
            # Reset to correct state
            monitor['remaining_size'] = current_size
            monitor['position_size'] = Decimal("258.13")  # Target size from the trade
            monitor['current_size'] = current_size
            monitor['initial_fill_processed'] = True
            monitor['filled_tps'] = []  # Clear any false TP fills
            monitor['tp1_hit'] = False
            
            # Remove any non-serializable fields
            fields_to_remove = []
            for field_key in monitor.keys():
                if 'task' in field_key.lower() or '_lock' in field_key:
                    fields_to_remove.append(field_key)
            
            for field in fields_to_remove:
                if field in monitor:
                    del monitor[field]
            
            print(f"✅ Updated main monitor: remaining_size={current_size}")
            updated = True
        
        # Update mirror account monitor
        mirror_key = f"{symbol}_{side}_mirror"
        if mirror_key in monitors:
            monitor = monitors[mirror_key]
            
            # Get mirror position size (approximately 1/3 of main)
            mirror_current_size = current_size / 3  # Approximate
            
            # Reset to correct state
            monitor['remaining_size'] = mirror_current_size
            monitor['position_size'] = Decimal("85.49")  # Target size from the trade
            monitor['current_size'] = mirror_current_size
            monitor['initial_fill_processed'] = True
            monitor['filled_tps'] = []  # Clear any false TP fills
            monitor['tp1_hit'] = False
            
            # Remove any non-serializable fields
            fields_to_remove = []
            for field_key in monitor.keys():
                if 'task' in field_key.lower() or '_lock' in field_key:
                    fields_to_remove.append(field_key)
            
            for field in fields_to_remove:
                if field in monitor:
                    del monitor[field]
            
            print(f"✅ Updated mirror monitor: remaining_size={mirror_current_size}")
            updated = True
        
        if not updated:
            print(f"⚠️ No monitors found for {symbol} {side}")
        
        data['bot_data']['enhanced_tp_sl_monitors'] = monitors
    
    # Update the pickle file
    success = main_pickle_lock.update_data(update_monitor)
    
    if success:
        print(f"\n✅ Successfully reset {symbol} {side} monitors")
        print("📝 Monitors have been reset to correct state")
        print("🔍 The bot should now track the position correctly")
    else:
        print(f"\n❌ Failed to update monitors")
    
    return success

async def main():
    print("🔧 Resetting APTUSDT monitor after false TP detection...")
    await reset_aptusdt_monitor()

if __name__ == "__main__":
    asyncio.run(main())