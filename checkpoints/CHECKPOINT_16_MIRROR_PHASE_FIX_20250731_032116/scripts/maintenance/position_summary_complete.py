#!/usr/bin/env python3
"""
Complete position summary with all TP/SL levels and potential P&L values
"""

import asyncio
import logging
from typing import Dict, List, Tuple
from decimal import Decimal
from collections import defaultdict
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_client import bybit_client
from clients.bybit_helpers import get_all_positions, get_all_open_orders, api_call_with_retry
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
from utils.order_identifier import identify_order_type, group_orders_by_type, ORDER_TYPE_TP, ORDER_TYPE_SL

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CompleteSummaryGenerator:
    def __init__(self):
        self.main_positions = []
        self.mirror_positions = []
        self.main_orders = []
        self.mirror_orders = []
    
    async def gather_all_data(self):
        """Gather all positions and orders from both accounts"""
        # Main account
        self.main_positions = await get_all_positions()
        self.main_orders = await get_all_open_orders()
        
        # Mirror account
        if is_mirror_trading_enabled():
            pos_response = await api_call_with_retry(
                lambda: bybit_client_2.get_positions(
                    category="linear",
                    settleCoin="USDT"
                ),
                timeout=30
            )
            self.mirror_positions = pos_response.get("result", {}).get("list", []) if pos_response and pos_response.get("retCode") == 0 else []
            
            order_response = await api_call_with_retry(
                lambda: bybit_client_2.get_open_orders(
                    category="linear",
                    settleCoin="USDT",
                    limit=200
                ),
                timeout=30
            )
            self.mirror_orders = order_response.get("result", {}).get("list", []) if order_response and order_response.get("retCode") == 0 else []
    
    def calculate_pnl(self, position: Dict, target_price: Decimal, qty: Decimal = None) -> Decimal:
        """Calculate P&L at target price"""
        size = qty or Decimal(str(position.get('size', 0)))
        side = position.get('side')
        avg_price = Decimal(str(position.get('avgPrice', 0)))
        
        if side == 'Buy':
            pnl = (target_price - avg_price) * size
        else:
            pnl = (avg_price - target_price) * size
            
        return pnl
    
    def get_order_price(self, order: Dict) -> Decimal:
        """Extract price from order"""
        price = order.get('triggerPrice') or order.get('price') or '0'
        if order.get('orderType') == 'Limit' and order.get('reduceOnly'):
            price = order.get('price', price)
        return Decimal(str(price))
    
    def print_position_summary(self, position: Dict, orders: List[Dict], account: str):
        """Print detailed position summary"""
        symbol = position['symbol']
        side = position['side']
        size = Decimal(str(position['size']))
        avg_price = Decimal(str(position['avgPrice']))
        mark_price = Decimal(str(position.get('markPrice', 0)))
        unrealized_pnl = Decimal(str(position.get('unrealisedPnl', 0)))
        
        # Filter orders for this position
        position_orders = [
            o for o in orders
            if o['symbol'] == symbol and o.get('positionIdx', 0) == (1 if side == 'Buy' else 2)
        ]
        
        # Group orders
        grouped = group_orders_by_type(position_orders, position)
        tp_orders = grouped['tp_orders']
        sl_orders = grouped['sl_orders']
        
        # Sort TP orders by price
        tp_orders_with_prices = []
        for tp in tp_orders:
            price = self.get_order_price(tp)
            if price > 0:
                tp_orders_with_prices.append((price, tp))
        tp_orders_with_prices.sort(key=lambda x: x[0], reverse=(side == 'Sell'))
        
        # Position header
        print(f"\n{'='*70}")
        print(f"{symbol} - {side} Position ({account.upper()} ACCOUNT)")
        print(f"{'='*70}")
        print(f"Size: {size:.8g}")
        print(f"Entry Price: ${avg_price:.8g}")
        print(f"Current Price: ${mark_price:.8g}")
        print(f"Position Value: ${size * mark_price:.2f}")
        print(f"Unrealized P&L: {'🟢' if unrealized_pnl >= 0 else '🔴'} ${unrealized_pnl:.2f}")
        
        # Take Profit Levels
        if tp_orders_with_prices:
            print(f"\n🎯 TAKE PROFIT LEVELS:")
            total_tp_pnl = Decimal('0')
            for i, (tp_price, tp) in enumerate(tp_orders_with_prices, 1):
                tp_qty = Decimal(str(tp.get('qty', 0)))
                tp_pnl = self.calculate_pnl(position, tp_price, tp_qty)
                pct = float((tp_qty / size) * 100)
                total_tp_pnl += tp_pnl
                
                price_diff_pct = ((tp_price - avg_price) / avg_price * 100) if side == 'Buy' else ((avg_price - tp_price) / avg_price * 100)
                
                print(f"  TP{i}: ${tp_price:.8g} ({'+' if price_diff_pct > 0 else ''}{price_diff_pct:.2f}%)")
                print(f"       Qty: {tp_qty:.8g} ({pct:.1f}%)")
                print(f"       P&L: {'🟢' if tp_pnl >= 0 else '🔴'} ${tp_pnl:.2f}")
            
            print(f"\n  Total TP P&L (if all hit): 🟢 ${total_tp_pnl:.2f}")
        else:
            print(f"\n❌ NO TAKE PROFIT ORDERS")
        
        # Stop Loss Levels
        if sl_orders:
            print(f"\n🛡️ STOP LOSS:")
            for sl in sl_orders:
                sl_price = self.get_order_price(sl)
                if sl_price > 0:
                    sl_qty = Decimal(str(sl.get('qty', 0)))
                    sl_pnl = self.calculate_pnl(position, sl_price, sl_qty)
                    pct = float((sl_qty / size) * 100)
                    
                    price_diff_pct = ((sl_price - avg_price) / avg_price * 100) if side == 'Buy' else ((avg_price - sl_price) / avg_price * 100)
                    
                    print(f"  SL: ${sl_price:.8g} ({price_diff_pct:.2f}%)")
                    print(f"      Qty: {sl_qty:.8g} ({pct:.1f}%)")
                    print(f"      Loss: 🔴 ${sl_pnl:.2f}")
        else:
            # Calculate 3% stop loss
            sl_price = avg_price * (Decimal('0.97') if side == 'Buy' else Decimal('1.03'))
            sl_pnl = self.calculate_pnl(position, sl_price)
            print(f"\n❌ NO STOP LOSS - Suggested 3% SL:")
            print(f"  SL: ${sl_price:.8g} (-3%)")
            print(f"  Potential Loss: 🔴 ${sl_pnl:.2f}")
    
    async def generate_summary(self):
        """Generate complete position summary"""
        await self.gather_all_data()
        
        # Filter active positions
        active_main = [p for p in self.main_positions if float(p.get('size', 0)) > 0]
        active_mirror = [p for p in self.mirror_positions if float(p.get('size', 0)) > 0]
        
        print("\n" + "="*80)
        print("COMPLETE POSITION SUMMARY WITH TP/SL LEVELS")
        print("="*80)
        
        # Main Account Summary
        if active_main:
            print(f"\n📊 MAIN ACCOUNT - {len(active_main)} Positions")
            print("─"*80)
            
            total_value = Decimal('0')
            total_pnl = Decimal('0')
            
            for position in active_main:
                self.print_position_summary(position, self.main_orders, "main")
                size = Decimal(str(position['size']))
                mark_price = Decimal(str(position.get('markPrice', 0)))
                unrealized_pnl = Decimal(str(position.get('unrealisedPnl', 0)))
                total_value += size * mark_price
                total_pnl += unrealized_pnl
            
            print(f"\n{'='*80}")
            print(f"MAIN ACCOUNT TOTALS:")
            print(f"Total Position Value: ${total_value:.2f}")
            print(f"Total Unrealized P&L: {'🟢' if total_pnl >= 0 else '🔴'} ${total_pnl:.2f}")
        
        # Mirror Account Summary
        if is_mirror_trading_enabled() and active_mirror:
            print(f"\n\n📊 MIRROR ACCOUNT - {len(active_mirror)} Positions")
            print("─"*80)
            
            total_value = Decimal('0')
            total_pnl = Decimal('0')
            
            for position in active_mirror:
                self.print_position_summary(position, self.mirror_orders, "mirror")
                size = Decimal(str(position['size']))
                mark_price = Decimal(str(position.get('markPrice', 0)))
                unrealized_pnl = Decimal(str(position.get('unrealisedPnl', 0)))
                total_value += size * mark_price
                total_pnl += unrealized_pnl
            
            print(f"\n{'='*80}")
            print(f"MIRROR ACCOUNT TOTALS:")
            print(f"Total Position Value: ${total_value:.2f}")
            print(f"Total Unrealized P&L: {'🟢' if total_pnl >= 0 else '🔴'} ${total_pnl:.2f}")
        
        # Risk Summary
        print(f"\n\n{'='*80}")
        print("RISK ANALYSIS SUMMARY")
        print("="*80)
        
        # Count positions without SL
        main_no_sl = []
        mirror_no_sl = []
        
        for pos in active_main:
            symbol = pos['symbol']
            side = pos['side']
            pos_orders = [o for o in self.main_orders if o['symbol'] == symbol and o.get('positionIdx', 0) == (1 if side == 'Buy' else 2)]
            grouped = group_orders_by_type(pos_orders, pos)
            if not grouped['sl_orders']:
                main_no_sl.append(pos)
        
        if is_mirror_trading_enabled():
            for pos in active_mirror:
                symbol = pos['symbol']
                side = pos['side']
                pos_orders = [o for o in self.mirror_orders if o['symbol'] == symbol and o.get('positionIdx', 0) == (1 if side == 'Buy' else 2)]
                grouped = group_orders_by_type(pos_orders, pos)
                if not grouped['sl_orders']:
                    mirror_no_sl.append(pos)
        
        print(f"\n⚠️ POSITIONS WITHOUT STOP LOSS:")
        if main_no_sl:
            print(f"\nMain Account ({len(main_no_sl)} positions):")
            total_risk = Decimal('0')
            for pos in main_no_sl:
                size = Decimal(str(pos['size']))
                avg_price = Decimal(str(pos['avgPrice']))
                side = pos['side']
                sl_price = avg_price * (Decimal('0.97') if side == 'Buy' else Decimal('1.03'))
                potential_loss = abs(self.calculate_pnl(pos, sl_price))
                total_risk += potential_loss
                print(f"  - {pos['symbol']} ({side}): 🔴 ${potential_loss:.2f} potential loss at 3% SL")
            print(f"  Total Risk (3% SL): 🔴 ${total_risk:.2f}")
        
        if mirror_no_sl:
            print(f"\nMirror Account ({len(mirror_no_sl)} positions):")
            total_risk = Decimal('0')
            for pos in mirror_no_sl:
                size = Decimal(str(pos['size']))
                avg_price = Decimal(str(pos['avgPrice']))
                side = pos['side']
                sl_price = avg_price * (Decimal('0.97') if side == 'Buy' else Decimal('1.03'))
                potential_loss = abs(self.calculate_pnl(pos, sl_price))
                total_risk += potential_loss
                print(f"  - {pos['symbol']} ({side}): 🔴 ${potential_loss:.2f} potential loss at 3% SL")
            print(f"  Total Risk (3% SL): 🔴 ${total_risk:.2f}")
        
        if not main_no_sl and not mirror_no_sl:
            print("✅ All positions have stop loss protection!")
        
        print(f"\n{'='*80}")
        print("SUMMARY COMPLETE")
        print("="*80)


async def main():
    """Main function"""
    generator = CompleteSummaryGenerator()
    await generator.generate_summary()


if __name__ == "__main__":
    asyncio.run(main())