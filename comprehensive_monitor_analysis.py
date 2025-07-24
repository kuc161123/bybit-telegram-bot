#!/usr/bin/env python3
"""
Comprehensive Monitor System Analysis
Analyzes monitor states, positions, orders and predicts next actions
"""

import pickle
import asyncio
from datetime import datetime
from decimal import Decimal
from tabulate import tabulate
import json
from typing import Dict, List, Any, Optional, Tuple

# Import Bybit clients
from execution.mirror_trader import bybit_client, bybit_client_2
from clients.bybit_helpers import get_all_positions, get_all_open_orders
from config.settings import EXTERNAL_ORDER_PROTECTION, BOT_ORDER_PREFIX


class MonitorAnalyzer:
    def __init__(self):
        self.pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        self.data = None
        self.monitors = {}
        self.positions_main = []
        self.positions_mirror = []
        self.orders_main = []
        self.orders_mirror = []
        
    async def load_data(self):
        """Load pickle data and fetch exchange data"""
        # Load pickle file
        try:
            with open(self.pickle_file, 'rb') as f:
                self.data = pickle.load(f)
                self.monitors = self.data.get('enhanced_monitors', {})
        except Exception as e:
            print(f"Error loading pickle: {e}")
            return False
            
        # Fetch positions
        print("Fetching positions from exchange...")
        self.positions_main = await get_all_positions(client=bybit_client)
        self.positions_mirror = await get_all_positions(client=bybit_client_2)
        
        # Fetch orders
        print("Fetching orders from exchange...")
        self.orders_main = await get_all_open_orders(client=bybit_client)
        self.orders_mirror = await get_all_open_orders(client=bybit_client_2)
        
        return True
        
    def analyze_monitor(self, key: str, monitor: Dict) -> Dict[str, Any]:
        """Analyze a single monitor and predict next action"""
        parts = key.split('_')
        symbol = parts[0]
        side = parts[1] if len(parts) > 1 else "Unknown"
        account = parts[2] if len(parts) > 2 else "main"
        
        # Find matching position
        positions = self.positions_main if account == "main" else self.positions_mirror
        position = next((p for p in positions if p['symbol'] == symbol and p['side'] == side), None)
        
        # Find matching orders
        orders = self.orders_main if account == "main" else self.orders_mirror
        position_orders = [o for o in orders if o['symbol'] == symbol]
        
        # Analyze monitor state
        analysis = {
            'key': key,
            'symbol': symbol,
            'side': side,
            'account': account,
            'active': monitor.get('active', False),
            'position_exists': position is not None,
            'position_size': float(position['size']) if position else 0,
            'position_value': float(position['positionValue']) if position else 0,
            'avg_price': float(position['avgPrice']) if position else 0,
            'mark_price': float(position['markPrice']) if position else 0,
            'unrealized_pnl': float(position['unrealizedPnl']) if position else 0,
            'order_count': len(position_orders),
            'tp_orders': [],
            'sl_orders': [],
            'limit_orders': [],
            'monitor_state': monitor,
            'next_action': 'Unknown',
            'issues': []
        }
        
        # Categorize orders
        for order in position_orders:
            if order['orderType'] == 'Limit':
                if order.get('reduceOnly', False) or order.get('tpslMode') == 'Full':
                    # TP order
                    analysis['tp_orders'].append({
                        'id': order['orderId'],
                        'price': float(order['price']),
                        'qty': float(order['qty']),
                        'status': order['orderStatus']
                    })
                elif order.get('stopOrderType') == 'Stop':
                    # SL order
                    analysis['sl_orders'].append({
                        'id': order['orderId'],
                        'trigger': float(order.get('triggerPrice', 0)),
                        'qty': float(order['qty']),
                        'status': order['orderStatus']
                    })
                else:
                    # Entry limit order
                    analysis['limit_orders'].append({
                        'id': order['orderId'],
                        'price': float(order['price']),
                        'qty': float(order['qty']),
                        'status': order['orderStatus']
                    })
            elif order['orderType'] == 'Market' and order.get('stopOrderType') == 'Stop':
                # Stop loss order
                analysis['sl_orders'].append({
                    'id': order['orderId'],
                    'trigger': float(order.get('triggerPrice', 0)),
                    'qty': float(order['qty']),
                    'status': order['orderStatus']
                })
                
        # Predict next action
        analysis['next_action'] = self._predict_next_action(analysis, monitor)
        
        # Identify issues
        analysis['issues'] = self._identify_issues(analysis, monitor)
        
        return analysis
        
    def _predict_next_action(self, analysis: Dict, monitor: Dict) -> str:
        """Predict what the monitor will do next"""
        if not analysis['position_exists']:
            if analysis['active']:
                return "CLOSE_MONITOR - Position closed, monitor should deactivate"
            return "NO_ACTION - No position, monitor inactive"
            
        # Check if monitoring is active
        if not analysis['active']:
            return "ACTIVATE_MONITOR - Position exists but monitor inactive"
            
        # Check TP states
        tp1_hit = monitor.get('tp1_hit', False)
        tp2_hit = monitor.get('tp2_hit', False)
        tp3_hit = monitor.get('tp3_hit', False)
        tp4_hit = monitor.get('tp4_hit', False)
        
        # Check current price vs TPs
        mark_price = analysis['mark_price']
        avg_price = analysis['avg_price']
        is_buy = analysis['side'] == 'Buy'
        
        # Get TP prices from monitor
        tp1_price = float(monitor.get('tp1_price', 0))
        tp2_price = float(monitor.get('tp2_price', 0))
        tp3_price = float(monitor.get('tp3_price', 0))
        tp4_price = float(monitor.get('tp4_price', 0))
        sl_price = float(monitor.get('sl_price', 0))
        
        # Check if price hit any triggers
        if is_buy:
            # Long position
            if sl_price > 0 and mark_price <= sl_price:
                return "TRIGGER_SL - Price at/below stop loss"
            if tp1_price > 0 and not tp1_hit and mark_price >= tp1_price:
                return "TRIGGER_TP1 - Price reached TP1"
            if tp2_price > 0 and not tp2_hit and mark_price >= tp2_price:
                return "TRIGGER_TP2 - Price reached TP2"
            if tp3_price > 0 and not tp3_hit and mark_price >= tp3_price:
                return "TRIGGER_TP3 - Price reached TP3"
            if tp4_price > 0 and not tp4_hit and mark_price >= tp4_price:
                return "TRIGGER_TP4 - Price reached TP4"
        else:
            # Short position
            if sl_price > 0 and mark_price >= sl_price:
                return "TRIGGER_SL - Price at/above stop loss"
            if tp1_price > 0 and not tp1_hit and mark_price <= tp1_price:
                return "TRIGGER_TP1 - Price reached TP1"
            if tp2_price > 0 and not tp2_hit and mark_price <= tp2_price:
                return "TRIGGER_TP2 - Price reached TP2"
            if tp3_price > 0 and not tp3_hit and mark_price <= tp3_price:
                return "TRIGGER_TP3 - Price reached TP3"
            if tp4_price > 0 and not tp4_hit and mark_price <= tp4_price:
                return "TRIGGER_TP4 - Price reached TP4"
                
        # Check for rebalancing needs
        if monitor.get('needs_rebalancing', False):
            return "REBALANCE_TPS - Pending TP rebalancing"
            
        # Check monitoring interval
        last_check = monitor.get('last_check', 0)
        interval = monitor.get('check_interval', 5)
        time_since_check = datetime.now().timestamp() - last_check
        
        if time_since_check >= interval:
            return f"MONITOR_CHECK - Due for check (last: {int(time_since_check)}s ago)"
            
        return "WAIT - Monitoring active, no triggers met"
        
    def _identify_issues(self, analysis: Dict, monitor: Dict) -> List[str]:
        """Identify any issues with the monitor/position"""
        issues = []
        
        # Check for monitor without position
        if analysis['active'] and not analysis['position_exists']:
            issues.append("ORPHANED_MONITOR - Active monitor but no position")
            
        # Check for position without monitor
        if analysis['position_exists'] and not analysis['active']:
            issues.append("MISSING_MONITOR - Position exists but monitor inactive")
            
        # Check for missing SL
        if analysis['position_exists'] and not analysis['sl_orders']:
            issues.append("MISSING_SL - No stop loss orders found")
            
        # Check for missing TPs
        if analysis['position_exists'] and not analysis['tp_orders']:
            issues.append("MISSING_TPS - No take profit orders found")
            
        # Check TP count
        expected_tps = 4 - sum([
            monitor.get('tp1_hit', False),
            monitor.get('tp2_hit', False),
            monitor.get('tp3_hit', False),
            monitor.get('tp4_hit', False)
        ])
        
        if analysis['position_exists'] and len(analysis['tp_orders']) != expected_tps:
            issues.append(f"TP_COUNT_MISMATCH - Expected {expected_tps}, found {len(analysis['tp_orders'])}")
            
        # Check for stuck monitor
        if monitor.get('last_check', 0) > 0:
            time_since_check = datetime.now().timestamp() - monitor['last_check']
            if time_since_check > 300:  # 5 minutes
                issues.append(f"STUCK_MONITOR - No check for {int(time_since_check/60)} minutes")
                
        # Check for price discrepancy
        if analysis['position_exists'] and monitor.get('avg_price', 0) > 0:
            monitor_price = float(monitor['avg_price'])
            actual_price = analysis['avg_price']
            if abs(monitor_price - actual_price) / actual_price > 0.001:  # 0.1% difference
                issues.append(f"PRICE_MISMATCH - Monitor: {monitor_price}, Actual: {actual_price}")
                
        return issues
        
    def generate_report(self):
        """Generate comprehensive analysis report"""
        print("\n" + "="*80)
        print("COMPREHENSIVE MONITOR SYSTEM ANALYSIS")
        print("="*80)
        print(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Pickle file: {self.pickle_file}")
        
        # Summary statistics
        print(f"\nSUMMARY:")
        print(f"- Total monitors: {len(self.monitors)}")
        print(f"- Active monitors: {sum(1 for m in self.monitors.values() if m.get('active', False))}")
        print(f"- Main positions: {len(self.positions_main)}")
        print(f"- Mirror positions: {len(self.positions_mirror)}")
        print(f"- Main orders: {len(self.orders_main)}")
        print(f"- Mirror orders: {len(self.orders_mirror)}")
        
        # Analyze all monitors
        analyses = []
        for key, monitor in self.monitors.items():
            analysis = self.analyze_monitor(key, monitor)
            analyses.append(analysis)
            
        # Monitor state table
        print("\n\nMONITOR STATE OVERVIEW:")
        monitor_data = []
        for a in analyses:
            monitor_data.append([
                a['key'],
                '✓' if a['active'] else '✗',
                '✓' if a['position_exists'] else '✗',
                f"{a['position_size']:.4f}" if a['position_size'] else '-',
                f"${a['unrealized_pnl']:.2f}" if a['position_exists'] else '-',
                a['next_action']
            ])
            
        print(tabulate(
            monitor_data,
            headers=['Monitor Key', 'Active', 'Position', 'Size', 'Unreal P&L', 'Next Action'],
            tablefmt='grid'
        ))
        
        # Positions without monitors
        print("\n\nPOSITIONS WITHOUT MONITORS:")
        orphaned_positions = []
        
        # Check main positions
        for pos in self.positions_main:
            key = f"{pos['symbol']}_{pos['side']}_main"
            if key not in self.monitors or not self.monitors[key].get('active', False):
                orphaned_positions.append(['main', pos['symbol'], pos['side'], 
                                         f"{float(pos['size']):.4f}", f"${float(pos['unrealizedPnl']):.2f}"])
                
        # Check mirror positions  
        for pos in self.positions_mirror:
            key = f"{pos['symbol']}_{pos['side']}_mirror"
            if key not in self.monitors or not self.monitors[key].get('active', False):
                orphaned_positions.append(['mirror', pos['symbol'], pos['side'],
                                         f"{float(pos['size']):.4f}", f"${float(pos['unrealizedPnl']):.2f}"])
                
        if orphaned_positions:
            print(tabulate(
                orphaned_positions,
                headers=['Account', 'Symbol', 'Side', 'Size', 'Unreal P&L'],
                tablefmt='grid'
            ))
        else:
            print("None found - all positions have active monitors ✓")
            
        # Issues summary
        print("\n\nISSUES DETECTED:")
        issues_found = False
        for a in analyses:
            if a['issues']:
                issues_found = True
                print(f"\n{a['key']}:")
                for issue in a['issues']:
                    print(f"  - {issue}")
                    
        if not issues_found:
            print("No issues detected ✓")
            
        # Detailed position analysis
        print("\n\nDETAILED POSITION ANALYSIS:")
        for a in analyses:
            if a['position_exists'] or a['active']:
                print(f"\n{'='*60}")
                print(f"Monitor: {a['key']}")
                print(f"Active: {'Yes' if a['active'] else 'No'}")
                print(f"Position: {'EXISTS' if a['position_exists'] else 'NOT FOUND'}")
                
                if a['position_exists']:
                    print(f"  Size: {a['position_size']:.4f}")
                    print(f"  Value: ${a['position_value']:.2f}")
                    print(f"  Avg Price: ${a['avg_price']:.5f}")
                    print(f"  Mark Price: ${a['mark_price']:.5f}")
                    print(f"  Unreal P&L: ${a['unrealized_pnl']:.2f}")
                    
                print(f"\nOrders:")
                print(f"  TP Orders: {len(a['tp_orders'])}")
                for tp in a['tp_orders']:
                    print(f"    - Price: ${tp['price']:.5f}, Qty: {tp['qty']:.4f}")
                    
                print(f"  SL Orders: {len(a['sl_orders'])}")
                for sl in a['sl_orders']:
                    print(f"    - Trigger: ${sl['trigger']:.5f}, Qty: {sl['qty']:.4f}")
                    
                print(f"  Limit Orders: {len(a['limit_orders'])}")
                for limit in a['limit_orders']:
                    print(f"    - Price: ${limit['price']:.5f}, Qty: {limit['qty']:.4f}")
                    
                print(f"\nMonitor State:")
                monitor = a['monitor_state']
                print(f"  TP1 Hit: {monitor.get('tp1_hit', False)}")
                print(f"  TP2 Hit: {monitor.get('tp2_hit', False)}")
                print(f"  TP3 Hit: {monitor.get('tp3_hit', False)}")
                print(f"  TP4 Hit: {monitor.get('tp4_hit', False)}")
                print(f"  Breakeven: {monitor.get('breakeven_moved', False)}")
                
                print(f"\nPredicted Next Action: {a['next_action']}")
                
                if a['issues']:
                    print(f"\nIssues:")
                    for issue in a['issues']:
                        print(f"  ⚠️  {issue}")
                        
        # Save detailed analysis to file
        analysis_file = f"monitor_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(analysis_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'summary': {
                    'total_monitors': len(self.monitors),
                    'active_monitors': sum(1 for m in self.monitors.values() if m.get('active', False)),
                    'main_positions': len(self.positions_main),
                    'mirror_positions': len(self.positions_mirror),
                    'main_orders': len(self.orders_main),
                    'mirror_orders': len(self.orders_mirror)
                },
                'analyses': analyses,
                'orphaned_positions': orphaned_positions
            }, f, indent=2, default=str)
            
        print(f"\n\nDetailed analysis saved to: {analysis_file}")
        

async def main():
    """Run the comprehensive monitor analysis"""
    analyzer = MonitorAnalyzer()
    
    # Load data
    if not await analyzer.load_data():
        print("Failed to load data")
        return
        
    # Generate report
    analyzer.generate_report()
    

if __name__ == "__main__":
    asyncio.run(main())