#!/usr/bin/env python3
"""
Fix all Enhanced TP/SL monitors - ensure every position has active monitoring
"""
import asyncio
import logging
import pickle
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default chat ID from previous fixes
DEFAULT_CHAT_ID = 5634913742

async def load_pickle_data() -> Dict[str, Any]:
    """Load pickle data"""
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    with open(pkl_path, 'rb') as f:
        return pickle.load(f)

async def save_pickle_data(data: Dict[str, Any]):
    """Save pickle data with backup"""
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    # Create backup
    import shutil
    backup_path = f"{pkl_path}.backup_enhanced_monitors_{int(datetime.now().timestamp())}"
    shutil.copy2(pkl_path, backup_path)
    logger.info(f"Created backup: {backup_path}")
    
    # Save data
    with open(pkl_path, 'wb') as f:
        pickle.dump(data, f)
    logger.info("Saved updated data")

async def get_all_active_positions() -> List[Dict]:
    """Get all active positions from both accounts"""
    from clients.bybit_client import bybit_client
    from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
    
    positions = []
    
    # Get main account positions
    logger.info("Getting main account positions...")
    response = bybit_client.get_positions(category="linear", settleCoin="USDT")
    if response and response.get('retCode') == 0:
        for pos in response.get('result', {}).get('list', []):
            if float(pos.get('size', 0)) > 0:
                pos['account_type'] = 'main'
                positions.append(pos)
    
    # Get mirror account positions
    if is_mirror_trading_enabled() and bybit_client_2:
        logger.info("Getting mirror account positions...")
        response = bybit_client_2.get_positions(category="linear", settleCoin="USDT")
        if response and response.get('retCode') == 0:
            for pos in response.get('result', {}).get('list', []):
                if float(pos.get('size', 0)) > 0:
                    pos['account_type'] = 'mirror'
                    positions.append(pos)
    
    return positions

async def create_enhanced_monitor_entry(position: Dict, chat_id: int) -> Dict:
    """Create Enhanced TP/SL monitor entry for a position"""
    return {
        'symbol': position['symbol'],
        'side': position['side'],
        'position_size': position['size'],
        'remaining_size': position['size'],
        'entry_price': position['avgPrice'],
        'avg_price': position['avgPrice'],
        'approach': 'conservative',  # Default to conservative
        'tp_orders': {},
        'sl_order': None,
        'filled_tps': [],
        'cancelled_limits': False,
        'tp1_hit': False,
        'tp1_info': None,
        'sl_moved_to_be': False,
        'sl_move_attempts': 0,
        'created_at': datetime.now().timestamp(),
        'last_check': datetime.now().timestamp(),
        'limit_orders': [],
        'limit_orders_cancelled': False,
        'phase': 'MONITORING',
        'chat_id': chat_id,
        'account_type': position.get('account_type', 'main'),
        'has_mirror': position.get('account_type') == 'main',  # Main positions can have mirror
        'mirror_synced': True,
        'target_size': position['size'],
        'current_size': position['size']
    }

async def create_dashboard_monitor_entry(position: Dict, chat_id: int, approach: str = 'conservative') -> Dict:
    """Create dashboard monitor task entry"""
    return {
        'symbol': position['symbol'],
        'side': position['side'],
        'approach': approach,
        'monitoring_mode': 'ENHANCED_TP_SL',
        'started_at': datetime.now().timestamp(),
        'active': True,
        'account_type': position.get('account_type', 'main'),
        'system_type': 'enhanced_tp_sl',
        'chat_id': chat_id
    }

