#!/usr/bin/env python3
"""
Position balance monitoring script that can be run periodically.
Sends alerts if positions need rebalancing.
"""

import asyncio
import os
import sys
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_position_balance_tolerant import TolerantPositionBalanceChecker
from force_rebalance_positions import PositionRebalancer

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('position_balance_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PositionBalanceMonitor:
    def __init__(self):
        """Initialize the position balance monitor."""
        self.checker = TolerantPositionBalanceChecker()
        self.rebalancer = PositionRebalancer()
        self.state_file = "position_balance_state.json"
        self.check_interval = 3600  # Check every hour
        self.auto_fix_threshold = 5  # Auto-fix if more than 5 positions need rebalancing
        
    def load_state(self) -> Dict:
        """Load previous monitoring state."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            'last_check': None,
            'issues_history': [],
            'auto_fixes_performed': []
        }
    
    def save_state(self, state: Dict):
        """Save monitoring state."""
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2, default=str)
    
    async def check_and_alert(self) -> Dict[str, any]:
        """Check position balance and generate alerts."""
        logger.info("Starting position balance check...")
        
        await self.checker.initialize()
        results = await self.checker.check_all_accounts()
        
        # Analyze results
        alerts = []
        positions_needing_rebalance = []
        
        for account in ['main', 'mirror']:
            if account not in results:
                continue
                
            summary = results[account]['summary']
            positions = results[account]['positions']
            
            # Check for critical issues
            critical_positions = [p for p in positions if p['has_critical_issues']]
            
            if critical_positions:
                alert = {
                    'level': 'CRITICAL',
                    'account': account,
                    'message': f"{len(critical_positions)} positions with critical issues on {account} account",
                    'positions': [p['symbol'] for p in critical_positions]
                }
                alerts.append(alert)
                positions_needing_rebalance.extend([(account, p['symbol']) for p in critical_positions])
            
            # Log summary
            logger.info(f"{account.upper()} Account Summary:")
            logger.info(f"  Total: {summary['total_positions']}")
            logger.info(f"  Balanced: {summary['properly_balanced']}")
            logger.info(f"  Critical: {summary['critical_issues']}")
        
        return {
            'timestamp': datetime.now(),
            'alerts': alerts,
            'positions_needing_rebalance': positions_needing_rebalance,
            'summary': {
                'main': results.get('main', {}).get('summary', {}),
                'mirror': results.get('mirror', {}).get('summary', {})
            }
        }
    
    async def auto_fix_positions(self, positions: List[tuple]) -> Dict:
        """Automatically fix positions that need rebalancing."""
        logger.info(f"Auto-fixing {len(positions)} positions...")
        
        results = {
            'fixed': [],
            'failed': []
        }
        
        for account, symbol in positions:
            try:
                is_mirror = (account == 'mirror')
                result = await self.rebalancer.rebalance_position(symbol, is_mirror=is_mirror)
                
                if result.get('success'):
                    results['fixed'].append((account, symbol))
                    logger.info(f"✅ Fixed {symbol} on {account} account")
                else:
                    results['failed'].append((account, symbol, result.get('error')))
                    logger.error(f"❌ Failed to fix {symbol} on {account}: {result.get('error')}")
                
                # Wait between fixes
                await asyncio.sleep(2)
                
            except Exception as e:
                results['failed'].append((account, symbol, str(e)))
                logger.error(f"Error fixing {symbol} on {account}: {e}")
        
        return results
    
    async def run_once(self, auto_fix: bool = False):
        """Run a single monitoring check."""
        state = self.load_state()
        
        # Check positions
        check_results = await self.check_and_alert()
        
        # Update state
        state['last_check'] = check_results['timestamp'].isoformat()
        state['issues_history'].append({
            'timestamp': check_results['timestamp'].isoformat(),
            'alerts': check_results['alerts'],
            'positions_needing_rebalance': check_results['positions_needing_rebalance']
        })
        
        # Keep only last 24 hours of history
        cutoff = datetime.now() - timedelta(hours=24)
        state['issues_history'] = [
            h for h in state['issues_history'] 
            if datetime.fromisoformat(h['timestamp']) > cutoff
        ]
        
        # Auto-fix if enabled and threshold met
        if auto_fix and len(check_results['positions_needing_rebalance']) >= self.auto_fix_threshold:
            logger.warning(f"Auto-fix threshold met ({len(check_results['positions_needing_rebalance'])} positions)")
            
            fix_results = await self.auto_fix_positions(check_results['positions_needing_rebalance'])
            
            state['auto_fixes_performed'].append({
                'timestamp': datetime.now().isoformat(),
                'fixed': fix_results['fixed'],
                'failed': fix_results['failed']
            })
            
            logger.info(f"Auto-fix complete: {len(fix_results['fixed'])} fixed, {len(fix_results['failed'])} failed")
        
        # Save state
        self.save_state(state)
        
        # Generate summary
        self.generate_summary(check_results)
        
        return check_results
    
    def generate_summary(self, results: Dict):
        """Generate and log a summary of the check."""
        print("\n" + "="*60)
        print("POSITION BALANCE MONITORING SUMMARY")
        print("="*60)
        print(f"Timestamp: {results['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Overall health
        total_positions = sum(s.get('total_positions', 0) for s in results['summary'].values())
        total_balanced = sum(s.get('properly_balanced', 0) for s in results['summary'].values())
        health_pct = (total_balanced / total_positions * 100) if total_positions > 0 else 0
        
        print(f"\nOverall Health: {health_pct:.1f}% ({total_balanced}/{total_positions} balanced)")
        
        # Alerts
        if results['alerts']:
            print(f"\n⚠️  ALERTS ({len(results['alerts'])})")
            for alert in results['alerts']:
                print(f"  [{alert['level']}] {alert['message']}")
                if alert.get('positions'):
                    print(f"    Positions: {', '.join(alert['positions'])}")
        else:
            print("\n✅ No alerts - all positions are healthy")
        
        # Positions needing rebalance
        if results['positions_needing_rebalance']:
            print(f"\n🔄 Positions Needing Rebalance ({len(results['positions_needing_rebalance'])})")
            for account, symbol in results['positions_needing_rebalance']:
                print(f"  • {symbol} ({account})")
        
        print("\n" + "="*60)
    
    async def run_continuous(self, auto_fix: bool = False):
        """Run continuous monitoring."""
        logger.info("Starting continuous position balance monitoring...")
        logger.info(f"Check interval: {self.check_interval} seconds")
        logger.info(f"Auto-fix: {'Enabled' if auto_fix else 'Disabled'}")
        
        while True:
            try:
                await self.run_once(auto_fix=auto_fix)
                
                logger.info(f"Next check in {self.check_interval} seconds...")
                await asyncio.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retrying

async def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor position balance and optionally auto-fix issues')
    parser.add_argument('--once', action='store_true', help='Run once instead of continuous monitoring')
    parser.add_argument('--auto-fix', action='store_true', help='Automatically fix positions when threshold is met')
    parser.add_argument('--interval', type=int, default=3600, help='Check interval in seconds (default: 3600)')
    
    args = parser.parse_args()
    
    monitor = PositionBalanceMonitor()
    monitor.check_interval = args.interval
    
    try:
        if args.once:
            await monitor.run_once(auto_fix=args.auto_fix)
        else:
            await monitor.run_continuous(auto_fix=args.auto_fix)
    except KeyboardInterrupt:
        logger.info("Monitoring stopped")

if __name__ == "__main__":
    asyncio.run(main())