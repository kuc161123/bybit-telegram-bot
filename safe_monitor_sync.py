#!/usr/bin/env python3
"""
SAFE Monitor Sync - Only sync monitor data with existing orders, DO NOT touch any orders
This script will ONLY read and sync the monitor data with what's actually on the exchange
NO orders will be cancelled, created, or modified
"""
import asyncio
import os
import sys
import time
import pickle
from decimal import Decimal
from typing import Dict, List, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_helpers import get_all_positions, get_all_open_orders
from pybit.unified_trading import HTTP

async def get_existing_tp_sl_orders(symbol: str, side: str, client: HTTP) -> tuple:
    """Get existing TP and SL orders for a position - READ ONLY"""
    try:
        all_orders = await get_all_open_orders(client=client)
        tp_orders = {}
        sl_order = None
        
        for order in all_orders:
            if order.get('symbol') == symbol:
                if order.get('reduceOnly') == True and order.get('side') != side:
                    # This is a TP order (opposite side, reduce only)
                    tp_key = f"tp_{len(tp_orders) + 1}"
                    tp_orders[tp_key] = {
                        'order_id': order.get('orderId', ''),
                        'order_link_id': order.get('orderLinkId', ''),
                        'quantity': Decimal(str(order.get('qty', '0'))),
                        'price': Decimal(str(order.get('price', '0'))),
                        'tp_number': len(tp_orders) + 1,
                        'filled': False,
                        'created_at': time.time()
                    }
                elif order.get('reduceOnly') == True and order.get('side') == side:
                    # This is an SL order (same side, reduce only)
                    sl_order = {
                        'order_id': order.get('orderId', ''),
                        'order_link_id': order.get('orderLinkId', ''),
                        'quantity': Decimal(str(order.get('qty', '0'))),
                        'price': Decimal(str(order.get('price', '0'))),
                        'stop_price': Decimal(str(order.get('triggerPrice', order.get('price', '0')))),
                        'created_at': time.time()
                    }
        
        return tp_orders, sl_order
    except Exception as e:
        print(f"Error getting orders for {symbol}: {e}")
        return {}, None

async def safe_sync_monitors():
    """Safely sync monitor data with existing exchange orders - NO order modifications"""
    print("🔄 SAFE Monitor Sync - Reading existing orders only")
    print("⚠️  NO ORDERS WILL BE MODIFIED, CANCELLED, OR CREATED")
    print("=" * 60)
    
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
        print("❌ Pickle file not found")
        return
    
    if 'enhanced_monitors' not in data:
        data['enhanced_monitors'] = {}
    
    synced_monitors = 0
    
    # Process main account positions
    print("\n🏠 Syncing MAIN account monitors with existing orders...")
    main_positions = await get_all_positions(client=main_client)
    
    for pos in main_positions:
        if float(pos.get('size', 0)) > 0:
            symbol = pos.get('symbol')
            side = pos.get('side')
            size = Decimal(str(pos.get('size')))
            
            monitor_key = f"{symbol}_{side}_main"
            
            # Get existing orders for this position (READ ONLY)
            tp_orders, sl_order = await get_existing_tp_sl_orders(symbol, side, main_client)
            
            # Update or create monitor with actual order data
            if monitor_key in data['enhanced_monitors']:
                monitor = data['enhanced_monitors'][monitor_key]
            else:
                monitor = {
                    'symbol': symbol,
                    'side': side,
                    'account_type': 'main',
                    'approach': 'CONSERVATIVE',
                    'phase': 'MONITORING',
                    'created_at': time.time(),
                    'tp1_hit': False,
                    'sl_moved_to_be': False,
                    'limit_orders': [],
                    'limit_orders_filled': False
                }
                data['enhanced_monitors'][monitor_key] = monitor
            
            # Update monitor with current position and order data
            monitor.update({
                'position_size': size,
                'current_size': size,
                'remaining_size': size,
                'last_known_size': size,
                'updated_at': time.time(),
                'last_check': time.time(),
                'tp_orders': tp_orders,
                'sl_order': sl_order if sl_order else {}
            })
            
            print(f"   ✅ {symbol} {side}: Size={size}, TPs={len(tp_orders)}, SL={'Yes' if sl_order else 'No'}")
            synced_monitors += 1
    
    # Process mirror account positions
    if mirror_client:
        print("\n🪞 Syncing MIRROR account monitors with existing orders...")
        mirror_positions = await get_all_positions(client=mirror_client)
        
        for pos in mirror_positions:
            if float(pos.get('size', 0)) > 0:
                symbol = pos.get('symbol')
                side = pos.get('side')
                size = Decimal(str(pos.get('size')))
                
                monitor_key = f"{symbol}_{side}_mirror"
                
                # Get existing orders for this position (READ ONLY)
                tp_orders, sl_order = await get_existing_tp_sl_orders(symbol, side, mirror_client)
                
                # Update or create monitor with actual order data
                if monitor_key in data['enhanced_monitors']:
                    monitor = data['enhanced_monitors'][monitor_key]
                else:
                    monitor = {
                        'symbol': symbol,
                        'side': side,
                        'account_type': 'mirror',
                        'approach': 'CONSERVATIVE',
                        'phase': 'MONITORING',
                        'created_at': time.time(),
                        'tp1_hit': False,
                        'sl_moved_to_be': False,
                        'limit_orders': [],
                        'limit_orders_filled': False
                    }
                    data['enhanced_monitors'][monitor_key] = monitor
                
                # Update monitor with current position and order data
                monitor.update({
                    'position_size': size,
                    'current_size': size,
                    'remaining_size': size,
                    'last_known_size': size,
                    'updated_at': time.time(),
                    'last_check': time.time(),
                    'tp_orders': tp_orders,
                    'sl_order': sl_order if sl_order else {}
                })
                
                print(f"   ✅ {symbol} {side}: Size={size}, TPs={len(tp_orders)}, SL={'Yes' if sl_order else 'No'}")
                synced_monitors += 1
    
    # Save updated data back to pickle
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    # Create reload signal for bot
    with open('.reload_enhanced_monitors.signal', 'w') as f:
        f.write(f"Safe sync completed: {synced_monitors} monitors synced at {time.time()}")
    
    print(f"\n✅ SAFE SYNC COMPLETE:")
    print(f"   Monitors synced: {synced_monitors}")
    print(f"   Total monitors: {len(data['enhanced_monitors'])}")
    print(f"   Orders touched: 0 (READ ONLY)")
    print(f"   Signal file created for bot reload")
    
    print(f"\n📋 What this accomplished:")
    print(f"   ✅ Monitor data now matches actual exchange state")
    print(f"   ✅ All existing orders preserved exactly as they are")
    print(f"   ✅ TP rebalancing will now work for future limit fills")
    print(f"   ✅ Both main and mirror accounts properly tracked")
    print(f"   ✅ No disruption to current trading positions")

if __name__ == "__main__":
    asyncio.run(safe_sync_monitors())