#!/usr/bin/env python3
"""
Comprehensive diagnostic check for Bybit Telegram Bot
"""
import asyncio
import logging
import pickle
import os
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional
from clients.bybit_helpers import get_all_positions, get_all_open_orders
from main import detect_approach_from_orders

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BotDiagnostics:
    def __init__(self):
        self.dashboard_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        self.log_file = 'trading_bot.log'
        self.issues = []
        self.warnings = []
        
    async def run_full_diagnostic(self):
        """Run complete diagnostic check"""
        logger.info("🔍 Starting Bybit Telegram Bot Diagnostic Check")
        logger.info("=" * 60)
        
        # 1. Check environment
        self.check_environment()
        
        # 2. Check persistence/dashboard
        await self.check_persistence()
        
        # 3. Check positions vs monitors
        await self.check_positions_monitors()
        
        # 4. Check recent errors
        self.check_recent_errors()
        
        # 5. Generate report
        self.generate_report()
    
    def check_environment(self):
        """Check environment setup"""
        logger.info("\n📋 ENVIRONMENT CHECK")
        logger.info("-" * 40)
        
        # Check Python version
        import sys
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        logger.info(f"Python version: {py_version}")
        
        # Check virtual environment
        in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        logger.info(f"Virtual environment: {'✅ Active' if in_venv else '❌ Not active'}")
        
        # Check .env file
        if os.path.exists('.env'):
            logger.info("Environment file: ✅ .env exists")
            # Check key variables
            from dotenv import load_dotenv
            load_dotenv()
            required_vars = ['TELEGRAM_TOKEN', 'BYBIT_API_KEY', 'BYBIT_API_SECRET']
            missing_vars = []
            for var in required_vars:
                if not os.getenv(var):
                    missing_vars.append(var)
            
            if missing_vars:
                self.issues.append(f"Missing environment variables: {', '.join(missing_vars)}")
                logger.error(f"❌ Missing environment variables: {', '.join(missing_vars)}")
            else:
                logger.info("✅ All required environment variables present")
        else:
            self.issues.append(".env file not found")
            logger.error("❌ .env file not found")
        
        # Check critical imports
        try:
            import pybit
            logger.info(f"✅ pybit installed")
        except ImportError:
            self.issues.append("pybit not installed")
            logger.error("❌ pybit not installed")
            
        try:
            import telegram
            logger.info(f"✅ python-telegram-bot installed")
        except ImportError:
            self.issues.append("python-telegram-bot not installed")
            logger.error("❌ python-telegram-bot not installed")
    
    async def check_persistence(self):
        """Check persistence/dashboard file"""
        logger.info("\n📊 PERSISTENCE CHECK")
        logger.info("-" * 40)
        
        if not os.path.exists(self.dashboard_file):
            self.issues.append(f"Dashboard file {self.dashboard_file} not found")
            logger.error(f"❌ Dashboard file not found: {self.dashboard_file}")
            return
            
        try:
            # Load dashboard data
            with open(self.dashboard_file, 'rb') as f:
                data = pickle.load(f)
            
            logger.info(f"✅ Dashboard file loaded successfully")
            logger.info(f"   File size: {os.path.getsize(self.dashboard_file) / 1024:.1f} KB")
            
            # Check data structure
            expected_keys = ['conversations', 'user_data', 'chat_data', 'bot_data']
            missing_keys = [k for k in expected_keys if k not in data]
            if missing_keys:
                self.warnings.append(f"Missing keys in dashboard: {missing_keys}")
                logger.warning(f"⚠️  Missing keys: {missing_keys}")
            
            # Analyze bot_data
            bot_data = data.get('bot_data', {})
            monitor_tasks = bot_data.get('monitor_tasks', {})
            
            logger.info(f"\n📍 Bot Data Analysis:")
            logger.info(f"   Total monitors: {len(monitor_tasks)}")
            
            # Group monitors by symbol
            monitors_by_symbol = {}
            for key, info in monitor_tasks.items():
                if isinstance(info, dict):
                    symbol = info.get('symbol', 'unknown')
                    if symbol not in monitors_by_symbol:
                        monitors_by_symbol[symbol] = []
                    monitors_by_symbol[symbol].append({
                        'key': key,
                        'approach': info.get('approach', 'unknown'),
                        'active': info.get('active', False),
                        'chat_id': info.get('chat_id', 'unknown')
                    })
            
            # Check for duplicates
            duplicate_symbols = []
            for symbol, monitors in monitors_by_symbol.items():
                if len(monitors) > 2:  # More than fast+conservative is suspicious
                    duplicate_symbols.append(symbol)
                    logger.warning(f"⚠️  {symbol} has {len(monitors)} monitors:")
                    for m in monitors:
                        status = '🟢' if m['active'] else '🔴'
                        logger.warning(f"     {status} {m['key']} ({m['approach']})")
            
            if duplicate_symbols:
                self.issues.append(f"Duplicate monitors found for: {', '.join(duplicate_symbols)}")
                
        except Exception as e:
            self.issues.append(f"Error loading dashboard: {str(e)}")
            logger.error(f"❌ Error loading dashboard: {e}")
    
    async def check_positions_monitors(self):
        """Check positions vs monitors alignment"""
        logger.info("\n🔄 POSITIONS VS MONITORS CHECK")
        logger.info("-" * 40)
        
        try:
            # Get active positions
            positions = await get_all_positions()
            logger.info(f"\n📈 Active Positions: {len(positions)}")
            
            position_details = {}
            for pos in positions:
                symbol = pos.get('symbol')
                side = pos.get('side')
                size = pos.get('size')
                pnl = float(pos.get('unrealisedPnl', 0))
                position_details[symbol] = {
                    'side': side,
                    'size': size,
                    'pnl': pnl
                }
                logger.info(f"   - {symbol} {side} | Size: {size} | P&L: ${pnl:.2f}")
            
            # Get orders to detect approaches
            all_orders = await get_all_open_orders()
            orders_by_symbol = {}
            for order in all_orders:
                symbol = order.get('symbol')
                if symbol not in orders_by_symbol:
                    orders_by_symbol[symbol] = []
                orders_by_symbol[symbol].append(order)
            
            logger.info(f"\n📋 Order Analysis:")
            for symbol, orders in orders_by_symbol.items():
                approach = detect_approach_from_orders(orders)
                tp_count = len([o for o in orders if 'TP' in o.get('orderLinkId', '')])
                logger.info(f"   - {symbol}: {len(orders)} orders | Detected approach: {approach or 'unknown'} | TPs: {tp_count}")
                
                if symbol in position_details:
                    position_details[symbol]['approach'] = approach
                    position_details[symbol]['order_count'] = len(orders)
            
            # Load monitors for comparison
            with open(self.dashboard_file, 'rb') as f:
                data = pickle.load(f)
            
            monitor_tasks = data.get('bot_data', {}).get('monitor_tasks', {})
            
            # Compare positions with monitors
            logger.info(f"\n⚖️  Position-Monitor Alignment:")
            
            for symbol, pos_info in position_details.items():
                symbol_monitors = [k for k, v in monitor_tasks.items() 
                                 if isinstance(v, dict) and v.get('symbol') == symbol and v.get('active')]
                
                expected_approach = pos_info.get('approach', 'conservative' if pos_info.get('order_count', 0) > 3 else 'fast')
                
                if len(symbol_monitors) == 0:
                    self.issues.append(f"{symbol} position has no active monitors")
                    logger.error(f"   ❌ {symbol}: No active monitors")
                elif len(symbol_monitors) > 2:
                    self.warnings.append(f"{symbol} has {len(symbol_monitors)} monitors (expected max 2)")
                    logger.warning(f"   ⚠️  {symbol}: {len(symbol_monitors)} monitors (possible duplicates)")
                else:
                    logger.info(f"   ✅ {symbol}: {len(symbol_monitors)} monitor(s) active")
                    
            # Check for orphaned monitors
            active_symbols = set(position_details.keys())
            all_monitored_symbols = set()
            for k, v in monitor_tasks.items():
                if isinstance(v, dict) and v.get('active'):
                    all_monitored_symbols.add(v.get('symbol'))
                    
            orphaned_symbols = all_monitored_symbols - active_symbols
            if orphaned_symbols:
                self.warnings.append(f"Monitors without positions: {', '.join(orphaned_symbols)}")
                logger.warning(f"\n⚠️  Orphaned monitors (no position): {', '.join(orphaned_symbols)}")
                
        except Exception as e:
            self.issues.append(f"Error checking positions: {str(e)}")
            logger.error(f"❌ Error checking positions: {e}")
    
    def check_recent_errors(self):
        """Check recent error logs"""
        logger.info("\n📜 RECENT ERROR LOG CHECK")
        logger.info("-" * 40)
        
        if not os.path.exists(self.log_file):
            logger.info("No log file found")
            return
            
        try:
            # Get file size
            log_size = os.path.getsize(self.log_file) / (1024 * 1024)  # MB
            logger.info(f"Log file size: {log_size:.1f} MB")
            
            if log_size > 100:
                self.warnings.append(f"Log file is large ({log_size:.1f} MB), consider rotation")
            
            # Read last 1000 lines
            with open(self.log_file, 'r') as f:
                lines = f.readlines()[-1000:]
            
            # Count errors
            error_count = 0
            critical_count = 0
            recent_errors = []
            
            for line in lines:
                if 'ERROR' in line:
                    error_count += 1
                    if len(recent_errors) < 5:
                        recent_errors.append(line.strip())
                elif 'CRITICAL' in line:
                    critical_count += 1
                    if len(recent_errors) < 5:
                        recent_errors.append(line.strip())
            
            logger.info(f"\nLast 1000 lines analysis:")
            logger.info(f"   Errors: {error_count}")
            logger.info(f"   Critical: {critical_count}")
            
            if recent_errors:
                logger.info(f"\nRecent errors (last 5):")
                for err in recent_errors:
                    logger.info(f"   {err[:100]}...")
                    
            if error_count > 50:
                self.warnings.append(f"High error count in recent logs: {error_count}")
                
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
    
    def generate_report(self):
        """Generate final diagnostic report"""
        logger.info("\n" + "=" * 60)
        logger.info("📋 DIAGNOSTIC REPORT SUMMARY")
        logger.info("=" * 60)
        
        if not self.issues and not self.warnings:
            logger.info("\n✅ ALL CHECKS PASSED! Bot appears to be healthy.")
        else:
            if self.issues:
                logger.info(f"\n❌ CRITICAL ISSUES ({len(self.issues)}):")
                for i, issue in enumerate(self.issues, 1):
                    logger.info(f"   {i}. {issue}")
                    
            if self.warnings:
                logger.info(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
                for i, warning in enumerate(self.warnings, 1):
                    logger.info(f"   {i}. {warning}")
        
        logger.info("\n📝 RECOMMENDATIONS:")
        
        # Generate recommendations based on findings
        if any('Duplicate monitors' in issue for issue in self.issues):
            logger.info("   1. Run fix_duplicate_monitors.py to clean up duplicate monitors")
            
        if any('Missing environment' in issue for issue in self.issues):
            logger.info("   2. Check .env file and ensure all required variables are set")
            
        if any('large' in warning.lower() for warning in self.warnings):
            logger.info("   3. Consider implementing log rotation to manage file size")
            
        if any('Orphaned monitors' in warning for warning in self.warnings):
            logger.info("   4. Clean up monitors for closed positions")
            
        logger.info("\n" + "=" * 60)
        logger.info("Diagnostic check complete!")

async def main():
    diagnostics = BotDiagnostics()
    await diagnostics.run_full_diagnostic()

if __name__ == "__main__":
    asyncio.run(main())