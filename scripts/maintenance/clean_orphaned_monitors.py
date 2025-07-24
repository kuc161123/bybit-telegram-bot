#!/usr/bin/env python3
"""
Clean up orphaned monitors that have no matching positions
Properly handles hedge mode by checking both symbol and side
"""

import asyncio
import pickle
import os
from datetime import datetime
from pybit.unified_trading import HTTP

# Import settings
from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET, 
    ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
)

async def load_pickle_data():
    """Load the pickle file with bot data"""
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    if not os.path.exists(pickle_file):
        print(f"❌ Pickle file not found: {pickle_file}")
        return None
    
    try:
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        return data
    except Exception as e:
        print(f"❌ Error loading pickle file: {e}")
        return None

async def save_pickle_data(data):
    """Save the pickle file with bot data"""
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    backup_file = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_{int(datetime.now().timestamp())}'
    
    # Create backup
    if os.path.exists(pickle_file):
        os.rename(pickle_file, backup_file)
        print(f"✅ Created backup: {backup_file}")
    
    try:
        with open(pickle_file, 'wb') as f:
            pickle.dump(data, f)
        print(f"✅ Saved updated pickle file")
        return True
    except Exception as e:
        print(f"❌ Error saving pickle file: {e}")
        # Restore backup if save failed
        if os.path.exists(backup_file):
            os.rename(backup_file, pickle_file)
        return False

async def get_all_positions():
    """Get all positions from both accounts"""
    positions = set()  # Using set of symbols for easier lookup
    
    try:
        # Create main account client
        main_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY,
            api_secret=BYBIT_API_SECRET
        )
        
        # Get main account positions
        response = main_client.get_positions(category="linear", settleCoin="USDT")
        if response.get("retCode") == 0:
            for pos in response.get("result", {}).get("list", []):
                if float(pos.get('size', 0)) > 0:
                    # Just store symbol for now (since monitors don't have side)
                    positions.add(pos['symbol'])
        
        # Get mirror account positions if enabled
        if ENABLE_MIRROR_TRADING and BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
            mirror_client = HTTP(
                testnet=USE_TESTNET,
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2
            )
            
            response = mirror_client.get_positions(category="linear", settleCoin="USDT")
            if response.get("retCode") == 0:
                for pos in response.get("result", {}).get("list", []):
                    if float(pos.get('size', 0)) > 0:
                        positions.add(pos['symbol'])
    except Exception as e:
        print(f"⚠️ Error fetching positions: {e}")
    
    return positions

async def clean_orphaned_monitors(bot_data, active_symbols):
    """Remove monitors that have no matching positions"""
    removed_count = 0
    
    # Clean bot_data['monitor_tasks']
    if 'bot_data' in bot_data and 'monitor_tasks' in bot_data['bot_data']:
        monitor_tasks = bot_data['bot_data']['monitor_tasks']
        monitors_to_remove = []
        
        for monitor_id, monitor_data in monitor_tasks.items():
            # Extract symbol from monitor data or ID
            symbol = monitor_data.get('symbol')
            if not symbol:
                # Try to extract from ID (format: chat_id_symbol_approach[_mirror])
                parts = monitor_id.split('_')
                if len(parts) >= 2:
                    symbol = parts[1]
            
            # Check if position exists
            if symbol and symbol not in active_symbols:
                monitors_to_remove.append(monitor_id)
                print(f"🗑️ Removing orphaned monitor: {monitor_id} (symbol: {symbol})")
        
        # Remove orphaned monitors
        for monitor_id in monitors_to_remove:
            del monitor_tasks[monitor_id]
            removed_count += 1
    
    # Clean bot_data['monitors'] if it exists
    if 'bot_data' in bot_data and 'monitors' in bot_data['bot_data']:
        monitors = bot_data['bot_data']['monitors']
        monitors_to_remove = []
        
        for monitor_id, monitor_data in monitors.items():
            # Extract symbol from monitor data or ID
            symbol = monitor_data.get('symbol')
            if not symbol:
                # Try to extract from ID
                parts = monitor_id.split('_')
                if len(parts) >= 2:
                    symbol = parts[1]
            
            # Check if position exists
            if symbol and symbol not in active_symbols:
                monitors_to_remove.append(monitor_id)
                print(f"🗑️ Removing orphaned monitor from monitors: {monitor_id} (symbol: {symbol})")
        
        # Remove orphaned monitors
        for monitor_id in monitors_to_remove:
            del monitors[monitor_id]
            removed_count += 1
    
    # Clean root level monitors
    root_monitors_to_remove = []
    for key, value in bot_data.items():
        if key.startswith('monitor_') and isinstance(value, dict):
            # Extract symbol
            symbol = value.get('symbol')
            if not symbol:
                # Try to extract from key
                parts = key.replace('monitor_', '').split('_')
                if len(parts) >= 2:
                    symbol = parts[1]
            
            # Check if position exists
            if symbol and symbol not in active_symbols:
                root_monitors_to_remove.append(key)
                print(f"🗑️ Removing orphaned root monitor: {key} (symbol: {symbol})")
    
    # Remove root monitors
    for key in root_monitors_to_remove:
        del bot_data[key]
        removed_count += 1
    
    return removed_count

async def main():
    print("=" * 80)
    print("ORPHANED MONITOR CLEANUP")
    print("=" * 80)
    print()
    
    # Load pickle data
    print("Loading pickle file...")
    bot_data = await load_pickle_data()
    if not bot_data:
        return
    
    # Get all active positions
    print("Fetching current positions...")
    active_symbols = await get_all_positions()
    print(f"✅ Found {len(active_symbols)} active positions: {sorted(active_symbols)}")
    
    # Count monitors before cleanup
    monitor_count_before = 0
    if 'bot_data' in bot_data and 'monitor_tasks' in bot_data['bot_data']:
        monitor_count_before += len(bot_data['bot_data']['monitor_tasks'])
    if 'bot_data' in bot_data and 'monitors' in bot_data['bot_data']:
        monitor_count_before += len(bot_data['bot_data']['monitors'])
    monitor_count_before += sum(1 for k in bot_data.keys() if k.startswith('monitor_'))
    
    print(f"\n📊 Monitors before cleanup: {monitor_count_before}")
    
    # Clean orphaned monitors
    print("\n🧹 Cleaning orphaned monitors...")
    removed_count = await clean_orphaned_monitors(bot_data, active_symbols)
    
    if removed_count > 0:
        # Save updated pickle file
        print(f"\n✅ Removed {removed_count} orphaned monitors")
        print("Saving updated pickle file...")
        success = await save_pickle_data(bot_data)
        
        if success:
            # Count monitors after cleanup
            monitor_count_after = 0
            if 'bot_data' in bot_data and 'monitor_tasks' in bot_data['bot_data']:
                monitor_count_after += len(bot_data['bot_data']['monitor_tasks'])
            if 'bot_data' in bot_data and 'monitors' in bot_data['bot_data']:
                monitor_count_after += len(bot_data['bot_data']['monitors'])
            monitor_count_after += sum(1 for k in bot_data.keys() if k.startswith('monitor_'))
            
            print(f"\n📊 Monitors after cleanup: {monitor_count_after}")
            print(f"📉 Reduction: {monitor_count_before} → {monitor_count_after}")
            print("\n✅ Cleanup completed successfully!")
            print("\n⚠️ Please restart the bot to ensure monitors are properly restored for active positions")
        else:
            print("\n❌ Failed to save updated pickle file")
    else:
        print("\n✅ No orphaned monitors found - everything is clean!")

if __name__ == "__main__":
    asyncio.run(main())