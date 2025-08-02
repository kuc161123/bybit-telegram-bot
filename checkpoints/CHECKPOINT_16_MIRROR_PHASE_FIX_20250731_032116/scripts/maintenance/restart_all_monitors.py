#!/usr/bin/env python3
"""
Restart monitors for all open positions on both main and mirror accounts.

IMPORTANT: This script assumes that for all currently open positions:
- All limit orders have already been filled
- Only TP and SL orders remain to be monitored
- This assumption only applies to existing positions at script runtime
- New positions opened after this script runs will work normally with full limit order tracking

This prevents the Conservative rebalancer from trying to recreate limit orders
for positions that have already had their entries filled.
"""

import asyncio
import logging
import sys
import os
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from pybit.unified_trading import HTTP

# Load environment variables first
load_dotenv()

from config import *
from config.constants import *
from clients.bybit_helpers import get_all_positions, get_order_info
from execution.monitor import monitor_position
from shared.state import MONITOR_INTERVAL

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor_restart.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MonitorRestarter:
    def __init__(self):
        """Initialize the monitor restarter."""
        self.main_client = HTTP(
            api_key=BYBIT_API_KEY,
            api_secret=BYBIT_API_SECRET,
            testnet=USE_TESTNET
        )
        
        self.mirror_client = None
        if BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
            self.mirror_client = HTTP(
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2,
                testnet=USE_TESTNET
            )
        
        # Track active monitors
        self.active_monitors = {}
        
    async def get_positions_with_approach(self, client: HTTP, account: str) -> List[Dict]:
        """Get all open positions and detect their trading approach."""
        positions_with_approach = []
        
        try:
            loop = asyncio.get_event_loop()
            
            # Get all positions
            response = await loop.run_in_executor(
                None,
                lambda: client.get_positions(category="linear", settleCoin="USDT")
            )
            
            if response and response.get("retCode") == 0:
                positions = response.get("result", {}).get("list", [])
                
                for pos in positions:
                    if float(pos.get("size", 0)) > 0:
                        symbol = pos["symbol"]
                        
                        # Get orders to detect approach
                        orders_response = await loop.run_in_executor(
                            None,
                            lambda: client.get_open_orders(category="linear", symbol=symbol)
                        )
                        
                        approach = "fast"  # Default
                        
                        if orders_response and orders_response.get("retCode") == 0:
                            orders = orders_response.get("result", {}).get("list", [])
                            
                            # Check for Conservative patterns
                            tp_orders = [
                                o for o in orders 
                                if ("TP" in o.get("orderLinkId", "") or o.get("stopOrderType") == "TakeProfit")
                                and ("CONS" in o.get("orderLinkId", "") or "cons" in o.get("orderLinkId", ""))
                            ]
                            
                            if len(tp_orders) >= 2:  # Multiple TPs = Conservative
                                approach = "conservative"
                            elif any("GGSHOT" in o.get("orderLinkId", "") for o in orders):
                                approach = "ggshot"
                        
                        position_data = {
                            "account": account,
                            "symbol": symbol,
                            "side": pos["side"],
                            "size": pos["size"],
                            "avgPrice": pos["avgPrice"],
                            "unrealizedPnl": pos.get("unrealisedPnl", "0"),
                            "approach": approach,
                            "positionIdx": pos.get("positionIdx", 0)
                        }
                        
                        positions_with_approach.append(position_data)
                        logger.info(f"📊 Found {account} position: {symbol} {pos['side']} {approach} approach")
            
            return positions_with_approach
            
        except Exception as e:
            logger.error(f"Error getting positions for {account}: {e}")
            return []
    
    async def create_monitor_task(self, position: Dict, chat_id: int = None) -> Optional[asyncio.Task]:
        """Create a monitor task for a position."""
        try:
            symbol = position["symbol"]
            approach = position["approach"]
            account = position["account"]
            
            # Use a default chat_id if not provided
            if chat_id is None:
                chat_id = 12345  # Default chat ID for automated monitors
            
            # Create chat data for the monitor
            chat_data = {
                TRADING_APPROACH: approach,
                SYMBOL_KEY: symbol,
                MONITORING_ENABLED: True,
                MONITOR_INTERVAL: 12,  # 12 seconds
                "position_side": position["side"],
                "entry_price": position["avgPrice"],
                "position_idx": position["positionIdx"],
                "is_mirror_account": account == "MIRROR",
                "original_position_size": position["size"]
            }
            
            # Add approach-specific data
            if approach == "conservative":
                # For existing positions, assume all limits are filled
                chat_data.update({
                    "conservative_tps_hit": [],
                    "conservative_limits_filled": 3,  # Assume all 3 limits filled
                    "conservative_total_limits": 3,
                    "all_limits_filled": True,  # Flag to indicate this is an existing position
                    "limits_filled_timestamp": datetime.now().isoformat(),
                    "monitor_restarted": True
                })
                logger.info(f"📝 Setting conservative position {symbol} as having all limits filled")
            
            # Create monitor key
            monitor_key = f"{account}_{symbol}_{approach}"
            
            # Check if monitor already exists
            if monitor_key in self.active_monitors:
                task = self.active_monitors[monitor_key]
                if not task.done():
                    logger.info(f"✅ Monitor already active for {monitor_key}")
                    return task
            
            # Create new monitor task
            logger.info(f"🚀 Starting {approach} monitor for {symbol} ({account})")
            
            # Create the monitor coroutine
            monitor_coro = monitor_position(
                chat_id=chat_id,
                chat_data=chat_data,
                ctx_app=None  # No app context for standalone monitors
            )
            
            # Create and track the task
            task = asyncio.create_task(monitor_coro)
            self.active_monitors[monitor_key] = task
            
            return task
            
        except Exception as e:
            logger.error(f"Error creating monitor for {position['symbol']}: {e}")
            return None
    
    async def restart_all_monitors(self):
        """Restart monitors for all positions on both accounts."""
        print("\n" + "="*80)
        print("RESTARTING ALL POSITION MONITORS")
        print("="*80)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\n⚠️  IMPORTANT: All existing positions will be marked as having")
        print("   their limit orders already filled. Only TP/SL will be monitored.")
        
        all_positions = []
        
        # Get positions from main account
        if self.main_client:
            logger.info("\n📊 Checking MAIN account positions...")
            main_positions = await self.get_positions_with_approach(self.main_client, "MAIN")
            all_positions.extend(main_positions)
            print(f"\nMain account: {len(main_positions)} positions")
            for pos in main_positions:
                print(f"  - {pos['symbol']} {pos['side']} ({pos['approach']})")
        
        # Get positions from mirror account
        if self.mirror_client:
            logger.info("\n📊 Checking MIRROR account positions...")
            mirror_positions = await self.get_positions_with_approach(self.mirror_client, "MIRROR")
            all_positions.extend(mirror_positions)
            print(f"\nMirror account: {len(mirror_positions)} positions")
            for pos in mirror_positions:
                print(f"  - {pos['symbol']} {pos['side']} ({pos['approach']})")
        
        if not all_positions:
            print("\n❌ No open positions found on either account")
            return
        
        # Create monitors for all positions
        print(f"\n🚀 Starting monitors for {len(all_positions)} positions...")
        
        tasks = []
        for position in all_positions:
            task = await self.create_monitor_task(position)
            if task:
                tasks.append(task)
        
        print(f"\n✅ Successfully started {len(tasks)} monitors")
        
        # Save monitor status
        status = {
            "timestamp": datetime.now().isoformat(),
            "total_positions": len(all_positions),
            "monitors_started": len(tasks),
            "positions": [
                {
                    "account": p["account"],
                    "symbol": p["symbol"],
                    "side": p["side"],
                    "approach": p["approach"],
                    "size": p["size"]
                }
                for p in all_positions
            ]
        }
        
        import json
        with open("monitor_restart_status.json", "w") as f:
            json.dump(status, f, indent=2)
        
        print(f"\n📄 Status saved to: monitor_restart_status.json")
        
        # Keep monitors running
        if tasks:
            print("\n🔄 Monitors are now running. Press Ctrl+C to stop.")
            try:
                # Keep the script running
                await asyncio.gather(*tasks, return_exceptions=True)
            except KeyboardInterrupt:
                print("\n⏹️  Stopping monitors...")
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                print("✅ All monitors stopped")

async def main():
    """Main function."""
    restarter = MonitorRestarter()
    
    try:
        await restarter.restart_all_monitors()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    # Run with proper event loop handling
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Script interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()