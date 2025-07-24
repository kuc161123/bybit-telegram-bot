#!/usr/bin/env python3
"""
Fix mirror Enhanced TP/SL monitoring by ensuring monitors are created for mirror positions
"""
import asyncio
import logging
import pickle
import time
from decimal import Decimal
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import required modules
from execution.mirror_trader import (
    is_mirror_trading_enabled, get_mirror_positions, bybit_client_2
)
from clients.bybit_helpers import get_all_positions, get_all_open_orders
from config.constants import BOT_PREFIX

async def check_all_positions_and_monitors():
    """Check all positions and their monitor status"""
    logger.info("=" * 50)
    logger.info("Checking all positions and monitors...")
    
    # Load pickle data
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    try:
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        logger.error(f"❌ Error loading pickle file: {e}")
        return None, None, None
    
    # Get monitors
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    dashboard_monitors = data.get('bot_data', {}).get('monitor_tasks', {})
    
    # Get positions from both accounts
    main_positions = await get_all_positions()
    active_main = [p for p in main_positions if float(p.get('size', 0)) > 0]
    
    mirror_positions = []
    active_mirror = []
    if is_mirror_trading_enabled():
        mirror_positions = await get_mirror_positions()
        active_mirror = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
    
    logger.info(f"\nActive positions:")
    logger.info(f"  Main account: {len(active_main)}")
    logger.info(f"  Mirror account: {len(active_mirror)}")
    
    logger.info(f"\nMonitors found:")
    logger.info(f"  Enhanced TP/SL: {len(enhanced_monitors)}")
    logger.info(f"  Dashboard: {len(dashboard_monitors)}")
    
    # Check each position
    logger.info("\n" + "-" * 50)
    logger.info("Main Account Positions:")
    for pos in active_main:
        symbol = pos['symbol']
        side = pos['side']
        size = pos['size']
        monitor_key = f"{symbol}_{side}"
        
        has_enhanced = monitor_key in enhanced_monitors
        dashboard_keys = [k for k in dashboard_monitors if symbol in k and not k.endswith('_MIRROR')]
        
        logger.info(f"\n{symbol} {side} (size: {size}):")
        logger.info(f"  Enhanced TP/SL monitor: {'✅' if has_enhanced else '❌'}")
        logger.info(f"  Dashboard monitors: {len(dashboard_keys)}")
        if dashboard_keys:
            for dk in dashboard_keys:
                logger.info(f"    - {dk}")
    
    if active_mirror:
        logger.info("\n" + "-" * 50)
        logger.info("Mirror Account Positions:")
        for pos in active_mirror:
            symbol = pos['symbol']
            side = pos['side']
            size = pos['size']
            monitor_key = f"{symbol}_{side}"
            
            # Check if main monitor has mirror flag
            has_enhanced = monitor_key in enhanced_monitors
            has_mirror_flag = enhanced_monitors.get(monitor_key, {}).get('has_mirror', False)
            
            # Check for dashboard monitors with _MIRROR suffix
            mirror_dashboard_keys = [k for k in dashboard_monitors if symbol in k and k.endswith('_MIRROR')]
            
            logger.info(f"\n{symbol} {side} (size: {size}):")
            logger.info(f"  Enhanced TP/SL monitor: {'✅' if has_enhanced else '❌'}")
            logger.info(f"  Mirror flag in monitor: {'✅' if has_mirror_flag else '❌'}")
            logger.info(f"  Dashboard monitors: {len(mirror_dashboard_keys)}")
            if mirror_dashboard_keys:
                for dk in mirror_dashboard_keys:
                    logger.info(f"    - {dk}")
    
    return data, active_main, active_mirror

async def check_orders_for_positions(active_main: List[Dict], active_mirror: List[Dict]):
    """Check orders for all positions"""
    logger.info("\n" + "=" * 50)
    logger.info("Checking orders for all positions...")
    
    # Main account orders
    all_main_orders = await get_all_open_orders()
    
    # Mirror account orders
    all_mirror_orders = []
    if is_mirror_trading_enabled() and bybit_client_2:
        try:
            response = bybit_client_2.get_open_orders(category="linear")
            if response and response.get('retCode') == 0:
                all_mirror_orders = response.get('result', {}).get('list', [])
        except Exception as e:
            logger.error(f"Error getting mirror orders: {e}")
    
    # Analyze orders by position
    logger.info("\nMain Account Orders:")
    for pos in active_main:
        symbol = pos['symbol']
        side = pos['side']
        
        pos_orders = [o for o in all_main_orders if o['symbol'] == symbol]
        tp_orders = [o for o in pos_orders if o.get('reduceOnly') and 'TP' in o.get('orderLinkId', '')]
        sl_orders = [o for o in pos_orders if o.get('reduceOnly') and 'SL' in o.get('orderLinkId', '')]
        
        logger.info(f"\n{symbol} {side}:")
        logger.info(f"  TP orders: {len(tp_orders)}")
        logger.info(f"  SL orders: {len(sl_orders)}")
    
    logger.info("\nMirror Account Orders:")
    missing_orders = []
    for pos in active_mirror:
        symbol = pos['symbol']
        side = pos['side']
        
        pos_orders = [o for o in all_mirror_orders if o['symbol'] == symbol]
        tp_orders = [o for o in pos_orders if o.get('reduceOnly') and 'TP' in o.get('orderLinkId', '')]
        sl_orders = [o for o in pos_orders if o.get('reduceOnly') and 'SL' in o.get('orderLinkId', '')]
        
        logger.info(f"\n{symbol} {side}:")
        logger.info(f"  TP orders: {len(tp_orders)}")
        logger.info(f"  SL orders: {len(sl_orders)}")
        
        if len(tp_orders) == 0 or len(sl_orders) == 0:
            missing_orders.append({
                'symbol': symbol,
                'side': side,
                'missing_tp': len(tp_orders) == 0,
                'missing_sl': len(sl_orders) == 0
            })
    
    return missing_orders

