#!/usr/bin/env python3
"""
Verify fill percentage calculations after position sync.
Shows current TP coverage for all positions.
"""

import asyncio
from decimal import Decimal
from typing import Dict, Any, List
from tabulate import tabulate
from pybit.unified_trading import HTTP
from config.settings import BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2, USE_TESTNET

class FillPercentageVerifier:
    def __init__(self):
        self.bybit_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY,
            api_secret=BYBIT_API_SECRET
        )
        
        self.mirror_client = None
        if BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
            self.mirror_client = HTTP(
                testnet=USE_TESTNET,
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2
            )
    
    def get_positions(self, client: HTTP) -> Dict[str, Dict[str, Any]]:
        """Get all positions from Bybit."""
        positions = {}
        try:
            response = client.get_positions(category="linear", settleCoin="USDT")
            if response["retCode"] == 0:
                for pos in response["result"]["list"]:
                    if float(pos["size"]) > 0:
                        symbol = pos["symbol"]
                        side = pos["side"]
                        key = f"{symbol}_{side}"
                        positions[key] = {
                            "symbol": symbol,
                            "side": side,
                            "size": float(pos["size"]),
                            "avgPrice": float(pos["avgPrice"]),
                            "markPrice": float(pos["markPrice"]),
                            "unrealisedPnl": float(pos["unrealisedPnl"])
                        }
        except Exception as e:
            print(f"❌ Error fetching positions: {e}")
        
        return positions
    
    def get_orders(self, client: HTTP, symbol: str) -> List[Dict[str, Any]]:
        """Get all open orders for a symbol."""
        orders = []
        try:
            response = client.get_open_orders(
                category="linear",
                symbol=symbol,
                limit=50
            )
            if response["retCode"] == 0:
                orders = response["result"]["list"]
        except Exception as e:
            print(f"❌ Error fetching orders for {symbol}: {e}")
        
        return orders
    
    def verify_fill_percentages(self):
        """Verify fill percentages for all positions."""
        print("=" * 100)
        print("FILL PERCENTAGE VERIFICATION")
        print("=" * 100)
        print()
        
        # Get positions from both accounts
        main_positions = self.get_positions(self.bybit_client)
        mirror_positions = self.get_positions(self.mirror_client) if self.mirror_client else {}
        
        print(f"📊 Checking {len(main_positions)} main account positions")
        print(f"📊 Checking {len(mirror_positions)} mirror account positions")
        print()
        
        # Check main account
        print("MAIN ACCOUNT:")
        print("-" * 100)
        self.check_account_positions(self.bybit_client, main_positions, "main")
        
        # Check mirror account
        if mirror_positions:
            print("\nMIRROR ACCOUNT:")
            print("-" * 100)
            self.check_account_positions(self.mirror_client, mirror_positions, "mirror")
        
        print("\n" + "=" * 100)
        print("VERIFICATION COMPLETE")
        print("=" * 100)
    
    def check_account_positions(self, client: HTTP, positions: Dict[str, Dict[str, Any]], account_type: str):
        """Check positions for a specific account."""
        results = []
        
        for pos_key, pos_data in positions.items():
            symbol = pos_data['symbol']
            side = pos_data['side']
            position_size = pos_data['size']
            
            # Get all orders
            orders = self.get_orders(client, symbol)
            
            # Separate TP and entry orders
            tp_orders = []
            entry_orders = []
            
            for order in orders:
                if order['side'] != side and order.get('reduceOnly'):
                    # TP order (opposite side, reduce only)
                    tp_orders.append(order)
                elif order['side'] == side:
                    # Entry order (same side)
                    entry_orders.append(order)
            
            # Calculate totals
            total_tp_qty = sum(float(o['qty']) for o in tp_orders)
            total_entry_qty = sum(float(o['qty']) for o in entry_orders)
            
            # Calculate fill percentages
            current_fill_pct = (total_tp_qty / position_size * 100) if position_size > 0 else 0
            
            # If we have pending entries, calculate what the fill % would be with full position
            potential_size = position_size + total_entry_qty
            potential_fill_pct = (total_tp_qty / potential_size * 100) if potential_size > 0 else 0
            
            status = "✅" if 99 <= current_fill_pct <= 101 else "⚠️"
            
            results.append({
                "Symbol": symbol,
                "Side": side,
                "Pos Size": f"{position_size:.2f}",
                "TP Orders": len(tp_orders),
                "TP Qty": f"{total_tp_qty:.2f}",
                "Fill %": f"{current_fill_pct:.1f}%",
                "Entry Orders": len(entry_orders),
                "Entry Qty": f"{total_entry_qty:.2f}",
                "Alt Fill %": f"{potential_fill_pct:.1f}%" if entry_orders else "-",
                "Status": status
            })
        
        if results:
            print(tabulate(results, headers="keys", tablefmt="grid"))
            
            # Summary
            correct_coverage = sum(1 for r in results if r["Status"] == "✅")
            print(f"\n📊 Summary for {account_type.upper()} account:")
            print(f"   Positions with correct TP coverage (99-101%): {correct_coverage}/{len(results)}")
            
            # Show positions with issues
            issues = [r for r in results if r["Status"] == "⚠️"]
            if issues:
                print(f"\n⚠️  Positions with incorrect TP coverage:")
                for issue in issues:
                    print(f"   - {issue['Symbol']} {issue['Side']}: {issue['Fill %']}")
                    if issue['Alt Fill %'] != "-":
                        print(f"     (Would be {issue['Alt Fill %']} with pending entries filled)")
        else:
            print("No positions found.")

async def main():
    """Main function."""
    verifier = FillPercentageVerifier()
    verifier.verify_fill_percentages()

if __name__ == "__main__":
    asyncio.run(main())