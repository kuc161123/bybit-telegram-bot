#!/usr/bin/env python3
"""
Debug script to find the source of the $337.3 TP1 calculation issue
"""
import asyncio
import logging
from decimal import Decimal
from dashboard.generator_analytics_compact import build_analytics_dashboard_text
from clients.bybit_helpers import get_all_positions, get_all_open_orders

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Focus on dashboard logger
dashboard_logger = logging.getLogger('dashboard.generator_analytics_compact')
dashboard_logger.setLevel(logging.WARNING)

async def debug_tp1_issue():
    """Debug the TP1 calculation showing $337.3 instead of correct value"""
    
    print("\n=== DEBUGGING TP1 $337.3 ISSUE ===\n")
    
    # Get actual positions and orders
    print("1. Fetching current positions...")
    positions = await get_all_positions()
    print(f"   Found {len(positions)} positions")
    
    # Show position details
    for pos in positions:
        symbol = pos.get('symbol', '')
        size = float(pos.get('size', 0))
        avg_price = float(pos.get('avgPrice', 0))
        side = pos.get('side', '')
        value = float(pos.get('positionValue', 0))
        print(f"   - {symbol}: {size} @ ${avg_price:.2f} ({side}) = ${value:.2f}")
    
    print("\n2. Fetching open orders...")
    orders = await get_all_open_orders()
    tp_orders = []
    
    # Filter TP orders
    for order in orders:
        trigger_price = order.get('triggerPrice', '')
        reduce_only = order.get('reduceOnly', False)
        
        if trigger_price and reduce_only:
            symbol = order.get('symbol', '')
            side = order.get('side', '')
            qty = float(order.get('qty', 0))
            price = float(trigger_price) if trigger_price else 0
            
            # Find matching position
            matching_pos = next((p for p in positions if p.get('symbol') == symbol), None)
            if matching_pos:
                pos_side = matching_pos.get('side', '')
                avg_price = float(matching_pos.get('avgPrice', 0))
                
                # Determine if it's a TP order
                is_tp = False
                if pos_side == 'Buy' and price > avg_price:
                    is_tp = True
                elif pos_side == 'Sell' and price < avg_price:
                    is_tp = True
                
                if is_tp:
                    tp_orders.append({
                        'symbol': symbol,
                        'qty': qty,
                        'price': price,
                        'pos_side': pos_side,
                        'avg_price': avg_price
                    })
    
    print(f"   Found {len(tp_orders)} TP orders")
    
    # Calculate TP1 profit manually
    print("\n3. Calculating TP1 profits manually...")
    total_tp1_profit = 0
    
    for i, tp in enumerate(tp_orders):
        if i == 0 or tp['symbol'] != tp_orders[i-1]['symbol']:  # First TP for each symbol
            profit = 0
            if tp['pos_side'] == 'Buy':
                profit = (tp['price'] - tp['avg_price']) * tp['qty']
            else:
                profit = (tp['avg_price'] - tp['price']) * tp['qty']
            
            total_tp1_profit += profit
            print(f"   - {tp['symbol']} TP1: {tp['qty']} @ ${tp['price']:.2f} = ${profit:.2f}")
    
    print(f"\n   MANUAL CALCULATION: Total TP1 profit = ${total_tp1_profit:.2f}")
    
    # Now build dashboard and extract TP1 value
    print("\n4. Building dashboard to see what it calculates...")
    
    class MockContext:
        def __init__(self):
            self.chat_data = {}
            self.bot_data = {}
    
    context = MockContext()
    dashboard = await build_analytics_dashboard_text(context.chat_data, context)
    
    # Extract TP1 value from dashboard
    lines = dashboard.split('\n')
    for line in lines:
        if 'TP1 Orders' in line:
            print(f"\n   DASHBOARD SHOWS: {line.strip()}")
            break
    
    # Check for discrepancy
    print("\n5. ANALYSIS:")
    print(f"   - Manual calculation: ${total_tp1_profit:.2f}")
    print("   - Dashboard shows: (see above)")
    print("   - User reports: $337.3")
    
    if abs(total_tp1_profit - 337.3) < 1:
        print("\n   ⚠️ The calculation matches what user sees!")
        print("   This suggests the issue is in the current state, not the code.")
    elif abs(total_tp1_profit * 2 - 337.3) < 1:
        print("\n   ⚠️ The user's value is exactly double!")
        print("   This suggests positions are being double-counted.")
    else:
        print("\n   ⚠️ The values don't match.")
        print("   Need to investigate further.")

if __name__ == "__main__":
    asyncio.run(debug_tp1_issue())