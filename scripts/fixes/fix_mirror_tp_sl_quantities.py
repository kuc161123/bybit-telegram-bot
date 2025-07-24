#!/usr/bin/env python3
"""
Fix mirror account TP/SL quantity mismatches.
This script will:
1. Analyze current positions and their TP/SL orders
2. Cancel orders with incorrect quantities
3. Recreate them with correct quantities matching position sizes
"""
import asyncio
import os
import sys
from decimal import Decimal, ROUND_DOWN
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_helpers import api_call_with_retry
from execution.mirror_trader import (
    bybit_client_2, 
    is_mirror_trading_enabled, 
    get_mirror_positions,
    mirror_tp_sl_order,
    cancel_mirror_order,
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

async def get_all_mirror_orders() -> List[Dict]:
    """Fetch all open orders from mirror account"""
    if not is_mirror_trading_enabled() or not bybit_client_2:
        return []
    
    all_orders = []
    cursor = None
    page_count = 0
    
    while page_count < 10:
        page_count += 1
        
        params = {
            "category": "linear",
            "settleCoin": "USDT",
            "limit": 200
        }
        
        if cursor:
            params["cursor"] = cursor
        
        try:
            response = await api_call_with_retry(
                lambda: bybit_client_2.get_open_orders(**params),
                timeout=30
            )
            
            if not response or response.get("retCode") != 0:
                break
            
            result = response.get("result", {})
            page_orders = result.get("list", [])
            next_cursor = result.get("nextPageCursor", "")
            
            all_orders.extend(page_orders)
            
            if not next_cursor or next_cursor == cursor:
                break
            
            cursor = next_cursor
            
        except Exception as e:
            print(f"{Colors.RED}❌ Error fetching orders: {e}{Colors.RESET}")
            break
    
    return all_orders

def classify_order(order: Dict, position: Dict, current_price: float) -> str:
    """Classify an order as TP or SL"""
    order_side = order.get("side", "")
    pos_side = position.get("side", "")
    trigger_price = order.get("triggerPrice", "")
    stop_order_type = order.get("stopOrderType", "")
    order_link_id = order.get("orderLinkId", "")
    reduce_only = order.get("reduceOnly", False)
    
    # Method 1: Check stopOrderType
    if stop_order_type == "TakeProfit":
        return "TP"
    elif stop_order_type == "StopLoss":
        return "SL"
    
    # Method 2: Check orderLinkId patterns
    if any(pattern in order_link_id for pattern in ["_TP", "TP1", "TP2", "TP3", "TP4"]):
        return "TP"
    elif "_SL" in order_link_id or order_link_id.endswith("SL"):
        return "SL"
    
    # Method 3: Analyze trigger price
    if trigger_price and reduce_only and order_side != pos_side:
        trigger_float = float(trigger_price)
        
        if pos_side == "Buy":  # Long position
            if trigger_float > current_price:
                return "TP"
            else:
                return "SL"
        else:  # Short position
            if trigger_float < current_price:
                return "TP"
            else:
                return "SL"
    
    return "OTHER"

async def analyze_position_orders(position: Dict, all_orders: List[Dict]) -> Dict:
    """Analyze orders for a position and identify mismatches"""
    symbol = position.get("symbol", "")
    pos_side = position.get("side", "")
    pos_size = Decimal(str(position.get("size", 0)))
    current_price = float(position.get("markPrice", 0))
    
    # Filter orders for this symbol
    symbol_orders = [o for o in all_orders if o.get("symbol") == symbol]
    
    # Classify orders
    tp_orders = []
    sl_orders = []
    
    for order in symbol_orders:
        order_type = classify_order(order, position, current_price)
        order_info = {
            "id": order.get("orderId", ""),
            "qty": Decimal(str(order.get("qty", 0))),
            "trigger": order.get("triggerPrice", ""),
            "side": order.get("side", ""),
            "linkId": order.get("orderLinkId", ""),
            "raw": order
        }
        
        if order_type == "TP":
            tp_orders.append(order_info)
        elif order_type == "SL":
            sl_orders.append(order_info)
    
    # Calculate totals
    tp_total = sum(o["qty"] for o in tp_orders)
    sl_total = sum(o["qty"] for o in sl_orders)
    
    # Check coverage
    tp_match = abs(tp_total - pos_size) < Decimal("0.00000001")
    sl_match = abs(sl_total - pos_size) < Decimal("0.00000001")
    
    return {
        "symbol": symbol,
        "side": pos_side,
        "size": pos_size,
        "current_price": current_price,
        "tp_orders": tp_orders,
        "sl_orders": sl_orders,
        "tp_total": tp_total,
        "sl_total": sl_total,
        "tp_match": tp_match,
        "sl_match": sl_match,
        "tp_coverage": (tp_total / pos_size * 100) if pos_size > 0 else 0,
        "sl_coverage": (sl_total / pos_size * 100) if pos_size > 0 else 0
    }

async def fix_tp_orders(analysis: Dict, dry_run: bool = True) -> List[Dict]:
    """Fix TP orders to match position size"""
    symbol = analysis["symbol"]
    pos_side = analysis["side"]
    pos_size = analysis["size"]
    tp_orders = analysis["tp_orders"]
    tp_total = analysis["tp_total"]
    
    fixes = []
    
    if not analysis["tp_match"] and tp_orders:
        print(f"\n{Colors.YELLOW}🔧 Fixing TP orders for {symbol}...{Colors.RESET}")
        
        # Strategy: Proportionally adjust all TP orders
        if tp_total > 0:
            adjustment_ratio = pos_size / tp_total
            
            for i, tp_order in enumerate(tp_orders):
                old_qty = tp_order["qty"]
                new_qty = old_qty * adjustment_ratio
                
                # Round to whole number for these symbols (0 decimals)
                new_qty = new_qty.quantize(Decimal("1"), rounding=ROUND_DOWN)
                
                fix = {
                    "order_id": tp_order["id"],
                    "old_qty": old_qty,
                    "new_qty": new_qty,
                    "trigger": tp_order["trigger"],
                    "side": tp_order["side"],
                    "type": "TP"
                }
                fixes.append(fix)
                
                print(f"  TP{i+1}: {old_qty} → {new_qty} @ ${tp_order['trigger']}")
                
                if not dry_run:
                    # Cancel old order
                    success = await cancel_mirror_order(symbol, tp_order["id"])
                    if success:
                        await asyncio.sleep(0.5)  # Brief delay
                        
                        # Create new order with correct quantity
                        result = await mirror_tp_sl_order(
                            symbol=symbol,
                            side=tp_order["side"],
                            qty=str(new_qty),
                            trigger_price=tp_order["trigger"],
                            position_idx=0,  # Will be auto-detected
                            order_type="Market",
                            reduce_only=True,
                            order_link_id=tp_order["linkId"]
                        )
                        
                        if result:
                            print(f"    ✅ Recreated with correct quantity")
                        else:
                            print(f"    ❌ Failed to recreate order")
    
    return fixes

async def fix_sl_orders(analysis: Dict, dry_run: bool = True) -> List[Dict]:
    """Fix SL orders to match position size"""
    symbol = analysis["symbol"]
    pos_side = analysis["side"]
    pos_size = analysis["size"]
    sl_orders = analysis["sl_orders"]
    sl_total = analysis["sl_total"]
    
    fixes = []
    
    if not analysis["sl_match"] and sl_orders:
        print(f"\n{Colors.YELLOW}🔧 Fixing SL orders for {symbol}...{Colors.RESET}")
        
        # For SL, we typically want a single order for the full position
        # If multiple SL orders exist, we'll consolidate to one
        if len(sl_orders) > 1:
            print(f"  Found {len(sl_orders)} SL orders, will consolidate to 1")
            
            # Find the most conservative SL (furthest from current price)
            current_price = analysis["current_price"]
            
            if pos_side == "Buy":  # Long position
                # For long, lowest trigger price is most conservative
                main_sl = min(sl_orders, key=lambda x: float(x["trigger"]))
            else:  # Short position
                # For short, highest trigger price is most conservative
                main_sl = max(sl_orders, key=lambda x: float(x["trigger"]))
            
            fix = {
                "order_ids": [o["id"] for o in sl_orders],
                "old_qty": sl_total,
                "new_qty": pos_size,
                "trigger": main_sl["trigger"],
                "side": main_sl["side"],
                "type": "SL"
            }
            fixes.append(fix)
            
            print(f"  Consolidating to single SL: {pos_size} @ ${main_sl['trigger']}")
            
            if not dry_run:
                # Cancel all existing SL orders
                for sl_order in sl_orders:
                    await cancel_mirror_order(symbol, sl_order["id"])
                    await asyncio.sleep(0.2)
                
                # Create single SL for full position
                result = await mirror_tp_sl_order(
                    symbol=symbol,
                    side=main_sl["side"],
                    qty=str(pos_size),
                    trigger_price=main_sl["trigger"],
                    position_idx=0,  # Will be auto-detected
                    order_type="Market",
                    reduce_only=True,
                    order_link_id=f"{symbol}_{pos_side}_SL_CONSOLIDATED"
                )
                
                if result:
                    print(f"    ✅ Created consolidated SL order")
                else:
                    print(f"    ❌ Failed to create consolidated SL")
        
        elif len(sl_orders) == 1:
            # Single SL order, just adjust quantity
            sl_order = sl_orders[0]
            
            fix = {
                "order_id": sl_order["id"],
                "old_qty": sl_order["qty"],
                "new_qty": pos_size,
                "trigger": sl_order["trigger"],
                "side": sl_order["side"],
                "type": "SL"
            }
            fixes.append(fix)
            
            print(f"  SL: {sl_order['qty']} → {pos_size} @ ${sl_order['trigger']}")
            
            if not dry_run:
                # Cancel old order
                success = await cancel_mirror_order(symbol, sl_order["id"])
                if success:
                    await asyncio.sleep(0.5)
                    
                    # Create new order with correct quantity
                    result = await mirror_tp_sl_order(
                        symbol=symbol,
                        side=sl_order["side"],
                        qty=str(pos_size),
                        trigger_price=sl_order["trigger"],
                        position_idx=0,  # Will be auto-detected
                        order_type="Market",
                        reduce_only=True,
                        order_link_id=sl_order["linkId"]
                    )
                    
                    if result:
                        print(f"    ✅ Recreated with correct quantity")
                    else:
                        print(f"    ❌ Failed to recreate order")
    
    return fixes

async def main():
    """Main function to fix TP/SL quantities"""
    if not is_mirror_trading_enabled() or not bybit_client_2:
        print(f"{Colors.RED}❌ Mirror trading is not enabled or configured{Colors.RESET}")
        return
    
    print(f"{Colors.BOLD}{Colors.CYAN}MIRROR ACCOUNT TP/SL QUANTITY FIX TOOL{Colors.RESET}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{Colors.YELLOW}⚠️  This tool will fix TP/SL order quantities to match position sizes{Colors.RESET}\n")
    
    # Check for command line argument
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--execute":
        dry_run = False
        print(f"\n{Colors.RED}Running in EXECUTE mode - orders will be modified!{Colors.RESET}")
        print(f"{Colors.YELLOW}Add --execute flag to apply fixes{Colors.RESET}")
    else:
        dry_run = True
        print(f"\n{Colors.CYAN}Running in DRY RUN mode - no changes will be made{Colors.RESET}")
        print(f"{Colors.YELLOW}Add --execute flag to apply fixes{Colors.RESET}")
    
    print(f"\n{Colors.CYAN}Fetching positions and orders...{Colors.RESET}")
    
    try:
        # Get positions and orders
        positions = await get_mirror_positions()
        all_orders = await get_all_mirror_orders()
        
        if not positions:
            print(f"{Colors.YELLOW}No active positions found.{Colors.RESET}")
            return
        
        print(f"\nFound {len(positions)} active position(s)\n")
        
        # Analyze each position
        all_fixes = []
        
        for position in positions:
            analysis = await analyze_position_orders(position, all_orders)
            
            symbol = analysis["symbol"]
            tp_match = analysis["tp_match"]
            sl_match = analysis["sl_match"]
            
            print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
            print(f"{Colors.BOLD}{symbol} - {analysis['side']} {analysis['size']}{Colors.RESET}")
            print(f"{'='*60}")
            
            # Display current state
            tp_color = Colors.GREEN if tp_match else Colors.RED
            sl_color = Colors.GREEN if sl_match else Colors.RED
            
            print(f"TP Coverage: {tp_color}{analysis['tp_coverage']:.1f}% ({analysis['tp_total']}/{analysis['size']}){Colors.RESET}")
            print(f"SL Coverage: {sl_color}{analysis['sl_coverage']:.1f}% ({analysis['sl_total']}/{analysis['size']}){Colors.RESET}")
            
            # Fix orders if needed
            if not tp_match or not sl_match:
                tp_fixes = await fix_tp_orders(analysis, dry_run)
                sl_fixes = await fix_sl_orders(analysis, dry_run)
                
                all_fixes.extend(tp_fixes)
                all_fixes.extend(sl_fixes)
            else:
                print(f"{Colors.GREEN}✅ No fixes needed - quantities match!{Colors.RESET}")
        
        # Summary
        print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}SUMMARY{Colors.RESET}")
        print(f"{'='*60}")
        
        if all_fixes:
            tp_fixes = [f for f in all_fixes if f["type"] == "TP"]
            sl_fixes = [f for f in all_fixes if f["type"] == "SL"]
            
            print(f"Total fixes {'identified' if dry_run else 'applied'}: {len(all_fixes)}")
            print(f"  - TP fixes: {len(tp_fixes)}")
            print(f"  - SL fixes: {len(sl_fixes)}")
            
            if dry_run:
                print(f"\n{Colors.YELLOW}⚠️  This was a DRY RUN. To apply fixes, run again and select Execute mode.{Colors.RESET}")
            else:
                print(f"\n{Colors.GREEN}✅ Fixes have been applied!{Colors.RESET}")
                print(f"{Colors.YELLOW}⚠️  Please verify positions and orders in your trading interface.{Colors.RESET}")
        else:
            print(f"{Colors.GREEN}✅ All positions have correct TP/SL coverage!{Colors.RESET}")
        
    except Exception as e:
        print(f"{Colors.RED}❌ Error: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())