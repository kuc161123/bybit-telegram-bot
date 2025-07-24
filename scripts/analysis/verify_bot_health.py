#!/usr/bin/env python3
"""
Comprehensive bot health verification
Checks all critical systems and reports status
"""
import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Tuple
import pickle
from datetime import datetime
from collections import defaultdict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from clients.bybit_helpers import get_position_info, get_open_orders
from execution.mirror_trader import is_mirror_trading_enabled, get_mirror_positions, bybit_client_2
from config.settings import ENABLE_ENHANCED_TP_SL

class BotHealthChecker:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.successes = []
        
    def add_issue(self, message: str):
        self.issues.append(f"❌ {message}")
        
    def add_warning(self, message: str):
        self.warnings.append(f"⚠️ {message}")
        
    def add_success(self, message: str):
        self.successes.append(f"✅ {message}")
    
    async def check_positions_and_orders(self) -> Dict:
        """Check all positions and their orders on both accounts"""
        results = {
            "main": {"positions": [], "orphaned_orders": []},
            "mirror": {"positions": [], "orphaned_orders": []}
        }
        
        # Get all symbols with positions
        all_symbols = set()
        
        # Main account positions
        try:
            # Get positions for all symbols
            from clients.bybit_client import bybit_client
            response = bybit_client.get_positions(category="linear", settleCoin="USDT")
            if response and response.get('retCode') == 0:
                main_positions = response.get('result', {}).get('list', [])
            else:
                main_positions = []
                
            for pos in main_positions:
                if float(pos.get('size', 0)) > 0:
                    symbol = pos['symbol']
                    all_symbols.add(symbol)
                    
                    # Get orders for this position
                    orders = await get_open_orders(symbol)
                    tp_count = sum(1 for o in orders if o.get('reduceOnly') and 'TP' in o.get('orderLinkId', ''))
                    sl_count = sum(1 for o in orders if o.get('reduceOnly') and 'SL' in o.get('orderLinkId', ''))
                    entry_count = sum(1 for o in orders if not o.get('reduceOnly'))
                    
                    results["main"]["positions"].append({
                        "symbol": symbol,
                        "side": pos['side'],
                        "size": pos['size'],
                        "tp_orders": tp_count,
                        "sl_orders": sl_count,
                        "entry_orders": entry_count
                    })
                    
            self.add_success(f"Found {len(results['main']['positions'])} main account positions")
        except Exception as e:
            self.add_issue(f"Failed to get main account positions: {e}")
            
        # Mirror account positions
        if is_mirror_trading_enabled():
            try:
                mirror_positions = await get_mirror_positions()
                for pos in mirror_positions:
                    if float(pos.get('size', 0)) > 0:
                        symbol = pos['symbol']
                        all_symbols.add(symbol)
                        
                        # Get mirror orders
                        if bybit_client_2:
                            response = bybit_client_2.get_open_orders(
                                category="linear",
                                symbol=symbol
                            )
                            if response and response.get('retCode') == 0:
                                orders = response.get('result', {}).get('list', [])
                                tp_count = sum(1 for o in orders if o.get('reduceOnly') and 'TP' in o.get('orderLinkId', ''))
                                sl_count = sum(1 for o in orders if o.get('reduceOnly') and 'SL' in o.get('orderLinkId', ''))
                                entry_count = sum(1 for o in orders if not o.get('reduceOnly'))
                                
                                results["mirror"]["positions"].append({
                                    "symbol": symbol,
                                    "side": pos['side'],
                                    "size": pos['size'],
                                    "tp_orders": tp_count,
                                    "sl_orders": sl_count,
                                    "entry_orders": entry_count
                                })
                                
                self.add_success(f"Found {len(results['mirror']['positions'])} mirror account positions")
            except Exception as e:
                self.add_issue(f"Failed to get mirror account positions: {e}")
        
        # Check for orphaned orders
        for symbol in all_symbols:
            # Main account
            main_has_position = any(p['symbol'] == symbol for p in results['main']['positions'])
            main_orders = await get_open_orders(symbol)
            if not main_has_position and main_orders:
                results["main"]["orphaned_orders"].append({
                    "symbol": symbol,
                    "order_count": len(main_orders)
                })
                
            # Mirror account
            if is_mirror_trading_enabled() and bybit_client_2:
                mirror_has_position = any(p['symbol'] == symbol for p in results['mirror']['positions'])
                response = bybit_client_2.get_open_orders(category="linear", symbol=symbol)
                if response and response.get('retCode') == 0:
                    mirror_orders = response.get('result', {}).get('list', [])
                    if not mirror_has_position and mirror_orders:
                        results["mirror"]["orphaned_orders"].append({
                            "symbol": symbol,
                            "order_count": len(mirror_orders)
                        })
        
        return results
    
    async def check_enhanced_monitors(self) -> Dict:
        """Check Enhanced TP/SL monitors"""
        try:
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
                data = pickle.load(f)
            
            enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
            monitor_tasks = data.get('bot_data', {}).get('monitor_tasks', {})
            
            active_enhanced = sum(1 for m in enhanced_monitors.values() if m.get('active'))
            active_dashboard = sum(1 for m in monitor_tasks.values() if m.get('active'))
            
            # Check for position/monitor mismatches
            position_symbols = set()
            positions_data = await self.check_positions_and_orders()
            for pos in positions_data['main']['positions']:
                position_symbols.add(f"{pos['symbol']}_{pos['side']}")
            for pos in positions_data['mirror']['positions']:
                position_symbols.add(f"{pos['symbol']}_{pos['side']}")
                
            monitor_symbols = set(enhanced_monitors.keys())
            
            missing_monitors = position_symbols - monitor_symbols
            orphaned_monitors = monitor_symbols - position_symbols
            
            if missing_monitors:
                self.add_warning(f"Positions without Enhanced monitors: {missing_monitors}")
            if orphaned_monitors:
                self.add_warning(f"Orphaned Enhanced monitors: {orphaned_monitors}")
                
            self.add_success(f"Enhanced monitors: {active_enhanced} active")
            self.add_success(f"Dashboard monitors: {active_dashboard} active")
            
            return {
                "enhanced_count": active_enhanced,
                "dashboard_count": active_dashboard,
                "missing_monitors": list(missing_monitors),
                "orphaned_monitors": list(orphaned_monitors)
            }
            
        except Exception as e:
            self.add_issue(f"Failed to check monitors: {e}")
            return {}
    
    async def check_tp_sl_coverage(self, positions_data: Dict) -> Dict:
        """Check TP/SL coverage for all positions"""
        coverage_issues = []
        
        for account in ['main', 'mirror']:
            for pos in positions_data[account]['positions']:
                symbol = pos['symbol']
                side = pos['side']
                size = Decimal(str(pos['size']))
                
                # Check SL coverage
                if pos['sl_orders'] == 0:
                    coverage_issues.append(f"{account.upper()} {symbol} {side}: No SL order")
                    self.add_issue(f"{account.upper()} {symbol} has no SL order!")
                
                # Check TP coverage (should have at least 1)
                if pos['tp_orders'] == 0:
                    coverage_issues.append(f"{account.upper()} {symbol} {side}: No TP orders")
                    self.add_warning(f"{account.upper()} {symbol} has no TP orders")
                
                # For conservative positions with entry orders, check SL coverage
                if pos['entry_orders'] > 0 and pos['sl_orders'] > 0:
                    # This would need actual order data to verify quantities
                    self.add_success(f"{account.upper()} {symbol} has pending entries - verify SL covers full target")
        
        return {"coverage_issues": coverage_issues}
    
    async def check_system_status(self) -> Dict:
        """Check overall system status"""
        status = {
            "enhanced_tp_sl": ENABLE_ENHANCED_TP_SL,
            "mirror_trading": is_mirror_trading_enabled(),
            "timestamp": datetime.now().isoformat()
        }
        
        if ENABLE_ENHANCED_TP_SL:
            self.add_success("Enhanced TP/SL system is enabled")
        else:
            self.add_warning("Enhanced TP/SL system is disabled")
            
        if is_mirror_trading_enabled():
            self.add_success("Mirror trading is enabled")
        else:
            self.add_warning("Mirror trading is disabled")
            
        return status
    
    def generate_report(self) -> str:
        """Generate health check report"""
        report = []
        report.append("=" * 60)
        report.append("🏥 BOT HEALTH CHECK REPORT")
        report.append("=" * 60)
        report.append(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        if self.issues:
            report.append("🚨 CRITICAL ISSUES:")
            for issue in self.issues:
                report.append(f"  {issue}")
            report.append("")
            
        if self.warnings:
            report.append("⚠️  WARNINGS:")
            for warning in self.warnings:
                report.append(f"  {warning}")
            report.append("")
            
        if self.successes:
            report.append("✅ HEALTHY COMPONENTS:")
            for success in self.successes:
                report.append(f"  {success}")
            report.append("")
        
        # Overall status
        if self.issues:
            report.append("🔴 OVERALL STATUS: NEEDS ATTENTION")
        elif self.warnings:
            report.append("🟡 OVERALL STATUS: OPERATIONAL WITH WARNINGS")
        else:
            report.append("🟢 OVERALL STATUS: ALL SYSTEMS HEALTHY")
            
        report.append("=" * 60)
        
        return "\n".join(report)

async def main():
    logger.info("Starting comprehensive bot health check...")
    
    checker = BotHealthChecker()
    
    # Run all checks
    logger.info("1. Checking system status...")
    system_status = await checker.check_system_status()
    
    logger.info("2. Checking positions and orders...")
    positions_data = await checker.check_positions_and_orders()
    
    logger.info("3. Checking Enhanced TP/SL monitors...")
    monitor_status = await checker.check_enhanced_monitors()
    
    logger.info("4. Checking TP/SL coverage...")
    coverage_status = await checker.check_tp_sl_coverage(positions_data)
    
    # Generate and display report
    report = checker.generate_report()
    print(report)
    
    # Detailed position summary
    print("\nDETAILED POSITION SUMMARY:")
    print("-" * 60)
    
    for account in ['main', 'mirror']:
        if positions_data[account]['positions']:
            print(f"\n{account.upper()} ACCOUNT:")
            for pos in positions_data[account]['positions']:
                print(f"  {pos['symbol']} {pos['side']}:")
                print(f"    Size: {pos['size']}")
                print(f"    TP orders: {pos['tp_orders']}")
                print(f"    SL orders: {pos['sl_orders']}")
                print(f"    Entry orders: {pos['entry_orders']}")
    
    if positions_data['main']['orphaned_orders'] or positions_data['mirror']['orphaned_orders']:
        print("\nORPHANED ORDERS (orders without positions):")
        for account in ['main', 'mirror']:
            for orphan in positions_data[account]['orphaned_orders']:
                print(f"  {account.upper()} {orphan['symbol']}: {orphan['order_count']} orders")
    
    print("\n" + "=" * 60)
    
    # Save report to file
    report_file = f"health_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w') as f:
        f.write(report)
        f.write("\n\nDETAILED DATA:\n")
        f.write(f"System Status: {system_status}\n")
        f.write(f"Positions Data: {positions_data}\n")
        f.write(f"Monitor Status: {monitor_status}\n")
        f.write(f"Coverage Status: {coverage_status}\n")
    
    logger.info(f"Report saved to {report_file}")

if __name__ == "__main__":
    asyncio.run(main())