#!/usr/bin/env python3
"""
Add Missing BANDUSDT Monitors to Enhanced TP/SL System
This adds the missing monitors for BANDUSDT on both main and mirror accounts
"""
import asyncio
import sys
import os
import pickle
import time
from decimal import Decimal

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

async def add_missing_bandusdt_monitors():
    """Add the missing BANDUSDT monitors"""
    try:
        print("🚀 ADDING MISSING BANDUSDT MONITORS")
        print("=" * 50)
        
        # Load current persistence data
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        current_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        print(f"📊 Current monitors: {len(current_monitors)}")
        
        # Check if BANDUSDT monitors exist
        bandusdt_main = 'BANDUSDT_Sell' in current_monitors
        bandusdt_mirror = 'BANDUSDT_Sell_MIRROR' in current_monitors
        
        print(f"🔍 BANDUSDT Main monitor exists: {bandusdt_main}")
        print(f"🔍 BANDUSDT Mirror monitor exists: {bandusdt_mirror}")
        
        new_monitors = {}
        
        # Add main account monitor if missing (from logs: position size 307.3, entry 0.544400)
        if not bandusdt_main:
            print("➕ Adding BANDUSDT main account monitor...")
            new_monitors['BANDUSDT_Sell'] = {
                "symbol": "BANDUSDT",
                "side": "Sell",
                "position_size": Decimal("307.3"),
                "remaining_size": Decimal("307.3"),
                "entry_price": Decimal("0.544400"),
                "tp_prices": [Decimal("0.5356"), Decimal("0.5226"), Decimal("0.5097"), Decimal("0.4708")],
                "tp_percentages": [Decimal("85"), Decimal("5"), Decimal("5"), Decimal("5")],
                "sl_price": Decimal("0.5947"),
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
        
        # Add mirror account monitor if missing (from logs: position size 110.5, entry 0.544400)
        if not bandusdt_mirror:
            print("➕ Adding BANDUSDT mirror account monitor...")
            new_monitors['BANDUSDT_Sell_MIRROR'] = {
                "symbol": "BANDUSDT",
                "side": "Sell",
                "position_size": Decimal("110.5"),
                "remaining_size": Decimal("110.5"),
                "entry_price": Decimal("0.544400"),
                "tp_prices": [Decimal("0.5356"), Decimal("0.5226"), Decimal("0.5097"), Decimal("0.4708")],
                "tp_percentages": [Decimal("85"), Decimal("5"), Decimal("5"), Decimal("5")],
                "sl_price": Decimal("0.5947"),
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
                f.write(f"{time.time()}\nAdded BANDUSDT monitors\n")
            
            print("📡 Signal file created for monitor reload")
            print("=" * 50)
            print("🎉 BANDUSDT MONITORS ADDED SUCCESSFULLY!")
            print("The Enhanced TP/SL Manager should now monitor 26 positions")
        else:
            print("✅ All BANDUSDT monitors already exist")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(add_missing_bandusdt_monitors())