async def fix_all_monitors():
    """Fix all Enhanced TP/SL monitors"""
    logger.info("Loading current data...")
    data = await load_pickle_data()
    
    bot_data = data.get('bot_data', {})
    enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
    monitor_tasks = bot_data.get('monitor_tasks', {})
    
    # Get all active positions
    logger.info("Getting all active positions...")
    positions = await get_all_active_positions()
    
    logger.info(f"Found {len(positions)} active positions")
    
    # Track what we're doing
    created_enhanced = []
    updated_enhanced = []
    created_dashboard = []
    
    # Process each position
    for pos in positions:
        symbol = pos['symbol']
        side = pos['side']
        account_type = pos.get('account_type', 'main')
        
        # Enhanced monitor key
        enhanced_key = f"{symbol}_{side}"
        
        # Dashboard monitor keys (we'll check multiple possible formats)
        possible_dashboard_keys = [
            f"{DEFAULT_CHAT_ID}_{symbol}_conservative",
            f"{DEFAULT_CHAT_ID}_{symbol}_CONSERVATIVE",
            f"{DEFAULT_CHAT_ID}_{symbol}_fast",
            f"{DEFAULT_CHAT_ID}_{symbol}_FAST"
        ]
        
        # Check/create Enhanced TP/SL monitor
        if enhanced_key not in enhanced_monitors:
            logger.info(f"Creating Enhanced monitor for {symbol} {side} ({account_type})")
            enhanced_monitors[enhanced_key] = await create_enhanced_monitor_entry(pos, DEFAULT_CHAT_ID)
            created_enhanced.append(f"{symbol} {side} ({account_type})")
        else:
            # Update chat_id if None
            if enhanced_monitors[enhanced_key].get('chat_id') is None:
                enhanced_monitors[enhanced_key]['chat_id'] = DEFAULT_CHAT_ID
                updated_enhanced.append(f"{symbol} {side}")
            # Update account type
            enhanced_monitors[enhanced_key]['account_type'] = account_type
        
        # Check/create dashboard monitor task
        has_dashboard_monitor = any(key in monitor_tasks for key in possible_dashboard_keys)
        
        if not has_dashboard_monitor and account_type == 'main':
            # Only create dashboard monitors for main account
            dashboard_key = f"{DEFAULT_CHAT_ID}_{symbol}_conservative"
            logger.info(f"Creating dashboard monitor for {symbol} {side}")
            monitor_tasks[dashboard_key] = await create_dashboard_monitor_entry(pos, DEFAULT_CHAT_ID)
            created_dashboard.append(f"{symbol} {side}")
    
    # Clean up orphaned monitors
    logger.info("\nChecking for orphaned monitors...")
    
    # Get active position keys
    active_position_keys = {f"{pos['symbol']}_{pos['side']}" for pos in positions}
    active_symbols = {pos['symbol'] for pos in positions}
    
    # Remove orphaned Enhanced monitors
    orphaned_enhanced = []
    for key in list(enhanced_monitors.keys()):
        if key not in active_position_keys:
            orphaned_enhanced.append(key)
            del enhanced_monitors[key]
    
    # Remove orphaned dashboard monitors
    orphaned_dashboard = []
    for key in list(monitor_tasks.keys()):
        # Extract symbol from key
        parts = key.split('_')
        if len(parts) >= 2:
            symbol = parts[1]
            if symbol not in active_symbols:
                orphaned_dashboard.append(key)
                del monitor_tasks[key]
    
    # Save updated data
    logger.info("\nSaving updated data...")
    await save_pickle_data(data)
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    
    logger.info(f"\nActive Positions: {len(positions)}")
    for pos in positions:
        logger.info(f"  - {pos['symbol']} {pos['side']} ({pos.get('account_type', 'main')})")
    
    logger.info(f"\nEnhanced Monitors Created: {len(created_enhanced)}")
    for item in created_enhanced:
        logger.info(f"  - {item}")
    
    logger.info(f"\nEnhanced Monitors Updated (chat_id fixed): {len(updated_enhanced)}")
    for item in updated_enhanced:
        logger.info(f"  - {item}")
    
    logger.info(f"\nDashboard Monitors Created: {len(created_dashboard)}")
    for item in created_dashboard:
        logger.info(f"  - {item}")
    
    logger.info(f"\nOrphaned Enhanced Monitors Removed: {len(orphaned_enhanced)}")
    for item in orphaned_enhanced:
        logger.info(f"  - {item}")
    
    logger.info(f"\nOrphaned Dashboard Monitors Removed: {len(orphaned_dashboard)}")
    for item in orphaned_dashboard:
        logger.info(f"  - {item}")
    
    logger.info(f"\nTotal Enhanced Monitors: {len(enhanced_monitors)}")
    logger.info(f"Total Dashboard Monitors: {len(monitor_tasks)}")
    
    # Expected alerts
    logger.info("\n" + "=" * 60)
    logger.info("EXPECTED ALERTS")
    logger.info("=" * 60)
    logger.info("\nWith all monitors properly configured, you can expect the following alerts:")
    logger.info("\n1. TP Hit Alerts:")
    logger.info("   - When any TP order is filled (TP1, TP2, TP3, or TP4)")
    logger.info("   - Format: '✅ TP1 Hit! {symbol} {side} @ {price}'")
    logger.info("\n2. SL Hit Alerts:")
    logger.info("   - When stop loss is triggered")
    logger.info("   - Format: '🛑 SL Hit! {symbol} {side} @ {price}'")
    logger.info("\n3. Position Closed Alerts:")
    logger.info("   - When position is fully closed")
    logger.info("   - Includes P&L summary")
    logger.info("\n4. Monitor Status Alerts:")
    logger.info("   - When monitors are started/stopped")
    logger.info("   - When errors occur during monitoring")
    logger.info("\n5. Mirror Sync Alerts:")
    logger.info("   - When mirror positions are synced")
    logger.info("   - When mirror orders are placed/cancelled")
    
    logger.info("\nAll alerts will be sent to Telegram chat ID: " + str(DEFAULT_CHAT_ID))

async def main():
    await fix_all_monitors()

if __name__ == "__main__":
    asyncio.run(main())