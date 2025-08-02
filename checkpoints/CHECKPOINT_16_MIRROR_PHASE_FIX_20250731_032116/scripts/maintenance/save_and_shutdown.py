#!/usr/bin/env python3
"""
Safe shutdown script for Bybit Telegram Bot
Saves all state data and prepares for clean restart
"""

import asyncio
import pickle
import json
import os
import sys
from datetime import datetime
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import *
from clients.bybit_client import bybit_client
from clients.bybit_helpers import get_all_positions, get_all_open_orders
from shared.state import chat_data, _cleanup_tasks
from utils.trade_logger import TradeLogger

async def save_bot_state():
    """Save all bot state data before shutdown"""
    
    print("\n=== BYBIT TELEGRAM BOT SAFE SHUTDOWN ===")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create backup directory
    backup_dir = Path("data/shutdown_backup")
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    results = {
        "timestamp": timestamp,
        "main_account": {
            "positions": [],
            "orders": [],
            "monitors": []
        },
        "mirror_account": {
            "positions": [],
            "orders": [],
            "monitors": []
        },
        "state_files": [],
        "trade_history": None
    }
    
    try:
        # 1. Initialize Bybit clients
        print("\n1. Initializing Bybit clients...")
        # Main client is already initialized globally
        main_client = bybit_client
        
        # Mirror client needs to be created if credentials exist
        mirror_client = None
        if os.getenv("BYBIT_API_KEY_2") and os.getenv("BYBIT_API_SECRET_2"):
            # Create mirror client manually
            from pybit.unified_trading import HTTP
            mirror_client = HTTP(
                api_key=os.getenv("BYBIT_API_KEY_2"),
                api_secret=os.getenv("BYBIT_API_SECRET_2"),
                testnet=os.getenv("USE_TESTNET", "false").lower() == "true"
            )
        
        # 2. Get current positions and orders
        print("\n2. Fetching current positions and orders...")
        
        # Main account
        main_positions = await get_all_positions()
        main_orders = await get_all_open_orders()
        
        for pos in main_positions:
            if float(pos.get('qty', 0)) > 0:
                results["main_account"]["positions"].append({
                    "symbol": pos["symbol"],
                    "side": pos["side"],
                    "qty": pos["qty"],
                    "avgPrice": pos.get("avgPrice", "0"),
                    "unrealisedPnl": pos.get("unrealisedPnl", "0"),
                    "positionIdx": pos.get("positionIdx", 0)
                })
        
        for order in main_orders:
            results["main_account"]["orders"].append({
                "symbol": order["symbol"],
                "side": order["side"],
                "orderType": order["orderType"],
                "qty": order["qty"],
                "price": order.get("price", "0"),
                "triggerPrice": order.get("triggerPrice", "0"),
                "orderId": order["orderId"],
                "orderLinkId": order.get("orderLinkId", ""),
                "stopOrderType": order.get("stopOrderType", "")
            })
        
        # Mirror account
        if mirror_client:
            # Use direct API calls for mirror client
            try:
                mirror_positions_response = mirror_client.get_positions(category="linear", settleCoin="USDT")
                mirror_positions = mirror_positions_response.get("result", {}).get("list", [])
                
                mirror_orders_response = mirror_client.get_open_orders(category="linear", settleCoin="USDT")
                mirror_orders = mirror_orders_response.get("result", {}).get("list", [])
            except Exception as e:
                print(f"   Warning: Could not fetch mirror account data: {e}")
                mirror_positions = []
                mirror_orders = []
            
            for pos in mirror_positions:
                if float(pos.get('qty', 0)) > 0:
                    results["mirror_account"]["positions"].append({
                        "symbol": pos["symbol"],
                        "side": pos["side"],
                        "qty": pos["qty"],
                        "avgPrice": pos.get("avgPrice", "0"),
                        "unrealisedPnl": pos.get("unrealisedPnl", "0"),
                        "positionIdx": pos.get("positionIdx", 0)
                    })
            
            for order in mirror_orders:
                results["mirror_account"]["orders"].append({
                    "symbol": order["symbol"],
                    "side": order["side"],
                    "orderType": order["orderType"],
                    "qty": order["qty"],
                    "price": order.get("price", "0"),
                    "triggerPrice": order.get("triggerPrice", "0"),
                    "orderId": order["orderId"],
                    "orderLinkId": order.get("orderLinkId", ""),
                    "stopOrderType": order.get("stopOrderType", "")
                })
        
        # 3. Check active monitors from chat_data
        print("\n3. Checking active monitors...")
        for chat_id, data in chat_data.items():
            if 'monitors' in data:
                for monitor_key, monitor_info in data['monitors'].items():
                    results["main_account"]["monitors"].append({
                        "chat_id": chat_id,
                        "monitor_key": monitor_key,
                        "symbol": monitor_info.get("symbol", "Unknown"),
                        "approach": monitor_info.get("approach", "Unknown"),
                        "created_at": monitor_info.get("created_at", "Unknown")
                    })
        
        # 4. Backup state files
        print("\n4. Backing up state files...")
        state_files = [
            "bybit_bot_dashboard_v4.1_enhanced.pkl",
            "alerts_data.pkl",
            "data/trade_history.json",
            "data/failed_alerts.json",
            "data/operation_history.json"
        ]
        
        for file in state_files:
            if os.path.exists(file):
                backup_path = backup_dir / f"{timestamp}_{os.path.basename(file)}"
                shutil.copy2(file, backup_path)
                results["state_files"].append({
                    "original": file,
                    "backup": str(backup_path),
                    "size": os.path.getsize(file)
                })
                print(f"   Backed up: {file} -> {backup_path}")
        
        # 5. Save dashboard state with proper persistence
        print("\n5. Saving dashboard state...")
        dashboard_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
        if os.path.exists(dashboard_file):
            # Force save current state
            try:
                with open(dashboard_file, 'rb') as f:
                    current_state = pickle.load(f)
                
                # Update with current monitor info
                if 'active_monitors' not in current_state:
                    current_state['active_monitors'] = {}
                
                # Save monitors from chat_data
                for chat_id, data in chat_data.items():
                    if 'monitors' in data:
                        for monitor_key, monitor_info in data['monitors'].items():
                            current_state['active_monitors'][monitor_key] = {
                                "symbol": monitor_info.get("symbol"),
                                "side": monitor_info.get("side"),
                                "approach": monitor_info.get("approach"),
                                "chat_id": chat_id,
                                "created_at": monitor_info.get("created_at"),
                                "last_update": datetime.now().isoformat()
                            }
                
                # Save updated state
                with open(dashboard_file, 'wb') as f:
                    pickle.dump(current_state, f)
                print("   Dashboard state saved successfully")
            except Exception as e:
                print(f"   Warning: Could not update dashboard state: {e}")
        
        # 6. Save trade history
        print("\n6. Checking trade history...")
        if os.path.exists("data/trade_history.json"):
            with open("data/trade_history.json", 'r') as f:
                trade_history = json.load(f)
                results["trade_history"] = {
                    "total_trades": len(trade_history.get("trades", [])),
                    "last_trade": trade_history.get("trades", [{}])[-1] if trade_history.get("trades") else None
                }
        
        # 7. Save shutdown report
        report_path = backup_dir / f"shutdown_report_{timestamp}.json"
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n7. Shutdown report saved to: {report_path}")
        
        # 8. Display summary
        print("\n=== SHUTDOWN SUMMARY ===")
        print(f"\nMain Account:")
        print(f"  Active Positions: {len(results['main_account']['positions'])}")
        print(f"  Open Orders: {len(results['main_account']['orders'])}")
        print(f"  Active Monitors: {len(results['main_account']['monitors'])}")
        
        if results['main_account']['positions']:
            print("\n  Positions:")
            for pos in results['main_account']['positions']:
                print(f"    - {pos['symbol']} {pos['side']}: {pos['qty']} @ {pos['avgPrice']} (PnL: {pos['unrealisedPnl']})")
        
        if mirror_client:
            print(f"\nMirror Account:")
            print(f"  Active Positions: {len(results['mirror_account']['positions'])}")
            print(f"  Open Orders: {len(results['mirror_account']['orders'])}")
            
            if results['mirror_account']['positions']:
                print("\n  Positions:")
                for pos in results['mirror_account']['positions']:
                    print(f"    - {pos['symbol']} {pos['side']}: {pos['qty']} @ {pos['avgPrice']} (PnL: {pos['unrealisedPnl']})")
        
        print(f"\nBackup Files Created: {len(results['state_files'])}")
        print(f"Backup Directory: {backup_dir}")
        
        # 9. Cancel all background tasks
        print("\n9. Cancelling background tasks...")
        if _cleanup_tasks:
            for task in _cleanup_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*_cleanup_tasks, return_exceptions=True)
            print(f"   Cancelled {len(_cleanup_tasks)} background tasks")
        
        # 10. Close client connections
        print("\n10. Closing client connections...")
        # Clients don't need explicit closing with pybit
        
        print("\n=== SHUTDOWN COMPLETE ===")
        print("\nIMPORTANT: The bot state has been saved. When restarting:")
        print("1. The bot will recognize existing positions and orders")
        print("2. Monitors will be recreated for active positions")
        print("3. No duplicate orders will be created")
        print("\nTo stop the bot process, use one of these commands:")
        print("  - Press Ctrl+C in the terminal running the bot")
        print("  - Run: ./kill_bot.sh")
        print("  - Run: pkill -f 'python main.py'")
        
        return True
        
    except Exception as e:
        print(f"\nERROR during shutdown: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main entry point"""
    success = await save_bot_state()
    if success:
        print("\n✅ Safe shutdown completed successfully")
        sys.exit(0)
    else:
        print("\n❌ Shutdown encountered errors")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())