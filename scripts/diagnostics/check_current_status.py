#!/usr/bin/env python3
"""
Check current status of both main and mirror accounts
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List
from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET,
    ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
)
from pybit.unified_trading import HTTP

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class StatusChecker:
    def __init__(self):
        # Main account client
        self.main_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY,
            api_secret=BYBIT_API_SECRET
        )
        
        # Mirror account client
        self.mirror_client = None
        if ENABLE_MIRROR_TRADING and BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
            self.mirror_client = HTTP(
                testnet=USE_TESTNET,
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2
            )
    
    async def check_account(self, client: HTTP, account_name: str):
        """Check positions and orders for an account"""
        print(f"\n{'='*60}")
        print(f"{account_name} ACCOUNT STATUS")
        print(f"{'='*60}")
        
        # Check positions
        print("\n📊 POSITIONS:")
        try:
            response = client.get_positions(category="linear", settleCoin="USDT")
            if response.get("retCode") == 0:
                positions = []
                total_pnl = 0
                
                for pos in response.get("result", {}).get("list", []):
                    if float(pos.get('size', 0)) > 0:
                        positions.append(pos)
                        total_pnl += float(pos.get('unrealisedPnl', 0))
                
                if positions:
                    print(f"Found {len(positions)} active positions:")
                    for pos in positions:
                        symbol = pos.get('symbol')
                        side = pos.get('side')
                        size = pos.get('size')
                        pnl = float(pos.get('unrealisedPnl', 0))
                        pnl_color = "🟢" if pnl >= 0 else "🔴"
                        print(f"  {pnl_color} {symbol} {side}: Size={size}, P&L=${pnl:.2f}")
                    print(f"\nTotal Unrealized P&L: ${total_pnl:.2f}")
                else:
                    print("✅ No active positions")
            else:
                print(f"❌ Error getting positions: {response}")
        except Exception as e:
            print(f"❌ Exception getting positions: {e}")
        
        # Check orders
        print("\n📝 ORDERS:")
        try:
            response = client.get_open_orders(category="linear", settleCoin="USDT", limit=50)
            if response.get("retCode") == 0:
                orders = response.get("result", {}).get("list", [])
                
                if orders:
                    # Group by symbol and type
                    orders_by_symbol = {}
                    for order in orders:
                        symbol = order.get('symbol')
                        if symbol not in orders_by_symbol:
                            orders_by_symbol[symbol] = {"TP": 0, "SL": 0, "Limit": 0}
                        
                        link_id = order.get('orderLinkId', '')
                        if 'TP' in link_id:
                            orders_by_symbol[symbol]["TP"] += 1
                        elif 'SL' in link_id:
                            orders_by_symbol[symbol]["SL"] += 1
                        else:
                            orders_by_symbol[symbol]["Limit"] += 1
                    
                    print(f"Found {len(orders)} open orders:")
                    for symbol, counts in orders_by_symbol.items():
                        order_summary = []
                        if counts["TP"] > 0:
                            order_summary.append(f"{counts['TP']} TP")
                        if counts["SL"] > 0:
                            order_summary.append(f"{counts['SL']} SL")
                        if counts["Limit"] > 0:
                            order_summary.append(f"{counts['Limit']} Limit")
                        print(f"  {symbol}: {', '.join(order_summary)}")
                else:
                    print("✅ No open orders")
            else:
                print(f"❌ Error getting orders: {response}")
        except Exception as e:
            print(f"❌ Exception getting orders: {e}")
        
        # Check for order/position mismatches
        print("\n🔍 CHECKING FOR ISSUES:")
        issues_found = False
        
        try:
            # Get positions again for detailed check
            pos_response = client.get_positions(category="linear", settleCoin="USDT")
            order_response = client.get_open_orders(category="linear", settleCoin="USDT", limit=50)
            
            if pos_response.get("retCode") == 0 and order_response.get("retCode") == 0:
                positions = {}
                for pos in pos_response.get("result", {}).get("list", []):
                    if float(pos.get('size', 0)) > 0:
                        symbol = pos.get('symbol')
                        positions[symbol] = float(pos.get('size'))
                
                orders = order_response.get("result", {}).get("list", [])
                
                # Check each position has proper orders
                for symbol, pos_size in positions.items():
                    symbol_orders = [o for o in orders if o.get('symbol') == symbol]
                    
                    tp_total = 0
                    sl_total = 0
                    
                    for order in symbol_orders:
                        if order.get('reduceOnly'):
                            qty = float(order.get('qty', 0))
                            link_id = order.get('orderLinkId', '')
                            
                            if 'TP' in link_id:
                                tp_total += qty
                            elif 'SL' in link_id:
                                sl_total += qty
                    
                    # Check for mismatches
                    if abs(tp_total - pos_size) > 1:
                        print(f"  ⚠️ {symbol}: TP orders ({tp_total}) don't match position size ({pos_size})")
                        issues_found = True
                    
                    if abs(sl_total - pos_size) > 1:
                        print(f"  ⚠️ {symbol}: SL orders ({sl_total}) don't match position size ({pos_size})")
                        issues_found = True
                
                # Check for orphaned orders (orders without positions)
                for order in orders:
                    symbol = order.get('symbol')
                    if order.get('reduceOnly') and symbol not in positions:
                        print(f"  ⚠️ {symbol}: Found orphaned reduce-only order (no position)")
                        issues_found = True
                
                if not issues_found:
                    print("  ✅ No issues detected")
                    
        except Exception as e:
            print(f"  ❌ Error checking for issues: {e}")
    
    async def run(self):
        """Main execution"""
        print("=" * 80)
        print("CURRENT ACCOUNT STATUS CHECK")
        print("=" * 80)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Check main account
        await self.check_account(self.main_client, "MAIN")
        
        # Check mirror account
        if self.mirror_client:
            await self.check_account(self.mirror_client, "MIRROR")
        
        print("\n" + "=" * 80)
        print("STATUS CHECK COMPLETE")
        print("=" * 80)


async def main():
    """Entry point"""
    checker = StatusChecker()
    await checker.run()


if __name__ == "__main__":
    asyncio.run(main())