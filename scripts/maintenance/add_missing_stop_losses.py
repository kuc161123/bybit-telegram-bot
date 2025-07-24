#!/usr/bin/env python3
"""
Add 3% stop loss orders for positions without SL protection
"""

import asyncio
import logging
from typing import Dict, List, Tuple
from decimal import Decimal
from collections import defaultdict

from clients.bybit_client import bybit_client
from clients.bybit_helpers import get_all_positions, get_all_open_orders, api_call_with_retry
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
from utils.order_identifier import group_orders_by_type, generate_order_link_id

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StopLossAdder:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.sl_percentage = Decimal('0.03')  # 3% stop loss
        self.orders_to_create = []
        
    async def get_account_data(self, account: str = "main") -> Tuple[List[Dict], List[Dict]]:
        """Get positions and orders for specified account"""
        if account == "mirror" and is_mirror_trading_enabled():
            pos_response = await api_call_with_retry(
                lambda: bybit_client_2.get_positions(
                    category="linear",
                    settleCoin="USDT"
                ),
                timeout=30
            )
            positions = pos_response.get("result", {}).get("list", []) if pos_response and pos_response.get("retCode") == 0 else []
            
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
            positions = await get_all_positions()
            orders = await get_all_open_orders()
            
        return positions, orders
    
    async def get_instrument_info(self, symbol: str, account: str = "main") -> Dict:
        """Get instrument info for proper decimal formatting"""
        try:
            client = bybit_client_2 if account == "mirror" else bybit_client
            info = client.get_instruments_info(
                category="linear",
                symbol=symbol
            )
            if info and info.get('result') and info['result'].get('list'):
                return info['result']['list'][0]
        except Exception as e:
            logger.error(f"Error getting instrument info for {symbol}: {e}")
        return {}
    
    def calculate_sl_price(self, entry_price: Decimal, side: str) -> Decimal:
        """Calculate stop loss price 3% from entry"""
        if side == 'Buy':
            # For long position, SL is below entry
            sl_price = entry_price * (Decimal('1') - self.sl_percentage)
        else:
            # For short position, SL is above entry
            sl_price = entry_price * (Decimal('1') + self.sl_percentage)
        return sl_price
    
    async def analyze_and_add_stop_losses(self, account: str = "main"):
        """Analyze positions and add missing stop losses"""
        account_name = "MIRROR" if account == "mirror" else "MAIN"
        logger.info(f"\nAnalyzing {account_name} account for missing stop losses...")
        
        positions, orders = await self.get_account_data(account)
        
        # Filter active positions
        active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
        
        # Group orders by symbol
        orders_by_symbol = defaultdict(list)
        for order in orders:
            orders_by_symbol[order['symbol']].append(order)
        
        positions_needing_sl = []
        total_potential_loss = Decimal('0')
        
        for position in active_positions:
            symbol = position['symbol']
            side = position['side']
            size = Decimal(str(position['size']))
            avg_price = Decimal(str(position['avgPrice']))
            
            # Get orders for this position
            position_orders = [
                o for o in orders_by_symbol[symbol]
                if o.get('positionIdx', 0) == (1 if side == 'Buy' else 2)
            ]
            
            # Check if position has SL
            grouped = group_orders_by_type(position_orders, position)
            sl_orders = grouped['sl_orders']
            
            if not sl_orders:
                # No SL - calculate and prepare order
                sl_price = self.calculate_sl_price(avg_price, side)
                
                # Get instrument info for proper formatting
                instrument = await self.get_instrument_info(symbol, account)
                if instrument:
                    tick_size = Decimal(str(instrument.get('priceFilter', {}).get('tickSize', '0.01')))
                    qty_step = Decimal(str(instrument.get('lotSizeFilter', {}).get('qtyStep', '0.01')))
                    
                    # Adjust SL price to tick size
                    sl_price = (sl_price / tick_size).quantize(Decimal('1')) * tick_size
                    
                    # Calculate potential loss
                    if side == 'Buy':
                        loss_per_unit = avg_price - sl_price
                    else:
                        loss_per_unit = sl_price - avg_price
                    
                    potential_loss = loss_per_unit * size
                    total_potential_loss += potential_loss
                    
                    # Determine approach (simplified - just check TP count)
                    tp_count = len(grouped['tp_orders'])
                    approach = "FAST" if tp_count <= 1 else "CONS"
                    
                    # Create SL order
                    sl_order = {
                        'account': account,
                        'symbol': symbol,
                        'side': side,
                        'size': size,
                        'entry_price': avg_price,
                        'sl_price': sl_price,
                        'potential_loss': potential_loss,
                        'order_params': {
                            'category': 'linear',
                            'symbol': symbol,
                            'side': side,  # Same side as position for SL
                            'orderType': 'Market',
                            'qty': str(size),
                            'triggerPrice': str(sl_price),
                            'triggerDirection': 2 if side == 'Buy' else 1,  # Below for long, above for short
                            'triggerBy': 'LastPrice',
                            'orderLinkId': generate_order_link_id(approach, symbol, "SL"),
                            'positionIdx': 1 if side == 'Buy' else 2,
                            'reduceOnly': True
                        }
                    }
                    
                    self.orders_to_create.append(sl_order)
                    positions_needing_sl.append(sl_order)
                    
                    logger.info(f"\n{symbol} ({side}):")
                    logger.info(f"  Position Size: {size}")
                    logger.info(f"  Entry Price: ${avg_price:.8g}")
                    logger.info(f"  SL Price (3%): ${sl_price:.8g}")
                    logger.info(f"  Potential Loss: 🔴 ${potential_loss:.2f}")
        
        # Summary
        logger.info(f"\n{'='*60}")
        logger.info(f"{account_name} ACCOUNT SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Positions needing SL: {len(positions_needing_sl)}")
        logger.info(f"Total Potential Loss (3% SL): 🔴 ${total_potential_loss:.2f}")
        
        return positions_needing_sl
    
    async def execute_orders(self):
        """Execute the stop loss orders"""
        if not self.orders_to_create:
            logger.info("\nNo stop loss orders to create.")
            return
        
        logger.info(f"\n{'='*60}")
        logger.info(f"STOP LOSS ORDERS TO CREATE: {len(self.orders_to_create)}")
        logger.info(f"{'='*60}")
        
        if self.dry_run:
            logger.info("[DRY RUN] Would create the following stop losses:")
            for order in self.orders_to_create:
                logger.info(f"\n{order['symbol']} ({order['side']}):")
                logger.info(f"  Entry: ${order['entry_price']:.8g}")
                logger.info(f"  SL: ${order['sl_price']:.8g} (-3%)")
                logger.info(f"  Size: {order['size']}")
                logger.info(f"  Potential Loss: 🔴 ${order['potential_loss']:.2f}")
            return
        
        # Execute orders
        success_count = 0
        error_count = 0
        
        for order_data in self.orders_to_create:
            try:
                client = bybit_client_2 if order_data['account'] == 'mirror' else bybit_client
                response = client.place_order(**order_data['order_params'])
                
                if response and response.get('retCode') == 0:
                    result = response.get('result', {})
                    order_id = result.get('orderId', '')
                    logger.info(f"✅ Created SL for {order_data['symbol']}: {order_id[:8]}...")
                    success_count += 1
                else:
                    logger.error(f"❌ Failed to create SL for {order_data['symbol']}: "
                               f"{response.get('retMsg', 'Unknown error')}")
                    error_count += 1
                    
            except Exception as e:
                logger.error(f"❌ Error creating SL for {order_data['symbol']}: {e}")
                error_count += 1
            
            # Small delay between orders
            await asyncio.sleep(0.1)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"SUMMARY: {success_count} created, {error_count} failed")
        logger.info(f"{'='*60}")


async def main():
    """Main function"""
    import sys
    
    dry_run = "--live" not in sys.argv
    
    if "--help" in sys.argv:
        print("Usage: python add_missing_stop_losses.py [OPTIONS]")
        print("\nOptions:")
        print("  --live    Execute order creation (default is dry-run)")
        print("  --help    Show this help message")
        print("\nThis script adds 3% stop loss orders for positions without SL protection.")
        return
    
    adder = StopLossAdder(dry_run=dry_run)
    
    try:
        # Analyze main account
        logger.info("Analyzing MAIN account...")
        main_positions = await adder.analyze_and_add_stop_losses("main")
        
        # Analyze mirror account if enabled
        if is_mirror_trading_enabled():
            logger.info("\nAnalyzing MIRROR account...")
            mirror_positions = await adder.analyze_and_add_stop_losses("mirror")
        
        # Execute orders
        await adder.execute_orders()
        
        if dry_run:
            logger.info("\n💡 This was a DRY RUN. Use --live to execute changes.")
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())