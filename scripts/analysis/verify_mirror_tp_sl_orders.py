#!/usr/bin/env python3
"""
Comprehensive script to verify mirror account positions and their TP/SL orders.
Checks for:
1. Each position has TP and SL orders
2. Conservative positions have 85/5/5/5 TP breakdown
3. Identifies any missing orders
"""

import asyncio
import os
import sys
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import pickle
from collections import defaultdict

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pybit.unified_trading import HTTP
from config.settings import BYBIT_API_KEY_2, BYBIT_API_SECRET_2, USE_TESTNET
import logging

# Set up logger
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

class MirrorOrderVerifier:
    def __init__(self):
        self.client = HTTP(
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2,
            testnet=USE_TESTNET == 'true'
        )
        self.positions = []
        self.orders_by_symbol = defaultdict(list)
        self.dashboard_data = None
        
    async def load_dashboard_data(self):
        """Load dashboard data to get approach information"""
        try:
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
                self.dashboard_data = pickle.load(f)
                logger.info("Dashboard data loaded successfully")
        except Exception as e:
            logger.error(f"Error loading dashboard data: {e}")
            self.dashboard_data = None
    
    def get_position_approach(self, symbol: str) -> Optional[str]:
        """Get the approach for a position from dashboard data"""
        if not self.dashboard_data:
            return None
            
        try:
            # Check user positions for approach info
            for chat_id, user_data in self.dashboard_data.get('user_data', {}).items():
                positions = user_data.get('positions', {})
                for pos_key, pos_data in positions.items():
                    if pos_data.get('symbol') == symbol and pos_data.get('account_type') == 'mirror':
                        return pos_data.get('approach', 'Unknown')
            return None
        except Exception as e:
            logger.error(f"Error getting approach for {symbol}: {e}")
            return None
    
    async def fetch_positions(self):
        """Fetch all positions from mirror account"""
        try:
            response = self.client.get_positions(category="linear", settleCoin="USDT")
            if response.get("retCode") == 0:
                positions = response.get("result", {}).get("list", [])
                self.positions = [p for p in positions if float(p.get('size', 0)) > 0]
                logger.info(f"Found {len(self.positions)} open positions on mirror account")
                return True
            else:
                logger.error(f"Failed to fetch positions: {response.get('retMsg')}")
                return False
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return False
    
    async def fetch_orders(self):
        """Fetch all active orders"""
        try:
            response = self.client.get_open_orders(category="linear", settleCoin="USDT")
            if response.get("retCode") == 0:
                orders = response.get("result", {}).get("list", [])
                
                # Group orders by symbol
                for order in orders:
                    symbol = order.get('symbol')
                    if symbol:
                        self.orders_by_symbol[symbol].append(order)
                
                total_orders = sum(len(orders) for orders in self.orders_by_symbol.values())
                logger.info(f"Found {total_orders} active orders across {len(self.orders_by_symbol)} symbols")
                return True
            else:
                logger.error(f"Failed to fetch orders: {response.get('retMsg')}")
                return False
        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            return False
    
    def calculate_tp_percentages(self, position: Dict, tp_orders: List[Dict]) -> Dict[str, any]:
        """Calculate TP percentage breakdown"""
        position_size = Decimal(str(position.get('size', 0)))
        if position_size == 0:
            return {'error': 'Position size is 0'}
        
        tp_breakdown = []
        total_tp_size = Decimal('0')
        
        for tp in sorted(tp_orders, key=lambda x: float(x.get('price', 0))):
            tp_qty = Decimal(str(tp.get('qty', 0)))
            percentage = (tp_qty / position_size * 100).quantize(Decimal('0.01'))
            total_tp_size += tp_qty
            
            tp_breakdown.append({
                'orderId': tp.get('orderId'),
                'price': tp.get('price'),
                'qty': str(tp_qty),
                'percentage': float(percentage),
                'orderStatus': tp.get('orderStatus')
            })
        
        coverage_percentage = (total_tp_size / position_size * 100).quantize(Decimal('0.01'))
        
        return {
            'breakdown': tp_breakdown,
            'total_coverage': float(coverage_percentage),
            'position_size': str(position_size),
            'total_tp_size': str(total_tp_size)
        }
    
    def check_conservative_breakdown(self, percentages: List[float]) -> Tuple[bool, str]:
        """Check if percentages match 85/5/5/5 pattern"""
        if len(percentages) != 4:
            return False, f"Expected 4 TPs, found {len(percentages)}"
        
        expected = [85.0, 5.0, 5.0, 5.0]
        tolerance = 0.5  # Allow 0.5% tolerance
        
        mismatches = []
        for i, (actual, exp) in enumerate(zip(percentages, expected)):
            if abs(actual - exp) > tolerance:
                mismatches.append(f"TP{i+1}: {actual}% (expected {exp}%)")
        
        if mismatches:
            return False, f"Mismatches: {', '.join(mismatches)}"
        
        return True, "Matches 85/5/5/5 pattern"
    
    def analyze_position(self, position: Dict) -> Dict:
        """Analyze a single position and its orders"""
        symbol = position.get('symbol')
        side = position.get('side')
        
        # Get orders for this symbol
        orders = self.orders_by_symbol.get(symbol, [])
        
        # Separate TP and SL orders
        tp_orders = []
        sl_orders = []
        
        for order in orders:
            order_type = order.get('orderType', '')
            order_side = order.get('side')
            
            # For a long position, TP is sell and SL is sell
            # For a short position, TP is buy and SL is buy
            if side == 'Buy':  # Long position
                if order_side == 'Sell':
                    if order_type == 'Limit':
                        tp_orders.append(order)
                    elif order_type in ['Market', 'Limit']:  # SL can be market or limit
                        if 'triggerPrice' in order or order.get('stopOrderType'):
                            sl_orders.append(order)
            else:  # Short position
                if order_side == 'Buy':
                    if order_type == 'Limit':
                        tp_orders.append(order)
                    elif order_type in ['Market', 'Limit']:  # SL can be market or limit
                        if 'triggerPrice' in order or order.get('stopOrderType'):
                            sl_orders.append(order)
        
        # Get approach
        approach = self.get_position_approach(symbol)
        
        # Calculate TP percentages
        tp_analysis = self.calculate_tp_percentages(position, tp_orders) if tp_orders else None
        
        # Check conservative breakdown if applicable
        conservative_check = None
        if approach == 'Conservative' and tp_analysis and 'breakdown' in tp_analysis:
            percentages = [tp['percentage'] for tp in tp_analysis['breakdown']]
            conservative_check = self.check_conservative_breakdown(percentages)
        
        return {
            'symbol': symbol,
            'side': side,
            'size': position.get('size'),
            'avgPrice': position.get('avgPrice'),
            'unrealisedPnl': position.get('unrealisedPnl'),
            'approach': approach or 'Unknown',
            'tp_count': len(tp_orders),
            'sl_count': len(sl_orders),
            'tp_analysis': tp_analysis,
            'conservative_check': conservative_check,
            'issues': self.identify_issues(position, tp_orders, sl_orders, approach, tp_analysis)
        }
    
    def identify_issues(self, position: Dict, tp_orders: List, sl_orders: List, 
                       approach: str, tp_analysis: Dict) -> List[str]:
        """Identify any issues with the position orders"""
        issues = []
        
        # Check for missing SL
        if len(sl_orders) == 0:
            issues.append("❌ Missing Stop Loss order")
        elif len(sl_orders) > 1:
            issues.append(f"⚠️ Multiple SL orders ({len(sl_orders)})")
        
        # Check for missing TP
        if len(tp_orders) == 0:
            issues.append("❌ Missing Take Profit orders")
        
        # Check conservative positions
        if approach == 'Conservative':
            if len(tp_orders) != 4:
                issues.append(f"❌ Conservative position should have 4 TPs, found {len(tp_orders)}")
            elif tp_analysis and tp_analysis.get('total_coverage', 0) < 99.5:
                issues.append(f"⚠️ TP coverage only {tp_analysis['total_coverage']}%")
        
        # Check TP coverage
        if tp_analysis and tp_analysis.get('total_coverage', 0) > 100.5:
            issues.append(f"⚠️ TP coverage exceeds position size: {tp_analysis['total_coverage']}%")
        
        return issues
    
    def print_analysis(self, analyses: List[Dict]):
        """Print detailed analysis results"""
        print("\n" + "="*80)
        print("MIRROR ACCOUNT POSITION ANALYSIS")
        print("="*80)
        
        # Summary
        total_positions = len(analyses)
        positions_with_issues = sum(1 for a in analyses if a['issues'])
        
        print(f"\nTotal Positions: {total_positions}")
        print(f"Positions with Issues: {positions_with_issues}")
        print(f"Healthy Positions: {total_positions - positions_with_issues}")
        
        # Group by approach
        by_approach = defaultdict(list)
        for analysis in analyses:
            by_approach[analysis['approach']].append(analysis)
        
        print("\nPositions by Approach:")
        for approach, positions in by_approach.items():
            print(f"  {approach}: {len(positions)}")
        
        # Detailed position analysis
        print("\n" + "-"*80)
        print("DETAILED POSITION ANALYSIS")
        print("-"*80)
        
        for i, analysis in enumerate(analyses, 1):
            print(f"\n{i}. {analysis['symbol']} ({analysis['side']})")
            print(f"   Approach: {analysis['approach']}")
            print(f"   Size: {analysis['size']}")
            print(f"   Avg Price: {analysis['avgPrice']}")
            print(f"   Unrealised PNL: {analysis['unrealisedPnl']}")
            print(f"   Orders: {analysis['tp_count']} TP, {analysis['sl_count']} SL")
            
            # TP Analysis
            if analysis['tp_analysis']:
                tp_data = analysis['tp_analysis']
                print(f"\n   TP Coverage: {tp_data['total_coverage']}% of position")
                print("   TP Breakdown:")
                for j, tp in enumerate(tp_data['breakdown'], 1):
                    print(f"     TP{j}: {tp['percentage']}% @ {tp['price']} (ID: {tp['orderId'][:8]}...)")
                
                # Conservative check
                if analysis['conservative_check']:
                    matches, message = analysis['conservative_check']
                    status = "✅" if matches else "❌"
                    print(f"   Conservative Pattern: {status} {message}")
            
            # Issues
            if analysis['issues']:
                print("\n   Issues Found:")
                for issue in analysis['issues']:
                    print(f"     • {issue}")
            else:
                print("\n   ✅ No issues found")
        
        # Summary of issues
        print("\n" + "="*80)
        print("ISSUES SUMMARY")
        print("="*80)
        
        all_issues = defaultdict(int)
        for analysis in analyses:
            for issue in analysis['issues']:
                # Normalize issue text for counting
                if "Missing Stop Loss" in issue:
                    all_issues["Missing Stop Loss"] += 1
                elif "Missing Take Profit" in issue:
                    all_issues["Missing Take Profit"] += 1
                elif "Multiple SL orders" in issue:
                    all_issues["Multiple SL orders"] += 1
                elif "should have 4 TPs" in issue:
                    all_issues["Wrong TP count for Conservative"] += 1
                elif "TP coverage only" in issue:
                    all_issues["Incomplete TP coverage"] += 1
                elif "TP coverage exceeds" in issue:
                    all_issues["Excessive TP coverage"] += 1
        
        if all_issues:
            for issue, count in sorted(all_issues.items(), key=lambda x: x[1], reverse=True):
                print(f"  • {issue}: {count} position(s)")
        else:
            print("  ✅ No issues found across all positions!")
        
        # Positions needing attention
        print("\n" + "="*80)
        print("POSITIONS REQUIRING ATTENTION")
        print("="*80)
        
        critical_positions = [a for a in analyses if any("❌" in issue for issue in a['issues'])]
        if critical_positions:
            for analysis in critical_positions:
                print(f"\n{analysis['symbol']}:")
                for issue in analysis['issues']:
                    if "❌" in issue:
                        print(f"  {issue}")
        else:
            print("\n✅ No critical issues found!")
    
    async def run(self):
        """Run the verification process"""
        print("Starting Mirror Account Order Verification...")
        
        # Load dashboard data
        await self.load_dashboard_data()
        
        # Fetch positions
        if not await self.fetch_positions():
            print("Failed to fetch positions")
            return
        
        if not self.positions:
            print("No open positions found on mirror account")
            return
        
        # Fetch orders
        if not await self.fetch_orders():
            print("Failed to fetch orders")
            return
        
        # Analyze each position
        analyses = []
        for position in self.positions:
            analysis = self.analyze_position(position)
            analyses.append(analysis)
        
        # Print results
        self.print_analysis(analyses)

async def main():
    verifier = MirrorOrderVerifier()
    await verifier.run()

if __name__ == "__main__":
    asyncio.run(main())