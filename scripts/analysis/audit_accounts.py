#!/usr/bin/env python3

import asyncio
import os
import sys
from datetime import datetime
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.getcwd())

from clients.bybit_helpers import get_all_positions, get_all_open_orders, api_call_with_retry
from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled

# Trading approach constants
FAST_MARKET_APPROACH = "fast"
CONSERVATIVE_APPROACH = "conservative"

async def analyze_account(account_name, is_mirror=False):
    """Analyze positions and orders for a specific account"""
    
    # Get positions
    if is_mirror:
        pos_response = await api_call_with_retry(
            lambda: bybit_client_2.get_positions(
                category="linear",
                settleCoin="USDT"
            ),
            timeout=30
        )
        positions = pos_response.get("result", {}).get("list", []) if pos_response and pos_response.get("retCode") == 0 else []
    else:
        positions = await get_all_positions()
    
    # Get all open orders
    if is_mirror:
        order_response = await api_call_with_retry(
            lambda: bybit_client_2.get_open_orders(
                category="linear",
                settleCoin="USDT",
                limit=200
            ),
            timeout=30
        )
        orders = order_response.get("result", {}).get("list", []) if order_response and order_response.get("retCode") == 0 else []
    else:
        orders = await get_all_open_orders()
    
    # Organize data by symbol and side
    position_map = {}
    order_map = defaultdict(list)
    
    # Filter active positions
    active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
    
    for pos in active_positions:
        key = f"{pos['symbol']}_{pos['side']}"
        position_map[key] = pos
    
    for order in orders:
        key = f"{order['symbol']}_{order['side']}"
        order_map[key].append(order)
    
    return position_map, order_map, active_positions, orders

def categorize_orders(orders, position_side):
    """Categorize orders into TP, SL, and Limit orders"""
    tp_orders = []
    sl_orders = []
    limit_orders = []
    
    for order in orders:
        order_link_id = order.get('orderLinkId', '').lower()
        order_type = order.get('orderType', '')
        trigger_price = order.get('triggerPrice', '')
        
        # Market orders with trigger prices are usually TP/SL
        if order_type == 'Market' and trigger_price:
            order_side = order.get('side')
            trigger_price_float = float(trigger_price)
            
            # For SELL positions, TP orders are BUY orders at lower prices, SL orders are BUY orders at higher prices
            # For BUY positions, TP orders are SELL orders at higher prices, SL orders are SELL orders at lower prices
            if 'tp' in order_link_id:
                tp_orders.append(order)
            elif 'sl' in order_link_id:
                sl_orders.append(order)
            else:
                # Categorize based on order side and trigger price logic
                if position_side == 'Sell' and order_side == 'Buy':
                    # For sell positions, buy orders are either TP (profit taking) or SL (stop loss)
                    # This requires additional logic based on trigger price relative to position entry price
                    tp_orders.append(order)  # Default to TP for now
                elif position_side == 'Buy' and order_side == 'Sell':
                    # For buy positions, sell orders are either TP or SL
                    tp_orders.append(order)  # Default to TP for now
                else:
                    sl_orders.append(order)
        else:
            limit_orders.append(order)
    
    return tp_orders, sl_orders, limit_orders

def detect_approach(tp_orders):
    """Detect trading approach from TP orders"""
    tp_count = len(tp_orders)
    
    if tp_count == 1:
        return FAST_MARKET_APPROACH
    elif tp_count == 4:
        return CONSERVATIVE_APPROACH
    else:
        return f"CUSTOM ({tp_count} TPs)"

