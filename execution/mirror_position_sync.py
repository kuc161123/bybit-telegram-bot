#!/usr/bin/env python3
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
