#!/usr/bin/env python3
"""
Add Missing NTRNUSDT Monitors to Enhanced TP/SL System
"""
import asyncio
import sys
import os
import pickle
import time
from decimal import Decimal

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

async def add_missing_ntrnusdt_monitors():
    """Add the missing NTRNUSDT monitors"""
    try:
        print("🚀 ADDING MISSING NTRNUSDT MONITORS")
        print("=" * 50)
        
        # Load current persistence data
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        current_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        print(f"📊 Current monitors: {len(current_monitors)}")
        
        # Check if NTRNUSDT monitors exist
        ntrnusdt_main = 'NTRNUSDT_Sell' in current_monitors
        ntrnusdt_mirror = 'NTRNUSDT_Sell_MIRROR' in current_monitors
        
        print(f"🔍 NTRNUSDT Main monitor exists: {ntrnusdt_main}")
        print(f"🔍 NTRNUSDT Mirror monitor exists: {ntrnusdt_mirror}")
        
        new_monitors = {}
        
        # Add main account monitor if missing
        if not ntrnusdt_main:
            print("➕ Adding NTRNUSDT main account monitor...")
            new_monitors['NTRNUSDT_Sell'] = {
                "symbol": "NTRNUSDT",
                "side": "Sell",
                "position_size": Decimal("1354"),
                "remaining_size": Decimal("1354"),
                "entry_price": Decimal("0.080400"),
                "tp_prices": [Decimal("0.0799"), Decimal("0.0780"), Decimal("0.0762"), Decimal("0.0705")],
                "tp_percentages": [Decimal("85"), Decimal("5"), Decimal("5"), Decimal("5")],
                "sl_price": Decimal("0.0887"),
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
        
        # Add mirror account monitor if missing
        if not ntrnusdt_mirror:
            print("➕ Adding NTRNUSDT mirror account monitor...")
            new_monitors['NTRNUSDT_Sell_MIRROR'] = {
                "symbol": "NTRNUSDT",
                "side": "Sell",
                "position_size": Decimal("488"),
                "remaining_size": Decimal("488"),
                "entry_price": Decimal("0.080400"),
                "tp_prices": [Decimal("0.0799"), Decimal("0.0780"), Decimal("0.0762"), Decimal("0.0705")],
                "tp_percentages": [Decimal("85"), Decimal("5"), Decimal("5"), Decimal("5")],
                "sl_price": Decimal("0.0887"),
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
                f.write(f"{time.time()}\nAdded NTRNUSDT monitors\n")
            
            print("📡 Signal file created for monitor reload")
            print("=" * 50)
            print("🎉 NTRNUSDT MONITORS ADDED SUCCESSFULLY!")
            print("The Enhanced TP/SL Manager should now monitor 22 positions")
        else:
            print("✅ All NTRNUSDT monitors already exist")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(add_missing_ntrnusdt_monitors())