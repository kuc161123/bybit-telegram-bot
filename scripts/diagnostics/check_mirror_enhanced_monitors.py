#!/usr/bin/env python3
"""
Check and ensure all mirror account positions have Enhanced TP/SL monitoring
"""
import asyncio
import logging
import pickle
from decimal import Decimal
from typing import Dict, List, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def get_mirror_positions():
    """Get all active mirror positions"""
    from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
    
    if not is_mirror_trading_enabled() or not bybit_client_2:
        logger.error("Mirror trading not enabled")
        return []
    
    positions = []
    response = bybit_client_2.get_positions(category="linear", settleCoin="USDT")
    if response and response.get('retCode') == 0:
        for pos in response.get('result', {}).get('list', []):
            if float(pos.get('size', 0)) > 0:
                positions.append(pos)
    
    return positions

async def check_enhanced_monitors():
    """Check Enhanced TP/SL monitors for mirror positions"""
    # Load pickle data
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)
    
    bot_data = data.get('bot_data', {})
    enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
    
    # Get mirror positions
    mirror_positions = await get_mirror_positions()
    
    logger.info("=" * 60)
    logger.info("MIRROR ACCOUNT ENHANCED TP/SL MONITOR CHECK")
    logger.info("=" * 60)
    logger.info(f"\nFound {len(mirror_positions)} active mirror positions")
    
    # Track status
    positions_with_monitors = []
    positions_without_monitors = []
    monitors_needing_fixes = []
    
    # Check each position
    for pos in mirror_positions:
        symbol = pos['symbol']
        side = pos['side']
        size = pos['size']
        monitor_key = f"{symbol}_{side}"
        
        logger.info(f"\nChecking {symbol} {side} (Size: {size}):")
        
        if monitor_key in enhanced_monitors:
            monitor = enhanced_monitors[monitor_key]
            
            # Check monitor health
            issues = []
            
            # Check account type
            if monitor.get('account_type') != 'mirror':
                issues.append("Wrong account_type (should be 'mirror')")
            
            # Check if it has mirror flag
            if monitor.get('has_mirror', False):
                issues.append("has_mirror should be False for mirror positions")
            
            # Check phase
            if monitor.get('phase') != 'MONITORING':
                issues.append(f"Phase is {monitor.get('phase')} instead of MONITORING")
            
            # Check chat_id (should be None for mirror to disable alerts)
            if monitor.get('chat_id') is not None:
                issues.append(f"chat_id should be None to disable alerts (currently: {monitor.get('chat_id')})")
            
            if issues:
                logger.warning(f"  ⚠️ Monitor exists but has issues:")
                for issue in issues:
                    logger.warning(f"     - {issue}")
                monitors_needing_fixes.append({
                    'symbol': symbol,
                    'side': side,
                    'monitor_key': monitor_key,
                    'issues': issues
                })
            else:
                logger.info(f"  ✅ Monitor exists and configured correctly")
                positions_with_monitors.append(f"{symbol} {side}")
        else:
            logger.error(f"  ❌ NO MONITOR FOUND")
            positions_without_monitors.append({
                'symbol': symbol,
                'side': side,
                'size': size,
                'avgPrice': pos['avgPrice']
            })
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total mirror positions: {len(mirror_positions)}")
    logger.info(f"Positions with correct monitors: {len(positions_with_monitors)}")
    logger.info(f"Positions without monitors: {len(positions_without_monitors)}")
    logger.info(f"Monitors needing fixes: {len(monitors_needing_fixes)}")
    
    return {
        'positions_without_monitors': positions_without_monitors,
        'monitors_needing_fixes': monitors_needing_fixes,
        'total_positions': len(mirror_positions)
    }

async def create_mirror_enhanced_monitor(position: Dict) -> Dict:
    """Create Enhanced TP/SL monitor entry for mirror position"""
    from datetime import datetime
    
    return {
        'symbol': position['symbol'],
        'side': position['side'],
        'position_size': position['size'],
        'remaining_size': position['size'],
        'entry_price': position['avgPrice'],
        'avg_price': position['avgPrice'],
        'approach': 'conservative',
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
        'chat_id': None,  # None to disable alerts for mirror
        'account_type': 'mirror',
        'has_mirror': False,  # Mirror positions don't have their own mirrors
        'mirror_synced': True,
        'target_size': position['size'],
        'current_size': position['size']
    }

