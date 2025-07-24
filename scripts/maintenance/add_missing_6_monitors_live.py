#!/usr/bin/env python3
"""
Add Missing 6 Monitors Live - While Bot is Running
Adds XTZUSDT, BANDUSDT, LQTYUSDT monitors for both main and mirror accounts
"""
import asyncio
import sys
import os
import pickle
import time
from decimal import Decimal

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

async def add_missing_6_monitors_live():
    """Add the 6 missing monitors to achieve 28/28 coverage"""
    try:
        print("🚀 ADDING MISSING 6 MONITORS LIVE (WHILE BOT RUNNING)")
        print("=" * 60)
        
        # Get actual positions to get current prices and sizes
        from clients.bybit_helpers import get_all_positions_with_client
        from clients.bybit_client import bybit_client
        from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
        
        main_positions = await get_all_positions_with_client(bybit_client)
        main_open = [p for p in main_positions if float(p.get('size', 0)) > 0]
        
        mirror_open = []
        if is_mirror_trading_enabled() and bybit_client_2:
            mirror_positions = await get_all_positions_with_client(bybit_client_2)
            mirror_open = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
        
        # Find the actual positions for the missing symbols
        positions_data = {}
        
        for symbol in ['XTZUSDT', 'BANDUSDT', 'LQTYUSDT']:
            for pos in main_open:
                if pos.get('symbol') == symbol:
                    positions_data[f"{symbol}_main"] = pos
                    break
            
            for pos in mirror_open:
                if pos.get('symbol') == symbol:
                    positions_data[f"{symbol}_mirror"] = pos
                    break
        
        print("📊 Found position data:")
        for key, pos in positions_data.items():
            print(f"  {key}: size={pos.get('size')}, avgPrice={pos.get('avgPrice')}")
        
        # Create backup of current persistence file
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        backup_path = f"{pkl_path}.backup_live_fix_{int(time.time())}"
        
        print(f"💾 Creating backup: {backup_path}")
        import shutil
        shutil.copy2(pkl_path, backup_path)
        
        # Load current persistence data
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        current_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        print(f"📊 Current Enhanced TP/SL monitors: {len(current_monitors)}")
        
        new_monitors = {}
        
        # Add XTZUSDT main account monitor
        if 'XTZUSDT_main' in positions_data:
            pos = positions_data['XTZUSDT_main']
            key = 'XTZUSDT_Sell'
            if key not in current_monitors:
                print(f"➕ Adding {key}...")
                new_monitors[key] = {
                    "symbol": "XTZUSDT",
                    "side": "Sell",
                    "position_size": Decimal(str(pos.get('size', '324'))),
                    "remaining_size": Decimal(str(pos.get('size', '324'))),
                    "entry_price": Decimal(str(pos.get('avgPrice', '0.5177354'))),
                    "tp_prices": [Decimal("0.5073"), Decimal("0.4940"), Decimal("0.4808"), Decimal("0.4422")],
                    "tp_percentages": [Decimal("85"), Decimal("5"), Decimal("5"), Decimal("5")],
                    "sl_price": Decimal("0.6415"),
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
        
        # Add XTZUSDT mirror account monitor
        if 'XTZUSDT_mirror' in positions_data:
            pos = positions_data['XTZUSDT_mirror']
            key = 'XTZUSDT_Sell_MIRROR'
            if key not in current_monitors:
                print(f"➕ Adding {key}...")
                new_monitors[key] = {
                    "symbol": "XTZUSDT",
                    "side": "Sell",
                    "position_size": Decimal(str(pos.get('size', '116.8'))),
                    "remaining_size": Decimal(str(pos.get('size', '116.8'))),
                    "entry_price": Decimal(str(pos.get('avgPrice', '0.51771961'))),
                    "tp_prices": [Decimal("0.5073"), Decimal("0.4940"), Decimal("0.4808"), Decimal("0.4422")],
                    "tp_percentages": [Decimal("85"), Decimal("5"), Decimal("5"), Decimal("5")],
                    "sl_price": Decimal("0.6415"),
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
        
        # Add BANDUSDT main account monitor
        if 'BANDUSDT_main' in positions_data:
            pos = positions_data['BANDUSDT_main']
            key = 'BANDUSDT_Sell'
            if key not in current_monitors:
                print(f"➕ Adding {key}...")
                new_monitors[key] = {
                    "symbol": "BANDUSDT",
                    "side": "Sell",
                    "position_size": Decimal(str(pos.get('size', '307.3'))),
                    "remaining_size": Decimal(str(pos.get('size', '307.3'))),
                    "entry_price": Decimal(str(pos.get('avgPrice', '0.54453059'))),
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
        if 'BANDUSDT_mirror' in positions_data:
            pos = positions_data['BANDUSDT_mirror']
            key = 'BANDUSDT_Sell_MIRROR'
            if key not in current_monitors:
                print(f"➕ Adding {key}...")
                new_monitors[key] = {
                    "symbol": "BANDUSDT",
                    "side": "Sell",
                    "position_size": Decimal(str(pos.get('size', '110.5'))),
                    "remaining_size": Decimal(str(pos.get('size', '110.5'))),
                    "entry_price": Decimal(str(pos.get('avgPrice', '0.5446'))),
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
        if 'LQTYUSDT_main' in positions_data:
            pos = positions_data['LQTYUSDT_main']
            key = 'LQTYUSDT_Sell'
            if key not in current_monitors:
                print(f"➕ Adding {key}...")
                new_monitors[key] = {
                    "symbol": "LQTYUSDT",
                    "side": "Sell",
                    "position_size": Decimal(str(pos.get('size', '138.5'))),
                    "remaining_size": Decimal(str(pos.get('size', '138.5'))),
                    "entry_price": Decimal(str(pos.get('avgPrice', '1.1533'))),
                    "tp_prices": [Decimal("1.1313"), Decimal("1.1013"), Decimal("1.0718"), Decimal("0.9865")],
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
        if 'LQTYUSDT_mirror' in positions_data:
            pos = positions_data['LQTYUSDT_mirror']
            key = 'LQTYUSDT_Sell_MIRROR'
            if key not in current_monitors:
                print(f"➕ Adding {key}...")
                new_monitors[key] = {
                    "symbol": "LQTYUSDT",
                    "side": "Sell",
                    "position_size": Decimal(str(pos.get('size', '50'))),
                    "remaining_size": Decimal(str(pos.get('size', '50'))),
                    "entry_price": Decimal(str(pos.get('avgPrice', '1.1533'))),
                    "tp_prices": [Decimal("1.1313"), Decimal("1.1013"), Decimal("1.0718"), Decimal("0.9865")],
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
            
            print(f"✅ Added {len(new_monitors)} missing monitors")
            print(f"📊 Total Enhanced TP/SL monitors now: {len(current_monitors)}")
            
            # Create signal file for immediate reload
            signal_file = '/Users/lualakol/bybit-telegram-bot/reload_enhanced_monitors.signal'
            with open(signal_file, 'w') as f:
                f.write(f"{time.time()}\\nAdded 6 missing monitors live while bot running\\n")
            
            print("📡 Signal file created for immediate reload")
            print("=" * 60)
            print("🎉 MISSING 6 MONITORS ADDED LIVE!")
            print("🏆 SHOULD NOW HAVE 28/28 ENHANCED TP/SL MONITOR COVERAGE!")
            print("✅ Bot should reload automatically within 5 seconds")
        else:
            print("✅ All required monitors already exist")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(add_missing_6_monitors_live())