#!/usr/bin/env python3
"""
Restart Enhanced TP/SL monitors for active positions
"""

import asyncio
import logging
from config.settings import BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET, ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
from pybit.unified_trading import HTTP
from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
import pickle

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def restart_monitors():
    """Restart Enhanced TP/SL monitors for all active positions"""
    
    print("\n🔄 RESTARTING ENHANCED TP/SL MONITORS")
    print("=" * 60)
    
    # Initialize clients
    main_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    mirror_client = None
    if ENABLE_MIRROR_TRADING and BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
        mirror_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2
        )
    
    # Use the singleton Enhanced TP/SL manager instance
    manager = enhanced_tp_sl_manager
    
    # Load persistence data to get monitor info
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    try:
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        print(f"❌ Error loading persistence: {e}")
        return
    
    # Get enhanced monitors
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    print(f"\n📊 Found {len(enhanced_monitors)} Enhanced TP/SL monitors in persistence")
    
    # Check main account positions
    print("\n🔍 MAIN ACCOUNT POSITIONS:")
    try:
        response = main_client.get_positions(category="linear", settleCoin="USDT")
        if response.get("retCode") == 0:
            positions = response.get("result", {}).get("list", [])
            for pos in positions:
                if float(pos.get("size", 0)) > 0:
                    symbol = pos.get("symbol")
                    side = pos.get("side")
                    size = pos.get("size")
                    print(f"  • {symbol} {side}: {size}")
                    
                    # Check if monitor exists
                    monitor_key = f"{symbol}_{side}_main"
                    legacy_key = f"{symbol}_{side}"
                    
                    if monitor_key in enhanced_monitors or legacy_key in enhanced_monitors:
                        # Get monitor data
                        monitor_data = enhanced_monitors.get(monitor_key, enhanced_monitors.get(legacy_key))
                        
                        # Ensure tp_orders is dict format
                        if isinstance(monitor_data.get("tp_orders"), list):
                            tp_dict = {}
                            for order in monitor_data["tp_orders"]:
                                if isinstance(order, dict) and "order_id" in order:
                                    tp_dict[order["order_id"]] = order
                            monitor_data["tp_orders"] = tp_dict
                        
                        # Restart monitor
                        manager.position_monitors[monitor_key] = monitor_data
                        monitor_task = asyncio.create_task(manager._run_monitor_loop(symbol, side, "main"))
                        monitor_data["monitoring_task"] = monitor_task
                        print(f"    ✅ Restarted main monitor for {symbol} {side}")
                    else:
                        print(f"    ⚠️  No monitor found for {symbol} {side}")
    except Exception as e:
        print(f"❌ Error checking main positions: {e}")
    
    # Check mirror account positions
    if mirror_client:
        print("\n🔍 MIRROR ACCOUNT POSITIONS:")
        try:
            response = mirror_client.get_positions(category="linear", settleCoin="USDT")
            if response.get("retCode") == 0:
                positions = response.get("result", {}).get("list", [])
                for pos in positions:
                    if float(pos.get("size", 0)) > 0:
                        symbol = pos.get("symbol")
                        side = pos.get("side")
                        size = pos.get("size")
                        print(f"  • {symbol} {side}: {size}")
                        
                        # Check if monitor exists
                        monitor_key = f"{symbol}_{side}_mirror"
                        
                        if monitor_key in enhanced_monitors:
                            # Get monitor data
                            monitor_data = enhanced_monitors[monitor_key]
                            
                            # Ensure tp_orders is dict format
                            if isinstance(monitor_data.get("tp_orders"), list):
                                tp_dict = {}
                                for order in monitor_data["tp_orders"]:
                                    if isinstance(order, dict) and "order_id" in order:
                                        tp_dict[order["order_id"]] = order
                                monitor_data["tp_orders"] = tp_dict
                            
                            # Restart monitor
                            manager.position_monitors[monitor_key] = monitor_data
                            monitor_task = asyncio.create_task(manager._run_monitor_loop(symbol, side, "mirror"))
                            monitor_data["monitoring_task"] = monitor_task
                            print(f"    ✅ Restarted mirror monitor for {symbol} {side}")
                        else:
                            print(f"    ⚠️  No monitor found for {symbol} {side}")
        except Exception as e:
            print(f"❌ Error checking mirror positions: {e}")
    
    print("\n✅ Monitor restart complete!")
    print("   The monitors will now track TP/SL levels independently")
    print("   Mirror monitors will continue even if main monitors have errors")
    
    # Keep the script running to maintain the monitors
    print("\n🔄 Monitors are running... Press Ctrl+C to stop")
    try:
        while True:
            await asyncio.sleep(10)
    except KeyboardInterrupt:
        print("\n⏹️  Stopping monitors...")

if __name__ == "__main__":
    asyncio.run(restart_monitors())