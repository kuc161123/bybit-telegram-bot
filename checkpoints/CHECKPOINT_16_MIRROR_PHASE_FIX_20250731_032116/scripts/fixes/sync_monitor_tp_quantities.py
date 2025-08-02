#!/usr/bin/env python3
"""
Sync monitor TP quantities with actual exchange orders
Fixes mismatches between monitor data and exchange orders
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pickle
import asyncio
import logging
from decimal import Decimal
from pybit.unified_trading import HTTP
from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET,
    ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def sync_tp_quantities():
    """Sync monitor TP quantities with exchange orders"""
    
    # Initialize clients
    main_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    mirror_client = None
    if ENABLE_MIRROR_TRADING and BYBIT_API_KEY_2:
        mirror_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2
        )
    
    print("=" * 80)
    print("SYNCING MONITOR TP QUANTITIES WITH EXCHANGE")
    print("=" * 80)
    
    # Load pickle data
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    bot_data = data.get('bot_data', {})
    monitors = bot_data.get('enhanced_tp_sl_monitors', {})
    
    # Get all positions and orders
    main_positions = main_client.get_positions(category="linear", settleCoin="USDT").get("result", {}).get("list", [])
    main_orders = main_client.get_open_orders(category="linear", settleCoin="USDT", limit=200).get("result", {}).get("list", [])
    
    mirror_positions = []
    mirror_orders = []
    if mirror_client:
        mirror_positions = mirror_client.get_positions(category="linear", settleCoin="USDT").get("result", {}).get("list", [])
        mirror_orders = mirror_client.get_open_orders(category="linear", settleCoin="USDT", limit=200).get("result", {}).get("list", [])
    
    # Track updates
    updates_made = 0
    
    # Process main account
    print("\nMAIN ACCOUNT:")
    for pos in main_positions:
        if float(pos.get('size', 0)) <= 0:
            continue
            
        symbol = pos['symbol']
        side = pos['side']
        monitor_key = f"{symbol}_{side}_main"
        
        if monitor_key not in monitors:
            print(f"  ❌ No monitor for {symbol} {side}")
            continue
        
        monitor = monitors[monitor_key]
        
        # Get TP orders for this position
        tp_orders = []
        for order in main_orders:
            if order['symbol'] != symbol:
                continue
            
            link_id = order.get('orderLinkId', '')
            if 'TP' in link_id or (order.get('reduceOnly') and order['side'] != side):
                tp_orders.append(order)
        
        # Update monitor TP data
        if tp_orders:
            new_tp_orders = {}
            for i, order in enumerate(sorted(tp_orders, key=lambda x: float(x.get('price', 0)))):
                order_id = order['orderId']
                new_tp_orders[order_id] = {
                    'price': float(order['price']),
                    'quantity': float(order['qty']),
                    'tp_number': i + 1,
                    'percentage': 0,  # Will be recalculated
                    'filled': False,
                    'order_id': order_id
                }
            
            if new_tp_orders != monitor.get('tp_orders', {}):
                monitor['tp_orders'] = new_tp_orders
                print(f"  ✅ Updated {symbol}: {len(tp_orders)} TPs")
                updates_made += 1
    
    # Process mirror account
    if mirror_client:
        print("\nMIRROR ACCOUNT:")
        for pos in mirror_positions:
            if float(pos.get('size', 0)) <= 0:
                continue
                
            symbol = pos['symbol']
            side = pos['side']
            monitor_key = f"{symbol}_{side}_mirror"
            
            if monitor_key not in monitors:
                print(f"  ❌ No monitor for {symbol} {side}")
                continue
            
            monitor = monitors[monitor_key]
            
            # Get TP orders for this position
            tp_orders = []
            for order in mirror_orders:
                if order['symbol'] != symbol:
                    continue
                
                link_id = order.get('orderLinkId', '')
                if 'TP' in link_id or (order.get('reduceOnly') and order['side'] != side):
                    tp_orders.append(order)
            
            # Update monitor TP data
            if tp_orders:
                new_tp_orders = {}
                for i, order in enumerate(sorted(tp_orders, key=lambda x: float(x.get('price', 0)))):
                    order_id = order['orderId']
                    new_tp_orders[order_id] = {
                        'price': float(order['price']),
                        'quantity': float(order['qty']),
                        'tp_number': i + 1,
                        'percentage': 0,  # Will be recalculated
                        'filled': False,
                        'order_id': order_id
                    }
                
                if new_tp_orders != monitor.get('tp_orders', {}):
                    monitor['tp_orders'] = new_tp_orders
                    print(f"  ✅ Updated {symbol}: {len(tp_orders)} TPs")
                    updates_made += 1
    
    # Save updated data
    if updates_made > 0:
        # Create backup
        import time
        backup_file = f"bybit_bot_dashboard_v4.1_enhanced.pkl.backup_tp_sync_{int(time.time())}"
        with open(backup_file, 'wb') as f:
            pickle.dump(data, f)
        print(f"\n📁 Created backup: {backup_file}")
        
        # Save updated data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        print(f"\n✅ Updated {updates_made} monitors with correct TP quantities")
        print("\n⚠️  IMPORTANT: Restart the bot to apply these changes!")
    else:
        print("\n✅ No updates needed - all monitors already in sync")
    
    return updates_made


if __name__ == "__main__":
    updates = sync_tp_quantities()
    if updates > 0:
        print("\n🔄 Please restart the bot now to apply the TP quantity sync")