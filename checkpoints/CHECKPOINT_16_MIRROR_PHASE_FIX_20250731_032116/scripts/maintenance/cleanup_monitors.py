#!/usr/bin/env python3
"""
Cleanup duplicate monitors for Bybit Telegram Bot
"""
import asyncio
import logging
import pickle
import os
from datetime import datetime
from typing import Dict, List, Set, Optional
from clients.bybit_helpers import get_all_positions, get_all_open_orders
from main import detect_approach_from_orders

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MonitorCleanup:
    def __init__(self):
        self.dashboard_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        self.backup_created = False
        
    def create_backup(self):
        """Create backup of dashboard before modifications"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'backup_{timestamp}_{self.dashboard_file}'
        
        try:
            import shutil
            shutil.copy2(self.dashboard_file, backup_file)
            logger.info(f"✅ Backup created: {backup_file}")
            self.backup_created = True
            return backup_file
        except Exception as e:
            logger.error(f"❌ Failed to create backup: {e}")
            return None
    
    async def cleanup_duplicate_monitors(self):
        """Main cleanup function"""
        logger.info("🧹 Starting Monitor Cleanup")
        logger.info("=" * 60)
        
        # Create backup first
        backup_file = self.create_backup()
        if not backup_file:
            logger.error("Cannot proceed without backup")
            return
        
        try:
            # Load data
            with open(self.dashboard_file, 'rb') as f:
                data = pickle.load(f)
            
            bot_data = data.get('bot_data', {})
            monitor_tasks = bot_data.get('monitor_tasks', {})
            
            logger.info(f"\n📊 Current state: {len(monitor_tasks)} monitors")
            
            # Get active positions
            positions = await get_all_positions()
            position_symbols = {pos.get('symbol') for pos in positions}
            
            logger.info(f"📈 Active positions: {', '.join(position_symbols)}")
            
            # Get orders to detect approaches
            all_orders = await get_all_open_orders()
            orders_by_symbol = {}
            for order in all_orders:
                symbol = order.get('symbol')
                if symbol not in orders_by_symbol:
                    orders_by_symbol[symbol] = []
                orders_by_symbol[symbol].append(order)
            
            # Detect approach for each position
            symbol_approaches = {}
            for symbol in position_symbols:
                if symbol in orders_by_symbol:
                    approach = detect_approach_from_orders(orders_by_symbol[symbol])
                    symbol_approaches[symbol] = approach or 'conservative'  # Default to conservative
                    logger.info(f"   - {symbol}: Detected approach = {symbol_approaches[symbol]}")
            
            # Analyze monitors
            monitors_by_symbol = {}
            for key, info in monitor_tasks.items():
                if isinstance(info, dict):
                    symbol = info.get('symbol')
                    if symbol:
                        if symbol not in monitors_by_symbol:
                            monitors_by_symbol[symbol] = []
                        monitors_by_symbol[symbol].append({
                            'key': key,
                            'info': info
                        })
            
            # Clean up duplicates
            monitors_to_remove = []
            monitors_kept = {}
            
            logger.info("\n🔍 Analyzing monitors:")
            
            for symbol, monitors in monitors_by_symbol.items():
                logger.info(f"\n{symbol}: {len(monitors)} monitors found")
                
                if symbol not in position_symbols:
                    # No active position for this symbol - remove all monitors
                    logger.info(f"   ⚠️  No active position - removing all monitors")
                    for m in monitors:
                        monitors_to_remove.append(m['key'])
                    continue
                
                # Position exists - keep only the correct approach monitor
                expected_approach = symbol_approaches.get(symbol, 'conservative')
                
                # Find monitors matching the expected approach
                matching_monitors = [m for m in monitors if m['info'].get('approach') == expected_approach]
                
                if matching_monitors:
                    # Keep the most recently started active monitor
                    matching_monitors.sort(
                        key=lambda x: (x['info'].get('active', False), x['info'].get('started_at', 0)), 
                        reverse=True
                    )
                    keeper = matching_monitors[0]
                    monitors_kept[symbol] = keeper['key']
                    
                    logger.info(f"   ✅ Keeping monitor: {keeper['key']} ({expected_approach} approach)")
                    
                    # Remove all others
                    for m in monitors:
                        if m['key'] != keeper['key']:
                            monitors_to_remove.append(m['key'])
                            logger.info(f"   🗑️  Removing: {m['key']} ({m['info'].get('approach')} approach)")
                else:
                    # No matching approach monitor - remove all and let bot recreate
                    logger.info(f"   ⚠️  No {expected_approach} approach monitor found - removing all")
                    for m in monitors:
                        monitors_to_remove.append(m['key'])
            
            # Perform cleanup
            if monitors_to_remove:
                logger.info(f"\n🗑️  Removing {len(monitors_to_remove)} duplicate/orphaned monitors...")
                
                for key in monitors_to_remove:
                    if key in monitor_tasks:
                        del monitor_tasks[key]
                        logger.info(f"   - Removed: {key}")
                
                # Save updated data
                with open(self.dashboard_file, 'wb') as f:
                    pickle.dump(data, f)
                
                logger.info(f"\n✅ Cleanup complete!")
                logger.info(f"   Monitors before: {len(monitors_to_remove) + len(monitors_kept)}")
                logger.info(f"   Monitors after: {len(monitors_kept)}")
                logger.info(f"   Removed: {len(monitors_to_remove)}")
            else:
                logger.info("\n✅ No cleanup needed - all monitors are valid")
            
            # Final summary
            logger.info("\n📊 Final Monitor Summary:")
            with open(self.dashboard_file, 'rb') as f:
                data = pickle.load(f)
            
            final_monitors = data.get('bot_data', {}).get('monitor_tasks', {})
            for key, info in final_monitors.items():
                if isinstance(info, dict) and info.get('active'):
                    symbol = info.get('symbol')
                    approach = info.get('approach')
                    chat_id = info.get('chat_id')
                    logger.info(f"   - {symbol} ({approach}) in chat {chat_id}")
            
        except Exception as e:
            logger.error(f"\n❌ Error during cleanup: {e}")
            logger.error(f"Backup available at: {backup_file}")
            raise

async def main():
    cleanup = MonitorCleanup()
    await cleanup.cleanup_duplicate_monitors()

if __name__ == "__main__":
    asyncio.run(main())