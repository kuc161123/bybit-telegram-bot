#!/usr/bin/env python3
"""
Create a separate position sync for mirror account
Independent from main account sync
"""
import os
import asyncio
import logging
from datetime import datetime
from typing import List, Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_mirror_sync_file():
    """Create the mirror position sync module"""
    
    mirror_sync_code = '''#!/usr/bin/env python3
"""
Mirror Account Position Sync
Separate and independent from main account sync
"""
import asyncio
import logging
import time
from typing import Dict, List
from decimal import Decimal

logger = logging.getLogger(__name__)

class MirrorPositionSync:
    """Handles position synchronization for mirror account only"""
    
    def __init__(self, enhanced_tp_sl_manager):
        self.manager = enhanced_tp_sl_manager
        self.last_sync = 0
        self.sync_interval = 60  # Sync every 60 seconds
        
    async def sync_mirror_positions(self):
        """Sync mirror account positions with monitors"""
        try:
            logger.info("🔄 Starting position sync for MIRROR account")
            
            # Get mirror trading client
            from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
            
            if not is_mirror_trading_enabled():
                logger.info("ℹ️ Mirror trading not enabled, skipping mirror sync")
                return
            
            # Fetch mirror positions
            mirror_positions = await self._fetch_mirror_positions()
            logger.info(f"📊 MIRROR: Total positions fetched: {len(mirror_positions)}")
            
            # Get current mirror monitors
            mirror_monitors = {k: v for k, v in self.manager.position_monitors.items() 
                             if k.endswith('_mirror')}
            
            created = 0
            skipped = 0
            
            # Check each mirror position
            for position in mirror_positions:
                symbol = position.get("symbol", "")
                side = position.get("side", "")
                monitor_key = f"{symbol}_{side}_mirror"
                
                if monitor_key in mirror_monitors:
                    skipped += 1
                    logger.debug(f"✓ MIRROR: Monitor exists for {symbol} {side}")
                else:
                    # Create monitor for missing position
                    await self._create_mirror_monitor(position)
                    created += 1
                    logger.info(f"✅ MIRROR: Created monitor for {symbol} {side}")
            
            logger.info(f"🔄 MIRROR sync complete: {created} created, {skipped} skipped")
            
            # Clean orphaned mirror monitors
            await self._clean_orphaned_mirror_monitors(mirror_positions, mirror_monitors)
            
        except Exception as e:
            logger.error(f"❌ Error in mirror position sync: {e}")
    
    async def _fetch_mirror_positions(self) -> List[Dict]:
        """Fetch positions from mirror account"""
        from execution.mirror_trader import bybit_client_2
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: bybit_client_2.get_positions(
                    category="linear",
                    settleCoin="USDT"
                )
            )
            
            if response and response.get("retCode") == 0:
                positions = response.get("result", {}).get("list", [])
                # Filter active positions
                return [p for p in positions if float(p.get("size", 0)) > 0]
            
            return []
            
        except Exception as e:
            logger.error(f"Error fetching mirror positions: {e}")
            return []
    
    async def _create_mirror_monitor(self, position: Dict):
        """Create monitor for mirror position"""
        symbol = position.get("symbol", "")
        side = position.get("side", "")
        size = Decimal(position.get("size", "0"))
        avg_price = Decimal(position.get("avgPrice", "0"))
        
        monitor_key = f"{symbol}_{side}_mirror"
        
        monitor_data = {
            'symbol': symbol,
            'side': side,
            'position_size': size,
            'remaining_size': size,
            'entry_price': avg_price,
            'avg_price': avg_price,
            'approach': 'conservative',  # Mirror uses conservative
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
            'account_type': 'mirror'
        }
        
        self.manager.position_monitors[monitor_key] = monitor_data
        logger.info(f"✅ Created mirror monitor: {monitor_key}")
    
    async def _clean_orphaned_mirror_monitors(self, positions: List[Dict], monitors: Dict):
        """Remove mirror monitors without positions"""
        position_keys = set()
        for pos in positions:
            symbol = pos.get("symbol", "")
            side = pos.get("side", "")
            position_keys.add(f"{symbol}_{side}_mirror")
        
        removed = 0
        for monitor_key in list(monitors.keys()):
            if monitor_key not in position_keys:
                del self.manager.position_monitors[monitor_key]
                removed += 1
                logger.info(f"🧹 Removed orphaned mirror monitor: {monitor_key}")
        
        if removed > 0:
            logger.info(f"🧹 MIRROR: Cleaned {removed} orphaned monitors")

# Create global instance
mirror_position_sync = None

async def start_mirror_position_sync(enhanced_tp_sl_manager):
    """Start the mirror position sync task"""
    global mirror_position_sync
    
    mirror_position_sync = MirrorPositionSync(enhanced_tp_sl_manager)
    
    logger.info("🎯 Starting independent MIRROR position sync")
    
    while True:
        try:
            await mirror_position_sync.sync_mirror_positions()
            await asyncio.sleep(60)  # Sync every minute
        except Exception as e:
            logger.error(f"Error in mirror sync loop: {e}")
            await asyncio.sleep(60)

# Export
__all__ = ['MirrorPositionSync', 'start_mirror_position_sync', 'mirror_position_sync']
'''
    
    # Write the file
    with open('execution/mirror_position_sync.py', 'w') as f:
        f.write(mirror_sync_code)
    
    print("✅ Created execution/mirror_position_sync.py")

