#!/usr/bin/env python3
"""
Show all open positions on main account with complete order details.
Fixed version that handles empty trigger prices properly.
"""

import asyncio
import os
import sys
import json
from datetime import datetime
from decimal import Decimal
from collections import defaultdict
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()


async def show_all_positions():
    """Show all positions with complete order information."""
    
    print("📊 Main Account - Complete Position and Order Status")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    from pybit.unified_trading import HTTP
    from config.settings import (
        BYBIT_API_KEY, BYBIT_API_SECRET,
        USE_TESTNET
    )
    
    if not all([BYBIT_API_KEY, BYBIT_API_SECRET]):
        print("❌ API credentials not configured")
        return
    
    # Initialize client
    client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    # Get all positions
    print("\n📋 Fetching all positions...")
    try:
        response = client.get_positions(
            category="linear",
            settleCoin="USDT"
        )
        
        if response['retCode'] != 0:
            print(f"❌ Error: {response['retMsg']}")
            return
        
        all_positions = response['result']['list']
        active_positions = [p for p in all_positions if float(p.get('size', 0)) > 0]
        
        print(f"Found {len(active_positions)} active position(s)\n")
        
        if not active_positions:
            print("✅ No active positions")
            return
        
        # Process each position
        position_summary = []
        total_issues = 0
        
        for pos in active_positions:
            symbol = pos['symbol']
            side = pos['side']
            size = float(pos['size'])
            avg_price = float(pos.get('avgPrice', 0))
            mark_price = float(pos.get('markPrice', 0))
            pnl = float(pos.get('unrealisedPnl', 0))
            position_idx = pos.get('positionIdx', 0)
            
            print(f"\n{'='*70}")
            print(f"🔸 {symbol} {side}")
            print(f"{'='*70}")
            print(f"   Size: {size:,.0f} units")
            print(f"   Entry: ${avg_price:.4f}")
            print(f"   Current: ${mark_price:.4f}")
            print(f"   P&L: ${pnl:,.2f}")
            print(f"   Position Index: {position_idx}")
            
            # Get all orders for this symbol
            try:
                order_resp = client.get_open_orders(
                    category="linear",
                    symbol=symbol,
                    openOnly=0,  # Get all orders
                    limit=50
                )
                
                if order_resp['retCode'] == 0:
                    all_orders = order_resp['result']['list']
                    
                    # Filter active orders and categorize
                    tp_orders = []
                    sl_orders = []
                    
                    for order in all_orders:
                        status = order.get('orderStatus', '')
                        
                        # Only consider active orders
                        if status not in ['New', 'PartiallyFilled', 'Untriggered']:
                            continue
                        
                        # Check if it's a reduce order
                        if not order.get('reduceOnly'):
                            continue
                        
                        # Get trigger price safely
                        trigger_price_str = order.get('triggerPrice', '')
                        if not trigger_price_str or trigger_price_str == '' or trigger_price_str == '0':
                            continue
                        
                        try:
                            trigger_price = float(trigger_price_str)
                            qty = float(order.get('qty', 0))
                            order_idx = order.get('positionIdx', 0)
                            
                            # Categorize as TP or SL
                            if side == 'Buy':
                                if trigger_price > avg_price:
                                    tp_orders.append({
                                        'price': trigger_price,
                                        'qty': qty,
                                        'idx': order_idx
                                    })
                                else:
                                    sl_orders.append({
                                        'price': trigger_price,
                                        'qty': qty,
                                        'idx': order_idx
                                    })
                            else:  # Sell
                                if trigger_price < avg_price:
                                    tp_orders.append({
                                        'price': trigger_price,
                                        'qty': qty,
                                        'idx': order_idx
                                    })
                                else:
                                    sl_orders.append({
                                        'price': trigger_price,
                                        'qty': qty,
                                        'idx': order_idx
                                    })
                        except ValueError:
                            continue
                    
                    # Sort orders
                    if side == 'Buy':
                        tp_orders.sort(key=lambda x: x['price'])
                    else:
                        tp_orders.sort(key=lambda x: x['price'], reverse=True)
                    
                    # Display orders
                    print(f"\n   📈 Take Profits: {len(tp_orders)}")
                    for i, tp in enumerate(tp_orders):
                        print(f"      TP{i+1}: ${tp['price']:.4f} for {tp['qty']:,.0f} units")
                    
                    print(f"\n   🛡️ Stop Losses: {len(sl_orders)}")
                    for sl in sl_orders:
                        print(f"      SL: ${sl['price']:.4f} for {sl['qty']:,.0f} units")
                    
                    # Check for issues
                    issues = []
                    if len(tp_orders) != 4:
                        issues.append(f"Expected 4 TPs, found {len(tp_orders)}")
                    if len(sl_orders) != 1:
                        issues.append(f"Expected 1 SL, found {len(sl_orders)}")
                    
                    if issues:
                        print(f"\n   ⚠️ ISSUES:")
                        for issue in issues:
                            print(f"      - {issue}")
                        total_issues += 1
                    else:
                        print(f"\n   ✅ Orders look good (4 TPs + 1 SL)")
                    
                    # Add to summary
                    position_summary.append({
                        'symbol': symbol,
                        'side': side,
                        'size': size,
                        'pnl': pnl,
                        'tp_count': len(tp_orders),
                        'sl_count': len(sl_orders),
                        'has_issues': len(issues) > 0
                    })
                    
            except Exception as e:
                print(f"\n   ❌ Error fetching orders: {e}")
                position_summary.append({
                    'symbol': symbol,
                    'side': side,
                    'size': size,
                    'pnl': pnl,
                    'tp_count': 0,
                    'sl_count': 0,
                    'has_issues': True
                })
                total_issues += 1
        
        # Final summary
        print(f"\n\n{'='*70}")
        print("📊 POSITION SUMMARY")
        print(f"{'='*70}")
        
        total_pnl = 0
        print(f"\n{'Symbol':<12} {'Side':<6} {'Size':>10} {'P&L':>10} {'TPs':>4} {'SLs':>4} {'Status':<10}")
        print("-" * 70)
        
        for pos in position_summary:
            total_pnl += pos['pnl']
            status = "⚠️ ISSUE" if pos['has_issues'] else "✅ OK"
            
            print(f"{pos['symbol']:<12} {pos['side']:<6} {pos['size']:>10,.0f} "
                  f"${pos['pnl']:>9,.2f} {pos['tp_count']:>4} {pos['sl_count']:>4} {status:<10}")
        
        print("-" * 70)
        print(f"{'TOTAL':<12} {'':<6} {'':<10} ${total_pnl:>9,.2f}")
        
        print(f"\n📊 Summary:")
        print(f"   Total Positions: {len(position_summary)}")
        print(f"   Positions with Issues: {total_issues}")
        print(f"   Total Unrealized P&L: ${total_pnl:,.2f}")
        
        # List positions needing attention
        if total_issues > 0:
            print(f"\n⚠️ Positions Needing Attention:")
            for pos in position_summary:
                if pos['has_issues']:
                    print(f"   - {pos['symbol']} {pos['side']}: {pos['tp_count']} TPs, {pos['sl_count']} SLs")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main function."""
    await show_all_positions()


if __name__ == "__main__":
    asyncio.run(main())