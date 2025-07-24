#!/usr/bin/env python3
"""
Simple script to restart monitors for all open positions.

IMPORTANT: This script assumes that for all currently open positions:
- All limit orders have already been filled  
- Only TP and SL orders remain to be monitored
- This only applies to existing positions when script runs
- New positions will work normally with full limit order tracking
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from pybit.unified_trading import HTTP
from config.settings import *

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def get_positions_and_orders():
    """Get all open positions and their orders from both accounts."""
    
    clients = {
        "MAIN": HTTP(
            api_key=BYBIT_API_KEY,
            api_secret=BYBIT_API_SECRET,
            testnet=USE_TESTNET
        )
    }
    
    if BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
        clients["MIRROR"] = HTTP(
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2,
            testnet=USE_TESTNET
        )
    
    all_data = []
    
    for account_name, client in clients.items():
        try:
            # Get positions
            pos_response = client.get_positions(category="linear", settleCoin="USDT")
            if pos_response.get("retCode") == 0:
                positions = pos_response["result"]["list"]
                
                for pos in positions:
                    if float(pos.get("size", 0)) > 0:
                        symbol = pos["symbol"]
                        
                        # Get orders for this position
                        order_response = client.get_open_orders(
                            category="linear", 
                            symbol=symbol,
                            limit=50
                        )
                        
                        orders = []
                        if order_response.get("retCode") == 0:
                            orders = order_response["result"]["list"]
                        
                        # Detect approach
                        tp_orders = [
                            o for o in orders 
                            if "TP" in o.get("orderLinkId", "") or o.get("stopOrderType") == "TakeProfit"
                        ]
                        
                        approach = "fast"
                        if len(tp_orders) >= 2:
                            approach = "conservative"
                        elif any("GGSHOT" in o.get("orderLinkId", "") for o in orders):
                            approach = "ggshot"
                        
                        position_data = {
                            "account": account_name,
                            "symbol": symbol,
                            "side": pos["side"],
                            "size": float(pos["size"]),
                            "avgPrice": float(pos["avgPrice"]),
                            "unrealizedPnl": float(pos.get("unrealisedPnl", 0)),
                            "approach": approach,
                            "tp_count": len(tp_orders),
                            "sl_count": len([o for o in orders if "SL" in o.get("orderLinkId", "") or o.get("stopOrderType") == "StopLoss"]),
                            "limit_count": len([o for o in orders if o.get("orderType") == "Limit" and "TP" not in o.get("orderLinkId", "")]),
                            "total_orders": len(orders)
                        }
                        
                        all_data.append(position_data)
                        
        except Exception as e:
            logger.error(f"Error getting data for {account_name}: {e}")
    
    return all_data

def create_monitor_config(positions: List[Dict]) -> Dict:
    """Create configuration for monitor restart."""
    
    config = {
        "timestamp": datetime.now().isoformat(),
        "total_positions": len(positions),
        "monitors": []
    }
    
    for pos in positions:
        monitor_data = {
            "account": pos["account"],
            "symbol": pos["symbol"],
            "side": pos["side"],
            "approach": pos["approach"],
            "size": pos["size"],
            "settings": {
                "assume_limits_filled": True,
                "conservative_limits_filled": 3 if pos["approach"] == "conservative" else 0,
                "monitor_interval": 12,
                "skip_limit_monitoring": True
            }
        }
        
        config["monitors"].append(monitor_data)
    
    return config

async def main():
    """Main function."""
    
    print("\n" + "="*80)
    print("POSITION MONITOR RESTART CONFIGURATION")
    print("="*80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n⚠️  IMPORTANT: All existing positions will be configured as having")
    print("   their limit orders already filled. Only TP/SL will be monitored.")
    
    # Get current positions
    print("\n📊 Fetching current positions...")
    positions = await get_positions_and_orders()
    
    if not positions:
        print("\n❌ No open positions found")
        return
    
    # Display positions
    print(f"\n✅ Found {len(positions)} open positions:\n")
    
    for i, pos in enumerate(positions, 1):
        print(f"{i}. {pos['account']:6} | {pos['symbol']:12} | {pos['side']:4} | "
              f"Size: {pos['size']:10.4f} | {pos['approach']:12} | "
              f"TP: {pos['tp_count']} | SL: {pos['sl_count']} | Limit: {pos['limit_count']}")
    
    # Create monitor configuration
    config = create_monitor_config(positions)
    
    # Save configuration
    config_file = "monitor_restart_config.json"
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"\n📄 Monitor configuration saved to: {config_file}")
    
    # Generate restart instructions
    print("\n" + "="*80)
    print("RESTART INSTRUCTIONS")
    print("="*80)
    
    print("\n1. Stop the current bot if running:")
    print("   - Press Ctrl+C in the bot terminal")
    print("   - Or run: pkill -f 'python main.py'")
    
    print("\n2. Apply the monitor configuration:")
    print("   - The saved configuration marks all positions as having filled limits")
    print("   - This prevents the Conservative rebalancer from recreating limit orders")
    
    print("\n3. Restart the bot:")
    print("   - Run: python main.py")
    print("   - The bot will load existing positions and monitor only TP/SL orders")
    
    print("\n4. For new positions opened after restart:")
    print("   - They will work normally with full limit order tracking")
    print("   - Only pre-existing positions are marked as having filled limits")
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    # Summary by account
    from collections import defaultdict
    by_account = defaultdict(lambda: {"count": 0, "approaches": defaultdict(int)})
    
    for pos in positions:
        by_account[pos["account"]]["count"] += 1
        by_account[pos["account"]]["approaches"][pos["approach"]] += 1
    
    for account, data in by_account.items():
        print(f"\n{account} Account:")
        print(f"  Total positions: {data['count']}")
        for approach, count in data["approaches"].items():
            print(f"  - {approach}: {count}")
    
    print("\n✅ Configuration complete. Follow the restart instructions above.")

if __name__ == "__main__":
    asyncio.run(main())