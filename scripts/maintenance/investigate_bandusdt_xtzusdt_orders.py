#!/usr/bin/env python3
"""
Comprehensive investigation of BANDUSDT and XTZUSDT order quantities
to determine if TP/SL orders need adjustment after limit order fills.
"""

import asyncio
import sys
import os
from datetime import datetime
from decimal import Decimal
import pickle
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pybit.unified_trading import HTTP
from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2,
    USE_TESTNET, ENABLE_MIRROR_TRADING
)


def load_enhanced_monitors():
    """Load Enhanced TP/SL monitors from pickle file"""
    try:
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        return monitors
    except Exception as e:
        print(f"❌ Error loading monitors: {e}")
        return {}


def search_trade_logs(symbol):
    """Search for trade logs related to the symbol"""
    logs = []
    
    # Check main trade history
    try:
        if os.path.exists('data/enhanced_trade_history.json'):
            with open('data/enhanced_trade_history.json', 'r') as f:
                content = f.read()
                if symbol in content:
                    # Find lines with the symbol
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if symbol in line and ('fill' in line.lower() or 'limit' in line.lower()):
                            logs.append(f"Line {i+1}: {line[:200]}...")
    except Exception as e:
        print(f"Warning: Could not read trade history: {e}")
    
    return logs


async def get_position_and_orders(client, symbol, account_name):
    """Get current position and orders for a symbol"""
    try:
        # Get position
        pos_response = client.get_positions(
            category="linear",
            symbol=symbol,
            settleCoin="USDT"
        )
        
        position = None
        if pos_response['retCode'] == 0:
            positions = pos_response['result']['list']
            for pos in positions:
                if float(pos.get('size', 0)) > 0:
                    position = pos
                    break
        
        # Get orders
        orders_response = client.get_open_orders(
            category="linear",
            symbol=symbol,
            limit=50
        )
        
        orders = []
        if orders_response['retCode'] == 0:
            orders = orders_response['result']['list']
        
        return position, orders
        
    except Exception as e:
        print(f"❌ Error getting data for {symbol} ({account_name}): {e}")
        return None, []


def analyze_orders(orders, position_size, entry_price, side):
    """Analyze orders and categorize them"""
    if not orders:
        return {}, {}, {}
    
    tp_orders = []
    sl_orders = []
    limit_orders = []
    
    for order in orders:
        status = order.get('orderStatus', '')
        if status not in ['New', 'PartiallyFilled', 'Untriggered']:
            continue
            
        order_type = order.get('orderType', '')
        stop_type = order.get('stopOrderType', '')
        order_side = order.get('side', '')
        reduce_only = order.get('reduceOnly', False)
        
        order_data = {
            'qty': float(order.get('qty', 0)),
            'price': float(order.get('price', 0)),
            'triggerPrice': float(order.get('triggerPrice', 0)),
            'status': status,
            'orderType': order_type,
            'stopOrderType': stop_type
        }
        
        if reduce_only:
            if stop_type == 'TakeProfit':
                tp_orders.append(order_data)
            elif stop_type == 'StopLoss':
                sl_orders.append(order_data)
        elif not reduce_only and order_side == side:
            if order_type == 'Limit':
                limit_orders.append(order_data)
    
    return tp_orders, sl_orders, limit_orders


def calculate_conservative_quantities(total_size):
    """Calculate Conservative approach quantities (85%, 5%, 5%, 5%)"""
    total_size = float(total_size)
    
    tp1_qty = total_size * 0.85
    tp2_qty = total_size * 0.05
    tp3_qty = total_size * 0.05
    tp4_qty = total_size * 0.05
    sl_qty = total_size
    
    return {
        'tp1': tp1_qty,
        'tp2': tp2_qty,
        'tp3': tp3_qty,
        'tp4': tp4_qty,
        'sl': sl_qty
    }


