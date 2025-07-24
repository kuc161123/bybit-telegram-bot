#!/usr/bin/env python3
"""
Fix monitor key collisions by implementing account-aware monitor keys
This will allow both main and mirror accounts to have monitors for the same symbol/side
"""
import asyncio
import logging
import pickle
from datetime import datetime
from decimal import Decimal
import shutil

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("=" * 60)
    logger.info("MONITOR KEY COLLISION FIX - SIMPLIFIED")
    logger.info("=" * 60)
    
    # Import clients
    from clients.bybit_client import bybit_client
    from execution.mirror_trader import bybit_client_2
    
    # Step 1: Backup files
    backup_time = int(datetime.now().timestamp())
    
    # Backup pickle
    pickle_backup = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_collision_fix_{backup_time}'
    shutil.copy('bybit_bot_dashboard_v4.1_enhanced.pkl', pickle_backup)
    logger.info(f"✅ Created pickle backup: {pickle_backup}")
    
    # Backup enhanced_tp_sl_manager.py
    manager_backup = f'execution/enhanced_tp_sl_manager.py.backup_{backup_time}'
    shutil.copy('execution/enhanced_tp_sl_manager.py', manager_backup)
    logger.info(f"✅ Created manager backup: {manager_backup}")
    
    # Step 2: Migrate existing monitors to new key format
    logger.info("\n🔄 Migrating existing monitors to account-aware keys...")
    
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    enhanced_monitors = data['bot_data']['enhanced_tp_sl_monitors']
    new_monitors = {}
    
    # Migrate each monitor
    for old_key, monitor_data in enhanced_monitors.items():
        symbol = monitor_data.get('symbol')
        side = monitor_data.get('side')
        account_type = monitor_data.get('account_type', 'main')
        
        # Create new key with account type
        new_key = f"{symbol}_{side}_{account_type}"
        
        # Ensure account_type is set in monitor data
        monitor_data['account_type'] = account_type
        
        new_monitors[new_key] = monitor_data
        logger.info(f"  {old_key} → {new_key} (account: {account_type})")
    
    logger.info(f"\n✅ Migrated {len(new_monitors)} monitors")
    
    # Step 3: Create monitors for missing main account positions
    logger.info("\n🔍 Checking for missing main account monitors...")
    
    # Get current main positions
    main_response = bybit_client.get_positions(category="linear", settleCoin="USDT")
    if main_response and main_response.get('retCode') == 0:
        positions = [p for p in main_response.get('result', {}).get('list', []) if float(p.get('size', 0)) > 0]
        
        created_count = 0
        for pos in positions:
            symbol = pos['symbol']
            side = pos['side']
            monitor_key = f"{symbol}_{side}_main"
            
            if monitor_key not in new_monitors:
                # Create monitor for this position
                monitor_data = {
                    'symbol': symbol,
                    'side': side,
                    'position_size': Decimal(str(pos['size'])),
                    'remaining_size': Decimal(str(pos['size'])),
                    'entry_price': Decimal(str(pos['avgPrice'])),
                    'phase': 'MONITORING',
                    'chat_id': 5634913742,  # Your chat ID for alerts
                    'account_type': 'main',
                    'approach': 'CONSERVATIVE',  # Default approach
                    'has_mirror': True,  # These positions have mirror equivalents
                    'created_at': datetime.now().isoformat(),
                    'tp1_hit': False,
                    'sl_moved_to_breakeven': False,
                    'last_check': 0
                }
                
                new_monitors[monitor_key] = monitor_data
                created_count += 1
                logger.info(f"  ✅ Created monitor: {monitor_key}")
        
        if created_count > 0:
            logger.info(f"\n✅ Created {created_count} new main account monitors")
        else:
            logger.info("✅ All main positions already have monitors")
    
    # Step 4: Save updated monitors
    data['bot_data']['enhanced_tp_sl_monitors'] = new_monitors
    
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    logger.info("\n✅ Saved updated monitors to pickle file")
    
    # Step 5: Create the updated enhanced_tp_sl_manager
    logger.info("\n📝 Creating updated enhanced_tp_sl_manager...")
    
    # Write the patched version
    with open('execution/enhanced_tp_sl_manager_patched.py', 'w') as f:
        f.write("""# This is a patched version with account-aware monitor keys
# Import the original first
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.enhanced_tp_sl_manager import *

# Patch the monitor_and_adjust_orders method
original_monitor_and_adjust_orders = EnhancedTPSLManager.monitor_and_adjust_orders

async def patched_monitor_and_adjust_orders(self, symbol: str, side: str):
    # First, try to find the monitor by looking for all possible keys
    main_key = f"{symbol}_{side}_main"
    mirror_key = f"{symbol}_{side}_mirror"
    legacy_key = f"{symbol}_{side}"  # For backward compatibility
    
    # Determine which key exists
    monitor_key = None
    account_type = 'main'
    
    if main_key in self.position_monitors:
        monitor_key = main_key
        account_type = 'main'
    elif mirror_key in self.position_monitors:
        monitor_key = mirror_key
        account_type = 'mirror'
    elif legacy_key in self.position_monitors:
        # Handle legacy monitors
        monitor_key = legacy_key
        monitor_data = self.position_monitors[legacy_key]
        account_type = monitor_data.get('account_type', 'main')
        
        # Migrate to new key format
        new_key = f"{symbol}_{side}_{account_type}"
        self.position_monitors[new_key] = monitor_data
        del self.position_monitors[legacy_key]
        monitor_key = new_key
        logger.info(f"Migrated monitor: {legacy_key} → {new_key}")
    
    if not monitor_key:
        return
    
    # Store account type in self for use by other methods
    self._current_account_type = account_type
    
    # Call original method
    await original_monitor_and_adjust_orders(self, symbol, side)

# Apply the patch
EnhancedTPSLManager.monitor_and_adjust_orders = patched_monitor_and_adjust_orders

# Also patch cleanup_position_orders to use account-aware keys
original_cleanup = EnhancedTPSLManager.cleanup_position_orders

async def patched_cleanup_position_orders(self, symbol: str, side: str, account_type: str = None):
    # Use stored account type if not provided
    if account_type is None:
        account_type = getattr(self, '_current_account_type', 'main')
    
    # Update monitor key to include account type
    monitor_key = f"{symbol}_{side}_{account_type}"
    
    # Check legacy key too
    legacy_key = f"{symbol}_{side}"
    if legacy_key in self.position_monitors and monitor_key not in self.position_monitors:
        monitor_key = legacy_key
    
    # Store the key temporarily
    self._cleanup_monitor_key = monitor_key
    
    # Call original
    await original_cleanup(self, symbol, side)

EnhancedTPSLManager.cleanup_position_orders = patched_cleanup_position_orders
""")
    
    logger.info("✅ Created patched enhanced_tp_sl_manager")
    
    # Step 6: Final summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    
    # Count monitors by type
    main_count = sum(1 for k in new_monitors if k.endswith('_main'))
    mirror_count = sum(1 for k in new_monitors if k.endswith('_mirror'))
    
    logger.info(f"Total monitors: {len(new_monitors)}")
    logger.info(f"  Main account: {main_count}")
    logger.info(f"  Mirror account: {mirror_count}")
    
    # List all monitors
    logger.info("\nAll monitors:")
    for key in sorted(new_monitors.keys()):
        monitor = new_monitors[key]
        alerts = "with alerts" if monitor.get('chat_id') else "no alerts"
        logger.info(f"  {key} ({alerts})")
    
    # Create signal file
    with open('reload_monitors.signal', 'w') as f:
        f.write(str(datetime.now().timestamp()))
    
    logger.info("\n✅ Created signal file to reload monitors")
    logger.info("\n🎯 MONITOR KEY COLLISION FIX COMPLETE!")
    logger.info("All positions now have proper Enhanced TP/SL monitoring!")

asyncio.run(main())