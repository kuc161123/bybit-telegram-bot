#!/usr/bin/env python3
"""
Comprehensive summary of positions and their TP/SL order status
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_helpers import get_all_positions, get_all_open_orders
from datetime import datetime

async def summarize_positions():
    # Get all positions
    positions = await get_all_positions()
    active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
    
    # Get all open orders
    all_orders = await get_all_open_orders()
    
    print(f"\n📊 POSITION TP/SL SUMMARY - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 120)
    
    # Group orders by symbol
    orders_by_symbol = {}
    for order in all_orders:
        symbol = order.get('symbol')
        if symbol not in orders_by_symbol:
            orders_by_symbol[symbol] = []
        orders_by_symbol[symbol].append(order)
    
    # Process each position
    results = []
    
    for pos in active_positions:
        symbol = pos.get('symbol')
        side = pos.get('side')
        size = float(pos.get('size', 0))
        avg_price = float(pos.get('avgPrice', 0))
        unrealized_pnl = float(pos.get('unrealisedPnl', 0))
        
        # Get orders for this symbol
        symbol_orders = orders_by_symbol.get(symbol, [])
        
        # Classify orders
        tp_orders = []
        sl_orders = []
        
        for order in symbol_orders:
            order_side = order.get('side')
            trigger_price_str = order.get('triggerPrice', '0')
            trigger_price = float(trigger_price_str) if trigger_price_str else 0
            
            # For long positions: TP = Sell above avg_price, SL = Sell below avg_price
            # For short positions: TP = Buy below avg_price, SL = Buy above avg_price
            if side == 'Buy':  # Long position
                if order_side == 'Sell':
                    if trigger_price > avg_price and trigger_price > 0:
                        tp_orders.append(order)
                    elif trigger_price < avg_price and trigger_price > 0:
                        sl_orders.append(order)
            else:  # Short position
                if order_side == 'Buy':
                    if trigger_price < avg_price and trigger_price > 0:
                        tp_orders.append(order)
                    elif trigger_price > avg_price and trigger_price > 0:
                        sl_orders.append(order)
        
        # Calculate totals
        total_tp_qty = sum(float(o.get('qty', 0)) for o in tp_orders)
        total_sl_qty = sum(float(o.get('qty', 0)) for o in sl_orders)
        
        # Detect approach
        approach = "Unknown"
        if tp_orders:
            if len(tp_orders) == 1:
                approach = "Fast"
            elif len(tp_orders) >= 3:
                sorted_tps = sorted(tp_orders, key=lambda x: float(x.get('qty', 0)), reverse=True)
                first_tp_qty = float(sorted_tps[0].get('qty', 0))
                first_tp_percent = (first_tp_qty / size * 100) if size > 0 else 0
                
                if 65 <= first_tp_percent <= 75:
                    approach = "Conservative"
                else:
                    approach = f"Custom-{len(tp_orders)}TP"
        
        # Check if quantities match
        tp_match = abs(total_tp_qty - size) < (size * 0.001)  # 0.1% tolerance
        sl_match = abs(total_sl_qty - size) < (size * 0.001)  # 0.1% tolerance
        
        results.append({
            'symbol': symbol,
            'side': side,
            'size': size,
            'avg_price': avg_price,
            'pnl': unrealized_pnl,
            'approach': approach,
            'tp_count': len(tp_orders),
            'tp_qty': total_tp_qty,
            'tp_match': tp_match,
            'sl_count': len(sl_orders),
            'sl_qty': total_sl_qty,
            'sl_match': sl_match,
            'has_issues': not (tp_match and sl_match and len(tp_orders) > 0 and len(sl_orders) > 0)
        })
    
    # Display results
    print(f"\n{'Symbol':<12} {'Side':<6} {'Size':<15} {'Avg Price':<10} {'PnL':<10} {'Approach':<15} {'TP Orders':<10} {'SL Orders':<10} {'Status':<15}")
    print("-" * 120)
    
    for r in results:
        tp_status = f"{r['tp_count']} ({'✓' if r['tp_match'] else '✗'})"
        sl_status = f"{r['sl_count']} ({'✓' if r['sl_match'] else '✗'})"
        overall_status = "❌ NEEDS FIX" if r['has_issues'] else "✅ OK"
        
        print(f"{r['symbol']:<12} {r['side']:<6} {r['size']:<15.4f} ${r['avg_price']:<9.4f} ${r['pnl']:<9.2f} {r['approach']:<15} {tp_status:<10} {sl_status:<10} {overall_status:<15}")
    
    # Summary
    total_positions = len(results)
    positions_with_issues = sum(1 for r in results if r['has_issues'])
    positions_ok = total_positions - positions_with_issues
    
    print("\n" + "=" * 120)
    print(f"SUMMARY: {total_positions} active positions")
    print(f"  ✅ Properly configured: {positions_ok}")
    print(f"  ❌ Need attention: {positions_with_issues}")
    
    if positions_with_issues > 0:
        print("\nISSUES BREAKDOWN:")
        for r in results:
            if r['has_issues']:
                issues = []
                if r['tp_count'] == 0:
                    issues.append("No TP orders")
                elif not r['tp_match']:
                    issues.append(f"TP qty mismatch ({r['tp_qty']:.4f} vs {r['size']:.4f})")
                
                if r['sl_count'] == 0:
                    issues.append("No SL orders")
                elif not r['sl_match']:
                    issues.append(f"SL qty mismatch ({r['sl_qty']:.4f} vs {r['size']:.4f})")
                
                print(f"  {r['symbol']}: {', '.join(issues)}")
        
        print("\n🔧 RECOMMENDATION: These positions need their TP/SL orders to be rebalanced or created.")
        print("   Use the bot's position management features to fix these issues.")

if __name__ == "__main__":
    asyncio.run(summarize_positions())