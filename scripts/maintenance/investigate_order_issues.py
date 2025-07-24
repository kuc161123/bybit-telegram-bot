#!/usr/bin/env python3
"""
Investigate why orders keep disappearing.
This script will:
1. Monitor order status changes in real-time
2. Check for any external order cancellations
3. Identify patterns in order disappearance
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import *

class OrderInvestigator:
    def __init__(self):
        """Initialize the order investigator."""
        self.main_client = HTTP(
            api_key=BYBIT_API_KEY,
            api_secret=BYBIT_API_SECRET,
            testnet=USE_TESTNET
        )
        
        self.mirror_client = None
        if BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
            self.mirror_client = HTTP(
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2,
                testnet=USE_TESTNET
            )
        
        self.known_orders: Dict[str, Set[str]] = {
            'main': set(),
            'mirror': set()
        }
        
        self.cancelled_orders: List[Dict] = []
        
    async def get_all_orders(self, client: HTTP, account: str) -> List[Dict]:
        """Get all open orders for an account."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.get_open_orders(category="linear", settleCoin="USDT", limit=200)
            )
            
            if response and response.get("retCode") == 0:
                return response.get("result", {}).get("list", [])
            return []
        except Exception as e:
            logger.error(f"Error getting orders for {account}: {e}")
            return []
    
    async def get_order_history(self, client: HTTP, account: str, hours: int = 1) -> List[Dict]:
        """Get order history for recent cancellations."""
        try:
            loop = asyncio.get_event_loop()
            
            # Get cancelled orders from order history
            response = await loop.run_in_executor(
                None,
                lambda: client.get_order_history(
                    category="linear",
                    orderStatus="Cancelled",
                    limit=200
                )
            )
            
            if response and response.get("retCode") == 0:
                orders = response.get("result", {}).get("list", [])
                
                # Filter orders cancelled in the last N hours
                cutoff_time = datetime.now() - timedelta(hours=hours)
                recent_cancelled = []
                
                for order in orders:
                    # Parse update time
                    update_time = int(order.get('updatedTime', '0'))
                    if update_time > 0:
                        order_time = datetime.fromtimestamp(update_time / 1000)
                        if order_time > cutoff_time:
                            recent_cancelled.append({
                                'account': account,
                                'symbol': order['symbol'],
                                'orderId': order['orderId'],
                                'orderLinkId': order.get('orderLinkId', ''),
                                'side': order['side'],
                                'orderType': order['orderType'],
                                'cancelType': order.get('cancelType', 'Unknown'),
                                'rejectReason': order.get('rejectReason', ''),
                                'cancelledTime': order_time.strftime('%Y-%m-%d %H:%M:%S'),
                                'createdTime': datetime.fromtimestamp(int(order.get('createdTime', '0')) / 1000).strftime('%Y-%m-%d %H:%M:%S')
                            })
                
                return recent_cancelled
            return []
            
        except Exception as e:
            logger.error(f"Error getting order history for {account}: {e}")
            return []
    
    async def monitor_orders_once(self):
        """Check orders once and detect changes."""
        changes_detected = []
        
        # Check main account
        if self.main_client:
            current_orders = await self.get_all_orders(self.main_client, 'main')
            current_order_ids = {order['orderId'] for order in current_orders}
            
            # Check for disappeared orders
            disappeared = self.known_orders['main'] - current_order_ids
            if disappeared:
                for order_id in disappeared:
                    changes_detected.append({
                        'account': 'main',
                        'type': 'disappeared',
                        'orderId': order_id,
                        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    logger.warning(f"❌ Order disappeared on MAIN: {order_id}")
            
            # Check for new orders
            new_orders = current_order_ids - self.known_orders['main']
            if new_orders:
                for order_id in new_orders:
                    order = next(o for o in current_orders if o['orderId'] == order_id)
                    changes_detected.append({
                        'account': 'main',
                        'type': 'new',
                        'orderId': order_id,
                        'symbol': order['symbol'],
                        'orderLinkId': order.get('orderLinkId', ''),
                        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    logger.info(f"✅ New order on MAIN: {order_id} ({order['symbol']})")
            
            self.known_orders['main'] = current_order_ids
        
        # Check mirror account
        if self.mirror_client:
            current_orders = await self.get_all_orders(self.mirror_client, 'mirror')
            current_order_ids = {order['orderId'] for order in current_orders}
            
            # Check for disappeared orders
            disappeared = self.known_orders['mirror'] - current_order_ids
            if disappeared:
                for order_id in disappeared:
                    changes_detected.append({
                        'account': 'mirror',
                        'type': 'disappeared',
                        'orderId': order_id,
                        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    logger.warning(f"❌ Order disappeared on MIRROR: {order_id}")
            
            # Check for new orders
            new_orders = current_order_ids - self.known_orders['mirror']
            if new_orders:
                for order_id in new_orders:
                    order = next(o for o in current_orders if o['orderId'] == order_id)
                    changes_detected.append({
                        'account': 'mirror',
                        'type': 'new',
                        'orderId': order_id,
                        'symbol': order['symbol'],
                        'orderLinkId': order.get('orderLinkId', ''),
                        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    logger.info(f"✅ New order on MIRROR: {order_id} ({order['symbol']})")
            
            self.known_orders['mirror'] = current_order_ids
        
        return changes_detected
    
    async def check_recent_cancellations(self):
        """Check for recently cancelled orders."""
        all_cancelled = []
        
        # Check main account
        if self.main_client:
            cancelled = await self.get_order_history(self.main_client, 'main', hours=1)
            all_cancelled.extend(cancelled)
            
            if cancelled:
                logger.info(f"\n📋 Recent cancellations on MAIN account ({len(cancelled)} orders):")
                for order in cancelled[:10]:  # Show first 10
                    logger.info(f"  - {order['symbol']} {order['orderId'][:8]}... "
                              f"(Link: {order['orderLinkId']}) "
                              f"Cancel Type: {order['cancelType']}")
        
        # Check mirror account
        if self.mirror_client:
            cancelled = await self.get_order_history(self.mirror_client, 'mirror', hours=1)
            all_cancelled.extend(cancelled)
            
            if cancelled:
                logger.info(f"\n📋 Recent cancellations on MIRROR account ({len(cancelled)} orders):")
                for order in cancelled[:10]:  # Show first 10
                    logger.info(f"  - {order['symbol']} {order['orderId'][:8]}... "
                              f"(Link: {order['orderLinkId']}) "
                              f"Cancel Type: {order['cancelType']}")
        
        return all_cancelled
    
    async def analyze_patterns(self, changes: List[Dict], cancellations: List[Dict]):
        """Analyze patterns in order disappearance."""
        print("\n" + "="*60)
        print("ORDER ISSUE ANALYSIS")
        print("="*60)
        
        # Group cancellations by cancel type
        cancel_types = {}
        for cancel in cancellations:
            cancel_type = cancel['cancelType']
            if cancel_type not in cancel_types:
                cancel_types[cancel_type] = []
            cancel_types[cancel_type].append(cancel)
        
        print("\n📊 Cancellation Types:")
        for cancel_type, orders in cancel_types.items():
            print(f"  - {cancel_type}: {len(orders)} orders")
            
            # Show examples
            if orders:
                print(f"    Examples:")
                for order in orders[:3]:
                    print(f"      • {order['symbol']} - {order['orderLinkId']}")
        
        # Analyze order link IDs
        bot_orders = [c for c in cancellations if 'BOT_' in c.get('orderLinkId', '')]
        non_bot_orders = [c for c in cancellations if 'BOT_' not in c.get('orderLinkId', '')]
        
        print(f"\n🤖 Order Sources:")
        print(f"  - Bot orders (BOT_): {len(bot_orders)}")
        print(f"  - Non-bot orders: {len(non_bot_orders)}")
        
        # Check for patterns in disappeared orders
        if changes:
            disappeared = [c for c in changes if c['type'] == 'disappeared']
            if disappeared:
                print(f"\n⚠️  Orders that disappeared without trace: {len(disappeared)}")
                for order in disappeared[:5]:
                    print(f"  - {order['orderId']} ({order['account']}) at {order['time']}")
        
        # Save detailed report
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_cancellations': len(cancellations),
                'cancel_types': {k: len(v) for k, v in cancel_types.items()},
                'bot_orders_cancelled': len(bot_orders),
                'non_bot_orders_cancelled': len(non_bot_orders),
                'disappeared_orders': len([c for c in changes if c['type'] == 'disappeared'])
            },
            'cancellations': cancellations,
            'changes': changes
        }
        
        with open('order_investigation_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: order_investigation_report.json")
    
    async def run_investigation(self, duration_minutes: int = 5):
        """Run investigation for specified duration."""
        logger.info(f"Starting order investigation for {duration_minutes} minutes...")
        
        # Initial snapshot
        logger.info("Taking initial order snapshot...")
        await self.monitor_orders_once()
        
        # Check recent cancellations
        logger.info("\nChecking recent order cancellations...")
        cancellations = await self.check_recent_cancellations()
        
        # Monitor for changes
        all_changes = []
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        check_interval = 30  # seconds
        
        logger.info(f"\nMonitoring orders every {check_interval} seconds...")
        
        while datetime.now() < end_time:
            await asyncio.sleep(check_interval)
            
            changes = await self.monitor_orders_once()
            if changes:
                all_changes.extend(changes)
            
            # Show progress
            remaining = (end_time - datetime.now()).total_seconds()
            if remaining > 0:
                logger.info(f"⏱️  {int(remaining/60)}:{int(remaining%60):02d} remaining...")
        
        # Analyze patterns
        await self.analyze_patterns(all_changes, cancellations)

async def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Investigate why orders are disappearing')
    parser.add_argument('--duration', type=int, default=5, help='Duration to monitor in minutes (default: 5)')
    
    args = parser.parse_args()
    
    investigator = OrderInvestigator()
    
    try:
        await investigator.run_investigation(duration_minutes=args.duration)
    except KeyboardInterrupt:
        logger.info("\nInvestigation stopped by user")

if __name__ == "__main__":
    asyncio.run(main())