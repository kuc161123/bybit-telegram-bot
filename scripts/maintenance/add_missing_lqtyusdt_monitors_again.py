#!/usr/bin/env python3
"""
Add Missing LQTYUSDT Monitors Again
The LQTYUSDT monitors seem to have been lost during bot restart
"""
import asyncio
import sys
import os
import pickle
import time
from decimal import Decimal

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

async def add_missing_lqtyusdt_monitors_again():
    """Add the missing LQTYUSDT monitors again"""
    try:
        print("🚀 ADDING MISSING LQTYUSDT MONITORS AGAIN")
        print("=" * 50)
        
        # Load current persistence data
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        current_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        print(f"📊 Current monitors: {len(current_monitors)}")
        
        # Check if LQTYUSDT monitors exist
        lqtyusdt_main = 'LQTYUSDT_Sell' in current_monitors
        lqtyusdt_mirror = 'LQTYUSDT_Sell_MIRROR' in current_monitors
        
        print(f"🔍 LQTYUSDT Main monitor exists: {lqtyusdt_main}")
        print(f"🔍 LQTYUSDT Mirror monitor exists: {lqtyusdt_mirror}")
        
        new_monitors = {}
        
        # Add main account monitor if missing (from previous logs: position size 138.5, entry 1.154000)
        if not lqtyusdt_main:
            print("➕ Adding LQTYUSDT main account monitor...")
            new_monitors['LQTYUSDT_Sell'] = {
                "symbol": "LQTYUSDT",
                "side": "Sell",
                "position_size": Decimal("138.5"),
                "remaining_size": Decimal("138.5"),
                "entry_price": Decimal("1.154000"),
                "tp_prices": [Decimal("1.1316"), Decimal("1.1016"), Decimal("1.0721"), Decimal("0.9829")],
                "tp_percentages": [Decimal("85"), Decimal("5"), Decimal("5"), Decimal("5")],
                "sl_price": Decimal("1.4280"),
                "chat_id": 5634913742,
                "approach": "CONSERVATIVE",
                "account_type": "main",
                "phase": "BUILDING",
                "tp1_hit": False,
                "sl_moved_to_be": False,
                "created_at": time.time(),
                "last_check": time.time(),
                "tp_orders": [],
                "sl_order": {},
                "limit_orders": [],
                "monitoring_active": True
            }
        
        # Add mirror account monitor if missing (from previous logs: position size 50.0, entry 1.154000)
        if not lqtyusdt_mirror:
            print("➕ Adding LQTYUSDT mirror account monitor...")
            new_monitors['LQTYUSDT_Sell_MIRROR'] = {
                "symbol": "LQTYUSDT",
                "side": "Sell",
                "position_size": Decimal("50.0"),
                "remaining_size": Decimal("50.0"),
                "entry_price": Decimal("1.154000"),
                "tp_prices": [Decimal("1.1316"), Decimal("1.1016"), Decimal("1.0721"), Decimal("0.9829")],
                "tp_percentages": [Decimal("85"), Decimal("5"), Decimal("5"), Decimal("5")],
                "sl_price": Decimal("1.4280"),
                "chat_id": 5634913742,
                "approach": "CONSERVATIVE",
                "account_type": "mirror",
                "phase": "BUILDING",
                "tp1_hit": False,
                "sl_moved_to_be": False,
                "created_at": time.time(),
                "last_check": time.time(),
                "tp_orders": [],
                "sl_order": {},
                "limit_orders": [],
                "monitoring_active": True
            }
        
        if new_monitors:
            # Add new monitors to existing ones
            current_monitors.update(new_monitors)
            data['bot_data']['enhanced_tp_sl_monitors'] = current_monitors
            
            # Save updated data
            with open(pkl_path, 'wb') as f:
                pickle.dump(data, f)
            
            print(f"✅ Added {len(new_monitors)} new monitors")
            print(f"📊 Total monitors now: {len(current_monitors)}")
            
            # Create signal file for reload
            signal_file = '/Users/lualakol/bybit-telegram-bot/reload_enhanced_monitors.signal'
            with open(signal_file, 'w') as f:
                f.write(f"{time.time()}\nAdded LQTYUSDT monitors again\n")
            
            print("📡 Signal file created for monitor reload")
            print("=" * 50)
            print("🎉 LQTYUSDT MONITORS ADDED SUCCESSFULLY!")
            print("The Enhanced TP/SL Manager should now monitor 26 positions")
        else:
            print("✅ All LQTYUSDT monitors already exist")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(add_missing_lqtyusdt_monitors_again())