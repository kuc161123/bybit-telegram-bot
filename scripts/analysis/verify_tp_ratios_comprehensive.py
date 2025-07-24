#!/usr/bin/env python3
"""
Comprehensive analysis of TP order ratios for all positions on both accounts.
Verifies if quantities follow the expected 85/5/5/5 ratio.
"""

import asyncio
import os
import sys
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_client import bybit_client
from clients.bybit_helpers import get_open_orders
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled


class TPRatioAnalyzer:
    """Analyzes TP order ratios for positions"""
    
    EXPECTED_RATIOS = [85, 5, 5, 5]  # Expected percentages
    TOLERANCE = 1.0  # 1% tolerance for ratio matching
    
    def __init__(self):
        self.main_client = bybit_client
        self.mirror_client = bybit_client_2 if is_mirror_trading_enabled() else None
    
    async def analyze_position_tp_orders(self, client, account_type: str, position: dict) -> dict:
        """Analyze TP orders for a single position"""
        symbol = position['symbol']
        side = position['side']
        position_size = float(position['size'])
        
        # Get all orders for this symbol
        if account_type == "MAIN":
            orders = await get_open_orders(symbol)
        else:
            response = client.get_open_orders(category="linear", symbol=symbol)
            orders = response.get('result', {}).get('list', []) if response.get('retCode') == 0 else []
        
        # Filter TP orders for this position
        tp_orders = []
        for order in orders:
            order_type = order.get('orderType', '')
            reduce_only = order.get('reduceOnly', False)
            order_side = order.get('side')
            order_link_id = order.get('orderLinkId', '')
            
            # TP orders are reduce-only limit orders on opposite side
            if (reduce_only and 
                order_type == 'Limit' and 
                order_side != side and
                ('TP' in order_link_id or 'tp' in order_link_id.lower())):
                tp_orders.append(order)
        
        # Sort TP orders by price (ascending for Buy positions, descending for Sell)
        tp_orders.sort(key=lambda x: float(x['price']), reverse=(side == 'Sell'))
        
        # Calculate ratios
        tp_data = []
        total_tp_qty = 0
        
        for i, order in enumerate(tp_orders):
            qty = float(order['qty'])
            total_tp_qty += qty
            percentage = (qty / position_size) * 100 if position_size > 0 else 0
            
            tp_data.append({
                'orderId': order['orderId'],
                'price': float(order['price']),
                'quantity': qty,
                'percentage': percentage,
                'expected': self.EXPECTED_RATIOS[i] if i < len(self.EXPECTED_RATIOS) else 0,
                'orderLinkId': order.get('orderLinkId', '')
            })
        
        # Calculate coverage
        coverage = (total_tp_qty / position_size) * 100 if position_size > 0 else 0
        
        # Check if ratios match expected
        matches_expected = True
        ratio_details = []
        
        for i, tp in enumerate(tp_data):
            if i < len(self.EXPECTED_RATIOS):
                expected = self.EXPECTED_RATIOS[i]
                actual = tp['percentage']
                diff = abs(actual - expected)
                matches = diff <= self.TOLERANCE
                
                ratio_details.append({
                    'tp_level': i + 1,
                    'expected': expected,
                    'actual': round(actual, 2),
                    'difference': round(diff, 2),
                    'matches': matches
                })
                
                if not matches:
                    matches_expected = False
        
        return {
            'account': account_type,
            'symbol': symbol,
            'side': side,
            'position_size': position_size,
            'tp_count': len(tp_orders),
            'tp_orders': tp_data,
            'total_tp_quantity': total_tp_qty,
            'coverage_percentage': round(coverage, 2),
            'matches_expected_ratio': matches_expected,
            'ratio_analysis': ratio_details
        }
    
    async def compare_main_mirror_positions(self, main_data: dict, mirror_data: dict) -> dict:
        """Compare main and mirror position sizing"""
        comparison = {
            'symbol': main_data['symbol'],
            'main_size': main_data['position_size'],
            'mirror_size': mirror_data['position_size'],
            'size_ratio': round(mirror_data['position_size'] / main_data['position_size'], 4) if main_data['position_size'] > 0 else 0,
            'main_coverage': main_data['coverage_percentage'],
            'mirror_coverage': mirror_data['coverage_percentage'],
            'main_matches_ratio': main_data['matches_expected_ratio'],
            'mirror_matches_ratio': mirror_data['matches_expected_ratio']
        }
        
        return comparison
    
    async def run_analysis(self):
        """Run comprehensive TP ratio analysis"""
        print("=" * 80)
        print("COMPREHENSIVE TP RATIO ANALYSIS")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Expected Ratios: {self.EXPECTED_RATIOS}% (Tolerance: ±{self.TOLERANCE}%)")
        print("=" * 80)
        
        # Get main account positions
        print("\n📊 MAIN ACCOUNT POSITIONS")
        print("-" * 80)
        
        response = self.main_client.get_positions(category="linear", settleCoin="USDT")
        main_positions = response.get('result', {}).get('list', []) if response.get('retCode') == 0 else []
        main_positions = [p for p in main_positions if float(p.get('size', 0)) > 0]
        
        main_analyses = {}
        
        if not main_positions:
            print("No positions found on main account")
        else:
            for position in main_positions:
                analysis = await self.analyze_position_tp_orders(self.main_client, "MAIN", position)
                main_analyses[position['symbol']] = analysis
                
                # Print position analysis
                print(f"\n{analysis['symbol']} ({analysis['side']}):")
                print(f"  Position Size: {analysis['position_size']}")
                print(f"  TP Orders: {analysis['tp_count']}")
                print(f"  Coverage: {analysis['coverage_percentage']}%")
                print(f"  Matches Expected: {'✅ YES' if analysis['matches_expected_ratio'] else '❌ NO'}")
                
                if analysis['ratio_analysis']:
                    print("\n  TP Order Analysis:")
                    for ratio in analysis['ratio_analysis']:
                        status = '✅' if ratio['matches'] else '❌'
                        print(f"    TP{ratio['tp_level']}: Expected {ratio['expected']}%, "
                              f"Actual {ratio['actual']}%, Diff {ratio['difference']}% {status}")
        
        # Get mirror account positions if enabled
        if self.mirror_client:
            print("\n\n📊 MIRROR ACCOUNT POSITIONS")
            print("-" * 80)
            
            response = self.mirror_client.get_positions(category="linear", settleCoin="USDT")
            mirror_positions = response.get('result', {}).get('list', []) if response.get('retCode') == 0 else []
            mirror_positions = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
            
            mirror_analyses = {}
            
            if not mirror_positions:
                print("No positions found on mirror account")
            else:
                for position in mirror_positions:
                    analysis = await self.analyze_position_tp_orders(self.mirror_client, "MIRROR", position)
                    mirror_analyses[position['symbol']] = analysis
                    
                    # Print position analysis
                    print(f"\n{analysis['symbol']} ({analysis['side']}):")
                    print(f"  Position Size: {analysis['position_size']}")
                    print(f"  TP Orders: {analysis['tp_count']}")
                    print(f"  Coverage: {analysis['coverage_percentage']}%")
                    print(f"  Matches Expected: {'✅ YES' if analysis['matches_expected_ratio'] else '❌ NO'}")
                    
                    if analysis['ratio_analysis']:
                        print("\n  TP Order Analysis:")
                        for ratio in analysis['ratio_analysis']:
                            status = '✅' if ratio['matches'] else '❌'
                            print(f"    TP{ratio['tp_level']}: Expected {ratio['expected']}%, "
                                  f"Actual {ratio['actual']}%, Diff {ratio['difference']}% {status}")
            
            # Compare main vs mirror
            print("\n\n📊 MAIN VS MIRROR COMPARISON")
            print("-" * 80)
            
            for symbol in main_analyses:
                if symbol in mirror_analyses:
                    comparison = await self.compare_main_mirror_positions(
                        main_analyses[symbol], 
                        mirror_analyses[symbol]
                    )
                    
                    print(f"\n{symbol}:")
                    print(f"  Main Size: {comparison['main_size']}")
                    print(f"  Mirror Size: {comparison['mirror_size']}")
                    print(f"  Size Ratio: {comparison['size_ratio']} ({round(comparison['size_ratio'] * 100, 2)}%)")
                    print(f"  Main Coverage: {comparison['main_coverage']}%")
                    print(f"  Mirror Coverage: {comparison['mirror_coverage']}%")
                    print(f"  Main Matches Ratio: {'✅' if comparison['main_matches_ratio'] else '❌'}")
                    print(f"  Mirror Matches Ratio: {'✅' if comparison['mirror_matches_ratio'] else '❌'}")
        
        # Summary
        print("\n\n📊 SUMMARY")
        print("-" * 80)
        
        # Count issues
        main_issues = sum(1 for a in main_analyses.values() if not a['matches_expected_ratio'])
        mirror_issues = sum(1 for a in mirror_analyses.values() if not a['matches_expected_ratio']) if self.mirror_client else 0
        
        print(f"\nMain Account:")
        print(f"  Total Positions: {len(main_analyses)}")
        print(f"  Positions with Correct Ratios: {len(main_analyses) - main_issues}")
        print(f"  Positions with Incorrect Ratios: {main_issues}")
        
        if self.mirror_client:
            print(f"\nMirror Account:")
            print(f"  Total Positions: {len(mirror_analyses)}")
            print(f"  Positions with Correct Ratios: {len(mirror_analyses) - mirror_issues}")
            print(f"  Positions with Incorrect Ratios: {mirror_issues}")
        
        # List positions needing attention
        if main_issues > 0 or mirror_issues > 0:
            print("\n⚠️  POSITIONS NEEDING ATTENTION:")
            
            for symbol, analysis in main_analyses.items():
                if not analysis['matches_expected_ratio']:
                    print(f"  - MAIN: {symbol} (Coverage: {analysis['coverage_percentage']}%)")
            
            if self.mirror_client:
                for symbol, analysis in mirror_analyses.items():
                    if not analysis['matches_expected_ratio']:
                        print(f"  - MIRROR: {symbol} (Coverage: {analysis['coverage_percentage']}%)")
        else:
            print("\n✅ All positions have correct TP ratios!")
        
        print("\n" + "=" * 80)


async def main():
    """Main entry point"""
    analyzer = TPRatioAnalyzer()
    await analyzer.run_analysis()


if __name__ == "__main__":
    asyncio.run(main())