async def investigate_symbol(symbol, expected_side="Sell"):
    """Investigate a specific symbol's order state"""
    
    print(f"\n{'='*80}")
    print(f"🔍 INVESTIGATING {symbol} ({expected_side})")
    print(f"{'='*80}")
    
    # Initialize clients
    main_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    mirror_client = None
    if ENABLE_MIRROR_TRADING and BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
        mirror_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2
        )
    
    # Load monitor data
    monitors = load_enhanced_monitors()
    
    main_monitor_key = f"{symbol}_{expected_side}"
    mirror_monitor_key = f"{symbol}_{expected_side}_MIRROR"
    
    main_monitor = monitors.get(main_monitor_key)
    mirror_monitor = monitors.get(mirror_monitor_key)
    
    print(f"\n📊 ENHANCED TP/SL MONITOR DATA:")
    print(f"   Main Monitor ({main_monitor_key}): {'✅ EXISTS' if main_monitor else '❌ MISSING'}")
    print(f"   Mirror Monitor ({mirror_monitor_key}): {'✅ EXISTS' if mirror_monitor else '❌ MISSING'}")
    
    if main_monitor:
        print(f"   Main Monitor Data:")
        print(f"      Position Size: {main_monitor.get('position_size', 'N/A')}")
        print(f"      Remaining Size: {main_monitor.get('remaining_size', 'N/A')}")
        print(f"      Entry Price: {main_monitor.get('entry_price', 'N/A')}")
        print(f"      Approach: {main_monitor.get('approach', 'N/A')}")
        print(f"      Phase: {main_monitor.get('phase', 'N/A')}")
        print(f"      TP1 Hit: {main_monitor.get('tp1_hit', 'N/A')}")
    
    if mirror_monitor:
        print(f"   Mirror Monitor Data:")
        print(f"      Position Size: {mirror_monitor.get('position_size', 'N/A')}")
        print(f"      Remaining Size: {mirror_monitor.get('remaining_size', 'N/A')}")
        print(f"      Entry Price: {mirror_monitor.get('entry_price', 'N/A')}")
        print(f"      Approach: {mirror_monitor.get('approach', 'N/A')}")
        print(f"      Phase: {mirror_monitor.get('phase', 'N/A')}")
        print(f"      TP1 Hit: {mirror_monitor.get('tp1_hit', 'N/A')}")
    
    # Get actual positions and orders
    print(f"\n📋 ACTUAL BYBIT DATA:")
    
    # Main account
    main_position, main_orders = await get_position_and_orders(main_client, symbol, "MAIN")
    
    if main_position:
        main_size = float(main_position.get('size', 0))
        main_entry = float(main_position.get('avgPrice', 0))
        main_side = main_position.get('side', '')
        
        print(f"   Main Account Position:")
        print(f"      Size: {main_size:,.1f}")
        print(f"      Entry Price: ${main_entry:.6f}")
        print(f"      Side: {main_side}")
        
        # Analyze orders
        tp_orders, sl_orders, limit_orders = analyze_orders(main_orders, main_size, main_entry, main_side)
        
        print(f"   Main Account Orders:")
        print(f"      TP Orders: {len(tp_orders)}")
        for i, tp in enumerate(tp_orders, 1):
            print(f"         TP{i}: {tp['qty']:,.1f} @ ${tp['triggerPrice']:.6f}")
        
        print(f"      SL Orders: {len(sl_orders)}")
        for sl in sl_orders:
            print(f"         SL: {sl['qty']:,.1f} @ ${sl['triggerPrice']:.6f}")
        
        print(f"      Limit Orders: {len(limit_orders)}")
        for i, limit in enumerate(limit_orders, 1):
            print(f"         Limit{i}: {limit['qty']:,.1f} @ ${limit['price']:.6f}")
        
        # Calculate what quantities should be
        expected_qtys = calculate_conservative_quantities(main_size)
        print(f"   Expected Conservative Quantities:")
        print(f"      TP1 (85%): {expected_qtys['tp1']:,.1f}")
        print(f"      TP2 (5%): {expected_qtys['tp2']:,.1f}")
        print(f"      TP3 (5%): {expected_qtys['tp3']:,.1f}")
        print(f"      TP4 (5%): {expected_qtys['tp4']:,.1f}")
        print(f"      SL (100%): {expected_qtys['sl']:,.1f}")
        
        # Compare with actual
        print(f"   Quantity Comparison:")
        if len(tp_orders) >= 1:
            diff1 = abs(tp_orders[0]['qty'] - expected_qtys['tp1'])
            status1 = "✅ MATCH" if diff1 < 0.1 else f"❌ MISMATCH ({diff1:,.1f} difference)"
            print(f"      TP1: {tp_orders[0]['qty']:,.1f} vs {expected_qtys['tp1']:,.1f} - {status1}")
        
        if len(sl_orders) >= 1:
            diff_sl = abs(sl_orders[0]['qty'] - expected_qtys['sl'])
            status_sl = "✅ MATCH" if diff_sl < 0.1 else f"❌ MISMATCH ({diff_sl:,.1f} difference)"
            print(f"      SL: {sl_orders[0]['qty']:,.1f} vs {expected_qtys['sl']:,.1f} - {status_sl}")
        
        # Check if monitor matches reality
        if main_monitor:
            monitor_size = float(main_monitor.get('remaining_size', 0))
            size_diff = abs(monitor_size - main_size)
            size_status = "✅ MATCH" if size_diff < 0.1 else f"❌ MISMATCH ({size_diff:,.1f} difference)"
            print(f"   Monitor vs Position Size: {monitor_size:,.1f} vs {main_size:,.1f} - {size_status}")
    
    else:
        print(f"   ❌ No main account position found for {symbol}")
    
    # Mirror account
    if mirror_client:
        mirror_position, mirror_orders = await get_position_and_orders(mirror_client, symbol, "MIRROR")
        
        if mirror_position:
            mirror_size = float(mirror_position.get('size', 0))
            mirror_entry = float(mirror_position.get('avgPrice', 0))
            mirror_side = mirror_position.get('side', '')
            
            print(f"   Mirror Account Position:")
            print(f"      Size: {mirror_size:,.1f}")
            print(f"      Entry Price: ${mirror_entry:.6f}")
            print(f"      Side: {mirror_side}")
            
            # Analyze orders
            tp_orders, sl_orders, limit_orders = analyze_orders(mirror_orders, mirror_size, mirror_entry, mirror_side)
            
            print(f"   Mirror Account Orders:")
            print(f"      TP Orders: {len(tp_orders)}")
            for i, tp in enumerate(tp_orders, 1):
                print(f"         TP{i}: {tp['qty']:,.1f} @ ${tp['triggerPrice']:.6f}")
            
            print(f"      SL Orders: {len(sl_orders)}")
            for sl in sl_orders:
                print(f"         SL: {sl['qty']:,.1f} @ ${sl['triggerPrice']:.6f}")
            
            print(f"      Limit Orders: {len(limit_orders)}")
            for i, limit in enumerate(limit_orders, 1):
                print(f"         Limit{i}: {limit['qty']:,.1f} @ ${limit['price']:.6f}")
            
            # Calculate what quantities should be
            expected_qtys = calculate_conservative_quantities(mirror_size)
            print(f"   Expected Conservative Quantities:")
            print(f"      TP1 (85%): {expected_qtys['tp1']:,.1f}")
            print(f"      TP2 (5%): {expected_qtys['tp2']:,.1f}")
            print(f"      TP3 (5%): {expected_qtys['tp3']:,.1f}")
            print(f"      TP4 (5%): {expected_qtys['tp4']:,.1f}")
            print(f"      SL (100%): {expected_qtys['sl']:,.1f}")
            
            # Compare with actual
            print(f"   Quantity Comparison:")
            if len(tp_orders) >= 1:
                diff1 = abs(tp_orders[0]['qty'] - expected_qtys['tp1'])
                status1 = "✅ MATCH" if diff1 < 0.1 else f"❌ MISMATCH ({diff1:,.1f} difference)"
                print(f"      TP1: {tp_orders[0]['qty']:,.1f} vs {expected_qtys['tp1']:,.1f} - {status1}")
            
            if len(sl_orders) >= 1:
                diff_sl = abs(sl_orders[0]['qty'] - expected_qtys['sl'])
                status_sl = "✅ MATCH" if diff_sl < 0.1 else f"❌ MISMATCH ({diff_sl:,.1f} difference)"
                print(f"      SL: {sl_orders[0]['qty']:,.1f} vs {expected_qtys['sl']:,.1f} - {status_sl}")
            
            # Check if monitor matches reality
            if mirror_monitor:
                monitor_size = float(mirror_monitor.get('remaining_size', 0))
                size_diff = abs(monitor_size - mirror_size)
                size_status = "✅ MATCH" if size_diff < 0.1 else f"❌ MISMATCH ({size_diff:,.1f} difference)"
                print(f"   Monitor vs Position Size: {monitor_size:,.1f} vs {mirror_size:,.1f} - {size_status}")
        
        else:
            print(f"   ❌ No mirror account position found for {symbol}")
    
    # Search for trade logs
    print(f"\n📚 TRADE LOG SEARCH:")
    logs = search_trade_logs(symbol)
    if logs:
        print(f"   Found {len(logs)} potentially relevant log entries:")
        for log in logs[:5]:  # Show first 5
            print(f"      {log}")
    else:
        print(f"   No relevant trade logs found for {symbol}")


async def main():
    """Main investigation function"""
    print("🔍 COMPREHENSIVE BANDUSDT AND XTZUSDT ORDER INVESTIGATION")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Check both symbols
    await investigate_symbol("BANDUSDT", "Sell")
    await investigate_symbol("XTZUSDT", "Sell")
    
    print(f"\n{'='*80}")
    print("📊 INVESTIGATION COMPLETE")
    print(f"{'='*80}")
    print("Key findings will be in the detailed output above.")
    print("Look for:")
    print("- ❌ MISMATCH indicators showing order quantity discrepancies")
    print("- Monitor vs Position Size mismatches")
    print("- Missing Enhanced TP/SL monitors")
    print("- Unexpected order quantities vs Conservative approach expectations")


if __name__ == "__main__":
    asyncio.run(main())