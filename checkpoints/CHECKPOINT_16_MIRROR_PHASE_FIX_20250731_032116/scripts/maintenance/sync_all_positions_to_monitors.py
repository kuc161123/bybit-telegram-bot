#!/usr/bin/env python3
"""
Comprehensive Position-to-Monitor Synchronization Script
========================================================

This script ensures perfect synchronization between actual Bybit positions
and the bot's monitor system by:
1. Fetching all positions from both main and mirror accounts
2. Updating existing monitors with correct position sizes
3. Creating missing monitors for untracked positions
4. Removing monitors for closed positions
5. Ensuring proper account_type suffixes
"""

import pickle
import logging
import asyncio
from decimal import Decimal
import time
from typing import Dict, List, Set, Optional, Tuple
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import clients and helpers
from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2
from clients.bybit_helpers import get_position_info_for_account, get_open_orders

class PositionMonitorSynchronizer:
    """Synchronizes actual positions with monitor system"""
    
    def __init__(self):
        self.main_client = bybit_client
        self.mirror_client = bybit_client_2
        self.pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        self.positions_found = {
            'main': {},
            'mirror': {}
        }
        self.monitors_updated = 0
        self.monitors_created = 0
        self.monitors_removed = 0
        
    async def run(self):
        """Main synchronization process"""
        logger.info("🔄 Starting comprehensive position-to-monitor synchronization...")
        
        # Step 1: Fetch all positions
        await self.fetch_all_positions()
        
        # Step 2: Load current monitors
        monitors = self.load_monitors()
        
        # Step 3: Update existing monitors
        monitors = await self.update_existing_monitors(monitors)
        
        # Step 4: Create missing monitors
        monitors = await self.create_missing_monitors(monitors)
        
        # Step 5: Remove orphaned monitors
        monitors = self.remove_orphaned_monitors(monitors)
        
        # Step 6: Save updated monitors
        self.save_monitors(monitors)
        
        # Step 7: Display summary
        self.display_summary()
        
    async def fetch_all_positions(self):
        """Fetch all positions from both accounts"""
        logger.info("\n📊 Fetching positions from both accounts...")
        
        # Fetch main account positions
        try:
            response = self.main_client.get_positions(
                category="linear",
                settleCoin="USDT"
            )
            if response['retCode'] == 0:
                for pos in response['result']['list']:
                    if float(pos.get('size', 0)) > 0:
                        key = f"{pos['symbol']}_{pos['side']}"
                        self.positions_found['main'][key] = pos
                        logger.info(f"  Main: {pos['symbol']} {pos['side']} - Size: {pos['size']}")
        except Exception as e:
            logger.error(f"Error fetching main positions: {e}")
        
        # Fetch mirror account positions
        try:
            response = self.mirror_client.get_positions(
                category="linear",
                settleCoin="USDT"
            )
            if response['retCode'] == 0:
                for pos in response['result']['list']:
                    if float(pos.get('size', 0)) > 0:
                        key = f"{pos['symbol']}_{pos['side']}"
                        self.positions_found['mirror'][key] = pos
                        logger.info(f"  Mirror: {pos['symbol']} {pos['side']} - Size: {pos['size']}")
        except Exception as e:
            logger.error(f"Error fetching mirror positions: {e}")
        
        logger.info(f"\n✅ Found {len(self.positions_found['main'])} main positions, {len(self.positions_found['mirror'])} mirror positions")
    
    def load_monitors(self) -> Dict:
        """Load current monitors from pickle file"""
        try:
            with open(self.pickle_file, 'rb') as f:
                data = pickle.load(f)
            
            if 'bot_data' not in data:
                data['bot_data'] = {}
            if 'enhanced_tp_sl_monitors' not in data['bot_data']:
                data['bot_data']['enhanced_tp_sl_monitors'] = {}
            
            monitors = data['bot_data']['enhanced_tp_sl_monitors']
            logger.info(f"\n📂 Loaded {len(monitors)} existing monitors")
            return monitors
            
        except Exception as e:
            logger.error(f"Error loading monitors: {e}")
            return {}
    
    async def update_existing_monitors(self, monitors: Dict) -> Dict:
        """Update existing monitors with correct position sizes and account types"""
        logger.info("\n🔄 Updating existing monitors...")
        
        for monitor_key, monitor_data in monitors.items():
            symbol = monitor_data.get('symbol')
            side = monitor_data.get('side')
            account_type = monitor_data.get('account_type', 'main')
            
            # Determine expected monitor key format
            expected_key = f"{symbol}_{side}_{account_type}"
            
            # Check if monitor key needs updating
            if monitor_key != expected_key:
                logger.warning(f"  ⚠️ Monitor key mismatch: {monitor_key} should be {expected_key}")
            
            # Find corresponding position
            position_key = f"{symbol}_{side}"
            position = self.positions_found.get(account_type, {}).get(position_key)
            
            if position:
                # Update position sizes
                current_size = Decimal(str(position['size']))
                old_size = monitor_data.get('remaining_size', Decimal('0'))
                
                if current_size != old_size:
                    logger.info(f"  📝 Updating {monitor_key}:")
                    logger.info(f"     Position size: {old_size} → {current_size}")
                    monitor_data['position_size'] = current_size
                    monitor_data['remaining_size'] = current_size
                    self.monitors_updated += 1
                
                # Ensure account_type is set
                if 'account_type' not in monitor_data:
                    monitor_data['account_type'] = account_type
                    logger.info(f"     Added account_type: {account_type}")
                
                # Update average price if available
                if 'avgPrice' in position:
                    monitor_data['avg_price'] = Decimal(str(position['avgPrice']))
            else:
                logger.warning(f"  ❌ No position found for monitor {monitor_key}")
        
        return monitors
    
    async def create_missing_monitors(self, monitors: Dict) -> Dict:
        """Create monitors for positions without monitoring"""
        logger.info("\n➕ Creating missing monitors...")
        
        # Check all positions for missing monitors
        for account_type in ['main', 'mirror']:
            for position_key, position in self.positions_found[account_type].items():
                symbol = position['symbol']
                side = position['side']
                monitor_key = f"{symbol}_{side}_{account_type}"
                
                # Check if monitor exists
                monitor_exists = False
                for mk in monitors.keys():
                    if mk.startswith(f"{symbol}_{side}") and account_type in mk:
                        monitor_exists = True
                        break
                
                if not monitor_exists:
                    logger.info(f"  🆕 Creating monitor for {symbol} {side} ({account_type})")
                    
                    # Create new monitor
                    monitor_data = {
                        'symbol': symbol,
                        'side': side,
                        'position_size': Decimal(str(position['size'])),
                        'remaining_size': Decimal(str(position['size'])),
                        'entry_price': Decimal(str(position.get('avgPrice', '0'))),
                        'avg_price': Decimal(str(position.get('avgPrice', '0'))),
                        'approach': 'fast',  # Default to fast, can be updated based on orders
                        'tp_orders': {},
                        'sl_order': None,
                        'filled_tps': [],
                        'cancelled_limits': False,
                        'tp1_hit': False,
                        'tp1_info': None,
                        'sl_moved_to_be': False,
                        'sl_move_attempts': 0,
                        'created_at': time.time(),
                        'last_check': time.time(),
                        'limit_orders': [],
                        'limit_orders_cancelled': False,
                        'phase': 'MONITORING',
                        'chat_id': None,
                        'account_type': account_type
                    }
                    
                    # Check if position has multiple TP orders (conservative approach)
                    try:
                        orders = await self.get_position_orders(symbol, account_type)
                        tp_count = sum(1 for o in orders if o.get('stopOrderType') == 'TakeProfit')
                        if tp_count > 1:
                            monitor_data['approach'] = 'conservative'
                            logger.info(f"     Detected {tp_count} TP orders - using conservative approach")
                    except Exception as e:
                        logger.error(f"     Error checking orders: {e}")
                    
                    monitors[monitor_key] = monitor_data
                    self.monitors_created += 1
        
        return monitors
    
    async def get_position_orders(self, symbol: str, account_type: str) -> List[Dict]:
        """Get orders for a specific position"""
        try:
            client = self.mirror_client if account_type == 'mirror' else self.main_client
            response = client.get_open_orders(
                category="linear",
                symbol=symbol,
                limit=50
            )
            if response['retCode'] == 0:
                return response['result']['list']
        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
        return []
    
    def remove_orphaned_monitors(self, monitors: Dict) -> Dict:
        """Remove monitors for positions that no longer exist"""
        logger.info("\n🗑️ Removing orphaned monitors...")
        
        monitors_to_remove = []
        
        for monitor_key, monitor_data in monitors.items():
            symbol = monitor_data.get('symbol')
            side = monitor_data.get('side')
            account_type = monitor_data.get('account_type', 'main')
            
            # Check if position still exists
            position_key = f"{symbol}_{side}"
            if position_key not in self.positions_found.get(account_type, {}):
                logger.info(f"  🗑️ Removing orphaned monitor: {monitor_key}")
                monitors_to_remove.append(monitor_key)
                self.monitors_removed += 1
        
        # Remove orphaned monitors
        for key in monitors_to_remove:
            del monitors[key]
        
        return monitors
    
    def save_monitors(self, monitors: Dict):
        """Save updated monitors to pickle file"""
        try:
            # Load full pickle data
            with open(self.pickle_file, 'rb') as f:
                data = pickle.load(f)
            
            # Update monitors
            data['bot_data']['enhanced_tp_sl_monitors'] = monitors
            
            # Save back
            with open(self.pickle_file, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"\n✅ Saved {len(monitors)} monitors to persistence")
            
        except Exception as e:
            logger.error(f"Error saving monitors: {e}")
    
    def display_summary(self):
        """Display synchronization summary"""
        logger.info("\n" + "="*60)
        logger.info("📊 SYNCHRONIZATION SUMMARY")
        logger.info("="*60)
        logger.info(f"Positions found:")
        logger.info(f"  Main account: {len(self.positions_found['main'])}")
        logger.info(f"  Mirror account: {len(self.positions_found['mirror'])}")
        logger.info(f"\nMonitor changes:")
        logger.info(f"  Updated: {self.monitors_updated}")
        logger.info(f"  Created: {self.monitors_created}")
        logger.info(f"  Removed: {self.monitors_removed}")
        logger.info("\n✅ Synchronization complete!")
        logger.info("🔄 Restart the bot to activate all monitors")
        logger.info("="*60)

async def main():
    """Main entry point"""
    synchronizer = PositionMonitorSynchronizer()
    await synchronizer.run()

if __name__ == "__main__":
    asyncio.run(main())