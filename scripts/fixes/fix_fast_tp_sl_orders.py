#!/usr/bin/env python3
"""
Fix missing TP/SL orders for fast approach positions.
Uses reasonable defaults: 7% TP, 2.5% SL for fast approach
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime

from clients.bybit_client import bybit_client
from clients.bybit_helpers import place_order_with_retry, get_all_positions, get_all_open_orders
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# BOT prefix for order IDs
BOT_PREFIX = "BOT_"


class FastApproachOrderFixer:
    def __init__(self):
        # Fast approach positions that need fixing
        self.fast_positions = ['ENAUSDT', 'TIAUSDT', 'WIFUSDT', 'JASMYUSDT', 'WLDUSDT', 'BTCUSDT']
        
        # Default TP/SL percentages for fast approach
        self.default_tp_percentage = Decimal('0.07')  # 7% profit
        self.default_sl_percentage = Decimal('0.025')  # 2.5% loss
    
    async def get_instrument_info(self, symbol: str) -> Dict:
        """Get instrument info for proper decimal precision"""
        try:
            response = bybit_client.get_instruments_info(
                category="linear",
                symbol=symbol
            )
            if response and response.get("retCode") == 0:
                instruments = response.get("result", {}).get("list", [])
                if instruments:
                    return instruments[0]
        except Exception as e:
            logger.error(f"Error getting instrument info for {symbol}: {e}")
        return {}
    
    def calculate_tp_sl_prices(self, avg_price: Decimal, side: str, 
                              tp_pct: Decimal = None, sl_pct: Decimal = None) -> tuple:
        """Calculate TP and SL prices based on position side"""
        tp_pct = tp_pct or self.default_tp_percentage
        sl_pct = sl_pct or self.default_sl_percentage
        
        if side == 'Buy':
            # Long position
            tp_price = avg_price * (Decimal('1') + tp_pct)
            sl_price = avg_price * (Decimal('1') - sl_pct)
        else:
            # Short position
            tp_price = avg_price * (Decimal('1') - tp_pct)
            sl_price = avg_price * (Decimal('1') + sl_pct)
        
        return tp_price, sl_price
    
    def round_to_tick_size(self, price: Decimal, tick_size: Decimal) -> Decimal:
        """Round price to the nearest tick size"""
        return (price / tick_size).quantize(Decimal('1')) * tick_size
    
    async def fix_position_orders(self, position: Dict, orders: List[Dict], 
                                 account: str = "main", dry_run: bool = False):
        """Fix missing TP/SL orders for a position"""
        symbol = position['symbol']
        side = position['side']
        size = Decimal(position['size'])
        avg_price = Decimal(position['avgPrice'])
        
        # Skip if not a fast position
        if symbol not in self.fast_positions:
            return
        
        # Check existing orders - debug version
        position_orders = [o for o in orders if o['symbol'] == symbol]
        tp_orders = []
        sl_orders = []
        
        print(f"\nDEBUG: Found {len(position_orders)} orders for {symbol}")
        
        for order in position_orders:
            order_type = order.get('orderType', '')
            stop_type = order.get('stopOrderType', '')
            trigger_price = order.get('triggerPrice') or order.get('price')
            is_reduce = order.get('reduceOnly', False)
            order_side = order.get('side', '')
            
            print(f"  Order: {order.get('orderId', '')[:8]}... Type: {order_type}, Stop: {stop_type}, Side: {order_side}, Reduce: {is_reduce}")
            
            # Skip non-reduce-only orders (entry orders)
            if not is_reduce:
                continue
                
            if stop_type == 'TakeProfit':
                tp_orders.append(order)
            elif stop_type == 'StopLoss':
                sl_orders.append(order)
            elif trigger_price:
                # Check by price relative to entry for orders without explicit stop type
                trigger_price = Decimal(trigger_price)
                if side == 'Buy':
                    if trigger_price > avg_price:
                        tp_orders.append(order)
                    else:
                        sl_orders.append(order)
                else:  # Sell
                    if trigger_price < avg_price:
                        tp_orders.append(order)
                    else:
                        sl_orders.append(order)
        
        # Check if orders need to be placed
        needs_tp = len(tp_orders) == 0
        needs_sl = len(sl_orders) == 0
        
        if not needs_tp and not needs_sl:
            logger.info(f"✅ {symbol} ({account}) - Already has TP/SL orders")
            return
        
        print(f"\n{'='*70}")
        print(f"🔧 FIXING {symbol} - {side} Position ({account.upper()})")
        print(f"{'='*70}")
        print(f"Position Size: {size}")
        print(f"Average Entry: ${avg_price}")
        print(f"Current TP Orders: {len(tp_orders)}")
        print(f"Current SL Orders: {len(sl_orders)}")
        
        # Get instrument info
        instrument = await self.get_instrument_info(symbol)
        price_filter = instrument.get("priceFilter", {})
        tick_size = Decimal(price_filter.get("tickSize", "0.01"))
        
        # Calculate TP/SL prices
        tp_price, sl_price = self.calculate_tp_sl_prices(avg_price, side)
        
        # Round to tick size
        tp_price = self.round_to_tick_size(tp_price, tick_size)
        sl_price = self.round_to_tick_size(sl_price, tick_size)
        
        print(f"\n📊 Calculated Prices:")
        print(f"  TP: ${tp_price} ({'+' if side == 'Buy' else ''}{(tp_price - avg_price) / avg_price * 100:.2f}%)")
        print(f"  SL: ${sl_price} ({'-' if side == 'Buy' else '+'}{abs(sl_price - avg_price) / avg_price * 100:.2f}%)")
        
        if dry_run:
            print("\n🔍 DRY RUN - No orders will be placed")
            return
        
        # Choose the appropriate client
        client = bybit_client_2 if account == "mirror" else bybit_client
        
        # Place TP order if needed
        if needs_tp:
            print(f"\n📈 Placing TP order...")
            try:
                tp_result = await place_order_with_retry(
                    client=client,
                    symbol=symbol,
                    side="Sell" if side == "Buy" else "Buy",
                    order_type="Market",
                    qty=str(size),
                    trigger_price=str(tp_price),
                    order_link_id=f"{BOT_PREFIX}FAST_{datetime.now().strftime('%H%M%S')}_{symbol}_TP",
                    reduce_only=True,
                    stop_order_type="TakeProfit"
                )
                
                if tp_result and tp_result.get('orderId'):
                    print(f"✅ TP order placed successfully: {tp_result['orderId'][:8]}...")
                else:
                    print(f"❌ Failed to place TP order")
                    logger.error(f"TP order failed for {symbol}: {tp_result}")
                    
            except Exception as e:
                print(f"❌ Error placing TP order: {e}")
                logger.error(f"Error placing TP order for {symbol}: {e}")
        
        # Place SL order if needed
        if needs_sl:
            print(f"\n🛡️ Placing SL order...")
            try:
                sl_result = await place_order_with_retry(
                    client=client,
                    symbol=symbol,
                    side="Sell" if side == "Buy" else "Buy",
                    order_type="Market",
                    qty=str(size),
                    trigger_price=str(sl_price),
                    order_link_id=f"{BOT_PREFIX}FAST_{datetime.now().strftime('%H%M%S')}_{symbol}_SL",
                    reduce_only=True,
                    stop_order_type="StopLoss"
                )
                
                if sl_result and sl_result.get('orderId'):
                    print(f"✅ SL order placed successfully: {sl_result['orderId'][:8]}...")
                else:
                    print(f"❌ Failed to place SL order")
                    logger.error(f"SL order failed for {symbol}: {sl_result}")
                    
            except Exception as e:
                print(f"❌ Error placing SL order: {e}")
                logger.error(f"Error placing SL order for {symbol}: {e}")
    
    async def fix_all_positions(self, dry_run: bool = False):
        """Fix all fast approach positions"""
        print("\n" + "="*80)
        print("FAST APPROACH ORDER FIXER")
        print("="*80)
        print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        print(f"Default TP: {float(self.default_tp_percentage * 100):.1f}%")
        print(f"Default SL: {float(self.default_sl_percentage * 100):.1f}%")
        
        # Main account
        print(f"\n📊 Checking MAIN account positions...")
        positions = await get_all_positions()
        orders = await get_all_open_orders()
        
        active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
        fast_active = [p for p in active_positions if p['symbol'] in self.fast_positions]
        
        print(f"Found {len(fast_active)} fast approach positions")
        
        for position in fast_active:
            await self.fix_position_orders(position, orders, "main", dry_run)
        
        # Mirror account
        if is_mirror_trading_enabled():
            print(f"\n📊 Checking MIRROR account positions...")
            
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
                
                active_mirror = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
                fast_mirror = [p for p in active_mirror if p['symbol'] in self.fast_positions]
                
                print(f"Found {len(fast_mirror)} fast approach positions")
                
                for position in fast_mirror:
                    await self.fix_position_orders(position, mirror_orders, "mirror", dry_run)
        
        print("\n" + "="*80)
        print("✅ FAST APPROACH ORDER FIX COMPLETE!")
        print("="*80)


async def main():
    """Main function"""
    import sys
    
    # Check for dry run flag
    dry_run = "--dry-run" in sys.argv or "-d" in sys.argv
    
    fixer = FastApproachOrderFixer()
    await fixer.fix_all_positions(dry_run=dry_run)


if __name__ == "__main__":
    asyncio.run(main())