#!/usr/bin/env python3
"""
Add Missing XTZUSDT Monitors to Complete 28/28 Coverage
This should be the final monitor addition to achieve full coverage
"""
import asyncio
import sys
import os
import pickle
import time
from decimal import Decimal

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

async def add_missing_xtzusdt_monitors():
    """Add the missing XTZUSDT monitors to achieve 28/28 coverage"""
    try:
        print("🎯 ADDING MISSING XTZUSDT MONITORS FOR 28/28 COVERAGE")
        print("=" * 60)
        
        # Get actual positions from both accounts
        from clients.bybit_helpers import get_all_positions_with_client
        from clients.bybit_client import bybit_client
        from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
        
        # Check actual positions
        main_positions = await get_all_positions_with_client(bybit_client)
        main_open = [p for p in main_positions if float(p.get('size', 0)) > 0]
        
        mirror_open = []
        if is_mirror_trading_enabled() and bybit_client_2:
            mirror_positions = await get_all_positions_with_client(bybit_client_2)
            mirror_open = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
        
        # Find XTZUSDT positions
        xtz_main = None
        xtz_mirror = None
        
        for pos in main_open:
            if pos.get('symbol') == 'XTZUSDT':
                xtz_main = pos
                break
                
        for pos in mirror_open:
            if pos.get('symbol') == 'XTZUSDT':
                xtz_mirror = pos
                break
        
        print(f"🔍 XTZUSDT Main Position: {xtz_main}")
        print(f"🔍 XTZUSDT Mirror Position: {xtz_mirror}")
        
        # Load current persistence data
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        current_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        print(f"📊 Current Enhanced TP/SL monitors: {len(current_monitors)}")
        
        # Check if XTZUSDT monitors exist
        xtz_main_key = 'XTZUSDT_Sell'
        xtz_mirror_key = 'XTZUSDT_Sell_MIRROR'
        
        xtz_main_exists = xtz_main_key in current_monitors
        xtz_mirror_exists = xtz_mirror_key in current_monitors
        
        print(f"🔍 XTZUSDT Main monitor exists: {xtz_main_exists}")
        print(f"🔍 XTZUSDT Mirror monitor exists: {xtz_mirror_exists}")
        
        new_monitors = {}
        
        # Add main account monitor if missing and position exists
        if not xtz_main_exists and xtz_main:
            print(f"➕ Adding XTZUSDT main account monitor (size: {xtz_main.get('size')})...")
            new_monitors[xtz_main_key] = {
                "symbol": "XTZUSDT",
                "side": "Sell",
                "position_size": Decimal(str(xtz_main.get('size', '324.0'))),
                "remaining_size": Decimal(str(xtz_main.get('size', '324.0'))),
                "entry_price": Decimal(str(xtz_main.get('avgPrice', '0.6620'))),
                "tp_prices": [Decimal("0.6491"), Decimal("0.6323"), Decimal("0.6157"), Decimal("0.5659")],
                "tp_percentages": [Decimal("85"), Decimal("5"), Decimal("5"), Decimal("5")],
                "sl_price": Decimal("0.8193"),
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
        
        # Add mirror account monitor if missing and position exists
        if not xtz_mirror_exists and xtz_mirror:
            print(f"➕ Adding XTZUSDT mirror account monitor (size: {xtz_mirror.get('size')})...")
            new_monitors[xtz_mirror_key] = {
                "symbol": "XTZUSDT",
                "side": "Sell",
                "position_size": Decimal(str(xtz_mirror.get('size', '116.8'))),
                "remaining_size": Decimal(str(xtz_mirror.get('size', '116.8'))),
                "entry_price": Decimal(str(xtz_mirror.get('avgPrice', '0.6620'))),
                "tp_prices": [Decimal("0.6491"), Decimal("0.6323"), Decimal("0.6157"), Decimal("0.5659")],
                "tp_percentages": [Decimal("85"), Decimal("5"), Decimal("5"), Decimal("5")],
                "sl_price": Decimal("0.8193"),
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
            
            print(f"✅ Added {len(new_monitors)} new XTZUSDT monitors")
            print(f"📊 Total Enhanced TP/SL monitors now: {len(current_monitors)}")
            
            # Create signal file for reload
            signal_file = '/Users/lualakol/bybit-telegram-bot/reload_enhanced_monitors.signal'
            with open(signal_file, 'w') as f:
                f.write(f"{time.time()}\\nAdded XTZUSDT monitors for 28/28 coverage\\n")
            
            print("📡 Signal file created for monitor reload")
            print("=" * 60)
            print("🎉 XTZUSDT MONITORS ADDED - TARGETING 28/28 COVERAGE!")
            print("The Enhanced TP/SL Manager should now monitor all positions")
        else:
            print("✅ All XTZUSDT monitors already exist or no positions found")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(add_missing_xtzusdt_monitors())