def create_integration_patch():
    """Create a patch to integrate mirror sync into the bot"""
    
    patch_code = '''#!/usr/bin/env python3
"""
Patch to integrate mirror position sync into the bot
"""
import logging
import asyncio

logger = logging.getLogger(__name__)

def integrate_mirror_sync():
    """Integrate mirror position sync into background tasks"""
    
    # Add this to your background tasks startup
    code_snippet = """
# In helpers/background_tasks.py or main.py, add:

# Import mirror sync
from execution.mirror_position_sync import start_mirror_position_sync

# In the background tasks section, add:
async def start_enhanced_background_tasks(application):
    # ... existing tasks ...
    
    # Start mirror position sync (independent from main sync)
    if ENABLE_MIRROR_TRADING:
        logger.info("🪞 Starting independent mirror position sync...")
        mirror_sync_task = asyncio.create_task(
            start_mirror_position_sync(enhanced_tp_sl_manager)
        )
        background_tasks.append(mirror_sync_task)
        logger.info("✅ Mirror position sync task started")
"""
    
    print("Integration code:")
    print(code_snippet)

# Run the integration
integrate_mirror_sync()
'''
    
    with open('integrate_mirror_sync.py', 'w') as f:
        f.write(patch_code)
    
    print("✅ Created integrate_mirror_sync.py")

def create_immediate_sync():
    """Create a script to immediately sync mirror positions"""
    
    immediate_sync = '''#!/usr/bin/env python3
"""
Immediately sync mirror positions without restarting bot
"""
import asyncio
import pickle
import time
from datetime import datetime
from decimal import Decimal

async def immediate_mirror_sync():
    """Run immediate mirror position sync"""
    print("="*60)
    print("IMMEDIATE MIRROR POSITION SYNC")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # First, add mirror monitors to pickle
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    # Mirror positions from exchange
    mirror_positions = {
        'COTIUSDT': {'side': 'Buy', 'size': '124', 'avgPrice': '0.05125'},
        'CAKEUSDT': {'side': 'Buy', 'size': '27.5', 'avgPrice': '2.29'},
        'SNXUSDT': {'side': 'Buy', 'size': '112', 'avgPrice': '0.57089098'},
        '1INCHUSDT': {'side': 'Buy', 'size': '328.7', 'avgPrice': '0.2012'},
        'SUSHIUSDT': {'side': 'Buy', 'size': '107.7', 'avgPrice': '0.6166'}
    }
    
    added = 0
    for symbol, pos_data in mirror_positions.items():
        monitor_key = f"{symbol}_{pos_data['side']}_mirror"
        
        if monitor_key not in monitors:
            monitors[monitor_key] = {
                'symbol': symbol,
                'side': pos_data['side'],
                'position_size': Decimal(pos_data['size']),
                'remaining_size': Decimal(pos_data['size']),
                'entry_price': Decimal(pos_data['avgPrice']),
                'avg_price': Decimal(pos_data['avgPrice']),
                'approach': 'conservative',
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
                'account_type': 'mirror'
            }
            added += 1
            print(f"✅ Added {monitor_key}")
    
    # Save back
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    print(f"\\n✅ Added {added} mirror monitors")
    print(f"✅ Total monitors: {len(monitors)}")
    
    # Create sync signal
    with open('mirror_sync_complete.signal', 'w') as f:
        f.write(f"SYNC_TIME={int(time.time())}\\n")
        f.write(f"MIRROR_MONITORS={added}\\n")
        f.write(f"TOTAL_MONITORS={len(monitors)}\\n")
    
    print("\\n✅ Mirror sync complete!")

if __name__ == "__main__":
    asyncio.run(immediate_mirror_sync())
'''
    
    with open('immediate_mirror_sync.py', 'w') as f:
        f.write(immediate_sync)
    
    print("✅ Created immediate_mirror_sync.py")

def main():
    """Main execution"""
    print("="*60)
    print("CREATING INDEPENDENT MIRROR POSITION SYNC")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Create the mirror sync module
    create_mirror_sync_file()
    
    # Create integration instructions
    create_integration_patch()
    
    # Create immediate sync script
    create_immediate_sync()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print("✅ Created independent mirror position sync module")
    print("✅ Mirror sync will run separately from main sync")
    print("\nBenefits:")
    print("- Main account sync: Monitors main positions only")
    print("- Mirror account sync: Monitors mirror positions only")
    print("- No interference between accounts")
    print("- Clear separation in logs")
    print("\nTo use immediately:")
    print("1. Run: python3 immediate_mirror_sync.py")
    print("2. This will add mirror monitors without restart")
    print("\nFor permanent fix:")
    print("- Add mirror sync to background tasks")
    print("- It will run independently every 60 seconds")

if __name__ == "__main__":
    main()