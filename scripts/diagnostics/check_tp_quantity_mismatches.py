#!/usr/bin/env python3
"""
Check for TP quantity mismatches between exchange orders and monitor data
Compares actual TP orders on exchange with stored monitor data for both accounts
"""

import pickle
import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pybit.unified_trading import HTTP
from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET,
    ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TPQuantityChecker:
    def __init__(self):
        # Initialize main account client
        self.main_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY,
            api_secret=BYBIT_API_SECRET
        )
        
        # Initialize mirror account client if enabled
        self.mirror_client = None
        if ENABLE_MIRROR_TRADING and BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
            self.mirror_client = HTTP(
                testnet=USE_TESTNET,
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2
            )
    
    def load_monitor_data(self) -> Dict:
        """Load monitor data from pickle file"""
        try:
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
                data = pickle.load(f)
                monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
                return monitors
        except Exception as e:
            logger.error(f"Failed to load monitor data: {e}")
            return {}
    
    async def get_positions_and_orders(self, client: HTTP, account_name: str) -> Tuple[List[Dict], List[Dict]]:
        """Get positions and orders for an account"""
        positions = []
        orders = []
        
        try:
            # Get positions
            pos_response = client.get_positions(category="linear", settleCoin="USDT")
            if pos_response.get("retCode") == 0:
                all_positions = pos_response.get("result", {}).get("list", [])
                # Filter active positions only
                positions = [p for p in all_positions if float(p.get('size', 0)) > 0]
            
            # Get orders
            order_response = client.get_open_orders(category="linear", settleCoin="USDT", limit=200)
            if order_response.get("retCode") == 0:
                orders = order_response.get("result", {}).get("list", [])
        
        except Exception as e:
            logger.error(f"Error fetching data for {account_name}: {e}")
        
        return positions, orders
    
    def extract_tp_orders(self, orders: List[Dict], symbol: str, side: str) -> List[Dict]:
        """Extract TP orders for a specific position"""
        tp_orders = []
        
        for order in orders:
            if order.get('symbol') != symbol:
                continue
            
            order_side = order.get('side')
            link_id = order.get('orderLinkId', '')
            stop_type = order.get('stopOrderType', '')
            reduce_only = order.get('reduceOnly', False)
            
            # Determine if this is a TP order
            is_tp = False
            
            # Check by orderLinkId
            if 'TP' in link_id:
                is_tp = True
            # Check by stopOrderType
            elif stop_type == 'TakeProfit':
                is_tp = True
            # Check by side logic for reduce-only limit orders
            elif reduce_only and order.get('orderType') == 'Limit':
                if (side == 'Buy' and order_side == 'Sell') or (side == 'Sell' and order_side == 'Buy'):
                    # If it's not explicitly marked as SL, consider it TP
                    if 'SL' not in link_id and stop_type != 'StopLoss':
                        is_tp = True
            
            if is_tp:
                tp_orders.append({
                    'order_id': order.get('orderId'),
                    'qty': Decimal(str(order.get('qty', 0))),
                    'price': order.get('price'),
                    'link_id': link_id
                })
        
        return tp_orders
    
    def compare_tp_quantities(self, exchange_tps: List[Dict], monitor_tps: Dict, position_size: Decimal) -> Dict:
        """Compare TP quantities between exchange and monitor data"""
        comparison = {
            'exchange_total': Decimal('0'),
            'monitor_total': Decimal('0'),
            'exchange_orders': [],
            'monitor_orders': [],
            'mismatches': [],
            'coverage_percentage': Decimal('0')
        }
        
        # Calculate exchange total
        for tp in exchange_tps:
            comparison['exchange_total'] += tp['qty']
            comparison['exchange_orders'].append({
                'qty': float(tp['qty']),
                'price': tp['price']
            })
        
        # Calculate monitor total and extract order details
        monitor_order_list = []
        for order_id, tp_data in monitor_tps.items():
            qty = Decimal(str(tp_data.get('quantity', 0)))
            comparison['monitor_total'] += qty
            monitor_order_list.append({
                'order_id': order_id,
                'qty': float(qty),
                'price': tp_data.get('price'),
                'tp_number': tp_data.get('tp_number', 0),
                'percentage': tp_data.get('percentage', 0)
            })
        
        # Sort monitor orders by tp_number
        monitor_order_list.sort(key=lambda x: x.get('tp_number', 0))
        comparison['monitor_orders'] = monitor_order_list
        
        # Calculate coverage percentage
        if position_size > 0:
            comparison['coverage_percentage'] = (comparison['exchange_total'] / position_size * 100).quantize(Decimal('0.01'))
        
        # Check for mismatches
        total_diff = abs(comparison['exchange_total'] - comparison['monitor_total'])
        if total_diff > Decimal('0.01'):  # Allow small rounding differences
            comparison['mismatches'].append({
                'type': 'total_quantity',
                'exchange': float(comparison['exchange_total']),
                'monitor': float(comparison['monitor_total']),
                'difference': float(total_diff)
            })
        
        # Check order count mismatch
        if len(exchange_tps) != len(monitor_tps):
            comparison['mismatches'].append({
                'type': 'order_count',
                'exchange': len(exchange_tps),
                'monitor': len(monitor_tps)
            })
        
        return comparison
    
    async def analyze_account(self, client: HTTP, account_name: str, monitors: Dict) -> Dict:
        """Analyze positions and orders for one account"""
        positions, orders = await self.get_positions_and_orders(client, account_name)
        
        results = {
            'account': account_name,
            'positions': [],
            'orphaned_monitors': [],
            'summary': {
                'total_positions': len(positions),
                'positions_with_issues': 0,
                'total_mismatches': 0
            }
        }
        
        # Track which monitors we've seen
        seen_monitors = set()
        
        # Analyze each position
        for pos in positions:
            symbol = pos.get('symbol')
            side = pos.get('side')
            size = Decimal(str(pos.get('size', 0)))
            avg_price = pos.get('avgPrice')
            pnl = pos.get('unrealisedPnl')
            
            # Create monitor key
            monitor_key = f"{symbol}_{side}_{account_name.lower()}"
            seen_monitors.add(monitor_key)
            
            # Get monitor data
            monitor_data = monitors.get(monitor_key, {})
            
            # Extract TP orders from exchange
            exchange_tps = self.extract_tp_orders(orders, symbol, side)
            
            # Extract TP orders from monitor
            monitor_tps = monitor_data.get('tp_orders', {})
            
            # Compare quantities
            comparison = self.compare_tp_quantities(exchange_tps, monitor_tps, size)
            
            position_result = {
                'symbol': symbol,
                'side': side,
                'size': float(size),
                'avg_price': avg_price,
                'pnl': pnl,
                'monitor_exists': bool(monitor_data),
                'approach': monitor_data.get('approach', 'Unknown'),
                'comparison': comparison
            }
            
            # Check if there are issues
            if comparison['mismatches'] or not monitor_data:
                results['summary']['positions_with_issues'] += 1
                results['summary']['total_mismatches'] += len(comparison['mismatches'])
            
            results['positions'].append(position_result)
        
        # Find orphaned monitors
        for monitor_key in monitors:
            if monitor_key.endswith(f'_{account_name.lower()}') and monitor_key not in seen_monitors:
                results['orphaned_monitors'].append(monitor_key)
        
        return results
    
    async def run(self):
        """Main execution"""
        print("=" * 80)
        print("TP QUANTITY MISMATCH CHECKER")
        print("=" * 80)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Load monitor data
        monitors = self.load_monitor_data()
        print(f"\nLoaded {len(monitors)} monitors from persistence file")
        
        # Analyze main account
        print("\n" + "="*60)
        print("MAIN ACCOUNT ANALYSIS")
        print("="*60)
        main_results = await self.analyze_account(self.main_client, "main", monitors)
        self.print_account_results(main_results)
        
        # Analyze mirror account if enabled
        if self.mirror_client:
            print("\n" + "="*60)
            print("MIRROR ACCOUNT ANALYSIS")
            print("="*60)
            mirror_results = await self.analyze_account(self.mirror_client, "mirror", monitors)
            self.print_account_results(mirror_results)
        
        # Print overall summary
        self.print_overall_summary(main_results, mirror_results if self.mirror_client else None)
    
    def print_account_results(self, results: Dict):
        """Print results for one account"""
        summary = results['summary']
        
        print(f"\n📊 SUMMARY:")
        print(f"  Total Positions: {summary['total_positions']}")
        print(f"  Positions with Issues: {summary['positions_with_issues']}")
        print(f"  Total Mismatches: {summary['total_mismatches']}")
        
        if results['orphaned_monitors']:
            print(f"  Orphaned Monitors: {len(results['orphaned_monitors'])}")
        
        # Print position details
        print(f"\n📈 POSITION DETAILS:")
        for i, pos in enumerate(results['positions'], 1):
            symbol = pos['symbol']
            side = pos['side']
            size = pos['size']
            approach = pos['approach']
            comparison = pos['comparison']
            
            # Determine status icon
            if not pos['monitor_exists']:
                status_icon = "❌"
                status_text = "NO MONITOR"
            elif comparison['mismatches']:
                status_icon = "⚠️"
                status_text = "MISMATCH"
            else:
                status_icon = "✅"
                status_text = "OK"
            
            print(f"\n{i}. {status_icon} {symbol} {side} - {status_text}")
            print(f"   Size: {size}, Approach: {approach}")
            print(f"   Coverage: {comparison['coverage_percentage']}%")
            
            if pos['monitor_exists']:
                print(f"   Exchange TPs: {len(comparison['exchange_orders'])} orders, Total: {comparison['exchange_total']}")
                print(f"   Monitor TPs: {len(comparison['monitor_orders'])} orders, Total: {comparison['monitor_total']}")
                
                # Print mismatches
                if comparison['mismatches']:
                    print("   🔴 Mismatches:")
                    for mismatch in comparison['mismatches']:
                        if mismatch['type'] == 'total_quantity':
                            print(f"      - Total Quantity: Exchange={mismatch['exchange']}, Monitor={mismatch['monitor']}, Diff={mismatch['difference']}")
                        elif mismatch['type'] == 'order_count':
                            print(f"      - Order Count: Exchange={mismatch['exchange']}, Monitor={mismatch['monitor']}")
                
                # Print detailed TP breakdown if there's a mismatch
                if comparison['mismatches'] and len(comparison['monitor_orders']) > 0:
                    print("   📋 Monitor TP Structure:")
                    for tp in comparison['monitor_orders']:
                        print(f"      TP{tp['tp_number']}: {tp['percentage']}% ({tp['qty']}) @ ${tp['price']}")
        
        # Print orphaned monitors
        if results['orphaned_monitors']:
            print(f"\n🗑️ ORPHANED MONITORS (monitors without positions):")
            for monitor_key in results['orphaned_monitors']:
                print(f"   - {monitor_key}")
    
    def print_overall_summary(self, main_results: Dict, mirror_results: Optional[Dict]):
        """Print overall summary and recommendations"""
        print("\n" + "="*80)
        print("OVERALL SUMMARY")
        print("="*80)
        
        total_positions = main_results['summary']['total_positions']
        total_issues = main_results['summary']['positions_with_issues']
        total_orphaned = len(main_results['orphaned_monitors'])
        
        if mirror_results:
            total_positions += mirror_results['summary']['total_positions']
            total_issues += mirror_results['summary']['positions_with_issues']
            total_orphaned += len(mirror_results['orphaned_monitors'])
        
        print(f"\n📊 Total Positions: {total_positions}")
        print(f"⚠️  Positions with Issues: {total_issues}")
        print(f"🗑️  Orphaned Monitors: {total_orphaned}")
        
        if total_issues > 0 or total_orphaned > 0:
            print("\n" + "="*80)
            print("RECOMMENDATIONS")
            print("="*80)
            
            recommendations = []
            
            # Check for missing monitors
            missing_monitors = []
            for pos in main_results['positions']:
                if not pos['monitor_exists']:
                    missing_monitors.append(f"{pos['symbol']}_{pos['side']}_main")
            
            if mirror_results:
                for pos in mirror_results['positions']:
                    if not pos['monitor_exists']:
                        missing_monitors.append(f"{pos['symbol']}_{pos['side']}_mirror")
            
            if missing_monitors:
                recommendations.append(f"Create monitors for {len(missing_monitors)} positions without monitors")
            
            # Check for quantity mismatches
            mismatch_positions = []
            for pos in main_results['positions']:
                if pos['monitor_exists'] and pos['comparison']['mismatches']:
                    mismatch_positions.append(pos['symbol'])
            
            if mirror_results:
                for pos in mirror_results['positions']:
                    if pos['monitor_exists'] and pos['comparison']['mismatches']:
                        mismatch_positions.append(pos['symbol'])
            
            if mismatch_positions:
                recommendations.append(f"Sync TP quantities for {len(set(mismatch_positions))} positions with mismatches")
            
            if total_orphaned > 0:
                recommendations.append(f"Clean up {total_orphaned} orphaned monitors")
            
            for i, rec in enumerate(recommendations, 1):
                print(f"{i}. {rec}")
            
            print("\n💡 Run the following scripts to fix issues:")
            if missing_monitors:
                print("   - scripts/maintenance/sync_all_positions_to_monitors.py")
            if mismatch_positions:
                print("   - scripts/fixes/sync_monitor_tp_quantities.py")
            if total_orphaned:
                print("   - scripts/maintenance/clean_orphaned_monitors.py")
        else:
            print("\n✅ All positions have matching TP quantities between exchange and monitors!")


async def main():
    """Entry point"""
    checker = TPQuantityChecker()
    await checker.run()


if __name__ == "__main__":
    asyncio.run(main())