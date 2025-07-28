#!/usr/bin/env python3
"""
Quick fix for TP rebalancing issue - focus on the core problem
"""
import asyncio
import os
import sys
import time
import pickle
from decimal import Decimal

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_helpers import get_all_positions

async def main():
    """Fix the core issue - monitors not being loaded for existing positions"""
    print("🔧 Quick Fix: Creating monitors for existing positions")
    
    # Get configuration from environment
    config = {
        'TESTNET': os.getenv('TESTNET', 'false').lower() == 'true',
        'BYBIT_API_KEY': os.getenv('BYBIT_API_KEY'),
        'BYBIT_API_SECRET': os.getenv('BYBIT_API_SECRET'),
        'ENABLE_MIRROR_TRADING': os.getenv('ENABLE_MIRROR_TRADING', 'false').lower() == 'true',
        'BYBIT_API_KEY_2': os.getenv('BYBIT_API_KEY_2'),
        'BYBIT_API_SECRET_2': os.getenv('BYBIT_API_SECRET_2')
    }
    
    # Initialize clients
    from pybit.unified_trading import HTTP
    
    main_client = HTTP(
        testnet=config['TESTNET'],
        api_key=config['BYBIT_API_KEY'],
        api_secret=config['BYBIT_API_SECRET']
    )
    
    mirror_client = None
    if config['ENABLE_MIRROR_TRADING']:
        mirror_client = HTTP(
            testnet=config['TESTNET'],
            api_key=config['BYBIT_API_KEY_2'],
            api_secret=config['BYBIT_API_SECRET_2']
        )
    
    # Load current pickle data
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
    except FileNotFoundError:
        data = {}
    
    # Ensure required sections exist
    if 'enhanced_monitors' not in data:
        data['enhanced_monitors'] = {}
    if 'positions' not in data:
        data['positions'] = {}
    
    total_monitors_created = 0
    
    # Process main account positions
    print("\n🏠 Creating monitors for MAIN account positions...")
    main_positions = await get_all_positions(client=main_client)
    
    for pos in main_positions:
        if float(pos.get('size', 0)) > 0:
            symbol = pos.get('symbol')
            side = pos.get('side')
            size = Decimal(str(pos.get('size')))
            
            monitor_key = f"{symbol}_{side}_main"
            
            if monitor_key not in data['enhanced_monitors']:
                print(f"   Creating monitor for {symbol} {side}: Size={size}")
                
                data['enhanced_monitors'][monitor_key] = {
                    'symbol': symbol,
                    'side': side,
                    'account_type': 'main',
                    'position_size': size,
                    'current_size': size,
                    'remaining_size': size,
                    'approach': 'CONSERVATIVE',
                    'phase': 'MONITORING',  # Set to monitoring for existing positions
                    'tp_orders': {},
                    'sl_order': {},
                    'last_known_size': size,
                    'last_check': time.time(),
                    'created_at': time.time(),
                    'updated_at': time.time(),
                    'tp1_hit': False,
                    'sl_moved_to_be': False,
                    'limit_orders': [],
                    'limit_orders_filled': False
                }
                total_monitors_created += 1
            else:
                # Update existing monitor with current size
                data['enhanced_monitors'][monitor_key]['current_size'] = size
                data['enhanced_monitors'][monitor_key]['position_size'] = size
                data['enhanced_monitors'][monitor_key]['updated_at'] = time.time()
                print(f"   Updated existing monitor for {symbol} {side}")
    
    # Process mirror account positions
    if mirror_client:
        print("\n🪞 Creating monitors for MIRROR account positions...")
        mirror_positions = await get_all_positions(client=mirror_client)
        
        for pos in mirror_positions:
            if float(pos.get('size', 0)) > 0:
                symbol = pos.get('symbol')
                side = pos.get('side')
                size = Decimal(str(pos.get('size')))
                
                monitor_key = f"{symbol}_{side}_mirror"
                
                if monitor_key not in data['enhanced_monitors']:
                    print(f"   Creating monitor for {symbol} {side}: Size={size}")
                    
                    data['enhanced_monitors'][monitor_key] = {
                        'symbol': symbol,
                        'side': side,
                        'account_type': 'mirror',
                        'position_size': size,
                        'current_size': size,
                        'remaining_size': size,
                        'approach': 'CONSERVATIVE',
                        'phase': 'MONITORING',
                        'tp_orders': {},
                        'sl_order': {},
                        'last_known_size': size,
                        'last_check': time.time(),
                        'created_at': time.time(),
                        'updated_at': time.time(),
                        'tp1_hit': False,
                        'sl_moved_to_be': False,
                        'limit_orders': [],
                        'limit_orders_filled': False
                    }
                    total_monitors_created += 1
                else:
                    # Update existing monitor with current size
                    data['enhanced_monitors'][monitor_key]['current_size'] = size
                    data['enhanced_monitors'][monitor_key]['position_size'] = size
                    data['enhanced_monitors'][monitor_key]['updated_at'] = time.time()
                    print(f"   Updated existing monitor for {symbol} {side}")
    
    # Save updated data back to pickle
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    # Create signal file to force monitor reload
    with open('.force_load_all_monitors', 'w') as f:
        f.write(f"Fixed TP rebalancing: Created {total_monitors_created} monitors at {time.time()}")
    
    print(f"\n✅ Quick Fix Complete:")
    print(f"   Monitors created/updated: {total_monitors_created}")
    print(f"   Total monitors in system: {len(data['enhanced_monitors'])}")
    print(f"   Signal file created for bot reload")
    
    print(f"\n📋 What this fixes:")
    print(f"   1. Monitors now exist for all open positions")
    print(f"   2. TP rebalancing will work for future limit fills")
    print(f"   3. Both main and mirror accounts are covered")
    print(f"   4. Bot will reload monitors on next cycle")

if __name__ == "__main__":
    asyncio.run(main())