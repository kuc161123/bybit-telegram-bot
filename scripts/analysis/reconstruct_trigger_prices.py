#!/usr/bin/env python3
"""
Reconstruct original trigger prices from order history and market data
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from collections import defaultdict

from clients.bybit_client import bybit_client
from clients.bybit_helpers import get_all_positions, get_all_open_orders, api_call_with_retry
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TriggerPriceReconstructor:
    def __init__(self):
        self.common_tp_percentages = {
            "Fast": [1.0],  # 100% at one level
            "Conservative": [0.70, 0.10, 0.10, 0.10],  # 70%, 10%, 10%, 10%
            "Custom_3TP": [0.425, 0.061, 0.061],  # Common 3TP pattern
            "Custom_4TP": [0.425, 0.061, 0.061, 0.061]  # Common 4TP pattern
        }
        
        # Common TP price increments from entry
        self.common_tp_increments = {
            "Conservative": [0.03, 0.05, 0.07, 0.10],  # 3%, 5%, 7%, 10%
            "Aggressive": [0.05, 0.08, 0.12, 0.20],    # 5%, 8%, 12%, 20%
            "Custom": [0.035, 0.06, 0.09, 0.17]        # Variable pattern
        }
        
        # Common SL percentages
        self.common_sl_percentages = [0.03, 0.05, 0.07, 0.10, 0.15]  # 3%, 5%, 7%, 10%, 15%
    
    async def get_detailed_order_history(self, symbol: str, account: str = "main", limit: int = 200) -> List[Dict]:
        """Get detailed order history including cancelled orders"""
        try:
            client = bybit_client_2 if account == "mirror" else bybit_client
            
            all_orders = []
            cursor = ""
            
            while len(all_orders) < limit:
                params = {
                    "category": "linear",
                    "symbol": symbol,
                    "limit": 50
                }
                
                if cursor:
                    params["cursor"] = cursor
                
                response = await api_call_with_retry(
                    lambda: client.get_order_history(**params),
                    timeout=30
                )
                
                if response and response.get("retCode") == 0:
                    result = response.get("result", {})
                    orders = result.get("list", [])
                    all_orders.extend(orders)
                    
                    cursor = result.get("nextPageCursor", "")
                    if not cursor:
                        break
                else:
                    break
            
            return all_orders[:limit]
            
        except Exception as e:
            logger.error(f"Error getting order history for {symbol}: {e}")
            return []
    
    def analyze_order_patterns(self, orders: List[Dict], position: Dict) -> Dict:
        """Analyze order patterns to determine likely approach and trigger prices"""
        side = position['side']
        avg_price = Decimal(str(position['avgPrice']))
        
        # Separate order types
        tp_orders = []
        sl_orders = []
        entry_orders = []
        
        for order in orders:
            order_type = order.get('orderType', '')
            stop_type = order.get('stopOrderType', '')
            order_side = order.get('side', '')
            status = order.get('orderStatus', '')
            
            # Entry orders (filled market/limit orders matching position side)
            if status == 'Filled' and order_side == side and not order.get('reduceOnly'):
                entry_orders.append(order)
            
            # TP/SL orders (including cancelled ones to see original setup)
            elif stop_type or order.get('reduceOnly'):
                if (side == 'Buy' and order_side == 'Sell') or (side == 'Sell' and order_side == 'Buy'):
                    if stop_type == 'TakeProfit' or (not stop_type and order.get('triggerPrice')):
                        tp_orders.append(order)
                    elif stop_type == 'StopLoss':
                        sl_orders.append(order)
        
        # Sort orders by creation time
        tp_orders.sort(key=lambda x: int(x.get('createdTime', 0)))
        sl_orders.sort(key=lambda x: int(x.get('createdTime', 0)))
        entry_orders.sort(key=lambda x: int(x.get('createdTime', 0)))
        
        # Find likely original TP setup
        original_tps = []
        tp_groups = defaultdict(list)
        
        # Group TPs by similar creation time (within 5 seconds)
        for tp in tp_orders:
            created_time = int(tp.get('createdTime', 0)) / 1000
            
            # Find group
            found_group = False
            for group_time in tp_groups:
                if abs(created_time - group_time) < 5:  # Within 5 seconds
                    tp_groups[group_time].append(tp)
                    found_group = True
                    break
            
            if not found_group:
                tp_groups[created_time].append(tp)
        
        # Find the largest group (likely the original setup)
        largest_group = []
        for group in tp_groups.values():
            if len(group) > len(largest_group):
                largest_group = group
        
        # Extract trigger prices from largest group
        for tp in largest_group:
            trigger_price = tp.get('triggerPrice') or tp.get('price')
            if trigger_price:
                original_tps.append({
                    'price': Decimal(str(trigger_price)),
                    'qty': Decimal(str(tp.get('qty', 0))),
                    'created': datetime.fromtimestamp(int(tp.get('createdTime', 0)) / 1000)
                })
        
        # Sort TPs by price
        original_tps.sort(key=lambda x: x['price'], reverse=(side == 'Sell'))
        
        # Find original SL
        original_sl = None
        if sl_orders:
            # Look for SL created around the same time as TPs
            for sl in sl_orders:
                sl_time = int(sl.get('createdTime', 0)) / 1000
                if largest_group and abs(sl_time - int(largest_group[0].get('createdTime', 0)) / 1000) < 60:
                    trigger_price = sl.get('triggerPrice') or sl.get('price')
                    if trigger_price:
                        original_sl = {
                            'price': Decimal(str(trigger_price)),
                            'qty': Decimal(str(sl.get('qty', 0))),
                            'created': datetime.fromtimestamp(sl_time)
                        }
                        break
        
        # Determine approach based on TP pattern
        approach = "Unknown"
        if len(original_tps) == 1:
            approach = "Fast"
        elif len(original_tps) == 4:
            # Check quantity distribution
            quantities = [tp['qty'] for tp in original_tps]
            total_qty = sum(quantities)
            if total_qty > 0:
                percentages = [float(q / total_qty) for q in quantities]
                if percentages[0] > 0.6:  # First TP > 60%
                    approach = "Conservative"
                else:
                    approach = "Custom_4TP"
        elif len(original_tps) == 3:
            approach = "Custom_3TP"
        
        # Calculate entry price from filled orders
        total_cost = Decimal('0')
        total_qty = Decimal('0')
        for entry in entry_orders:
            qty = Decimal(str(entry.get('qty', 0)))
            price = Decimal(str(entry.get('avgPrice', 0) or entry.get('price', 0)))
            total_cost += qty * price
            total_qty += qty
        
        calculated_entry = total_cost / total_qty if total_qty > 0 else avg_price
        
        return {
            'approach': approach,
            'original_tps': original_tps,
            'original_sl': original_sl,
            'entry_orders': entry_orders,
            'calculated_entry': calculated_entry,
            'tp_order_count': len(tp_orders),
            'sl_order_count': len(sl_orders)
        }
    
    async def reconstruct_position_triggers(self, position: Dict, orders: List[Dict], account: str = "main"):
        """Reconstruct trigger prices for a position"""
        symbol = position['symbol']
        side = position['side']
        size = Decimal(str(position['size']))
        avg_price = Decimal(str(position['avgPrice']))
        mark_price = Decimal(str(position.get('markPrice', 0)))
        unrealized_pnl = Decimal(str(position.get('unrealisedPnl', 0)))
        
        # Get detailed order history
        detailed_orders = await self.get_detailed_order_history(symbol, account, 200)
        
        # Analyze patterns
        analysis = self.analyze_order_patterns(detailed_orders, position)
        
        print(f"\n{'='*70}")
        print(f"{symbol} - {side} Position ({account.upper()})")
        print(f"{'='*70}")
        print(f"Current Size: {size:.8g}")
        print(f"Average Entry: ${avg_price:.8g}")
        print(f"Current Price: ${mark_price:.8g}")
        print(f"Unrealized P&L: {'🟢' if unrealized_pnl >= 0 else '🔴'} ${unrealized_pnl:.2f}")
        
        print(f"\n📊 POSITION ANALYSIS:")
        print(f"Detected Approach: {analysis['approach']}")
        print(f"Calculated Entry: ${analysis['calculated_entry']:.8g}")
        print(f"Entry Orders: {len(analysis['entry_orders'])}")
        print(f"Total TP Orders Found: {analysis['tp_order_count']} (including cancelled)")
        print(f"Total SL Orders Found: {analysis['sl_order_count']} (including cancelled)")
        
        if analysis['entry_orders']:
            print(f"\n📈 ENTRY HISTORY:")
            for i, entry in enumerate(analysis['entry_orders'][:5], 1):
                entry_time = datetime.fromtimestamp(int(entry.get('createdTime', 0)) / 1000)
                qty = entry.get('qty', 0)
                price = entry.get('avgPrice', 0) or entry.get('price', 0)
                print(f"  {entry_time.strftime('%Y-%m-%d %H:%M')}: {qty} @ ${price}")
        
        if analysis['original_tps']:
            print(f"\n🎯 RECONSTRUCTED ORIGINAL TP LEVELS:")
            total_tp_qty = sum(tp['qty'] for tp in analysis['original_tps'])
            
            for i, tp in enumerate(analysis['original_tps'], 1):
                pct_of_total = float(tp['qty'] / total_tp_qty * 100) if total_tp_qty > 0 else 0
                price_diff = ((tp['price'] - avg_price) / avg_price * 100) if side == 'Buy' else ((avg_price - tp['price']) / avg_price * 100)
                
                # Calculate potential P&L
                if side == 'Buy':
                    pnl = (tp['price'] - avg_price) * tp['qty']
                else:
                    pnl = (avg_price - tp['price']) * tp['qty']
                
                print(f"  TP{i}: ${tp['price']:.8g} ({'+' if price_diff > 0 else ''}{price_diff:.2f}%)")
                print(f"       Qty: {tp['qty']:.8g} ({pct_of_total:.1f}% of setup)")
                print(f"       Potential P&L: {'🟢' if pnl >= 0 else '🔴'} ${pnl:.2f}")
                print(f"       Created: {tp['created'].strftime('%Y-%m-%d %H:%M')}")
        
        if analysis['original_sl']:
            sl = analysis['original_sl']
            price_diff = ((sl['price'] - avg_price) / avg_price * 100) if side == 'Buy' else ((avg_price - sl['price']) / avg_price * 100)
            
            # Calculate potential loss
            if side == 'Buy':
                loss = (sl['price'] - avg_price) * sl['qty']
            else:
                loss = (avg_price - sl['price']) * sl['qty']
            
            print(f"\n🛡️ RECONSTRUCTED ORIGINAL SL:")
            print(f"  SL: ${sl['price']:.8g} ({price_diff:.2f}%)")
            print(f"      Qty: {sl['qty']:.8g}")
            print(f"      Potential Loss: 🔴 ${loss:.2f}")
            print(f"      Created: {sl['created'].strftime('%Y-%m-%d %H:%M')}")
        
        # Show current active orders for comparison
        current_tps = [o for o in orders if o['symbol'] == symbol and 
                      o.get('positionIdx', 0) == (1 if side == 'Buy' else 2) and
                      ((side == 'Buy' and o.get('side') == 'Sell') or (side == 'Sell' and o.get('side') == 'Buy'))]
        
        if current_tps:
            print(f"\n📍 CURRENT ACTIVE TP ORDERS:")
            for i, tp in enumerate(current_tps[:5], 1):
                price = tp.get('triggerPrice') or tp.get('price', 0)
                qty = tp.get('qty', 0)
                print(f"  TP{i}: ${price} - Qty: {qty}")
    
    async def analyze_all_positions(self):
        """Analyze all positions"""
        # Get current positions and orders
        positions = await get_all_positions()
        orders = await get_all_open_orders()
        
        active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
        
        print("\n" + "="*80)
        print("RECONSTRUCTED TRIGGER PRICE ANALYSIS")
        print("="*80)
        
        # Main account
        print(f"\n📊 MAIN ACCOUNT - {len(active_positions)} Positions")
        for position in active_positions:
            await self.reconstruct_position_triggers(position, orders, "main")
        
        # Mirror account
        if is_mirror_trading_enabled():
            mirror_orders = []
            order_response = await api_call_with_retry(
                lambda: bybit_client_2.get_open_orders(
                    category="linear",
                    settleCoin="USDT",
                    limit=200
                ),
                timeout=30
            )
            if order_response and order_response.get("retCode") == 0:
                mirror_orders = order_response.get("result", {}).get("list", [])
            
            pos_response = await api_call_with_retry(
                lambda: bybit_client_2.get_positions(
                    category="linear",
                    settleCoin="USDT"
                ),
                timeout=30
            )
            if pos_response and pos_response.get("retCode") == 0:
                mirror_positions = pos_response.get("result", {}).get("list", [])
                active_mirror = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
                
                print(f"\n\n📊 MIRROR ACCOUNT - {len(active_mirror)} Positions")
                for position in active_mirror:
                    await self.reconstruct_position_triggers(position, mirror_orders, "mirror")


async def main():
    """Main function"""
    reconstructor = TriggerPriceReconstructor()
    await reconstructor.analyze_all_positions()


if __name__ == "__main__":
    asyncio.run(main())