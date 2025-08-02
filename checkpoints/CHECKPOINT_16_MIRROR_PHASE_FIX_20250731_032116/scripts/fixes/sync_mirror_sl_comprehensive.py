#!/usr/bin/env python3
"""
Comprehensive Mirror SL Sync Script
Syncs mirror account SL orders to match main account, with fallback to pickle data
"""

import asyncio
import logging
from decimal import Decimal
import time
import sys
import os
from typing import Dict, List, Optional, Tuple
import pickle
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MirrorSLSynchronizer:
    def __init__(self):
        self.main_client = None
        self.mirror_client = None
        self.pickle_data = None
        self.sync_report = {
            'synced': [],
            'created': [],
            'errors': [],
            'skipped': []
        }
    
    async def initialize(self):
        """Initialize clients and load data"""
        try:
            from clients.bybit_client import bybit_client
            from execution.mirror_trader import is_mirror_trading_enabled, bybit_client_2
            
            if not is_mirror_trading_enabled() or not bybit_client_2:
                raise Exception("Mirror trading is not enabled")
            
            self.main_client = bybit_client
            self.mirror_client = bybit_client_2
            
            # Load pickle data
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
                self.pickle_data = pickle.load(f)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            return False
    
    async def get_sl_price_for_position(self, symbol: str, side: str, account: str = "main") -> Optional[Decimal]:
        """Get SL price from multiple sources with fallback"""
        try:
            client = self.main_client if account == "main" else self.mirror_client
            
            # First try: Get from active orders
            response = client.get_open_orders(
                category="linear",
                symbol=symbol
            )
            
            if response['retCode'] == 0:
                orders = response.get('result', {}).get('list', [])
                sl_side = "Sell" if side == "Buy" else "Buy"
                
                for order in orders:
                    if (order.get('stopOrderType') in ['StopLoss', 'Stop'] and
                        order.get('side') == sl_side and
                        order.get('reduceOnly')):
                        return Decimal(str(order.get('triggerPrice', '0')))
            
            # Second try: Get from pickle monitors
            monitors = self.pickle_data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
            
            # Try different monitor key formats
            for key_format in [f"{symbol}_{side}", f"{symbol}_{side}_{account}"]:
                if key_format in monitors:
                    monitor = monitors[key_format]
                    if monitor.get('sl_order'):
                        sl_price = monitor['sl_order'].get('price')
                        if sl_price:
                            return Decimal(str(sl_price))
            
            # Third try: Get from user positions in pickle
            user_data = self.pickle_data.get('user_data', {})
            for chat_id, chat_data in user_data.items():
                positions = chat_data.get('positions', {})
                for pos_key, pos_data in positions.items():
                    if (pos_data.get('symbol') == symbol and 
                        pos_data.get('side') == side and
                        pos_data.get('account_type', 'main') == account):
                        
                        sl_price = pos_data.get('sl_price')
                        if sl_price:
                            return Decimal(str(sl_price))
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting SL price for {symbol} {side} {account}: {e}")
            return None
    
    async def calculate_target_size_with_limits(self, symbol: str, side: str, current_size: Decimal) -> Decimal:
        """Calculate target position size including unfilled limit orders"""
        try:
            response = self.mirror_client.get_open_orders(
                category="linear",
                symbol=symbol
            )
            
            if response['retCode'] != 0:
                return current_size
            
            unfilled_limit_qty = Decimal('0')
            orders = response.get('result', {}).get('list', [])
            
            for order in orders:
                if (order.get('orderType') == 'Limit' and 
                    not order.get('reduceOnly') and 
                    order.get('side') == side and
                    order.get('orderStatus') in ['New', 'PartiallyFilled'] and
                    ('BOT_' in order.get('orderLinkId', '') or 'MIR_' in order.get('orderLinkId', ''))):
                    
                    if order.get('orderStatus') == 'PartiallyFilled':
                        total_qty = Decimal(str(order.get('qty', '0')))
                        filled_qty = Decimal(str(order.get('cumExecQty', '0')))
                        unfilled_limit_qty += (total_qty - filled_qty)
                    else:
                        unfilled_limit_qty += Decimal(str(order.get('qty', '0')))
            
            return current_size + unfilled_limit_qty
            
        except Exception as e:
            logger.error(f"Error calculating target size: {e}")
            return current_size
    
    async def sync_single_position(self, symbol: str, side: str, mirror_position: Dict) -> str:
        """Sync SL for a single position"""
        try:
            from execution.mirror_trader import mirror_tp_sl_order, amend_mirror_sl_order, cancel_mirror_order
            from clients.bybit_helpers import get_instrument_info
            from utils.helpers import value_adjusted_to_step
            
            mirror_size = Decimal(str(mirror_position.get('size', '0')))
            
            # Get main SL price
            main_sl_price = await self.get_sl_price_for_position(symbol, side, "main")
            if not main_sl_price:
                logger.warning(f"No main SL price found for {symbol} {side}")
                return "no_main_sl"
            
            # Get mirror SL order
            mirror_sl_price = None
            mirror_sl_order = None
            
            response = self.mirror_client.get_open_orders(
                category="linear",
                symbol=symbol
            )
            
            if response['retCode'] == 0:
                orders = response.get('result', {}).get('list', [])
                sl_side = "Sell" if side == "Buy" else "Buy"
                
                for order in orders:
                    if (order.get('stopOrderType') in ['StopLoss', 'Stop'] and
                        order.get('side') == sl_side and
                        order.get('reduceOnly')):
                        mirror_sl_order = order
                        mirror_sl_price = Decimal(str(order.get('triggerPrice', '0')))
                        break
            
            # Case 1: No mirror SL exists - create one
            if not mirror_sl_order:
                logger.info(f"Creating new SL for {symbol} {side} @ {main_sl_price}")
                
                # Calculate target size with limits
                target_size = await self.calculate_target_size_with_limits(symbol, side, mirror_size)
                
                # Get instrument info
                instrument_info = await get_instrument_info(symbol)
                if instrument_info:
                    lot_size_filter = instrument_info.get('lotSizeFilter', {})
                    qty_step = Decimal(lot_size_filter.get('qtyStep', '1'))
                    adjusted_qty = value_adjusted_to_step(target_size, qty_step)
                else:
                    adjusted_qty = target_size
                
                # Place SL order
                sl_side = "Sell" if side == "Buy" else "Buy"
                order_link_id = f"MIR_SL_SYNC_{symbol}_{int(time.time())}"
                
                sl_result = await mirror_tp_sl_order(
                    symbol=symbol,
                    side=sl_side,
                    qty=str(adjusted_qty),
                    trigger_price=str(main_sl_price),
                    position_idx=0,
                    order_link_id=order_link_id,
                    stop_order_type="StopLoss"
                )
                
                if sl_result and sl_result.get('orderId'):
                    self.sync_report['created'].append({
                        'symbol': symbol,
                        'side': side,
                        'price': str(main_sl_price),
                        'quantity': str(adjusted_qty),
                        'order_id': sl_result['orderId']
                    })
                    return "created"
                else:
                    return "create_failed"
            
            # Case 2: Mirror SL exists but price differs - sync it
            if mirror_sl_price != main_sl_price:
                logger.info(f"Syncing SL for {symbol} {side}: {mirror_sl_price} → {main_sl_price}")
                
                # Try to amend first
                amend_result = await amend_mirror_sl_order(
                    symbol=symbol,
                    order_id=mirror_sl_order['orderId'],
                    new_trigger_price=str(main_sl_price)
                )
                
                if amend_result:
                    self.sync_report['synced'].append({
                        'symbol': symbol,
                        'side': side,
                        'old_price': str(mirror_sl_price),
                        'new_price': str(main_sl_price),
                        'method': 'amended'
                    })
                    return "synced"
                
                # If amend fails, cancel and replace
                cancel_result = await cancel_mirror_order(symbol, mirror_sl_order['orderId'])
                if not cancel_result:
                    return "sync_failed"
                
                # Place new order
                sl_result = await mirror_tp_sl_order(
                    symbol=symbol,
                    side=mirror_sl_order['side'],
                    qty=mirror_sl_order['qty'],
                    trigger_price=str(main_sl_price),
                    position_idx=0,
                    order_link_id=f"MIR_SL_SYNC_{symbol}_{int(time.time())}",
                    stop_order_type="StopLoss"
                )
                
                if sl_result and sl_result.get('orderId'):
                    self.sync_report['synced'].append({
                        'symbol': symbol,
                        'side': side,
                        'old_price': str(mirror_sl_price),
                        'new_price': str(main_sl_price),
                        'method': 'replaced'
                    })
                    return "synced"
                else:
                    return "sync_failed"
            
            # Case 3: Prices already match
            return "already_synced"
            
        except Exception as e:
            logger.error(f"Error syncing {symbol} {side}: {e}")
            self.sync_report['errors'].append({
                'symbol': symbol,
                'side': side,
                'error': str(e)
            })
            return "error"
    
    async def run_sync(self):
        """Run the complete synchronization process"""
        try:
            if not await self.initialize():
                return
            
            logger.info("🔄 Comprehensive Mirror SL Synchronization")
            logger.info("=" * 80)
            
            from clients.bybit_helpers import get_all_positions
            
            # Get all positions
            main_positions = await get_all_positions(client=self.main_client)
            mirror_positions = await get_all_positions(client=self.mirror_client)
            
            # Filter active positions
            active_mirror = [pos for pos in mirror_positions if float(pos.get('size', 0)) > 0]
            
            logger.info(f"📊 Found {len(active_mirror)} active mirror positions")
            
            # Track results
            results = {
                'already_synced': 0,
                'synced': 0,
                'created': 0,
                'no_main_sl': 0,
                'errors': 0
            }
            
            # Process each mirror position
            for position in active_mirror:
                symbol = position['symbol']
                side = position['side']
                
                logger.info(f"\n🎯 Processing {symbol} {side}")
                
                result = await self.sync_single_position(symbol, side, position)
                
                if result == "already_synced":
                    logger.info(f"   ✅ Already synced")
                    results['already_synced'] += 1
                elif result == "synced":
                    logger.info(f"   ✅ Successfully synced")
                    results['synced'] += 1
                elif result == "created":
                    logger.info(f"   ✅ SL order created")
                    results['created'] += 1
                elif result == "no_main_sl":
                    logger.warning(f"   ⚠️ No main SL found - skipped")
                    results['no_main_sl'] += 1
                    self.sync_report['skipped'].append({
                        'symbol': symbol,
                        'side': side,
                        'reason': 'no_main_sl'
                    })
                else:
                    logger.error(f"   ❌ Sync failed: {result}")
                    results['errors'] += 1
            
            # Save detailed report
            report_data = {
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'summary': results,
                'details': self.sync_report
            }
            
            with open('mirror_sl_sync_detailed_report.json', 'w') as f:
                json.dump(report_data, f, indent=2)
            
            # Print summary
            logger.info("\n" + "=" * 80)
            logger.info("✅ Mirror SL Synchronization Complete!")
            logger.info(f"📊 Summary:")
            logger.info(f"   Total positions: {len(active_mirror)}")
            logger.info(f"   Already synced: {results['already_synced']}")
            logger.info(f"   Newly synced: {results['synced']}")
            logger.info(f"   SL created: {results['created']}")
            logger.info(f"   No main SL: {results['no_main_sl']}")
            logger.info(f"   Errors: {results['errors']}")
            logger.info("=" * 80)
            logger.info("📝 Detailed report saved to mirror_sl_sync_detailed_report.json")
            
        except Exception as e:
            logger.error(f"❌ Critical error in sync process: {e}")
            import traceback
            traceback.print_exc()

async def main():
    synchronizer = MirrorSLSynchronizer()
    await synchronizer.run_sync()

if __name__ == "__main__":
    asyncio.run(main())