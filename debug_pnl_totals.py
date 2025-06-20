#!/usr/bin/env python3
"""
Debug script to analyze P&L totals and position calculations.
Helps identify discrepancies in aggregate P&L calculations.
"""

import asyncio
import os
import sys
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_client import BybitClient
from config.settings import settings
from shared.logging import logger

class PnLDebugger:
    def __init__(self):
        self.client = BybitClient()
        self.positions = []
        
    async def fetch_all_positions(self) -> List[Dict[str, Any]]:
        """Fetch ALL positions with proper pagination"""
        all_positions = []
        cursor = ""
        page = 1
        
        print("\n=== FETCHING ALL POSITIONS ===")
        
        while True:
            try:
                response = await self.client.get_positions(
                    category="linear",
                    limit=200,  # Max limit
                    cursor=cursor if cursor else None
                )
                
                if response["retCode"] != 0:
                    print(f"Error fetching positions: {response['retMsg']}")
                    break
                
                positions = response["result"]["list"]
                all_positions.extend(positions)
                
                print(f"Page {page}: Fetched {len(positions)} positions")
                
                # Check for next page
                next_cursor = response["result"].get("nextPageCursor", "")
                if not next_cursor:
                    break
                    
                cursor = next_cursor
                page += 1
                
            except Exception as e:
                print(f"Error during pagination: {e}")
                break
        
        # Filter for active positions only
        active_positions = [p for p in all_positions if float(p.get("size", 0)) > 0]
        
        print(f"\nTotal positions fetched: {len(all_positions)}")
        print(f"Active positions (size > 0): {len(active_positions)}")
        
        return active_positions
    
    def calculate_position_pnl(self, position: Dict[str, Any]) -> Dict[str, Decimal]:
        """Calculate P&L for a single position"""
        try:
            symbol = position.get("symbol", "")
            side = position.get("side", "")
            size = Decimal(str(position.get("size", 0)))
            avg_price = Decimal(str(position.get("avgPrice", 0)))
            mark_price = Decimal(str(position.get("markPrice", 0)))
            unrealized_pnl = Decimal(str(position.get("unrealizedPnl", 0)))
            
            # Calculate price for 1% profit
            if side == "Buy":
                tp1_price = avg_price * Decimal("1.01")  # 1% above entry
                sl_price = avg_price * Decimal("0.99")   # 1% below entry
            else:  # Sell
                tp1_price = avg_price * Decimal("0.99")  # 1% below entry
                sl_price = avg_price * Decimal("1.01")   # 1% above entry
            
            # Calculate P&L for TP1 (1% profit)
            tp1_pnl = size * avg_price * Decimal("0.01")
            
            # For all TPs, assume conservative strategy:
            # TP1: 70% at 1%, TP2: 10% at 2%, TP3: 10% at 3%, TP4: 10% at 4%
            all_tp_pnl = (
                size * avg_price * Decimal("0.007") +  # 70% at 1%
                size * avg_price * Decimal("0.002") +  # 10% at 2%
                size * avg_price * Decimal("0.003") +  # 10% at 3%
                size * avg_price * Decimal("0.004")    # 10% at 4%
            )
            
            # Calculate SL P&L (1% loss)
            sl_pnl = -size * avg_price * Decimal("0.01")
            
            return {
                "symbol": symbol,
                "side": side,
                "size": size,
                "avg_price": avg_price,
                "mark_price": mark_price,
                "unrealized_pnl": unrealized_pnl,
                "tp1_pnl": tp1_pnl,
                "all_tp_pnl": all_tp_pnl,
                "sl_pnl": sl_pnl,
                "tp1_price": tp1_price,
                "sl_price": sl_price
            }
            
        except Exception as e:
            print(f"Error calculating P&L for position: {e}")
            return None
    
    async def analyze_pnl(self):
        """Main analysis function"""
        print("\n" + "="*60)
        print("P&L TOTALS DEBUG ANALYSIS")
        print("="*60)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Fetch all positions
        self.positions = await self.fetch_all_positions()
        
        if not self.positions:
            print("\nNo active positions found!")
            return
        
        # Calculate P&L for each position
        position_details = []
        total_tp1_pnl = Decimal("0")
        total_all_tp_pnl = Decimal("0")
        total_sl_pnl = Decimal("0")
        total_unrealized_pnl = Decimal("0")
        
        print("\n=== INDIVIDUAL POSITION ANALYSIS ===")
        print("-" * 120)
        print(f"{'Symbol':<15} {'Side':<5} {'Size':<12} {'Avg Price':<10} {'Mark Price':<10} "
              f"{'Unreal P&L':<12} {'TP1 P&L':<12} {'All TP P&L':<12} {'SL P&L':<12}")
        print("-" * 120)
        
        for i, pos in enumerate(self.positions, 1):
            details = self.calculate_position_pnl(pos)
            if details:
                position_details.append(details)
                
                # Accumulate totals
                total_tp1_pnl += details["tp1_pnl"]
                total_all_tp_pnl += details["all_tp_pnl"]
                total_sl_pnl += details["sl_pnl"]
                total_unrealized_pnl += details["unrealized_pnl"]
                
                # Print position details
                print(f"{details['symbol']:<15} {details['side']:<5} "
                      f"{float(details['size']):<12.4f} "
                      f"{float(details['avg_price']):<10.4f} "
                      f"{float(details['mark_price']):<10.4f} "
                      f"${float(details['unrealized_pnl']):<11.2f} "
                      f"${float(details['tp1_pnl']):<11.2f} "
                      f"${float(details['all_tp_pnl']):<11.2f} "
                      f"${float(details['sl_pnl']):<11.2f}")
        
        print("-" * 120)
        
        # Print aggregate totals
        print("\n=== AGGREGATE TOTALS ===")
        print(f"Total Positions: {len(self.positions)}")
        print(f"Current Unrealized P&L: ${float(total_unrealized_pnl):,.2f}")
        print(f"Total TP1 P&L (1% profit): ${float(total_tp1_pnl):,.2f}")
        print(f"Total All TP P&L (Conservative): ${float(total_all_tp_pnl):,.2f}")
        print(f"Total SL P&L (1% loss): ${float(total_sl_pnl):,.2f}")
        
        # Calculate position value statistics
        total_position_value = sum(
            Decimal(str(p.get("size", 0))) * Decimal(str(p.get("avgPrice", 0)))
            for p in self.positions
        )
        
        print(f"\nTotal Position Value: ${float(total_position_value):,.2f}")
        print(f"Average Position Size: ${float(total_position_value / len(self.positions)):,.2f}")
        
        # Group by symbol for analysis
        print("\n=== POSITIONS BY SYMBOL ===")
        symbol_groups = {}
        for details in position_details:
            symbol = details["symbol"]
            if symbol not in symbol_groups:
                symbol_groups[symbol] = {
                    "count": 0,
                    "total_size": Decimal("0"),
                    "total_tp1_pnl": Decimal("0"),
                    "total_all_tp_pnl": Decimal("0"),
                    "total_sl_pnl": Decimal("0")
                }
            
            symbol_groups[symbol]["count"] += 1
            symbol_groups[symbol]["total_size"] += details["size"]
            symbol_groups[symbol]["total_tp1_pnl"] += details["tp1_pnl"]
            symbol_groups[symbol]["total_all_tp_pnl"] += details["all_tp_pnl"]
            symbol_groups[symbol]["total_sl_pnl"] += details["sl_pnl"]
        
        print(f"{'Symbol':<15} {'Count':<7} {'Total Size':<12} {'TP1 P&L':<12} {'All TP P&L':<12} {'SL P&L':<12}")
        print("-" * 80)
        
        for symbol, data in sorted(symbol_groups.items()):
            print(f"{symbol:<15} {data['count']:<7} "
                  f"{float(data['total_size']):<12.4f} "
                  f"${float(data['total_tp1_pnl']):<11.2f} "
                  f"${float(data['total_all_tp_pnl']):<11.2f} "
                  f"${float(data['total_sl_pnl']):<11.2f}")
        
        # Check for potential issues
        print("\n=== POTENTIAL ISSUES ===")
        
        # Check for positions with zero size
        zero_size = [p for p in self.positions if float(p.get("size", 0)) == 0]
        if zero_size:
            print(f"⚠️  Found {len(zero_size)} positions with zero size")
        
        # Check for positions with missing data
        missing_data = []
        for p in self.positions:
            if not p.get("avgPrice") or not p.get("markPrice"):
                missing_data.append(p.get("symbol", "Unknown"))
        
        if missing_data:
            print(f"⚠️  Positions with missing price data: {', '.join(missing_data)}")
        
        # Check for extreme unrealized P&L
        extreme_pnl = []
        for details in position_details:
            pnl_percent = (details["unrealized_pnl"] / (details["size"] * details["avg_price"])) * 100
            if abs(float(pnl_percent)) > 10:
                extreme_pnl.append({
                    "symbol": details["symbol"],
                    "pnl_percent": float(pnl_percent)
                })
        
        if extreme_pnl:
            print(f"⚠️  Positions with extreme unrealized P&L (>10%):")
            for ep in extreme_pnl:
                print(f"   - {ep['symbol']}: {ep['pnl_percent']:.2f}%")
        
        print("\n" + "="*60)
        print("DEBUG ANALYSIS COMPLETE")
        print("="*60)

async def main():
    """Main entry point"""
    try:
        debugger = PnLDebugger()
        await debugger.analyze_pnl()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Ensure cleanup
        if hasattr(debugger, 'client') and debugger.client:
            await debugger.client.close()

if __name__ == "__main__":
    asyncio.run(main())