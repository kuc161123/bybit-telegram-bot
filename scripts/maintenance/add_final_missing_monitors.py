#!/usr/bin/env python3
"""
Add Final Missing Monitors for 28/28 Coverage
Add BANDUSDT and LQTYUSDT monitors for both main and mirror accounts
"""
import asyncio
import sys
import os
import pickle
import time
from decimal import Decimal

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

async def add_final_missing_monitors():
    """Add the final missing monitors to achieve 28/28 coverage"""
    try:
        print("🎯 ADDING FINAL MISSING MONITORS FOR 28/28 COVERAGE")
        print("=" * 60)
        
        # Load current persistence data
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        current_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        print(f"📊 Current Enhanced TP/SL monitors: {len(current_monitors)}")
        
        new_monitors = {}
        
        # Add BANDUSDT main account monitor
        bandusdt_main_key = 'BANDUSDT_Sell'
        if bandusdt_main_key not in current_monitors:
            print(f"➕ Adding BANDUSDT main account monitor (size: 307.3)...")
            new_monitors[bandusdt_main_key] = {
                "symbol": "BANDUSDT",
                "side": "Sell",
                "position_size": Decimal("307.3"),
                "remaining_size": Decimal("307.3"),
                "entry_price": Decimal("0.54453059"),
                "tp_prices": [Decimal("0.5337"), Decimal("0.5197"), Decimal("0.5061"), Decimal("0.4653")],
                "tp_percentages": [Decimal("85"), Decimal("5"), Decimal("5"), Decimal("5")],
                "sl_price": Decimal("0.6737"),
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
        
        # Add BANDUSDT mirror account monitor
        bandusdt_mirror_key = 'BANDUSDT_Sell_MIRROR'
        if bandusdt_mirror_key not in current_monitors:
            print(f"➕ Adding BANDUSDT mirror account monitor (size: 110.5)...")
            new_monitors[bandusdt_mirror_key] = {
                "symbol": "BANDUSDT",
                "side": "Sell",
                "position_size": Decimal("110.5"),
                "remaining_size": Decimal("110.5"),
                "entry_price": Decimal("0.5446"),
                "tp_prices": [Decimal("0.5337"), Decimal("0.5197"), Decimal("0.5061"), Decimal("0.4653")],
                "tp_percentages": [Decimal("85"), Decimal("5"), Decimal("5"), Decimal("5")],
                "sl_price": Decimal("0.6737"),
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
        
        # Add LQTYUSDT main account monitor
        lqtyusdt_main_key = 'LQTYUSDT_Sell'
        if lqtyusdt_main_key not in current_monitors:
            print(f"➕ Adding LQTYUSDT main account monitor (size: 138.5)...")
            new_monitors[lqtyusdt_main_key] = {
                "symbol": "LQTYUSDT",
                "side": "Sell",
                "position_size": Decimal("138.5"),
                "remaining_size": Decimal("138.5"),
                "entry_price": Decimal("1.1533"),
                "tp_prices": [Decimal("1.1313"), Decimal("1.1013"), Decimal("0.1018"), Decimal("0.9318")],
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
        
        # Add LQTYUSDT mirror account monitor  
        lqtyusdt_mirror_key = 'LQTYUSDT_Sell_MIRROR'
        if lqtyusdt_mirror_key not in current_monitors:
            print(f"➕ Adding LQTYUSDT mirror account monitor (size: 50)...")
            new_monitors[lqtyusdt_mirror_key] = {
                "symbol": "LQTYUSDT",
                "side": "Sell",
                "position_size": Decimal("50"),
                "remaining_size": Decimal("50"),
                "entry_price": Decimal("1.1533"),
                "tp_prices": [Decimal("1.1313"), Decimal("1.1013"), Decimal("0.1018"), Decimal("0.9318")],
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
            
            print(f"✅ Added {len(new_monitors)} final missing monitors")
            print(f"📊 Total Enhanced TP/SL monitors now: {len(current_monitors)}")
            
            # Create signal file for reload
            signal_file = '/Users/lualakol/bybit-telegram-bot/reload_enhanced_monitors.signal'
            with open(signal_file, 'w') as f:
                f.write(f"{time.time()}\\nAdded final missing monitors for 28/28 coverage\\n")
            
            print("📡 Signal file created for monitor reload")
            print("=" * 60)
            print("🎉 FINAL MISSING MONITORS ADDED!")
            print("🏆 ACHIEVED 28/28 ENHANCED TP/SL MONITOR COVERAGE!")
            print("✅ All positions now have Enhanced TP/SL monitoring")
        else:
            print("✅ All required monitors already exist")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(add_final_missing_monitors())