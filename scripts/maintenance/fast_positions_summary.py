#!/usr/bin/env python3
"""
Summary of fast approach positions and their TP/SL orders
Shows current vs expected trigger prices
"""

import asyncio
from decimal import Decimal
from clients.bybit_client import bybit_client
from clients.bybit_helpers import get_all_positions, get_all_open_orders
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled

async def analyze_fast_positions():
    """Analyze fast approach positions and their orders"""
    
    fast_symbols = ['ENAUSDT', 'TIAUSDT', 'WIFUSDT', 'JASMYUSDT', 'WLDUSDT', 'BTCUSDT']
    
    # Default percentages for fast approach
    default_tp_pct = Decimal('0.07')  # 7%
    default_sl_pct = Decimal('0.025')  # 2.5%
    
    print("\n" + "="*80)
    print("FAST APPROACH POSITIONS - TP/SL ANALYSIS")
    print("="*80)
    print(f"Expected TP: 7% profit | Expected SL: 2.5% loss")
    
    # Main account
    print(f"\n{'='*80}")
    print("MAIN ACCOUNT")
    print("="*80)
    
    positions = await get_all_positions()
    orders = await get_all_open_orders()
    
    for symbol in fast_symbols:
        pos = next((p for p in positions if p['symbol'] == symbol and float(p['size']) > 0), None)
        if not pos:
            continue
            
        side = pos['side']
        size = Decimal(pos['size'])
        avg_price = Decimal(pos['avgPrice'])
        current_price = Decimal(pos.get('markPrice', 0))
        unrealized_pnl = Decimal(pos.get('unrealisedPnl', 0))
        
        # Calculate expected TP/SL
        if side == 'Buy':
            expected_tp = avg_price * (Decimal('1') + default_tp_pct)
            expected_sl = avg_price * (Decimal('1') - default_sl_pct)
        else:
            expected_tp = avg_price * (Decimal('1') - default_tp_pct)
            expected_sl = avg_price * (Decimal('1') + default_sl_pct)
        
        # Get actual orders
        sym_orders = [o for o in orders if o['symbol'] == symbol and o.get('reduceOnly')]
        
        print(f"\n📊 {symbol} - {side} Position")
        print(f"   Size: {size} | Entry: ${avg_price}")
        print(f"   Current: ${current_price} | P&L: {'🟢' if unrealized_pnl >= 0 else '🔴'} ${unrealized_pnl:.2f}")
        
        # Find TP and SL from orders
        actual_tp = None
        actual_sl = None
        
        for order in sym_orders:
            trigger_price = Decimal(order.get('triggerPrice') or order.get('price', 0))
            qty = Decimal(order.get('qty', 0))
            
            if side == 'Buy':
                if trigger_price > avg_price:
                    actual_tp = trigger_price
                else:
                    actual_sl = trigger_price
            else:  # Sell
                if trigger_price < avg_price:
                    actual_tp = trigger_price
                else:
                    actual_sl = trigger_price
        
        print(f"\n   Expected vs Actual:")
        
        # TP Analysis
        if actual_tp:
            tp_diff_pct = abs((actual_tp - avg_price) / avg_price * 100)
            print(f"   TP: Expected ${expected_tp:.4f} (7.0%) | Actual ${actual_tp:.4f} ({tp_diff_pct:.1f}%)")
            if abs(tp_diff_pct - Decimal('7.0')) > Decimal('0.5'):
                print(f"       ⚠️  TP differs from expected by {abs(tp_diff_pct - Decimal('7.0')):.1f}%")
        else:
            print(f"   TP: Expected ${expected_tp:.4f} (7.0%) | ❌ MISSING")
        
        # SL Analysis
        if actual_sl:
            sl_diff_pct = abs((actual_sl - avg_price) / avg_price * 100)
            print(f"   SL: Expected ${expected_sl:.4f} (2.5%) | Actual ${actual_sl:.4f} ({sl_diff_pct:.1f}%)")
            if abs(sl_diff_pct - Decimal('2.5')) > Decimal('0.5'):
                print(f"       ⚠️  SL differs from expected by {abs(sl_diff_pct - Decimal('2.5')):.1f}%")
        else:
            print(f"   SL: Expected ${expected_sl:.4f} (2.5%) | ❌ MISSING")
    
    # Mirror account
    if is_mirror_trading_enabled():
        print(f"\n\n{'='*80}")
        print("MIRROR ACCOUNT")
        print("="*80)
        
        # Get mirror positions
        pos_response = bybit_client_2.get_positions(
            category="linear",
            settleCoin="USDT"
        )
        if pos_response and pos_response.get("retCode") == 0:
            mirror_positions = pos_response.get("result", {}).get("list", [])
            
            # Get mirror orders
            order_response = bybit_client_2.get_open_orders(
                category="linear",
                settleCoin="USDT",
                limit=200
            )
            mirror_orders = []
            if order_response and order_response.get("retCode") == 0:
                mirror_orders = order_response.get("result", {}).get("list", [])
            
            for symbol in fast_symbols:
                pos = next((p for p in mirror_positions if p['symbol'] == symbol and float(p['size']) > 0), None)
                if not pos:
                    continue
                    
                side = pos['side']
                size = Decimal(pos['size'])
                avg_price = Decimal(pos['avgPrice'])
                current_price = Decimal(pos.get('markPrice', 0))
                unrealized_pnl = Decimal(pos.get('unrealisedPnl', 0))
                
                # Calculate expected TP/SL
                if side == 'Buy':
                    expected_tp = avg_price * (Decimal('1') + default_tp_pct)
                    expected_sl = avg_price * (Decimal('1') - default_sl_pct)
                else:
                    expected_tp = avg_price * (Decimal('1') - default_tp_pct)
                    expected_sl = avg_price * (Decimal('1') + default_sl_pct)
                
                # Get actual orders
                sym_orders = [o for o in mirror_orders if o['symbol'] == symbol and o.get('reduceOnly')]
                
                print(f"\n📊 {symbol} - {side} Position")
                print(f"   Size: {size} | Entry: ${avg_price}")
                print(f"   Current: ${current_price} | P&L: {'🟢' if unrealized_pnl >= 0 else '🔴'} ${unrealized_pnl:.2f}")
                
                # Find TP and SL from orders
                actual_tp = None
                actual_sl = None
                
                for order in sym_orders:
                    trigger_price = Decimal(order.get('triggerPrice') or order.get('price', 0))
                    qty = Decimal(order.get('qty', 0))
                    
                    if side == 'Buy':
                        if trigger_price > avg_price:
                            actual_tp = trigger_price
                        else:
                            actual_sl = trigger_price
                    else:  # Sell
                        if trigger_price < avg_price:
                            actual_tp = trigger_price
                        else:
                            actual_sl = trigger_price
                
                print(f"\n   Expected vs Actual:")
                
                # TP Analysis
                if actual_tp:
                    tp_diff_pct = abs((actual_tp - avg_price) / avg_price * 100)
                    print(f"   TP: Expected ${expected_tp:.4f} (7.0%) | Actual ${actual_tp:.4f} ({tp_diff_pct:.1f}%)")
                    if abs(tp_diff_pct - Decimal('7.0')) > Decimal('0.5'):
                        print(f"       ⚠️  TP differs from expected by {abs(tp_diff_pct - Decimal('7.0')):.1f}%")
                else:
                    print(f"   TP: Expected ${expected_tp:.4f} (7.0%) | ❌ MISSING")
                
                # SL Analysis
                if actual_sl:
                    sl_diff_pct = abs((actual_sl - avg_price) / avg_price * 100)
                    print(f"   SL: Expected ${expected_sl:.4f} (2.5%) | Actual ${actual_sl:.4f} ({sl_diff_pct:.1f}%)")
                    if abs(sl_diff_pct - Decimal('2.5')) > Decimal('0.5'):
                        print(f"       ⚠️  SL differs from expected by {abs(sl_diff_pct - Decimal('2.5')):.1f}%")
                else:
                    print(f"   SL: Expected ${expected_sl:.4f} (2.5%) | ❌ MISSING")


async def main():
    await analyze_fast_positions()


if __name__ == "__main__":
    asyncio.run(main())