#!/usr/bin/env python3
"""
Fix missing TP/SL orders in mirror account by creating them based on main account orders.
"""

import asyncio
import logging
from typing import Dict, List, Tuple
from decimal import Decimal
from collections import defaultdict

from clients.bybit_client import bybit_client
from clients.bybit_helpers import get_all_positions, get_all_open_orders, api_call_with_retry
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
from utils.order_identifier import (
    identify_order_type, generate_order_link_id, group_orders_by_type,
    validate_order_coverage, ORDER_TYPE_TP, ORDER_TYPE_SL
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MirrorOrderFixer:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.orders_to_create = []
        
    async def get_main_account_data(self) -> Tuple[List[Dict], List[Dict]]:
        """Get positions and orders from main account"""
        positions = await get_all_positions()
        orders = await get_all_open_orders()
        return positions, orders
    
    async def get_mirror_account_data(self) -> Tuple[List[Dict], List[Dict]]:
        """Get positions and orders from mirror account"""
        if not is_mirror_trading_enabled():
            return [], []
            
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
                settleCoin="USDT"
            ),
            timeout=30
        )
        orders = order_response.get("result", {}).get("list", []) if order_response and order_response.get("retCode") == 0 else []
        
        return positions, orders
    
    async def analyze_missing_orders(self):
        """Analyze and create missing orders for mirror account"""
        logger.info("Analyzing missing orders in mirror account...")
        
        # Get data from both accounts
        main_positions, main_orders = await self.get_main_account_data()
        mirror_positions, mirror_orders = await self.get_mirror_account_data()
        
        if not is_mirror_trading_enabled():
            logger.error("Mirror trading is not enabled!")
            return
        
        # Group orders by symbol
        main_orders_by_symbol = defaultdict(list)
        for order in main_orders:
            main_orders_by_symbol[order['symbol']].append(order)
            
        mirror_orders_by_symbol = defaultdict(list)
        for order in mirror_orders:
            mirror_orders_by_symbol[order['symbol']].append(order)
        
        # Analyze each mirror position
        for mirror_pos in mirror_positions:
            if float(mirror_pos.get('size', 0)) <= 0:
                continue
                
            symbol = mirror_pos['symbol']
            side = mirror_pos['side']
            size = Decimal(str(mirror_pos['size']))
            
            # Find corresponding main position
            main_pos = None
            for mp in main_positions:
                if mp['symbol'] == symbol and mp['side'] == side and float(mp.get('size', 0)) > 0:
                    main_pos = mp
                    break
            
            if not main_pos:
                logger.warning(f"No corresponding main position found for {symbol} {side}")
                continue
            
            # Get orders
            main_pos_orders = main_orders_by_symbol.get(symbol, [])
            mirror_pos_orders = mirror_orders_by_symbol.get(symbol, [])
            
            # Filter orders for this position
            main_pos_orders = [
                o for o in main_pos_orders 
                if o.get('positionIdx', 0) == (1 if side == 'Buy' else 2)
            ]
            mirror_pos_orders = [
                o for o in mirror_pos_orders 
                if o.get('positionIdx', 0) == (1 if side == 'Buy' else 2)
            ]
            
            # Validate coverage
            main_coverage = validate_order_coverage(main_pos, main_pos_orders)
            mirror_coverage = validate_order_coverage(mirror_pos, mirror_pos_orders)
            
            logger.info(f"\n{symbol} ({side}):")
            logger.info(f"  Main account: {main_coverage['tp_count']} TPs ({main_coverage['tp_coverage_pct']:.1f}%), "
                       f"{main_coverage['sl_count']} SLs ({main_coverage['sl_coverage_pct']:.1f}%)")
            logger.info(f"  Mirror account: {mirror_coverage['tp_count']} TPs ({mirror_coverage['tp_coverage_pct']:.1f}%), "
                       f"{mirror_coverage['sl_count']} SLs ({mirror_coverage['sl_coverage_pct']:.1f}%)")
            
            # If mirror has no orders, copy from main
            if mirror_coverage['tp_count'] == 0 and mirror_coverage['sl_count'] == 0:
                await self._create_mirror_orders_from_main(
                    mirror_pos, main_pos, main_pos_orders
                )
            elif not mirror_coverage['has_complete_coverage']:
                logger.warning(f"  Mirror account has incomplete coverage: {mirror_coverage['issues']}")
                # Could implement partial fix logic here
    
    async def _create_mirror_orders_from_main(self, mirror_pos: Dict, main_pos: Dict, main_orders: List[Dict]):
        """Create mirror orders based on main account orders"""
        symbol = mirror_pos['symbol']
        side = mirror_pos['side']
        mirror_size = Decimal(str(mirror_pos['size']))
        main_size = Decimal(str(main_pos['size']))
        
        # Calculate size ratio for proportional orders
        size_ratio = mirror_size / main_size if main_size > 0 else Decimal('1')
        
        # Group main orders
        grouped = group_orders_by_type(main_orders, main_pos)
        
        logger.info(f"  Creating orders for {symbol} (size ratio: {size_ratio:.4f})")
        
        # Create TP orders
        for i, tp_order in enumerate(grouped['tp_orders']):
            new_qty = Decimal(str(tp_order['qty'])) * size_ratio
            
            # Determine approach from order count
            approach = "FAST" if len(grouped['tp_orders']) == 1 else "CONS"
            
            new_order = {
                'category': 'linear',
                'symbol': symbol,
                'side': tp_order['side'],
                'orderType': tp_order['orderType'],
                'qty': str(new_qty.quantize(Decimal('0.001'))),  # Will be adjusted per symbol later
                'positionIdx': 1 if side == 'Buy' else 2,
                'reduceOnly': True
            }
            
            # Add price info based on order type
            if tp_order['orderType'] == 'Limit':
                new_order['price'] = tp_order['price']
                new_order['orderLinkId'] = generate_order_link_id(
                    approach, symbol, "TP", 
                    index=i+1 if len(grouped['tp_orders']) > 1 else None
                )
            else:  # Market order with trigger
                new_order['triggerPrice'] = tp_order['triggerPrice']
                new_order['triggerDirection'] = tp_order.get('triggerDirection', 1)
                new_order['triggerBy'] = tp_order.get('triggerBy', 'LastPrice')
                new_order['orderLinkId'] = generate_order_link_id(
                    approach, symbol, "TP",
                    index=i+1 if len(grouped['tp_orders']) > 1 else None
                )
            
            self.orders_to_create.append(('mirror', new_order))
            logger.info(f"    - TP{i+1 if len(grouped['tp_orders']) > 1 else ''}: "
                       f"{new_order.get('price') or new_order.get('triggerPrice')} "
                       f"(qty: {new_order['qty']})")
        
        # Create SL orders
        for sl_order in grouped['sl_orders']:
            new_qty = Decimal(str(sl_order['qty'])) * size_ratio
            
            # Determine approach
            approach = "FAST" if len(grouped['tp_orders']) == 1 else "CONS"
            
            new_order = {
                'category': 'linear',
                'symbol': symbol,
                'side': sl_order['side'],
                'orderType': 'Market',
                'qty': str(new_qty.quantize(Decimal('0.001'))),
                'triggerPrice': sl_order['triggerPrice'],
                'triggerDirection': sl_order.get('triggerDirection', 2 if side == 'Buy' else 1),
                'triggerBy': sl_order.get('triggerBy', 'LastPrice'),
                'orderLinkId': generate_order_link_id(approach, symbol, "SL"),
                'positionIdx': 1 if side == 'Buy' else 2,
                'reduceOnly': True
            }
            
            self.orders_to_create.append(('mirror', new_order))
            logger.info(f"    - SL: {new_order['triggerPrice']} (qty: {new_order['qty']})")
    
    async def execute_orders(self):
        """Execute the order creation"""
        if not self.orders_to_create:
            logger.info("\nNo orders to create.")
            return
        
        logger.info(f"\n{'='*60}")
        logger.info(f"ORDERS TO CREATE: {len(self.orders_to_create)}")
        logger.info(f"{'='*60}")
        
        if self.dry_run:
            logger.info("[DRY RUN] Would create the following orders:")
            for account, order in self.orders_to_create:
                logger.info(f"  [{account.upper()}] {order['symbol']} "
                           f"{order.get('orderLinkId', 'NO_LINK_ID')}")
            return
        
        # Execute orders
        success_count = 0
        error_count = 0
        
        for account, order in self.orders_to_create:
            try:
                if account == 'mirror':
                    # Get instrument info for proper quantity formatting
                    symbol = order['symbol']
                    info_response = bybit_client_2.get_instruments_info(
                        category="linear",
                        symbol=symbol
                    )
                    
                    if info_response and info_response.get('result'):
                        instrument = info_response['result']['list'][0]
                        qty_step = Decimal(str(instrument['lotSizeFilter']['qtyStep']))
                        
                        # Adjust quantity to match step size
                        current_qty = Decimal(order['qty'])
                        order['qty'] = str((current_qty / qty_step).quantize(Decimal('1')) * qty_step)
                    
                    # Place order
                    response = bybit_client_2.place_order(**order)
                    
                    if response and response.get('retCode') == 0:
                        logger.info(f"✅ Created {order.get('orderLinkId', 'order')}")
                        success_count += 1
                    else:
                        logger.error(f"❌ Failed to create {order.get('orderLinkId', 'order')}: "
                                   f"{response.get('retMsg', 'Unknown error')}")
                        error_count += 1
                        
            except Exception as e:
                logger.error(f"❌ Error creating order: {e}")
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
        print("Usage: python fix_mirror_missing_orders.py [OPTIONS]")
        print("\nOptions:")
        print("  --live    Execute order creation (default is dry-run)")
        print("  --help    Show this help message")
        return
    
    fixer = MirrorOrderFixer(dry_run=dry_run)
    
    try:
        await fixer.analyze_missing_orders()
        await fixer.execute_orders()
        
        if dry_run:
            logger.info("\n💡 This was a DRY RUN. Use --live to execute changes.")
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())