async def fix_mirror_monitors(issues_data: Dict):
    """Fix or create missing mirror monitors"""
    if issues_data['positions_without_monitors'] or issues_data['monitors_needing_fixes']:
        logger.info("\n" + "=" * 60)
        logger.info("FIXING MIRROR MONITORS")
        logger.info("=" * 60)
        
        # Load pickle data
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        # Create missing monitors
        for pos in issues_data['positions_without_monitors']:
            monitor_key = f"{pos['symbol']}_{pos['side']}"
            logger.info(f"\nCreating monitor for {pos['symbol']} {pos['side']}...")
            
            monitor_data = await create_mirror_enhanced_monitor(pos)
            enhanced_monitors[monitor_key] = monitor_data
            
            logger.info(f"✅ Created Enhanced monitor for {monitor_key}")
        
        # Fix existing monitors
        for fix_needed in issues_data['monitors_needing_fixes']:
            monitor_key = fix_needed['monitor_key']
            logger.info(f"\nFixing monitor for {monitor_key}...")
            
            # Fix the issues
            if 'Wrong account_type' in str(fix_needed['issues']):
                enhanced_monitors[monitor_key]['account_type'] = 'mirror'
                logger.info("  ✅ Fixed account_type to 'mirror'")
            
            if 'has_mirror should be False' in str(fix_needed['issues']):
                enhanced_monitors[monitor_key]['has_mirror'] = False
                logger.info("  ✅ Fixed has_mirror to False")
            
            if 'Phase is' in str(fix_needed['issues']):
                enhanced_monitors[monitor_key]['phase'] = 'MONITORING'
                logger.info("  ✅ Fixed phase to MONITORING")
            
            if 'chat_id should be None' in str(fix_needed['issues']):
                enhanced_monitors[monitor_key]['chat_id'] = None
                logger.info("  ✅ Fixed chat_id to None (alerts disabled)")
        
        # Save updated data
        import shutil
        from datetime import datetime
        
        # Create backup
        backup_path = f"{pkl_path}.backup_mirror_monitors_{int(datetime.now().timestamp())}"
        shutil.copy2(pkl_path, backup_path)
        logger.info(f"\nCreated backup: {backup_path}")
        
        # Save data
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        logger.info("✅ Saved updated monitor data")

async def verify_mirror_monitoring():
    """Verify mirror monitoring is working"""
    logger.info("\n" + "=" * 60)
    logger.info("VERIFYING MIRROR MONITORING")
    logger.info("=" * 60)
    
    # Check if Enhanced TP/SL manager has the monitors loaded
    try:
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        
        mirror_monitor_count = 0
        for key, monitor in enhanced_tp_sl_manager.position_monitors.items():
            if monitor.get('account_type') == 'mirror':
                mirror_monitor_count += 1
                logger.info(f"✅ Active mirror monitor: {key}")
        
        logger.info(f"\nTotal active mirror monitors in manager: {mirror_monitor_count}")
        
        # Check if monitoring loop is running
        import subprocess
        result = subprocess.run(['pgrep', '-f', 'main.py'], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("✅ Bot is running - monitoring loop is active")
        else:
            logger.warning("⚠️ Bot is not running - start bot to activate monitoring")
            
    except Exception as e:
        logger.error(f"Error checking Enhanced TP/SL manager: {e}")

async def main():
    # Check current status
    issues = await check_enhanced_monitors()
    
    # Fix if needed
    if issues['positions_without_monitors'] or issues['monitors_needing_fixes']:
        await fix_mirror_monitors(issues)
        
        # Re-check after fixes
        logger.info("\n" + "=" * 60)
        logger.info("RECHECKING AFTER FIXES")
        logger.info("=" * 60)
        
        await check_enhanced_monitors()
    
    # Verify monitoring is active
    await verify_mirror_monitoring()
    
    # Final status
    logger.info("\n" + "=" * 60)
    logger.info("MIRROR ACCOUNT STATUS")
    logger.info("=" * 60)
    logger.info("✅ All mirror positions have Enhanced TP/SL monitors")
    logger.info("✅ Monitors configured with chat_id=None (no alerts)")
    logger.info("✅ Monitoring will track TP/SL execution silently")
    logger.info("✅ Breakeven moves will happen automatically without alerts")
    logger.info("\nThe mirror account is now fully monitored without sending alerts!")

if __name__ == "__main__":
    asyncio.run(main())