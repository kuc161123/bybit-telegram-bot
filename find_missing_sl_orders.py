#!/usr/bin/env python3
"""
Find missing SL orders by analyzing trading logs and cross-referencing with exchange
"""
import re
import os
import sys
import asyncio
from typing import Dict, List, Set
from decimal import Decimal

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_helpers import get_all_positions, get_all_open_orders
from pybit.unified_trading import HTTP

def extract_sl_orders_from_logs() -> Dict[str, List[Dict]]:
    """Extract SL order creation, modification, and cancellation from logs"""
    log_file = 'trading_bot.log'
    if not os.path.exists(log_file):
        print(f"❌ Log file {log_file} not found")
        return {}
    
    sl_events = {}  # position_key -> list of events
    
    print("📖 Analyzing trading logs for SL order events...")
    
    with open(log_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            if 'SL' in line and any(keyword in line for keyword in [
                'placed', 'created', 'cancelled', 'moved', 'breakeven', 'adjusted'
            ]):
                # Extract timestamp
                timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if not timestamp_match:
                    continue
                
                timestamp = timestamp_match.group(1)
                message = line[timestamp_match.end():].strip()
                
                # Try to extract symbol and side
                symbol_match = re.search(r'([A-Z]{3,}USDT)', message)
                side_match = re.search(r'(Buy|Sell)', message, re.IGNORECASE)
                
                if symbol_match:
                    symbol = symbol_match.group(1)
                    side = side_match.group(1) if side_match else 'Unknown'
                    
                    # Determine account type
                    account = 'main'
                    if 'MIRROR' in message or 'mirror' in message or '🪞' in message:
                        account = 'mirror'
                    
                    position_key = f"{symbol}_{side}_{account}"
                    
                    if position_key not in sl_events:
                        sl_events[position_key] = []
                    
                    sl_events[position_key].append({
                        'timestamp': timestamp,
                        'line_number': line_num,
                        'message': message,
                        'event_type': 'sl_event'
                    })
    
    return sl_events

def extract_order_ids_from_logs() -> Dict[str, Set[str]]:
    """Extract SL order IDs that were created from logs"""
    log_file = 'trading_bot.log'
    sl_order_ids = {}  # position_key -> set of order IDs
    
    with open(log_file, 'r') as f:
        for line in f:
            if 'SL' in line and ('OrderID' in line or 'orderId' in line):
                # Extract order ID
                order_id_match = re.search(r'[Oo]rder[Ii][Dd][:=]\s*([a-f0-9-]{8,})', line)
                if order_id_match:
                    order_id = order_id_match.group(1)
                    
                    # Extract symbol
                    symbol_match = re.search(r'([A-Z]{3,}USDT)', line)
                    side_match = re.search(r'(Buy|Sell)', line, re.IGNORECASE)
                    
                    if symbol_match:
                        symbol = symbol_match.group(1)
                        side = side_match.group(1) if side_match else 'Unknown'
                        
                        account = 'main'
                        if 'MIRROR' in line or 'mirror' in line or '🪞' in line:
                            account = 'mirror'
                        
                        position_key = f"{symbol}_{side}_{account}"
                        
                        if position_key not in sl_order_ids:
                            sl_order_ids[position_key] = set()
                        
                        sl_order_ids[position_key].add(order_id)
    
    return sl_order_ids

async def check_missing_orders():
    """Check for missing SL, TP, and limit orders by comparing logs with exchange"""
    print("🔍 Finding Missing Orders - SL, TP, and Limit Orders")
    print("=" * 60)
    
    # Get configuration
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
    
    # Get current positions
    print("📊 Getting current positions...")
    positions = []
    
    # Main account positions
    main_positions = await get_all_positions(client=main_client)
    for pos in main_positions:
        if float(pos.get('size', 0)) > 0:
            positions.append({
                'symbol': pos.get('symbol'),
                'side': pos.get('side'),
                'size': pos.get('size'),
                'account': 'main',
                'client': main_client
            })
    
    # Mirror account positions
    if mirror_client:
        mirror_positions = await get_all_positions(client=mirror_client)
        for pos in mirror_positions:
            if float(pos.get('size', 0)) > 0:
                positions.append({
                    'symbol': pos.get('symbol'),
                    'side': pos.get('side'),
                    'size': pos.get('size'),
                    'account': 'mirror',
                    'client': mirror_client
                })
    
    print(f"Found {len(positions)} active positions")
    
    # Extract SL events from logs
    sl_events = extract_sl_orders_from_logs()
    sl_order_ids = extract_order_ids_from_logs()
    
    print(f"Found SL events for {len(sl_events)} positions in logs")
    print(f"Found {sum(len(ids) for ids in sl_order_ids.values())} SL order IDs in logs")
    
    # Check each position for missing orders
    missing_sl_positions = []
    positions_with_sl_in_logs = []
    
    for pos in positions:
        symbol = pos['symbol']
        side = pos['side']
        account = pos['account']
        client = pos['client']
        
        position_key = f"{symbol}_{side}_{account}"
        
        # Get all orders for this position
        all_orders = await get_all_open_orders(client=client)
        position_orders = [o for o in all_orders if o.get('symbol') == symbol]
        
        # Categorize orders
        tp_orders = []
        sl_orders = []
        limit_orders = []
        
        for order in position_orders:
            if order.get('reduceOnly') == True:
                # This is either TP or SL
                if (order.get('stopOrderType') or 
                    order.get('triggerPrice') or 
                    'SL' in order.get('orderLinkId', '').upper()):
                    sl_orders.append(order)
                else:
                    tp_orders.append(order)
            else:
                # This is a limit order for building position
                limit_orders.append(order)
        
        print(f"\n📊 {position_key}:")
        print(f"   Position Size: {pos['size']}")
        print(f"   TP Orders: {len(tp_orders)}")
        print(f"   SL Orders: {len(sl_orders)}")
        print(f"   Limit Orders: {len(limit_orders)}")
        
        # Check if SL should exist based on logs
        if position_key in sl_events:
            positions_with_sl_in_logs.append(position_key)
            print(f"   📖 SL events found in logs: {len(sl_events[position_key])}")
            
            # Show recent SL events
            recent_events = sl_events[position_key][-3:]  # Last 3 events
            for event in recent_events:
                print(f"      {event['timestamp']}: {event['message'][:80]}...")
        else:
            print(f"   📖 No SL events found in logs")
        
        # Check for missing SL orders
        if len(sl_orders) == 0:
            missing_sl_positions.append(position_key)
            print(f"   ❌ MISSING SL ORDER!")
        else:
            print(f"   ✅ SL order exists")
    
    # Summary
    print(f"\n📋 SUMMARY")
    print(f"Total positions checked: {len(positions)}")
    print(f"Positions with SL events in logs: {len(positions_with_sl_in_logs)}")
    print(f"Positions missing SL orders: {len(missing_sl_positions)}")
    
    if missing_sl_positions:
        print(f"\n❌ POSITIONS MISSING SL ORDERS:")
        for pos_key in missing_sl_positions:
            print(f"   • {pos_key}")
            if pos_key in sl_events:
                print(f"     - Had {len(sl_events[pos_key])} SL events in logs")
            if pos_key in sl_order_ids:
                print(f"     - Order IDs in logs: {list(sl_order_ids[pos_key])}")
    
    print(f"\n🔧 RECOMMENDED ACTIONS:")
    print(f"1. Create SL orders for positions missing them")
    print(f"2. Investigate why SL orders were cancelled/removed")
    print(f"3. Ensure SL orders are properly maintained for all positions")
    
    return {
        'positions': positions,
        'missing_sl': missing_sl_positions,
        'sl_events': sl_events,
        'sl_order_ids': sl_order_ids
    }

if __name__ == "__main__":
    asyncio.run(check_missing_orders())