async def main():
    print(f"\n{'='*80}")
    print(f"COMPREHENSIVE TRADING ACCOUNT AUDIT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")
    
    # Analyze main account
    print("MAIN ACCOUNT ANALYSIS")
    print("-"*80)
    main_positions, main_orders, main_pos_raw, main_ord_raw = await analyze_account('main', False)
    
    # Analyze mirror account
    print("\nMIRROR ACCOUNT ANALYSIS")
    print("-"*80)
    mirror_positions, mirror_orders, mirror_pos_raw, mirror_ord_raw = await analyze_account('mirror', True)
    
    # Detailed position and order analysis
    all_symbols = set(list(main_positions.keys()) + list(mirror_positions.keys()))
    
    issues_found = []
    
    for symbol_side in sorted(all_symbols):
        symbol, side = symbol_side.split('_')
        
        print(f"\n{'='*60}")
        print(f"SYMBOL: {symbol} | SIDE: {side}")
        print(f"{'='*60}")
        
        # Main account analysis
        if symbol_side in main_positions:
            pos = main_positions[symbol_side]
            orders = main_orders.get(symbol_side, [])
            
            print(f"\nMAIN ACCOUNT:")
            print(f"  Position Size: {pos['size']}")
            print(f"  Entry Price: {pos['avgPrice']}")
            print(f"  Mark Price: {pos['markPrice']}")
            pnl_value = float(pos['unrealisedPnl'])
            print(f"  Unrealized PnL: ${pnl_value:.2f}")
            
            # Categorize orders
            tp_orders = []
            sl_orders = []
            limit_orders = []
            
            for order in orders:
                order_link_id = order.get('orderLinkId', '').lower()
                trigger_direction = order.get('triggerDirection', 0)
                
                if 'tp' in order_link_id or trigger_direction == 1 or (trigger_direction == 2 and order.get('side') != side):
                    tp_orders.append(order)
                elif 'sl' in order_link_id or trigger_direction == 2 or (trigger_direction == 1 and order.get('side') != side):
                    sl_orders.append(order)
                else:
                    limit_orders.append(order)
            
            approach = detect_approach(tp_orders)
            print(f"  Detected Approach: {approach}")
            
            print(f"\n  Orders:")
            print(f"    Take Profit Orders: {len(tp_orders)}")
            for i, tp in enumerate(tp_orders, 1):
                trigger_price = tp.get('triggerPrice', tp.get('price'))
                print(f"      TP{i}: Qty={tp['qty']}, Price={trigger_price}, ID={tp['orderLinkId']}")
            
            print(f"    Stop Loss Orders: {len(sl_orders)}")
            for i, sl in enumerate(sl_orders, 1):
                trigger_price = sl.get('triggerPrice', sl.get('price'))
                print(f"      SL{i}: Qty={sl['qty']}, Price={trigger_price}, ID={sl['orderLinkId']}")
            
            if limit_orders:
                print(f"    Limit Orders: {len(limit_orders)}")
                for i, lo in enumerate(limit_orders, 1):
                    print(f"      Limit{i}: Qty={lo['qty']}, Price={lo['price']}, ID={lo['orderLinkId']}")
            
            # Verify quantities
            total_tp_qty = sum(float(o['qty']) for o in tp_orders)
            total_sl_qty = sum(float(o['qty']) for o in sl_orders)
            position_size = float(pos['size'])
            
            print(f"\n  Quantity Verification:")
            print(f"    Position Size: {position_size}")
            print(f"    Total TP Quantity: {total_tp_qty}")
            print(f"    Total SL Quantity: {total_sl_qty}")
            
            if abs(total_tp_qty - position_size) > 0.00001:
                issue = f"MAIN {symbol} {side}: TP quantity mismatch - Position: {position_size}, TP Total: {total_tp_qty}"
                issues_found.append(issue)
                print(f"    ⚠️  TP QUANTITY MISMATCH: Expected {position_size}, Got {total_tp_qty}")
            else:
                print(f"    ✅ TP quantities match position size")
            
            if abs(total_sl_qty - position_size) > 0.00001:
                issue = f"MAIN {symbol} {side}: SL quantity mismatch - Position: {position_size}, SL Total: {total_sl_qty}"
                issues_found.append(issue)
                print(f"    ⚠️  SL QUANTITY MISMATCH: Expected {position_size}, Got {total_sl_qty}")
            else:
                print(f"    ✅ SL quantities match position size")
            
            # Verify approach requirements
            if approach == FAST_MARKET_APPROACH:
                if len(tp_orders) != 1:
                    issue = f"MAIN {symbol} {side}: Fast approach should have 1 TP, found {len(tp_orders)}"
                    issues_found.append(issue)
                    print(f"    ⚠️  Fast approach should have exactly 1 TP order")
                if len(sl_orders) != 1:
                    issue = f"MAIN {symbol} {side}: Fast approach should have 1 SL, found {len(sl_orders)}"
                    issues_found.append(issue)
                    print(f"    ⚠️  Fast approach should have exactly 1 SL order")
            elif approach == CONSERVATIVE_APPROACH:
                if len(tp_orders) != 4:
                    issue = f"MAIN {symbol} {side}: Conservative approach should have 4 TPs, found {len(tp_orders)}"
                    issues_found.append(issue)
                    print(f"    ⚠️  Conservative approach should have exactly 4 TP orders")
                if len(sl_orders) != 1:
                    issue = f"MAIN {symbol} {side}: Conservative approach should have 1 SL, found {len(sl_orders)}"
                    issues_found.append(issue)
                    print(f"    ⚠️  Conservative approach should have exactly 1 SL order")
                
                # Verify conservative TP distribution (85%, 5%, 5%, 5%)
                if len(tp_orders) == 4:
                    expected_qtys = [position_size * 0.85, position_size * 0.05, position_size * 0.05, position_size * 0.05]
                    tp_qtys = sorted([float(o['qty']) for o in tp_orders], reverse=True)
                    
                    for i, (expected, actual) in enumerate(zip(expected_qtys, tp_qtys)):
                        if abs(expected - actual) > 0.00001:
                            print(f"    ⚠️  TP{i+1} quantity mismatch: Expected {expected:.8f}, Got {actual:.8f}")
            
            # Show individual order details
            print(f"\n  Individual Order Details:")
            for i, tp in enumerate(tp_orders, 1):
                trigger_price = tp.get('triggerPrice', tp.get('price'))
                pct_of_pos = (float(tp['qty']) / position_size) * 100
                print(f"    TP{i}: ${trigger_price} - Qty: {tp['qty']} ({pct_of_pos:.1f}% of position) - ID: {tp['orderLinkId']}")
            
            for i, sl in enumerate(sl_orders, 1):
                trigger_price = sl.get('triggerPrice', sl.get('price'))
                pct_of_pos = (float(sl['qty']) / position_size) * 100
                print(f"    SL{i}: ${trigger_price} - Qty: {sl['qty']} ({pct_of_pos:.1f}% of position) - ID: {sl['orderLinkId']}")
            
            if limit_orders:
                for i, lo in enumerate(limit_orders, 1):
                    pct_of_pos = (float(lo['qty']) / position_size) * 100
                    print(f"    Limit{i}: ${lo['price']} - Qty: {lo['qty']} ({pct_of_pos:.1f}% of position) - ID: {lo['orderLinkId']}")
        
        # Mirror account analysis
        if symbol_side in mirror_positions:
            pos = mirror_positions[symbol_side]
            orders = mirror_orders.get(symbol_side, [])
            
            print(f"\nMIRROR ACCOUNT:")
            print(f"  Position Size: {pos['size']}")
            print(f"  Entry Price: {pos['avgPrice']}")
            print(f"  Mark Price: {pos['markPrice']}")
            pnl_value = float(pos['unrealisedPnl'])
            print(f"  Unrealized PnL: ${pnl_value:.2f}")
            
            # Categorize orders
            tp_orders = []
            sl_orders = []
            limit_orders = []
            
            for order in orders:
                order_link_id = order.get('orderLinkId', '').lower()
                trigger_direction = order.get('triggerDirection', 0)
                
                if 'tp' in order_link_id or trigger_direction == 1 or (trigger_direction == 2 and order.get('side') != side):
                    tp_orders.append(order)
                elif 'sl' in order_link_id or trigger_direction == 2 or (trigger_direction == 1 and order.get('side') != side):
                    sl_orders.append(order)
                else:
                    limit_orders.append(order)
            
            approach = detect_approach(tp_orders)
            print(f"  Detected Approach: {approach}")
            
            print(f"\n  Orders:")
            print(f"    Take Profit Orders: {len(tp_orders)}")
            for i, tp in enumerate(tp_orders, 1):
                trigger_price = tp.get('triggerPrice', tp.get('price'))
                print(f"      TP{i}: Qty={tp['qty']}, Price={trigger_price}, ID={tp['orderLinkId']}")
            
            print(f"    Stop Loss Orders: {len(sl_orders)}")
            for i, sl in enumerate(sl_orders, 1):
                trigger_price = sl.get('triggerPrice', sl.get('price'))
                print(f"      SL{i}: Qty={sl['qty']}, Price={trigger_price}, ID={sl['orderLinkId']}")
            
            if limit_orders:
                print(f"    Limit Orders: {len(limit_orders)}")
                for i, lo in enumerate(limit_orders, 1):
                    print(f"      Limit{i}: Qty={lo['qty']}, Price={lo['price']}, ID={lo['orderLinkId']}")
            
            # Verify quantities
            total_tp_qty = sum(float(o['qty']) for o in tp_orders)
            total_sl_qty = sum(float(o['qty']) for o in sl_orders)
            position_size = float(pos['size'])
            
            print(f"\n  Quantity Verification:")
            print(f"    Position Size: {position_size}")
            print(f"    Total TP Quantity: {total_tp_qty}")
            print(f"    Total SL Quantity: {total_sl_qty}")
            
            if abs(total_tp_qty - position_size) > 0.00001:
                issue = f"MIRROR {symbol} {side}: TP quantity mismatch - Position: {position_size}, TP Total: {total_tp_qty}"
                issues_found.append(issue)
                print(f"    ⚠️  TP QUANTITY MISMATCH: Expected {position_size}, Got {total_tp_qty}")
            else:
                print(f"    ✅ TP quantities match position size")
            
            if abs(total_sl_qty - position_size) > 0.00001:
                issue = f"MIRROR {symbol} {side}: SL quantity mismatch - Position: {position_size}, SL Total: {total_sl_qty}"
                issues_found.append(issue)
                print(f"    ⚠️  SL QUANTITY MISMATCH: Expected {position_size}, Got {total_sl_qty}")
            else:
                print(f"    ✅ SL quantities match position size")
        
        # Cross-account comparison
        if symbol_side in main_positions and symbol_side in mirror_positions:
            main_pos = main_positions[symbol_side]
            mirror_pos = mirror_positions[symbol_side]
            
            print(f"\nCROSS-ACCOUNT COMPARISON:")
            print(f"  Main Position Size: {main_pos['size']}")
            print(f"  Mirror Position Size: {mirror_pos['size']}")
            
            # Check if mirror is proportional (could be same size or smaller)
            if float(mirror_pos['size']) > float(main_pos['size']):
                issue = f"{symbol} {side}: Mirror position larger than main - Main: {main_pos['size']}, Mirror: {mirror_pos['size']}"
                issues_found.append(issue)
                print(f"  ⚠️  Mirror position is larger than main position")
    
    # Summary
    print(f"\n{'='*80}")
    print("AUDIT SUMMARY")
    print(f"{'='*80}")
    
    print(f"\nMain Account:")
    print(f"  Total Positions: {len(main_positions)}")
    print(f"  Total Orders: {len(main_ord_raw)}")
    
    print(f"\nMirror Account:")
    print(f"  Total Positions: {len(mirror_positions)}")
    print(f"  Total Orders: {len(mirror_ord_raw)}")
    
    if issues_found:
        print(f"\n⚠️  ISSUES FOUND ({len(issues_found)}):")
        for i, issue in enumerate(issues_found, 1):
            print(f"  {i}. {issue}")
        
        print(f"\nRECOMMENDATIONS:")
        print("  1. For quantity mismatches: Run rebalance_positions_smart.py to fix order quantities")
        print("  2. For missing orders: Check if orders were manually cancelled or filled")
        print("  3. For approach mismatches: Verify the intended trading approach and recreate orders")
        print("  4. Consider enabling auto-rebalancer with /rebalancer_start to prevent future issues")
    else:
        print(f"\n✅ NO ISSUES FOUND - All positions and orders are properly configured")

if __name__ == '__main__':
    asyncio.run(main())