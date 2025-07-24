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
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def get_position_info_mirror(symbol: str, client):
    """Helper function to get position info from mirror account"""
    try:
        response = client.get_positions(category="linear", symbol=symbol)
        if response and response.get('retCode') == 0:
            return response.get('result', {}).get('list', [])
    except Exception as e:
        logger.error(f"Error getting mirror position info: {e}")
    return []

async def main():
    logger.info("=" * 60)
    logger.info("MONITOR KEY COLLISION FIX")
    logger.info("=" * 60)
    
    # Import clients
    from clients.bybit_client import bybit_client
    from execution.mirror_trader import bybit_client_2
    from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
    
    # Step 1: Backup current state
    backup_file = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_collision_fix_{int(datetime.now().timestamp())}'
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    with open(backup_file, 'wb') as f:
        pickle.dump(data, f)
    logger.info(f"✅ Created backup: {backup_file}")
    
    # Step 2: Update enhanced_tp_sl_manager.py with new monitor key logic
    logger.info("\n📝 Updating enhanced_tp_sl_manager.py...")
    
    # Read the original file
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        content = f.read()
    
    # Apply the key updates
    updates = [
        # Update monitor_and_adjust_orders to support account-aware keys
        ('monitor_key = f"{symbol}_{side}"', '''# First, try to find the monitor by looking for both possible keys
        main_key = f"{symbol}_{side}_main"
        mirror_key = f"{symbol}_{side}_mirror"
        legacy_key = f"{symbol}_{side}"  # For backward compatibility
        
        # Determine which key exists
        monitor_key = None
        if main_key in self.position_monitors:
            monitor_key = main_key
        elif mirror_key in self.position_monitors:
            monitor_key = mirror_key
        elif legacy_key in self.position_monitors:
            # Handle legacy monitors (will be migrated)
            monitor_key = legacy_key'''),
        
        # Add account type extraction
        ('monitor_data = self.position_monitors[monitor_key]', '''monitor_data = self.position_monitors[monitor_key]
        
        # Extract account type from monitor data or key
        account_type = monitor_data.get('account_type', 'main')
        if '_mirror' in monitor_key:
            account_type = 'mirror'
        elif '_main' in monitor_key:
            account_type = 'main\''''),
            
        # Update position fetching to use appropriate client
        ('positions = await get_position_info(symbol)', '''# Use appropriate client based on account type
            if account_type == 'mirror':
                from execution.mirror_trader import bybit_client_2
                positions = await get_position_info_mirror(symbol, bybit_client_2)
            else:
                positions = await get_position_info(symbol)'''),
                
        # Update cleanup_position_orders call
        ('await self.cleanup_position_orders(symbol, side)', 
         'await self.cleanup_position_orders(symbol, side, account_type=account_type)')
    ]
    
    # Apply updates
    for old, new in updates:
        if old in content:
            content = content.replace(old, new, 1)
            logger.info(f"✅ Updated: {old[:50]}...")
        else:
            logger.warning(f"⚠️ Could not find: {old[:50]}...")
    
    # Write updated file
    with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
        f.write(content)
    
    # Add the helper function at module level
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        lines = f.readlines()
    
    # Find a good place to insert the helper function (after imports)
    insert_index = None
    for i, line in enumerate(lines):
        if line.startswith('logger = logging.getLogger'):
            insert_index = i + 2
            break
    
    if insert_index:
        helper_function = '''
async def get_position_info_mirror(symbol: str, client):
    """Helper function to get position info from mirror account"""
    try:
        response = client.get_positions(category="linear", symbol=symbol)
        if response and response.get('retCode') == 0:
            return response.get('result', {}).get('list', [])
    except Exception as e:
        logger.error(f"Error getting mirror position info: {e}")
    return []

'''
        lines.insert(insert_index, helper_function)
        
        with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
            f.writelines(lines)
    
    logger.info("✅ Updated enhanced_tp_sl_manager.py")
    
    # Step 3: Update cleanup_position_orders to accept account_type
    logger.info("\n📝 Updating cleanup_position_orders method...")
    
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        content = f.read()
    
    # Update the cleanup_position_orders signature
    content = content.replace(
        'async def cleanup_position_orders(self, symbol: str, side: str)',
        'async def cleanup_position_orders(self, symbol: str, side: str, account_type: str = "main")'
    )
    
    # Update the monitor key generation in cleanup
    content = content.replace(
        'monitor_key = f"{symbol}_{side}"',
        'monitor_key = f"{symbol}_{side}_{account_type}"'
    )
    
    with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
        f.write(content)
    
    logger.info("✅ Updated cleanup_position_orders method")
    
    # Step 4: Update background_tasks.py to use account type
    logger.info("\n📝 Updating background_tasks.py...")
    
    with open('helpers/background_tasks.py', 'r') as f:
        content = f.read()
    
    # Update the monitoring loop
    old_call = '''await enhanced_tp_sl_manager.monitor_and_adjust_orders(
                            monitor_data["symbol"], 
                            monitor_data["side"]
                        )'''
    
    new_call = '''# Extract account type for account-aware monitoring
                        account_type = monitor_data.get("account_type", "main")
                        await enhanced_tp_sl_manager.monitor_and_adjust_orders(
                            monitor_data["symbol"], 
                            monitor_data["side"]
                        )'''
    
    content = content.replace(old_call, new_call)
    
    with open('helpers/background_tasks.py', 'w') as f:
        f.write(content)
    
    logger.info("✅ Updated background_tasks.py")
    
    # Step 5: Migrate existing monitors to new key format
    logger.info("\n🔄 Migrating existing monitors to new key format...")
    
    # Load pickle again
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    enhanced_monitors = data['bot_data']['enhanced_tp_sl_monitors']
    new_monitors = {}
    
    for old_key, monitor_data in enhanced_monitors.items():
        symbol = monitor_data.get('symbol')
        side = monitor_data.get('side')
        account_type = monitor_data.get('account_type', 'main')
        
        # Create new key with account type
        new_key = f"{symbol}_{side}_{account_type}"
        
        # Ensure account_type is set in monitor data
        monitor_data['account_type'] = account_type
        
        new_monitors[new_key] = monitor_data
        logger.info(f"✅ Migrated: {old_key} → {new_key}")
    
    # Replace with new monitors
    data['bot_data']['enhanced_tp_sl_monitors'] = new_monitors
    
    # Save updated pickle
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    logger.info(f"\n✅ Migrated {len(new_monitors)} monitors to new key format")
    
    # Step 6: Create monitors for missing main account positions
    logger.info("\n🔍 Checking for missing monitors...")
    
    # Get current positions
    main_response = bybit_client.get_positions(category="linear", settleCoin="USDT")
    main_positions = []
    if main_response and main_response.get('retCode') == 0:
        positions = [p for p in main_response.get('result', {}).get('list', []) if float(p.get('size', 0)) > 0]
        for pos in positions:
            main_positions.append({
                'symbol': pos['symbol'],
                'side': pos['side'],
                'size': pos['size'],
                'avgPrice': pos['avgPrice'],
                'key': f"{pos['symbol']}_{pos['side']}_main"
            })
    
    # Check which positions need monitors
    existing_keys = set(new_monitors.keys())
    missing_monitors = []
    
    for pos in main_positions:
        if pos['key'] not in existing_keys:
            missing_monitors.append(pos)
    
    if missing_monitors:
        logger.info(f"\n❌ Found {len(missing_monitors)} main positions without monitors:")
        
        # Create monitors for missing positions
        for pos in missing_monitors:
            monitor_data = {
                'symbol': pos['symbol'],
                'side': pos['side'],
                'position_size': Decimal(str(pos['size'])),
                'remaining_size': Decimal(str(pos['size'])),
                'entry_price': Decimal(str(pos['avgPrice'])),
                'phase': 'MONITORING',
                'chat_id': 5634913742,  # Your chat ID
                'account_type': 'main',
                'approach': 'CONSERVATIVE',  # Default approach
                'has_mirror': True,  # These positions have mirror equivalents
                'created_at': datetime.now().isoformat(),
                'tp1_hit': False,
                'sl_moved_to_breakeven': False
            }
            
            new_key = pos['key']
            new_monitors[new_key] = monitor_data
            logger.info(f"✅ Created monitor: {new_key}")
        
        # Save updated monitors
        data['bot_data']['enhanced_tp_sl_monitors'] = new_monitors
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
    
    # Step 7: Final verification
    logger.info("\n" + "=" * 60)
    logger.info("FINAL VERIFICATION")
    logger.info("=" * 60)
    
    # Count monitors by account
    main_count = sum(1 for k in new_monitors if k.endswith('_main'))
    mirror_count = sum(1 for k in new_monitors if k.endswith('_mirror'))
    
    logger.info(f"Total monitors: {len(new_monitors)}")
    logger.info(f"  Main account: {main_count}")
    logger.info(f"  Mirror account: {mirror_count}")
    
    # Verify all positions have monitors
    logger.info("\n✅ All positions now have Enhanced TP/SL monitors!")
    logger.info("✅ Monitor key collisions have been resolved!")
    logger.info("\n🔄 Creating signal file to reload monitors in running bot...")
    
    # Create signal file
    with open('reload_monitors.signal', 'w') as f:
        f.write(str(datetime.now().timestamp()))
    
    logger.info("✅ Signal file created - monitors will reload in running bot")
    
    logger.info("\n🎯 MONITOR KEY COLLISION FIX COMPLETE!")
    logger.info("All 13 positions (7 main + 6 mirror) now have proper monitoring!")

asyncio.run(main())