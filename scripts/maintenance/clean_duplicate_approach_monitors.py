#!/usr/bin/env python3
"""
Clean up duplicate approach monitors for the same symbol
Keep only the monitor that matches the actual trading approach based on orders
"""

import asyncio
import pickle
import os
from datetime import datetime
from pybit.unified_trading import HTTP
from collections import defaultdict

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

async def get_position_approaches():
    """Get the actual trading approach for each position based on orders"""
    position_approaches = {}
    
    try:
        # Create main account client
        main_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY,
            api_secret=BYBIT_API_SECRET
        )
        
        # Get main account orders
        response = main_client.get_open_orders(category="linear", settleCoin="USDT")
        if response.get("retCode") == 0:
            for order in response.get("result", {}).get("list", []):
                symbol = order.get('symbol')
                order_link_id = order.get('orderLinkId', '')
                
                # Detect approach from order patterns
                approach = 'unknown'
                if any(pattern in order_link_id for pattern in ['CONS_', 'TP1_', 'TP2_', 'TP3_', 'TP4_']):
                    approach = 'conservative'
                elif any(pattern in order_link_id for pattern in ['FAST_', 'TP_BOT_FAST', 'SL_BOT_FAST']):
                    approach = 'fast'
                elif order_link_id.startswith('TP_') or order_link_id.startswith('SL_'):
                    # Generic TP/SL without CONS is likely fast
                    approach = 'fast'
                
                if symbol and approach != 'unknown':
                    key = f"{symbol}_main"
                    if key not in position_approaches or approach == 'conservative':
                        # Prefer conservative if we find both
                        position_approaches[key] = approach
        
        # Get mirror account orders if enabled
        if ENABLE_MIRROR_TRADING and BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
            mirror_client = HTTP(
                testnet=USE_TESTNET,
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2
            )
            
            response = mirror_client.get_open_orders(category="linear", settleCoin="USDT")
            if response.get("retCode") == 0:
                for order in response.get("result", {}).get("list", []):
                    symbol = order.get('symbol')
                    order_link_id = order.get('orderLinkId', '')
                    
                    # Detect approach from order patterns
                    approach = 'unknown'
                    if any(pattern in order_link_id for pattern in ['CONS_', 'TP1_', 'TP2_', 'TP3_', 'TP4_']):
                        approach = 'conservative'
                    elif any(pattern in order_link_id for pattern in ['FAST_', 'TP_BOT_FAST', 'SL_BOT_FAST']):
                        approach = 'fast'
                    elif order_link_id.startswith('TP_') or order_link_id.startswith('SL_'):
                        # Generic TP/SL without CONS is likely fast
                        approach = 'fast'
                    
                    if symbol and approach != 'unknown':
                        key = f"{symbol}_mirror"
                        if key not in position_approaches or approach == 'conservative':
                            # Prefer conservative if we find both
                            position_approaches[key] = approach
    except Exception as e:
        print(f"⚠️ Error fetching orders: {e}")
    
    return position_approaches

async def clean_duplicate_monitors(bot_data, position_approaches):
    """Remove duplicate monitors, keeping only the one that matches actual orders"""
    removed_count = 0
    
    # Analyze monitors by symbol and account
    monitors_by_symbol = defaultdict(list)
    
    # Check bot_data['monitor_tasks']
    if 'bot_data' in bot_data and 'monitor_tasks' in bot_data['bot_data']:
        monitor_tasks = bot_data['bot_data']['monitor_tasks']
        
        for monitor_id, monitor_data in monitor_tasks.items():
            # Parse monitor ID
            parts = monitor_id.split('_')
            if len(parts) >= 3:
                symbol = parts[1]
                approach = parts[2]
                account = 'mirror' if monitor_id.endswith('_mirror') else 'main'
                
                key = f"{symbol}_{account}"
                monitors_by_symbol[key].append({
                    'id': monitor_id,
                    'approach': approach,
                    'data': monitor_data
                })
    
    # Process duplicates
    for symbol_key, monitors in monitors_by_symbol.items():
        if len(monitors) > 1:
            print(f"\n🔍 Found {len(monitors)} monitors for {symbol_key}")
            
            # Get the correct approach from orders
            correct_approach = position_approaches.get(symbol_key, None)
            
            if correct_approach:
                print(f"  ✅ Correct approach based on orders: {correct_approach}")
                
                # Keep only the monitor with correct approach
                for monitor in monitors:
                    if monitor['approach'] != correct_approach:
                        monitor_id = monitor['id']
                        if monitor_id in monitor_tasks:
                            del monitor_tasks[monitor_id]
                            removed_count += 1
                            print(f"  🗑️ Removed {monitor_id} (wrong approach: {monitor['approach']})")
            else:
                # No orders found, keep conservative if available, otherwise keep first
                has_conservative = any(m['approach'] == 'conservative' for m in monitors)
                keep_approach = 'conservative' if has_conservative else monitors[0]['approach']
                
                print(f"  ⚠️ No orders found, keeping {keep_approach} monitor")
                
                for monitor in monitors:
                    if monitor['approach'] != keep_approach:
                        monitor_id = monitor['id']
                        if monitor_id in monitor_tasks:
                            del monitor_tasks[monitor_id]
                            removed_count += 1
                            print(f"  🗑️ Removed {monitor_id} (duplicate approach: {monitor['approach']})")
    
    return removed_count

async def main():
    print("=" * 80)
    print("DUPLICATE APPROACH MONITOR CLEANUP")
    print("=" * 80)
    print()
    
    # Load pickle data
    print("Loading pickle file...")
    bot_data = await load_pickle_data()
    if not bot_data:
        return
    
    # Get position approaches based on orders
    print("Analyzing position orders to detect approaches...")
    position_approaches = await get_position_approaches()
    print(f"✅ Detected approaches for {len(position_approaches)} positions")
    
    for key, approach in sorted(position_approaches.items()):
        print(f"  - {key}: {approach}")
    
    # Count monitors before cleanup
    monitor_count_before = 0
    if 'bot_data' in bot_data and 'monitor_tasks' in bot_data['bot_data']:
        monitor_count_before = len(bot_data['bot_data']['monitor_tasks'])
    
    print(f"\n📊 Monitors before cleanup: {monitor_count_before}")
    
    # Clean duplicate monitors
    print("\n🧹 Cleaning duplicate approach monitors...")
    removed_count = await clean_duplicate_monitors(bot_data, position_approaches)
    
    if removed_count > 0:
        # Save updated pickle file
        print(f"\n✅ Removed {removed_count} duplicate monitors")
        print("Saving updated pickle file...")
        success = await save_pickle_data(bot_data)
        
        if success:
            # Count monitors after cleanup
            monitor_count_after = 0
            if 'bot_data' in bot_data and 'monitor_tasks' in bot_data['bot_data']:
                monitor_count_after = len(bot_data['bot_data']['monitor_tasks'])
            
            print(f"\n📊 Monitors after cleanup: {monitor_count_after}")
            print(f"📉 Reduction: {monitor_count_before} → {monitor_count_after}")
            print(f"\n✅ Expected monitor count: {monitor_count_after} (should be 30 for 15 positions × 2 accounts)")
            print("\n⚠️ Please restart the bot to ensure proper monitor restoration")
        else:
            print("\n❌ Failed to save updated pickle file")
    else:
        print("\n✅ No duplicate monitors found!")

if __name__ == "__main__":
    asyncio.run(main())