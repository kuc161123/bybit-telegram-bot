#!/usr/bin/env python3
"""
Rebalance positions to have proper TP/SL orders according to their trading approach.
Fast approach: 1 TP (100%) + 1 SL
Conservative approach: 4 TPs (70%, 10%, 10%, 10%) + 1 SL
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import sys

from clients.bybit_client import bybit_client
from clients.bybit_helpers import get_all_positions, get_all_open_orders, api_call_with_retry
from config.settings import ENABLE_MIRROR_TRADING
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Conservative approach TP percentages
CONSERVATIVE_TP_PERCENTAGES = [70, 10, 10, 10]

def format_decimal(value: Decimal, scale: int) -> Decimal:
    """Format decimal to specific number of decimal places"""
    if scale == 0:
        return value.quantize(Decimal('1'))
    format_str = '0.' + '0' * scale
    return value.quantize(Decimal(format_str))

class PositionRebalancer:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.client = bybit_client
        
    async def get_positions_and_orders(self, account: str = "main") -> Tuple[List[Dict], List[Dict]]:
        """Get all positions and orders for the specified account"""
        if account == "mirror" and is_mirror_trading_enabled():
            # Get mirror positions
            pos_response = await api_call_with_retry(
                lambda: bybit_client_2.get_positions(
                    category="linear",
                    settleCoin="USDT"
                ),
                timeout=30
            )
            positions = pos_response.get("result", {}).get("list", []) if pos_response and pos_response.get("retCode") == 0 else []
            
            # Get mirror orders
            order_response = await api_call_with_retry(
                lambda: bybit_client_2.get_open_orders(
                    category="linear",
                    settleCoin="USDT"
                ),
                timeout=30
            )
            orders = order_response.get("result", {}).get("list", []) if order_response and order_response.get("retCode") == 0 else []
        else:
            positions = await get_all_positions()
            orders = await get_all_open_orders()
            
        return positions, orders
    
    async def get_instrument_info(self, symbol: str) -> Dict:
        """Get instrument info for proper decimal formatting"""
        try:
            info = self.client.get_instruments_info(
                category="linear",
                symbol=symbol
            )
            if info and info.get('result') and info['result'].get('list'):
                return info['result']['list'][0]
        except Exception as e:
            logger.error(f"Error getting instrument info for {symbol}: {e}")
        return {}
    
    def detect_current_approach(self, position: Dict, tp_orders: List[Dict]) -> str:
        """Detect the current trading approach based on TP orders"""
        tp_count = len(tp_orders)
        
        if tp_count == 1:
            return "Fast"
        elif tp_count == 4:
            # Check if it follows conservative percentages
            position_qty = Decimal(str(position['size']))
            tp_percentages = []
            
            for tp in sorted(tp_orders, key=lambda x: float(x['price']), 
                           reverse=position['side'] == 'Buy'):
                tp_qty = Decimal(str(tp['qty']))
                percentage = (tp_qty / position_qty * 100).quantize(Decimal('0.1'))
                tp_percentages.append(float(percentage))
            
            # Check if it matches conservative pattern (allowing some tolerance)
            if len(tp_percentages) == 4:
                expected = CONSERVATIVE_TP_PERCENTAGES
                tolerance = 2  # 2% tolerance
                matches = all(
                    abs(actual - expected[i]) <= tolerance 
                    for i, actual in enumerate(tp_percentages)
                )
                if matches:
                    return "Conservative"
                    
        return f"Custom_{tp_count}TP"
    
    async def cancel_orders(self, symbol: str, order_ids: List[str], account: str = "main") -> bool:
        """Cancel multiple orders"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would cancel {len(order_ids)} orders for {symbol}")
            return True
            
        success = True
        for order_id in order_ids:
            try:
                if account == "mirror" and is_mirror_trading_enabled():
                    bybit_client_2.cancel_order(
                        category="linear",
                        symbol=symbol,
                        orderId=order_id
                    )
                else:
                    self.client.cancel_order(
                        category="linear",
                        symbol=symbol,
                        orderId=order_id
                    )
                logger.info(f"Cancelled order {order_id} for {symbol}")
            except Exception as e:
                logger.error(f"Failed to cancel order {order_id}: {e}")
                success = False
                
        return success
    
    async def create_tp_sl_orders(self, position: Dict, approach: str, 
                                  instrument_info: Dict, account: str = "main") -> bool:
        """Create proper TP and SL orders for a position"""
        symbol = position['symbol']
        side = position['side']
        position_qty = Decimal(str(position['size']))
        avg_price = Decimal(str(position['avgPrice']))
        
        # Get decimal precisions
        price_scale = int(instrument_info.get('priceScale', 2))
        qty_scale = int(instrument_info.get('qtyScale', 2))
        
        # Calculate SL price (2% from entry)
        sl_percentage = Decimal('0.02')
        if side == 'Buy':
            sl_price = avg_price * (Decimal('1') - sl_percentage)
        else:
            sl_price = avg_price * (Decimal('1') + sl_percentage)
        
        sl_price = format_decimal(sl_price, price_scale)
        
        # Create SL order
        sl_order = {
            'category': 'linear',
            'symbol': symbol,
            'side': 'Sell' if side == 'Buy' else 'Buy',
            'orderType': 'Market',
            'qty': str(format_decimal(position_qty, qty_scale)),
            'triggerPrice': str(sl_price),
            'triggerDirection': 2 if side == 'Buy' else 1,  # 2=below, 1=above
            'triggerBy': 'LastPrice',
            'orderLinkId': f"BOT_SL_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'positionIdx': 1 if side == 'Buy' else 2,
            'reduceOnly': True
        }
        
        orders_to_create = [sl_order]
        
        if approach == "Fast":
            # Single TP at 3% profit
            tp_percentage = Decimal('0.03')
            if side == 'Buy':
                tp_price = avg_price * (Decimal('1') + tp_percentage)
            else:
                tp_price = avg_price * (Decimal('1') - tp_percentage)
            
            tp_price = format_decimal(tp_price, price_scale)
            
            tp_order = {
                'category': 'linear',
                'symbol': symbol,
                'side': 'Sell' if side == 'Buy' else 'Buy',
                'orderType': 'Limit',
                'qty': str(format_decimal(position_qty, qty_scale)),
                'price': str(tp_price),
                'orderLinkId': f"BOT_TP1_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'positionIdx': 1 if side == 'Buy' else 2,
                'reduceOnly': True
            }
            orders_to_create.append(tp_order)
            
        else:  # Conservative
            # 4 TPs at different levels
            tp_levels = [
                (Decimal('0.015'), Decimal('70')),  # 1.5% profit, 70% qty
                (Decimal('0.03'), Decimal('10')),   # 3% profit, 10% qty
                (Decimal('0.045'), Decimal('10')),  # 4.5% profit, 10% qty
                (Decimal('0.06'), Decimal('10'))    # 6% profit, 10% qty
            ]
            
            for i, (tp_percentage, qty_percentage) in enumerate(tp_levels, 1):
                if side == 'Buy':
                    tp_price = avg_price * (Decimal('1') + tp_percentage)
                else:
                    tp_price = avg_price * (Decimal('1') - tp_percentage)
                
                tp_price = format_decimal(tp_price, price_scale)
                tp_qty = position_qty * qty_percentage / Decimal('100')
                tp_qty = format_decimal(tp_qty, qty_scale)
                
                tp_order = {
                    'category': 'linear',
                    'symbol': symbol,
                    'side': 'Sell' if side == 'Buy' else 'Buy',
                    'orderType': 'Limit',
                    'qty': str(tp_qty),
                    'price': str(tp_price),
                    'orderLinkId': f"BOT_TP{i}_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    'positionIdx': 1 if side == 'Buy' else 2,
                    'reduceOnly': True
                }
                orders_to_create.append(tp_order)
        
        # Place orders
        if self.dry_run:
            logger.info(f"[DRY RUN] Would create {len(orders_to_create)} orders for {symbol}:")
            for order in orders_to_create:
                order_type = "SL" if "SL" in order.get('orderLinkId', '') else "TP"
                logger.info(f"  - {order_type}: qty={order['qty']}, "
                          f"price={order.get('price') or order.get('trigger_price')}")
            return True
        
        success = True
        for order in orders_to_create:
            try:
                if account == "mirror" and is_mirror_trading_enabled():
                    bybit_client_2.place_order(**order)
                else:
                    self.client.place_order(**order)
                order_type = "SL" if "SL" in order.get('orderLinkId', '') else "TP"
                logger.info(f"Created {order_type} order for {symbol}")
            except Exception as e:
                logger.error(f"Failed to create order for {symbol}: {e}")
                success = False
                
        return success
    
    async def rebalance_position(self, position: Dict, orders: List[Dict], 
                                target_approach: str, account: str = "main") -> bool:
        """Rebalance a single position to the target approach"""
        symbol = position['symbol']
        side = position['side']
        
        # Filter orders for this position
        position_orders = [
            o for o in orders 
            if o['symbol'] == symbol and 
               o.get('positionIdx', 0) == (1 if side == 'Buy' else 2)
        ]
        
        # Separate TP and SL orders
        tp_orders = [o for o in position_orders if o['side'] != side]
        sl_orders = [o for o in position_orders if o['side'] == side]
        
        # Detect current approach
        current_approach = self.detect_current_approach(position, tp_orders)
        
        logger.info(f"\nRebalancing {symbol} ({side}):")
        logger.info(f"  Current approach: {current_approach}")
        logger.info(f"  Target approach: {target_approach}")
        logger.info(f"  Current orders: {len(tp_orders)} TPs, {len(sl_orders)} SLs")
        
        # Get instrument info
        instrument_info = await self.get_instrument_info(symbol)
        if not instrument_info:
            logger.error(f"Failed to get instrument info for {symbol}")
            return False
        
        # Cancel all existing TP/SL orders
        all_order_ids = [o['orderId'] for o in position_orders]
        if all_order_ids:
            logger.info(f"Cancelling {len(all_order_ids)} existing orders...")
            if not await self.cancel_orders(symbol, all_order_ids, account):
                logger.error(f"Failed to cancel some orders for {symbol}")
                if not self.dry_run:
                    return False
        
        # Create new orders according to target approach
        logger.info(f"Creating new {target_approach} orders...")
        return await self.create_tp_sl_orders(position, target_approach, 
                                            instrument_info, account)
    
    async def rebalance_all_positions(self, target_approach: Optional[str] = None):
        """Rebalance all positions in main account"""
        logger.info("=== Rebalancing Main Account Positions ===")
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        if target_approach:
            logger.info(f"Target approach: {target_approach}")
        
        # Get positions and orders
        positions, orders = await self.get_positions_and_orders("main")
        
        if not positions:
            logger.info("No positions found in main account")
            return
        
        logger.info(f"Found {len(positions)} positions to rebalance")
        
        success_count = 0
        for position in positions:
            symbol = position['symbol']
            side = position['side']
            
            # Skip if no size
            if float(position['size']) == 0:
                continue
            
            # Determine target approach if not specified
            if not target_approach:
                # Check existing orders to guess preferred approach
                position_orders = [
                    o for o in orders 
                    if o['symbol'] == symbol and 
                       o.get('positionIdx', 0) == (1 if side == 'Buy' else 2)
                ]
                tp_orders = [o for o in position_orders if o['side'] != side]
                
                # If has 4 or more TPs, assume Conservative, otherwise Fast
                position_target = "Conservative" if len(tp_orders) >= 4 else "Fast"
            else:
                position_target = target_approach
            
            # Rebalance position
            success = await self.rebalance_position(position, orders, 
                                                  position_target, "main")
            if success:
                success_count += 1
            
            # Small delay between positions
            await asyncio.sleep(0.5)
        
        logger.info(f"\n=== Rebalancing Complete ===")
        logger.info(f"Successfully rebalanced: {success_count}/{len(positions)} positions")


async def main():
    """Main function"""
    # Parse command line arguments
    dry_run = "--live" not in sys.argv
    target_approach = None
    
    if "--fast" in sys.argv:
        target_approach = "Fast"
    elif "--conservative" in sys.argv:
        target_approach = "Conservative"
    
    # Show usage if needed
    if "--help" in sys.argv:
        print("Usage: python rebalance_positions_tp_sl.py [OPTIONS]")
        print("\nOptions:")
        print("  --live          Execute changes (default is dry-run)")
        print("  --fast          Set all positions to Fast approach")
        print("  --conservative  Set all positions to Conservative approach")
        print("  --help          Show this help message")
        print("\nIf no approach is specified, each position will be set to:")
        print("  - Conservative if it currently has 4+ TPs")
        print("  - Fast otherwise")
        return
    
    # Create rebalancer
    rebalancer = PositionRebalancer(dry_run=dry_run)
    
    # Run rebalancing
    await rebalancer.rebalance_all_positions(target_approach)


if __name__ == "__main__":
    asyncio.run(main())