async def fix_missing_monitors(data: Dict, active_mirror: List[Dict]):
    """Fix missing monitors for mirror positions"""
    logger.info("\n" + "=" * 50)
    logger.info("Fixing missing monitors...")
    
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    dashboard_monitors = data.get('bot_data', {}).get('monitor_tasks', {})
    
    fixes_made = 0
    
    for pos in active_mirror:
        symbol = pos['symbol']
        side = pos['side']
        monitor_key = f"{symbol}_{side}"
        
        # Check if Enhanced TP/SL monitor exists
        if monitor_key not in enhanced_monitors:
            logger.warning(f"❌ Missing Enhanced TP/SL monitor for {symbol} {side}")
            continue
        
        # Check if mirror flag is set
        monitor_data = enhanced_monitors[monitor_key]
        if not monitor_data.get('has_mirror'):
            logger.info(f"🔧 Enabling mirror flag for {symbol} {side}")
            monitor_data['has_mirror'] = True
            monitor_data['mirror_synced'] = True
            fixes_made += 1
        
        # Check for dashboard monitor with _MIRROR suffix
        mirror_dashboard_key = None
        for key in dashboard_monitors:
            if symbol in key and side in key and key.endswith('_MIRROR'):
                mirror_dashboard_key = key
                break
        
        if not mirror_dashboard_key:
            logger.info(f"🔧 Creating dashboard monitor for {symbol} {side} mirror")
            
            # Find a chat_id from existing monitors
            chat_id = None
            for key, monitor in dashboard_monitors.items():
                if isinstance(monitor, dict) and 'chat_id' in monitor:
                    chat_id = monitor['chat_id']
                    break
            
            if chat_id:
                # Create mirror dashboard monitor
                mirror_key = f"{chat_id}_{symbol}_enhanced_{side}_MIRROR"
                dashboard_monitors[mirror_key] = {
                    'symbol': symbol,
                    'approach': 'enhanced',
                    'side': side,
                    'account_type': 'mirror',
                    'chat_id': chat_id,
                    'active': True,
                    'started_at': time.time(),
                    'task': None  # Will be set by monitoring system
                }
                logger.info(f"✅ Created dashboard monitor: {mirror_key}")
                fixes_made += 1
    
    if fixes_made > 0:
        # Save updated pickle
        pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        try:
            with open(pickle_file, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"\n✅ Saved {fixes_made} fixes to pickle file")
        except Exception as e:
            logger.error(f"❌ Error saving pickle file: {e}")
    else:
        logger.info("\n✅ No fixes needed - all monitors are properly configured")

async def trigger_position_sync():
    """Trigger Enhanced TP/SL position sync"""
    logger.info("\n" + "=" * 50)
    logger.info("Triggering Enhanced TP/SL position sync...")
    
    try:
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        await enhanced_tp_sl_manager.sync_existing_positions()
        logger.info("✅ Position sync completed")
    except Exception as e:
        logger.error(f"❌ Error syncing positions: {e}")

async def main():
    """Main function"""
    logger.info("Mirror Enhanced TP/SL Monitoring Fix")
    logger.info("=" * 50)
    
    # Step 1: Check all positions and monitors
    data, active_main, active_mirror = await check_all_positions_and_monitors()
    if not data:
        return
    
    # Step 2: Check orders
    missing_orders = await check_orders_for_positions(active_main, active_mirror)
    
    if missing_orders:
        logger.warning(f"\n⚠️ Found {len(missing_orders)} positions with missing orders:")
        for mo in missing_orders:
            logger.warning(f"  - {mo['symbol']} {mo['side']}: "
                          f"{'Missing TP' if mo['missing_tp'] else ''} "
                          f"{'Missing SL' if mo['missing_sl'] else ''}")
    
    # Step 3: Fix missing monitors
    await fix_missing_monitors(data, active_mirror)
    
    # Step 4: Trigger position sync
    await trigger_position_sync()
    
    logger.info("\n" + "=" * 50)
    logger.info("✅ Mirror monitoring fix completed!")
    
    if missing_orders:
        logger.info("\n⚠️ Note: Some positions are still missing orders.")
        logger.info("Run fix_jupusdt_mirror_tp_sl.py for specific positions")

if __name__ == "__main__":
    asyncio.run(main())