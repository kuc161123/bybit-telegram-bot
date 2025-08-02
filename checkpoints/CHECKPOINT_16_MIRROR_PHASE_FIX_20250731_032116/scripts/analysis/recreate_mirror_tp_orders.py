#!/usr/bin/env python3
"""
Recreate missing TP orders for mirror account positions
Based on the conservative approach (70%, 10%, 10%, 10%)
"""
import asyncio
import os
import sys
from decimal import Decimal, ROUND_DOWN
from datetime import datetime
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_helpers import api_call_with_retry
from execution.mirror_trader import (
    bybit_client_2, 
    is_mirror_trading_enabled, 
    get_mirror_positions,
    mirror_tp_sl_order,
    get_mirror_current_price
)

# ANSI color codes
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

# Conservative approach TP percentages
CONSERVATIVE_TP_PERCENTAGES = [0.7, 0.1, 0.1, 0.1]  # 70%, 10%, 10%, 10%

# TP price percentages from entry (rough estimates based on typical bot behavior)
TP_PRICE_PERCENTAGES = {
    "Buy": [1.02, 1.04, 1.06, 1.08],   # 2%, 4%, 6%, 8% above entry for longs
    "Sell": [0.98, 0.96, 0.94, 0.92]   # 2%, 4%, 6%, 8% below entry for shorts
}

async def create_tp_orders_for_position(position: Dict) -> List[Dict]:
    """Create TP orders for a position based on conservative approach"""
    symbol = position.get("symbol", "")
    side = position.get("side", "")
    size = Decimal(str(position.get("size", 0)))
    avg_price = float(position.get("avgPrice", 0))
    
    created_orders = []
    
    if size == 0 or avg_price == 0:
        return created_orders
    
    print(f"\n{Colors.CYAN}Creating TP orders for {symbol} {side} {size}...{Colors.RESET}")
    
    # Calculate TP quantities
    tp_quantities = []
    remaining_size = size
    
    for i, percentage in enumerate(CONSERVATIVE_TP_PERCENTAGES):
        if i == len(CONSERVATIVE_TP_PERCENTAGES) - 1:
            # Last TP gets all remaining quantity to avoid rounding issues
            qty = remaining_size
        else:
            qty = (size * Decimal(str(percentage))).quantize(Decimal("1"), rounding=ROUND_DOWN)
            remaining_size -= qty
        
        if qty > 0:
            tp_quantities.append(qty)
    
    # Calculate TP prices based on position side
    tp_multipliers = TP_PRICE_PERCENTAGES[side]
    tp_prices = [avg_price * mult for mult in tp_multipliers]
    
    # Get current price for better TP placement
    current_price = await get_mirror_current_price(symbol)
    if current_price:
        # Adjust TP prices if current price has moved significantly
        if side == "Buy" and current_price > avg_price * 1.01:
            # Price has moved up, adjust TPs higher
            adjustment = (current_price - avg_price) * 0.5
            tp_prices = [p + adjustment for p in tp_prices]
        elif side == "Sell" and current_price < avg_price * 0.99:
            # Price has moved down, adjust TPs lower
            adjustment = (avg_price - current_price) * 0.5
            tp_prices = [p - adjustment for p in tp_prices]
    
    # Create TP orders
    opposite_side = "Sell" if side == "Buy" else "Buy"
    
    for i, (qty, price) in enumerate(zip(tp_quantities, tp_prices)):
        if qty <= 0:
            continue
            
        # Format price based on tick size (guessing 4-6 decimals)
        if symbol in ["JASMYUSDT"]:
            price_str = f"{price:.6f}"
        elif symbol in ["COTIUSDT", "GALAUSDT"]:
            price_str = f"{price:.5f}"
        else:
            price_str = f"{price:.4f}"
        
        order_link_id = f"{symbol}_{side}_TP{i+1}_RECREATED_{int(datetime.now().timestamp())}"
        
        print(f"  Creating TP{i+1}: {opposite_side} {qty} @ ${price_str}...")
        
        result = await mirror_tp_sl_order(
            symbol=symbol,
            side=opposite_side,
            qty=str(qty),
            trigger_price=price_str,
            position_idx=0,  # Will be auto-detected
            order_type="Market",
            reduce_only=True,
            order_link_id=order_link_id
        )
        
        if result:
            print(f"    {Colors.GREEN}✅ Created successfully{Colors.RESET}")
            created_orders.append({
                "tp_num": i+1,
                "qty": qty,
                "price": price_str,
                "order_id": result.get("orderId", "")
            })
        else:
            print(f"    {Colors.RED}❌ Failed to create{Colors.RESET}")
        
        await asyncio.sleep(0.5)  # Brief delay between orders
    
    return created_orders

async def main():
    """Main function to recreate TP orders"""
    if not is_mirror_trading_enabled() or not bybit_client_2:
        print(f"{Colors.RED}❌ Mirror trading is not enabled or configured{Colors.RESET}")
        return
    
    print(f"{Colors.BOLD}{Colors.CYAN}MIRROR ACCOUNT TP ORDER RECREATION TOOL{Colors.RESET}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{Colors.YELLOW}This tool will create missing TP orders using conservative approach{Colors.RESET}")
    print(f"TP Distribution: 70%, 10%, 10%, 10%\n")
    
    try:
        # Get all positions
        positions = await get_mirror_positions()
        
        if not positions:
            print(f"{Colors.YELLOW}No active positions found.{Colors.RESET}")
            return
        
        print(f"Found {len(positions)} active position(s)")
        
        all_created = []
        
        for position in positions:
            symbol = position.get("symbol", "")
            side = position.get("side", "")
            size = position.get("size", 0)
            avg_price = position.get("avgPrice", 0)
            
            print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
            print(f"{Colors.BOLD}{symbol} - {side} {size} @ ${avg_price}{Colors.RESET}")
            print(f"{'='*60}")
            
            created = await create_tp_orders_for_position(position)
            all_created.extend(created)
        
        # Summary
        print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}SUMMARY{Colors.RESET}")
        print(f"{'='*60}")
        
        if all_created:
            print(f"{Colors.GREEN}✅ Successfully created {len(all_created)} TP orders{Colors.RESET}")
            
            # Group by position
            by_symbol = {}
            for order in all_created:
                symbol = order.get("symbol", "Unknown")
                if symbol not in by_symbol:
                    by_symbol[symbol] = []
                by_symbol[symbol].append(order)
            
        else:
            print(f"{Colors.YELLOW}No TP orders were created{Colors.RESET}")
        
        print(f"\n{Colors.YELLOW}⚠️  Please verify the TP orders in your trading interface{Colors.RESET}")
        
    except Exception as e:
        print(f"{Colors.RED}❌ Error: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())