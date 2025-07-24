#!/usr/bin/env python3
"""
Sync All Position Monitors - Comprehensive Monitor Creation Tool
Creates monitors for all existing positions on both main and mirror accounts
"""
import asyncio
import logging
import pickle
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional

from clients.bybit_client import bybit_client
from clients.bybit_helpers import api_call_with_retry, get_all_positions, get_open_orders
from config.settings import ENABLE_MIRROR_TRADING
from shared.state import get_application
from utils.robust_persistence import RobustPersistenceManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PositionMonitorSync:
    """Comprehensive position monitor synchronization"""
    
    def __init__(self):
        self.persistence_manager = RobustPersistenceManager()
        self.persistence_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        self.monitors_created = 0
        self.monitors_skipped = 0
        self.positions_found = 0
        
    async def sync_all_monitors(self):
        """Main sync function to create monitors for all positions"""
        logger.info("=" * 60)
        logger.info("🔄 STARTING COMPREHENSIVE MONITOR SYNC")
        logger.info("=" * 60)
        
        try:
            # Get all positions from both accounts
            main_positions = await self._get_positions('main')
            mirror_positions = await self._get_positions('mirror') if ENABLE_MIRROR_TRADING else []
            
            all_positions = main_positions + mirror_positions
            self.positions_found = len(all_positions)
            
            logger.info(f"📊 Found {len(main_positions)} main positions, {len(mirror_positions)} mirror positions")
            logger.info(f"📊 Total positions to process: {self.positions_found}")
            
            if not all_positions:
                logger.warning("⚠️ No positions found to sync")
                return
            
            # Get current monitors
            current_monitors = await self._get_current_monitors()
            logger.info(f"📊 Current active monitors: {len(current_monitors)}")
            
            # Process each position
            for position in all_positions:
                await self._process_position(position, current_monitors)
            
            # Save persistence
            await self._save_persistence()
            
            # Summary
            logger.info("\n" + "=" * 60)
            logger.info("✅ MONITOR SYNC COMPLETE")
            logger.info(f"📊 Positions found: {self.positions_found}")
            logger.info(f"✅ Monitors created: {self.monitors_created}")
            logger.info(f"⏭️ Monitors skipped (already exist): {self.monitors_skipped}")
            logger.info("=" * 60)
            
            # List all active monitors
            await self._list_active_monitors()
            
        except Exception as e:
            logger.error(f"❌ Error during monitor sync: {e}")
            import traceback
            traceback.print_exc()
    
    async def _get_positions(self, account_type: str) -> List[Dict]:
        """Get all positions for an account"""
        try:
            logger.info(f"🔍 Fetching {account_type} account positions...")
            
            if account_type == 'main':
                positions = await get_all_positions()
            else:
                # Get mirror positions
                from clients.bybit_client_mirror import bybit_client_mirror
                positions = await api_call_with_retry(
                    lambda: bybit_client_mirror.get_positions(
                        category="linear",
                        settleCoin="USDT"
                    )
                )
                positions = positions.get('result', {}).get('list', []) if positions else []
            
            # Filter for open positions only
            open_positions = []
            for pos in positions:
                if float(pos.get('size', 0)) > 0:
                    pos['account_type'] = account_type
                    open_positions.append(pos)
                    logger.info(f"  📈 {pos['symbol']} {pos['side']}: {pos['size']} contracts (Avg: ${pos.get('avgPrice', 0)})")
            
            return open_positions
            
        except Exception as e:
            logger.error(f"❌ Error fetching {account_type} positions: {e}")
            return []
    
    async def _get_current_monitors(self) -> Dict[str, Any]:
        """Get all current monitors from persistence"""
        try:
            with open(self.persistence_file, 'rb') as f:
                data = pickle.load(f)
            
            bot_data = data.get('bot_data', {})
            enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
            dashboard_monitors = bot_data.get('monitor_tasks', {})
            
            all_monitors = {}
            all_monitors.update(enhanced_monitors)
            all_monitors.update(dashboard_monitors)
            
            return all_monitors
            
        except Exception as e:
            logger.error(f"❌ Error loading monitors: {e}")
            return {}
    
    async def _process_position(self, position: Dict, current_monitors: Dict):
        """Process a single position and create monitors if needed"""
        try:
            symbol = position['symbol']
            side = position['side']
            account_type = position.get('account_type', 'main')
            
            # Generate monitor keys
            enhanced_key = f"{symbol}_{side}"
            if account_type == 'mirror':
                enhanced_key += "_MIRROR"
            
            logger.info(f"\n🔍 Processing {account_type} position: {symbol} {side}")
            
            # Check if Enhanced TP/SL monitor exists
            if enhanced_key in current_monitors:
                logger.info(f"  ✅ Enhanced monitor already exists: {enhanced_key}")
                self.monitors_skipped += 1
            else:
                # Create Enhanced TP/SL monitor
                await self._create_enhanced_monitor(position, enhanced_key)
                self.monitors_created += 1
            
            # Get orders for this position
            orders = await self._get_position_orders(position)
            logger.info(f"  📋 Found {len(orders)} orders for this position")
            
        except Exception as e:
            logger.error(f"❌ Error processing position {position.get('symbol')} {position.get('side')}: {e}")
    
    async def _create_enhanced_monitor(self, position: Dict, monitor_key: str):
        """Create Enhanced TP/SL monitor for a position"""
        try:
            logger.info(f"  🆕 Creating Enhanced TP/SL monitor: {monitor_key}")
            
            # Load current data
            with open(self.persistence_file, 'rb') as f:
                data = pickle.load(f)
            
            bot_data = data.setdefault('bot_data', {})
            enhanced_monitors = bot_data.setdefault('enhanced_tp_sl_monitors', {})
            
            # Create monitor data
            monitor_data = {
                'symbol': position['symbol'],
                'side': position['side'],
                'position_size': Decimal(str(position['size'])),
                'remaining_size': Decimal(str(position['size'])),
                'avg_price': Decimal(str(position.get('avgPrice', 0))),
                'account_type': position.get('account_type', 'main'),
                'created_at': datetime.now(),
                'last_check': datetime.now(),
                'tp_orders': {},
                'sl_order': None,
                'status': 'active',
                'approach': 'unknown',  # Will be determined by order structure
                'chat_id': None,  # No chat context for existing positions
                'monitoring': True
            }
            
            # Add to monitors
            enhanced_monitors[monitor_key] = monitor_data
            
            # Also create dashboard monitor entry for UI visibility
            await self._create_dashboard_monitor(position, monitor_data)
            
            # Save immediately
            with open(self.persistence_file, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"  ✅ Enhanced monitor created: {monitor_key}")
            
        except Exception as e:
            logger.error(f"❌ Error creating enhanced monitor: {e}")
    
    async def _create_dashboard_monitor(self, position: Dict, monitor_data: Dict):
        """Create dashboard monitor entry for UI visibility"""
        try:
            # Load current data
            with open(self.persistence_file, 'rb') as f:
                data = pickle.load(f)
            
            bot_data = data.setdefault('bot_data', {})
            monitor_tasks = bot_data.setdefault('monitor_tasks', {})
            
            # Create dashboard monitor key (simplified without chat_id)
            account_suffix = '_mirror' if position.get('account_type') == 'mirror' else ''
            dashboard_key = f"sync_{position['symbol']}_{monitor_data['approach']}{account_suffix}"
            
            # Create dashboard monitor
            dashboard_monitor = {
                'symbol': position['symbol'],
                'side': position['side'],
                'approach': monitor_data['approach'],
                'account_type': position.get('account_type', 'main'),
                'active': True,
                'created_at': datetime.now(),
                'chat_id': None
            }
            
            monitor_tasks[dashboard_key] = dashboard_monitor
            
            # Save
            with open(self.persistence_file, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"  ✅ Dashboard monitor created: {dashboard_key}")
            
        except Exception as e:
            logger.error(f"❌ Error creating dashboard monitor: {e}")
    
    async def _get_position_orders(self, position: Dict) -> List[Dict]:
        """Get all orders for a position"""
        try:
            symbol = position['symbol']
            account_type = position.get('account_type', 'main')
            
            if account_type == 'main':
                orders = await get_open_orders(symbol)
            else:
                from clients.bybit_client_mirror import bybit_client_mirror
                response = await api_call_with_retry(
                    lambda: bybit_client_mirror.get_open_orders(
                        category="linear",
                        symbol=symbol
                    )
                )
                orders = response.get('result', {}).get('list', []) if response else []
            
            # Filter for this position's side
            position_orders = []
            for order in orders:
                # TP orders are opposite side, SL orders are same side
                if order['orderType'] in ['TakeProfit', 'StopLoss']:
                    position_orders.append(order)
            
            return position_orders
            
        except Exception as e:
            logger.error(f"❌ Error getting orders: {e}")
            return []
    
    async def _save_persistence(self):
        """Save persistence with backup"""
        try:
            # The RobustPersistenceManager handles saving
            await self.persistence_manager.save_monitors({})
            logger.info("💾 Persistence saved successfully")
            
        except Exception as e:
            logger.error(f"❌ Error saving persistence: {e}")
    
    async def _list_active_monitors(self):
        """List all active monitors after sync"""
        try:
            logger.info("\n📊 ACTIVE MONITORS SUMMARY:")
            logger.info("=" * 60)
            
            # Load current monitors
            with open(self.persistence_file, 'rb') as f:
                data = pickle.load(f)
            
            bot_data = data.get('bot_data', {})
            enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
            
            if not enhanced_monitors:
                logger.info("⚠️ No active monitors found")
                return
            
            # Group by account
            main_monitors = []
            mirror_monitors = []
            
            for key, monitor in enhanced_monitors.items():
                if key.endswith('_MIRROR'):
                    mirror_monitors.append((key, monitor))
                else:
                    main_monitors.append((key, monitor))
            
            # Display main account monitors
            if main_monitors:
                logger.info(f"\n📍 MAIN ACCOUNT MONITORS ({len(main_monitors)}):")
                for key, monitor in main_monitors:
                    logger.info(f"  • {key}: {monitor['remaining_size']}/{monitor['position_size']} @ ${monitor['avg_price']}")
            
            # Display mirror account monitors
            if mirror_monitors:
                logger.info(f"\n🪞 MIRROR ACCOUNT MONITORS ({len(mirror_monitors)}):")
                for key, monitor in mirror_monitors:
                    logger.info(f"  • {key}: {monitor['remaining_size']}/{monitor['position_size']} @ ${monitor['avg_price']}")
            
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Error listing monitors: {e}")

async def main():
    """Main entry point"""
    sync = PositionMonitorSync()
    await sync.sync_all_monitors()

if __name__ == "__main__":
    asyncio.run(main())