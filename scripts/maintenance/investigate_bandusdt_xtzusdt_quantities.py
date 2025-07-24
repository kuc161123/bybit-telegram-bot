#!/usr/bin/env python3
"""
Comprehensive Investigation of BANDUSDT and XTZUSDT Order Quantities
Check current positions vs TP/SL order quantities for both main and mirror accounts
"""
import asyncio
import sys
import os
import pickle
from decimal import Decimal
from typing import Dict, List

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

async def investigate_order_quantities():
    """Investigate current order quantities vs expected quantities"""
    try:
        print("🔍 COMPREHENSIVE BANDUSDT & XTZUSDT ORDER QUANTITY INVESTIGATION")
        print("=" * 80)
        
        # Import required modules
        from clients.bybit_helpers import get_all_positions_with_client, get_all_open_orders
        from clients.bybit_client import bybit_client
        from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
        
        # 1. GET CURRENT POSITIONS
        print("\n📊 STEP 1: CURRENT POSITIONS")
        print("-" * 40)
        
        main_positions = await get_all_positions_with_client(bybit_client)
        main_open = [p for p in main_positions if float(p.get('size', 0)) > 0]
        
        mirror_open = []
        if is_mirror_trading_enabled() and bybit_client_2:
            mirror_positions = await get_all_positions_with_client(bybit_client_2)
            mirror_open = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
        
        # Find BANDUSDT and XTZUSDT positions
        target_symbols = ['BANDUSDT', 'XTZUSDT']
        position_data = {}
        
        for symbol in target_symbols:
            # Main account
            for pos in main_open:
                if pos.get('symbol') == symbol:
                    position_data[f"{symbol}_main"] = {
                        'size': Decimal(str(pos.get('size', '0'))),
                        'avgPrice': Decimal(str(pos.get('avgPrice', '0'))),
                        'side': pos.get('side', ''),
                        'unrealisedPnl': pos.get('unrealisedPnl', '0'),
                        'markPrice': pos.get('markPrice', '0')
                    }
                    print(f"✅ {symbol} MAIN: {pos.get('size')} @ {pos.get('avgPrice')} ({pos.get('side')})")
                    break
            
            # Mirror account
            for pos in mirror_open:
                if pos.get('symbol') == symbol:
                    position_data[f"{symbol}_mirror"] = {
                        'size': Decimal(str(pos.get('size', '0'))),
                        'avgPrice': Decimal(str(pos.get('avgPrice', '0'))),
                        'side': pos.get('side', ''),
                        'unrealisedPnl': pos.get('unrealisedPnl', '0'),
                        'markPrice': pos.get('markPrice', '0')
                    }
                    print(f"✅ {symbol} MIRROR: {pos.get('size')} @ {pos.get('avgPrice')} ({pos.get('side')})")
                    break
        
        # 2. GET CURRENT ORDERS
        print("\n📋 STEP 2: CURRENT ORDERS")
        print("-" * 40)
        
        main_orders = await get_all_open_orders(bybit_client)
        mirror_orders = []
        if is_mirror_trading_enabled() and bybit_client_2:
            mirror_orders = await get_all_open_orders(bybit_client_2)
        
        order_data = {}
        
        for symbol in target_symbols:
            order_data[symbol] = {
                'main': {'tp_orders': [], 'sl_orders': [], 'limit_orders': []},
                'mirror': {'tp_orders': [], 'sl_orders': [], 'limit_orders': []}
            }
            
            # Process main account orders
            for order in main_orders:
                if order.get('symbol') == symbol and order.get('orderStatus') == 'New':
                    order_type = order.get('orderType', '')
                    stop_order_type = order.get('stopOrderType', '')
                    qty = Decimal(str(order.get('qty', '0')))
                    price = order.get('price', '0')
                    trigger_price = order.get('triggerPrice', '0')
                    
                    if 'TP' in order.get('orderLinkId', ''):
                        order_data[symbol]['main']['tp_orders'].append({
                            'qty': qty, 'price': price, 'triggerPrice': trigger_price,
                            'orderLinkId': order.get('orderLinkId', ''), 'orderType': order_type
                        })
                    elif 'SL' in order.get('orderLinkId', ''):
                        order_data[symbol]['main']['sl_orders'].append({
                            'qty': qty, 'price': price, 'triggerPrice': trigger_price,
                            'orderLinkId': order.get('orderLinkId', ''), 'orderType': order_type
                        })
                    elif 'LIMIT' in order.get('orderLinkId', ''):
                        order_data[symbol]['main']['limit_orders'].append({
                            'qty': qty, 'price': price,
                            'orderLinkId': order.get('orderLinkId', ''), 'orderType': order_type
                        })
            
            # Process mirror account orders
            for order in mirror_orders:
                if order.get('symbol') == symbol and order.get('orderStatus') == 'New':
                    order_type = order.get('orderType', '')
                    qty = Decimal(str(order.get('qty', '0')))
                    price = order.get('price', '0')
                    trigger_price = order.get('triggerPrice', '0')
                    
                    if 'TP' in order.get('orderLinkId', ''):
                        order_data[symbol]['mirror']['tp_orders'].append({
                            'qty': qty, 'price': price, 'triggerPrice': trigger_price,
                            'orderLinkId': order.get('orderLinkId', ''), 'orderType': order_type
                        })
                    elif 'SL' in order.get('orderLinkId', ''):
                        order_data[symbol]['mirror']['sl_orders'].append({
                            'qty': qty, 'price': price, 'triggerPrice': trigger_price,
                            'orderLinkId': order.get('orderLinkId', ''), 'orderType': order_type
                        })
                    elif 'LIMIT' in order.get('orderLinkId', ''):
                        order_data[symbol]['mirror']['limit_orders'].append({
                            'qty': qty, 'price': price,
                            'orderLinkId': order.get('orderLinkId', ''), 'orderType': order_type
                        })
        
        # Display current orders
        for symbol in target_symbols:
            if f"{symbol}_main" in position_data or f"{symbol}_mirror" in position_data:
                print(f"\n📋 {symbol} ORDERS:")
                
                # Main account orders
                if f"{symbol}_main" in position_data:
                    print(f"  MAIN ACCOUNT:")
                    print(f"    TP Orders: {len(order_data[symbol]['main']['tp_orders'])}")
                    for i, tp in enumerate(order_data[symbol]['main']['tp_orders'], 1):
                        print(f"      TP{i}: {tp['qty']} @ {tp.get('triggerPrice', tp.get('price'))} ({tp['orderLinkId']})")
                    
                    print(f"    SL Orders: {len(order_data[symbol]['main']['sl_orders'])}")
                    for sl in order_data[symbol]['main']['sl_orders']:
                        print(f"      SL: {sl['qty']} @ {sl.get('triggerPrice', sl.get('price'))} ({sl['orderLinkId']})")
                    
                    print(f"    Limit Orders: {len(order_data[symbol]['main']['limit_orders'])}")
                    for limit in order_data[symbol]['main']['limit_orders']:
                        print(f"      LIMIT: {limit['qty']} @ {limit['price']} ({limit['orderLinkId']})")
                
                # Mirror account orders
                if f"{symbol}_mirror" in position_data:
                    print(f"  MIRROR ACCOUNT:")
                    print(f"    TP Orders: {len(order_data[symbol]['mirror']['tp_orders'])}")
                    for i, tp in enumerate(order_data[symbol]['mirror']['tp_orders'], 1):
                        print(f"      TP{i}: {tp['qty']} @ {tp.get('triggerPrice', tp.get('price'))} ({tp['orderLinkId']})")
                    
                    print(f"    SL Orders: {len(order_data[symbol]['mirror']['sl_orders'])}")
                    for sl in order_data[symbol]['mirror']['sl_orders']:
                        print(f"      SL: {sl['qty']} @ {sl.get('triggerPrice', sl.get('price'))} ({sl['orderLinkId']})")
                    
                    print(f"    Limit Orders: {len(order_data[symbol]['mirror']['limit_orders'])}")
                    for limit in order_data[symbol]['mirror']['limit_orders']:
                        print(f"      LIMIT: {limit['qty']} @ {limit['price']} ({limit['orderLinkId']})")
        
        # 3. CHECK ENHANCED TP/SL MONITOR DATA
        print("\n🔍 STEP 3: ENHANCED TP/SL MONITOR DATA")
        print("-" * 40)
        
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        monitor_data = {}
        for symbol in target_symbols:
            for account in ['main', 'mirror']:
                account_suffix = '_MIRROR' if account == 'mirror' else ''
                monitor_key = f"{symbol}_Sell{account_suffix}"
                
                if monitor_key in monitors:
                    monitor = monitors[monitor_key]
                    monitor_data[f"{symbol}_{account}"] = {
                        'position_size': monitor.get('position_size', Decimal('0')),
                        'remaining_size': monitor.get('remaining_size', Decimal('0')),
                        'entry_price': monitor.get('entry_price', Decimal('0')),
                        'tp_prices': monitor.get('tp_prices', []),
                        'tp_percentages': monitor.get('tp_percentages', []),
                        'sl_price': monitor.get('sl_price', Decimal('0')),
                        'monitoring_active': monitor.get('monitoring_active', False)
                    }
                    print(f"✅ {symbol} {account.upper()} MONITOR:")
                    print(f"    Position Size: {monitor.get('position_size', 'N/A')}")
                    print(f"    Remaining Size: {monitor.get('remaining_size', 'N/A')}")
                    print(f"    Entry Price: {monitor.get('entry_price', 'N/A')}")
                    print(f"    Monitoring Active: {monitor.get('monitoring_active', False)}")
                else:
                    print(f"❌ {symbol} {account.upper()} MONITOR: NOT FOUND")
        
        # 4. CALCULATE EXPECTED QUANTITIES (CONSERVATIVE APPROACH)
        print("\n📊 STEP 4: EXPECTED VS ACTUAL QUANTITY ANALYSIS")
        print("-" * 40)
        
        for symbol in target_symbols:
            if f"{symbol}_main" in position_data or f"{symbol}_mirror" in position_data:
                print(f"\n📊 {symbol} QUANTITY ANALYSIS:")
                
                for account in ['main', 'mirror']:
                    pos_key = f"{symbol}_{account}"
                    if pos_key in position_data:
                        current_size = position_data[pos_key]['size']
                        
                        # Conservative approach quantities (85%, 5%, 5%, 5%)
                        expected_tp1 = current_size * Decimal('0.85')  # 85%
                        expected_tp2 = current_size * Decimal('0.05')  # 5%
                        expected_tp3 = current_size * Decimal('0.05')  # 5%
                        expected_tp4 = current_size * Decimal('0.05')  # 5%
                        expected_sl = current_size  # 100%
                        
                        print(f"\n  {account.upper()} ACCOUNT - Current Position Size: {current_size}")
                        print(f"    EXPECTED QUANTITIES (Conservative Approach):")
                        print(f"      TP1 (85%): {expected_tp1}")
                        print(f"      TP2 (5%):  {expected_tp2}")
                        print(f"      TP3 (5%):  {expected_tp3}")
                        print(f"      TP4 (5%):  {expected_tp4}")
                        print(f"      SL (100%): {expected_sl}")
                        
                        # Compare with actual orders
                        actual_orders = order_data[symbol][account]
                        print(f"    ACTUAL ORDER QUANTITIES:")
                        
                        tp_orders = actual_orders['tp_orders']
                        sl_orders = actual_orders['sl_orders']
                        
                        if tp_orders:
                            for i, tp in enumerate(tp_orders, 1):
                                expected = [expected_tp1, expected_tp2, expected_tp3, expected_tp4][i-1] if i <= 4 else Decimal('0')
                                match = "✅" if tp['qty'] == expected else "❌"
                                print(f"      TP{i}: {tp['qty']} (expected: {expected}) {match}")
                        else:
                            print(f"      TP Orders: NONE FOUND ❌")
                        
                        if sl_orders:
                            for sl in sl_orders:
                                match = "✅" if sl['qty'] == expected_sl else "❌"
                                print(f"      SL: {sl['qty']} (expected: {expected_sl}) {match}")
                        else:
                            print(f"      SL Orders: NONE FOUND ❌")
                        
                        # Check monitor data accuracy
                        if pos_key in monitor_data:
                            monitor_size = monitor_data[pos_key]['position_size']
                            monitor_match = "✅" if monitor_size == current_size else "❌"
                            print(f"    MONITOR DATA:")
                            print(f"      Monitor Position Size: {monitor_size} {monitor_match}")
                            print(f"      Monitor Active: {monitor_data[pos_key]['monitoring_active']}")
                        else:
                            print(f"    MONITOR DATA: NOT FOUND ❌")
        
        # 5. SUMMARY AND RECOMMENDATIONS
        print("\n📋 STEP 5: SUMMARY AND RECOMMENDATIONS")
        print("-" * 40)
        
        issues_found = []
        
        for symbol in target_symbols:
            for account in ['main', 'mirror']:
                pos_key = f"{symbol}_{account}"
                if pos_key in position_data:
                    current_size = position_data[pos_key]['size']
                    
                    # Check if orders exist and have correct quantities
                    actual_orders = order_data[symbol][account]
                    
                    # Expected quantities
                    expected_quantities = [
                        current_size * Decimal('0.85'),  # TP1
                        current_size * Decimal('0.05'),  # TP2
                        current_size * Decimal('0.05'),  # TP3
                        current_size * Decimal('0.05'),  # TP4
                        current_size  # SL
                    ]
                    
                    # Check TP orders
                    tp_orders = actual_orders['tp_orders']
                    if len(tp_orders) != 4:
                        issues_found.append(f"{symbol} {account}: Expected 4 TP orders, found {len(tp_orders)}")
                    else:
                        for i, tp in enumerate(tp_orders):
                            if tp['qty'] != expected_quantities[i]:
                                issues_found.append(f"{symbol} {account} TP{i+1}: Expected {expected_quantities[i]}, found {tp['qty']}")
                    
                    # Check SL orders
                    sl_orders = actual_orders['sl_orders']
                    if len(sl_orders) != 1:
                        issues_found.append(f"{symbol} {account}: Expected 1 SL order, found {len(sl_orders)}")
                    elif sl_orders[0]['qty'] != expected_quantities[4]:
                        issues_found.append(f"{symbol} {account} SL: Expected {expected_quantities[4]}, found {sl_orders[0]['qty']}")
                    
                    # Check monitor data
                    if pos_key in monitor_data:
                        monitor_size = monitor_data[pos_key]['position_size']
                        if monitor_size != current_size:
                            issues_found.append(f"{symbol} {account} Monitor: Position size mismatch - Monitor: {monitor_size}, Actual: {current_size}")
                    else:
                        issues_found.append(f"{symbol} {account}: Enhanced TP/SL monitor not found")
        
        if issues_found:
            print("❌ ISSUES FOUND:")
            for issue in issues_found:
                print(f"   • {issue}")
                
            print("\n🔧 RECOMMENDED FIXES:")
            print("   1. Update monitor position sizes to match actual positions")
            print("   2. Recreate TP/SL orders with correct quantities")
            print("   3. Fix Enhanced TP/SL system to auto-adjust on limit fills")
            print("   4. Apply fixes to both main and mirror accounts")
        else:
            print("✅ NO ISSUES FOUND - All order quantities match expected values")
        
        print("\n" + "=" * 80)
        print("🔍 INVESTIGATION COMPLETE")
        
    except Exception as e:
        print(f"❌ Error during investigation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(investigate_order_quantities())