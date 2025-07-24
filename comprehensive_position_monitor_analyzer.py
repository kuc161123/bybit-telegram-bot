#!/usr/bin/env python3
"""
Comprehensive Position vs Monitor Analyzer
Compares actual Bybit positions with monitors in pickle file
Identifies missing monitors and missing chat_ids
"""

import asyncio
import logging
import sys
import os
import pickle
import json
from typing import Dict, List, Set, Optional, Tuple
from datetime import datetime
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

from clients.bybit_helpers import get_all_positions, get_open_orders
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
from config.settings import DEFAULT_ALERT_CHAT_ID

class PositionMonitorAnalyzer:
    """Comprehensive analyzer for positions and monitors"""
    
    def __init__(self):
        self.analysis_results = {
            "timestamp": datetime.now().isoformat(),
            "bybit_positions": {
                "main": [],
                "mirror": []
            },
            "pickle_monitors": {},
            "issues": {
                "positions_without_monitors": [],
                "monitors_without_chat_id": [],
                "orphaned_monitors": [],
                "monitors_missing_orders": []
            },
            "statistics": {
                "total_bybit_positions": 0,
                "total_pickle_monitors": 0,
                "monitors_with_chat_id": 0,
                "monitors_without_chat_id": 0,
                "coverage_percentage": 0
            },
            "recommendations": []
        }
        
    async def fetch_bybit_positions(self):
        """Fetch all positions from both Bybit accounts"""
        logger.info("🔍 Fetching positions from Bybit...")
        
        # Fetch main account positions
        try:
            main_positions = await get_all_positions()
            active_main = []
            
            for pos in main_positions:
                if float(pos.get('size', 0)) > 0:
                    active_main.append({
                        "symbol": pos.get('symbol'),
                        "side": pos.get('side'),
                        "size": float(pos.get('size', 0)),
                        "avgPrice": float(pos.get('avgPrice', 0)),
                        "markPrice": float(pos.get('markPrice', 0)),
                        "unrealisedPnl": float(pos.get('unrealisedPnl', 0)),
                        "account": "main"
                    })
            
            self.analysis_results["bybit_positions"]["main"] = active_main
            logger.info(f"✅ Found {len(active_main)} active positions on main account")
            
        except Exception as e:
            logger.error(f"❌ Error fetching main positions: {e}")
            
        # Fetch mirror account positions
        if is_mirror_trading_enabled() and bybit_client_2:
            try:
                mirror_positions = await get_all_positions(client=bybit_client_2)
                active_mirror = []
                
                for pos in mirror_positions:
                    if float(pos.get('size', 0)) > 0:
                        active_mirror.append({
                            "symbol": pos.get('symbol'),
                            "side": pos.get('side'),
                            "size": float(pos.get('size', 0)),
                            "avgPrice": float(pos.get('avgPrice', 0)),
                            "markPrice": float(pos.get('markPrice', 0)),
                            "unrealisedPnl": float(pos.get('unrealisedPnl', 0)),
                            "account": "mirror"
                        })
                
                self.analysis_results["bybit_positions"]["mirror"] = active_mirror
                logger.info(f"✅ Found {len(active_mirror)} active positions on mirror account")
                
            except Exception as e:
                logger.error(f"❌ Error fetching mirror positions: {e}")
        else:
            logger.info("ℹ️ Mirror trading not enabled or configured")
            
        # Update statistics
        total_positions = len(self.analysis_results["bybit_positions"]["main"]) + \
                         len(self.analysis_results["bybit_positions"]["mirror"])
        self.analysis_results["statistics"]["total_bybit_positions"] = total_positions
        
    def load_pickle_monitors(self):
        """Load monitors from pickle file"""
        logger.info("📂 Loading monitors from pickle file...")
        
        try:
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
                data = pickle.load(f)
            
            monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
            self.analysis_results["pickle_monitors"] = monitors
            self.analysis_results["statistics"]["total_pickle_monitors"] = len(monitors)
            
            # Analyze monitors
            for key, monitor in monitors.items():
                if monitor.get('chat_id'):
                    self.analysis_results["statistics"]["monitors_with_chat_id"] += 1
                else:
                    self.analysis_results["statistics"]["monitors_without_chat_id"] += 1
                    self.analysis_results["issues"]["monitors_without_chat_id"].append({
                        "monitor_key": key,
                        "symbol": monitor.get('symbol'),
                        "side": monitor.get('side'),
                        "account": monitor.get('account_type', 'unknown')
                    })
            
            logger.info(f"✅ Loaded {len(monitors)} monitors from pickle")
            
        except Exception as e:
            logger.error(f"❌ Error loading pickle: {e}")
            
    def compare_positions_and_monitors(self):
        """Compare Bybit positions with pickle monitors"""
        logger.info("🔄 Comparing positions with monitors...")
        
        # Create position keys for comparison
        bybit_position_keys = set()
        position_details = {}
        
        # Main account positions
        for pos in self.analysis_results["bybit_positions"]["main"]:
            key = f"{pos['symbol']}_{pos['side']}_main"
            bybit_position_keys.add(key)
            position_details[key] = pos
            
        # Mirror account positions
        for pos in self.analysis_results["bybit_positions"]["mirror"]:
            key = f"{pos['symbol']}_{pos['side']}_mirror"
            bybit_position_keys.add(key)
            position_details[key] = pos
            
        # Get monitor keys
        monitor_keys = set(self.analysis_results["pickle_monitors"].keys())
        
        # Find positions without monitors
        positions_without_monitors = bybit_position_keys - monitor_keys
        for key in positions_without_monitors:
            pos = position_details[key]
            self.analysis_results["issues"]["positions_without_monitors"].append({
                "position_key": key,
                "symbol": pos['symbol'],
                "side": pos['side'],
                "account": pos['account'],
                "size": pos['size'],
                "avgPrice": pos['avgPrice'],
                "unrealisedPnl": pos['unrealisedPnl']
            })
            
        # Find orphaned monitors (monitors without positions)
        orphaned_monitors = monitor_keys - bybit_position_keys
        for key in orphaned_monitors:
            monitor = self.analysis_results["pickle_monitors"][key]
            self.analysis_results["issues"]["orphaned_monitors"].append({
                "monitor_key": key,
                "symbol": monitor.get('symbol'),
                "side": monitor.get('side'),
                "account": monitor.get('account_type', 'unknown'),
                "size": float(monitor.get('position_size', 0))
            })
            
        # Check monitors for missing orders
        for key, monitor in self.analysis_results["pickle_monitors"].items():
            if key in bybit_position_keys:  # Only check active positions
                has_tp = bool(monitor.get('tp_orders'))
                has_sl = bool(monitor.get('sl_order'))
                
                if not has_tp or not has_sl:
                    self.analysis_results["issues"]["monitors_missing_orders"].append({
                        "monitor_key": key,
                        "symbol": monitor.get('symbol'),
                        "side": monitor.get('side'),
                        "missing_tp": not has_tp,
                        "missing_sl": not has_sl
                    })
                    
    def calculate_coverage(self):
        """Calculate alert coverage percentage"""
        total_positions = self.analysis_results["statistics"]["total_bybit_positions"]
        
        if total_positions > 0:
            # Positions with monitors that have chat_id
            covered_positions = 0
            
            for pos in (self.analysis_results["bybit_positions"]["main"] + 
                       self.analysis_results["bybit_positions"]["mirror"]):
                key = f"{pos['symbol']}_{pos['side']}_{pos['account']}"
                monitor = self.analysis_results["pickle_monitors"].get(key)
                
                if monitor and monitor.get('chat_id'):
                    covered_positions += 1
                    
            coverage = (covered_positions / total_positions) * 100
            self.analysis_results["statistics"]["coverage_percentage"] = coverage
            
    def generate_recommendations(self):
        """Generate recommendations based on analysis"""
        recommendations = []
        
        # Missing monitors
        if self.analysis_results["issues"]["positions_without_monitors"]:
            count = len(self.analysis_results["issues"]["positions_without_monitors"])
            recommendations.append(f"Create {count} missing monitors for positions without monitoring")
            
        # Missing chat IDs
        if self.analysis_results["issues"]["monitors_without_chat_id"]:
            count = len(self.analysis_results["issues"]["monitors_without_chat_id"])
            recommendations.append(f"Fix {count} monitors missing chat_id for alert delivery")
            
        # Orphaned monitors
        if self.analysis_results["issues"]["orphaned_monitors"]:
            count = len(self.analysis_results["issues"]["orphaned_monitors"])
            recommendations.append(f"Clean up {count} orphaned monitors (positions closed)")
            
        # Missing orders
        if self.analysis_results["issues"]["monitors_missing_orders"]:
            count = len(self.analysis_results["issues"]["monitors_missing_orders"])
            recommendations.append(f"Fix {count} monitors missing TP/SL orders")
            
        # DEFAULT_ALERT_CHAT_ID
        if not DEFAULT_ALERT_CHAT_ID:
            recommendations.append("Set DEFAULT_ALERT_CHAT_ID in .env file for future positions")
            
        self.analysis_results["recommendations"] = recommendations
        
    def generate_report(self):
        """Generate comprehensive report"""
        logger.info("\n" + "="*80)
        logger.info("📊 POSITION VS MONITOR ANALYSIS REPORT")
        logger.info("="*80)
        
        # Statistics
        stats = self.analysis_results["statistics"]
        logger.info(f"\n📈 STATISTICS:")
        logger.info(f"   Bybit Positions: {stats['total_bybit_positions']}")
        logger.info(f"   Pickle Monitors: {stats['total_pickle_monitors']}")
        logger.info(f"   Monitors with Chat ID: {stats['monitors_with_chat_id']}")
        logger.info(f"   Monitors without Chat ID: {stats['monitors_without_chat_id']}")
        logger.info(f"   Alert Coverage: {stats['coverage_percentage']:.1f}%")
        
        # Issues
        logger.info(f"\n⚠️ ISSUES FOUND:")
        
        # Positions without monitors
        if self.analysis_results["issues"]["positions_without_monitors"]:
            logger.info(f"\n❌ Positions Without Monitors ({len(self.analysis_results['issues']['positions_without_monitors'])}):")
            for pos in self.analysis_results["issues"]["positions_without_monitors"]:
                logger.info(f"   - {pos['symbol']} {pos['side']} ({pos['account']}) - Size: {pos['size']}, P&L: ${pos['unrealisedPnl']:.2f}")
                
        # Monitors without chat_id
        if self.analysis_results["issues"]["monitors_without_chat_id"]:
            logger.info(f"\n❌ Monitors Without Chat ID ({len(self.analysis_results['issues']['monitors_without_chat_id'])}):")
            for mon in self.analysis_results["issues"]["monitors_without_chat_id"]:
                logger.info(f"   - {mon['symbol']} {mon['side']} ({mon['account']})")
                
        # Orphaned monitors
        if self.analysis_results["issues"]["orphaned_monitors"]:
            logger.info(f"\n⚠️ Orphaned Monitors ({len(self.analysis_results['issues']['orphaned_monitors'])}):")
            for mon in self.analysis_results["issues"]["orphaned_monitors"]:
                logger.info(f"   - {mon['symbol']} {mon['side']} ({mon['account']}) - Size: {mon['size']}")
                
        # Monitors missing orders
        if self.analysis_results["issues"]["monitors_missing_orders"]:
            logger.info(f"\n⚠️ Monitors Missing Orders ({len(self.analysis_results['issues']['monitors_missing_orders'])}):")
            for mon in self.analysis_results["issues"]["monitors_missing_orders"]:
                missing = []
                if mon['missing_tp']:
                    missing.append("TP")
                if mon['missing_sl']:
                    missing.append("SL")
                logger.info(f"   - {mon['symbol']} {mon['side']} - Missing: {', '.join(missing)}")
                
        # Recommendations
        if self.analysis_results["recommendations"]:
            logger.info(f"\n💡 RECOMMENDATIONS:")
            for i, rec in enumerate(self.analysis_results["recommendations"], 1):
                logger.info(f"   {i}. {rec}")
                
        # Summary
        logger.info(f"\n📋 SUMMARY:")
        if stats['coverage_percentage'] >= 100:
            logger.info("   ✅ All positions have monitors with chat IDs!")
            logger.info("   ✅ Full alert coverage achieved!")
        elif stats['coverage_percentage'] >= 80:
            logger.info("   ⚠️ Good coverage but some positions lack alerts")
            logger.info("   ⚠️ Fix missing monitors and chat IDs for 100% coverage")
        else:
            logger.info("   ❌ Poor alert coverage - immediate action needed")
            logger.info("   ❌ Many positions won't receive alerts")
            
        logger.info("\n" + "="*80)
        
    def save_analysis(self):
        """Save analysis results to file"""
        filename = f"position_monitor_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(self.analysis_results, f, indent=2, default=str)
        logger.info(f"📁 Analysis saved to: {filename}")

async def main():
    """Run comprehensive analysis"""
    analyzer = PositionMonitorAnalyzer()
    
    # Fetch Bybit positions
    await analyzer.fetch_bybit_positions()
    
    # Load pickle monitors
    analyzer.load_pickle_monitors()
    
    # Compare and analyze
    analyzer.compare_positions_and_monitors()
    
    # Calculate coverage
    analyzer.calculate_coverage()
    
    # Generate recommendations
    analyzer.generate_recommendations()
    
    # Generate report
    analyzer.generate_report()
    
    # Save analysis
    analyzer.save_analysis()
    
    return analyzer.analysis_results

if __name__ == "__main__":
    asyncio.run(main())