#!/usr/bin/env python3
"""
Sync Mirror Account SL Prices from Main Account
This script ensures mirror account SL orders have the same prices as main account SL orders
"""

import asyncio
import logging
from decimal import Decimal
import time
import sys
import os
from typing import Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def get_sl_order_for_position(client, symbol: str, side: str) -> Optional[Dict]:
    """Get active SL order for a position"""
    try:
        response = client.get_open_orders(
            category="linear",
            symbol=symbol
        )
        
        if response['retCode'] != 0:
            return None
        
        orders = response.get('result', {}).get('list', [])
        
        # Find SL order for this position
        # SL orders have opposite side to position and reduceOnly=True
        sl_side = "Sell" if side == "Buy" else "Buy"
        
        for order in orders:
            if (order.get('stopOrderType') in ['StopLoss', 'Stop'] and
                order.get('side') == sl_side and
                order.get('reduceOnly')):
                return order
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting SL order for {symbol} {side}: {e}")
        return None

async def sync_mirror_sl_prices():
    """Sync mirror account SL prices to match main account"""
    try:
        from clients.bybit_helpers import get_all_positions, get_instrument_info
        from utils.helpers import value_adjusted_to_step
        from execution.mirror_trader import (
            is_mirror_trading_enabled, bybit_client_2, 
            mirror_tp_sl_order, amend_mirror_sl_order, cancel_mirror_order
        )
        from clients.bybit_client import bybit_client
        import pickle
        
        if not is_mirror_trading_enabled() or not bybit_client_2:
            logger.error("❌ Mirror trading is not enabled")
            return
        
        logger.info("🔄 Syncing Mirror Account SL Prices from Main Account")
        logger.info("=" * 80)
        
        # Get all positions from both accounts
        main_positions = await get_all_positions(client=bybit_client)
        mirror_positions = await get_all_positions(client=bybit_client_2)
        
        # Filter active positions
        active_main = {f"{pos['symbol']}_{pos['side']}": pos 
                      for pos in main_positions if float(pos.get('size', 0)) > 0}
        active_mirror = {f"{pos['symbol']}_{pos['side']}": pos 
                        for pos in mirror_positions if float(pos.get('size', 0)) > 0}
        
        logger.info(f"📊 Found {len(active_main)} main positions, {len(active_mirror)} mirror positions")
        
        synced_count = 0
        created_count = 0
        error_count = 0
        already_synced = 0
        
        # Process each mirror position
        for position_key, mirror_pos in active_mirror.items():
            try:
                symbol = mirror_pos['symbol']
                side = mirror_pos['side']
                mirror_size = Decimal(str(mirror_pos.get('size', '0')))
                
                logger.info(f"\n🎯 Processing {symbol} {side}")
                
                # Check if main position exists
                if position_key not in active_main:
                    logger.warning(f"   ⚠️ No matching main position found - skipping")
                    continue
                
                main_pos = active_main[position_key]
                
                # Get SL orders from both accounts
                main_sl = await get_sl_order_for_position(bybit_client, symbol, side)
                mirror_sl = await get_sl_order_for_position(bybit_client_2, symbol, side)
                
                if not main_sl:
                    logger.warning(f"   ⚠️ No SL order found on main account - skipping")
                    continue
                
                main_sl_price = Decimal(str(main_sl.get('triggerPrice', '0')))
                logger.info(f"   Main SL price: {main_sl_price}")
                
                # Handle missing mirror SL
                if not mirror_sl:
                    logger.info(f"   ❗ No SL order on mirror account - creating one")
                    
                    # Get unfilled limit orders for full coverage
                    response = bybit_client_2.get_open_orders(
                        category="linear",
                        symbol=symbol
                    )
                    
                    unfilled_limit_qty = Decimal('0')
                    if response['retCode'] == 0:
                        orders = response.get('result', {}).get('list', [])
                        for order in orders:
                            if (order.get('orderType') == 'Limit' and 
                                not order.get('reduceOnly') and 
                                order.get('side') == side and
                                order.get('orderStatus') in ['New', 'PartiallyFilled']):
                                
                                if order.get('orderStatus') == 'PartiallyFilled':
                                    total_qty = Decimal(str(order.get('qty', '0')))
                                    filled_qty = Decimal(str(order.get('cumExecQty', '0')))
                                    unfilled_limit_qty += (total_qty - filled_qty)
                                else:
                                    unfilled_limit_qty += Decimal(str(order.get('qty', '0')))
                    
                    # Calculate target size
                    target_size = mirror_size + unfilled_limit_qty
                    
                    # Get instrument info for quantity adjustment
                    instrument_info = await get_instrument_info(symbol)
                    if instrument_info:
                        lot_size_filter = instrument_info.get('lotSizeFilter', {})
                        qty_step = Decimal(lot_size_filter.get('qtyStep', '1'))
                        adjusted_qty = value_adjusted_to_step(target_size, qty_step)
                    else:
                        adjusted_qty = target_size
                    
                    # Place new SL order
                    sl_side = "Sell" if side == "Buy" else "Buy"
                    order_link_id = f"MIR_SL_SYNC_{symbol}_{int(time.time())}"
                    
                    logger.info(f"   Placing SL: {adjusted_qty} @ {main_sl_price}")
                    
                    sl_result = await mirror_tp_sl_order(
                        symbol=symbol,
                        side=sl_side,
                        qty=str(adjusted_qty),
                        trigger_price=str(main_sl_price),
                        position_idx=0,  # Mirror uses One-Way mode
                        order_link_id=order_link_id,
                        stop_order_type="StopLoss"
                    )
                    
                    if sl_result and sl_result.get('orderId'):
                        logger.info(f"   ✅ SL created: {sl_result['orderId'][:8]}...")
                        created_count += 1
                    else:
                        logger.error(f"   ❌ Failed to create SL order")
                        error_count += 1
                    
                    continue
                
                # Check if prices match
                mirror_sl_price = Decimal(str(mirror_sl.get('triggerPrice', '0')))
                
                if mirror_sl_price == main_sl_price:
                    logger.info(f"   ✅ SL prices already synced: {mirror_sl_price}")
                    already_synced += 1
                    continue
                
                logger.info(f"   Mirror SL price: {mirror_sl_price}")
                logger.info(f"   📈 Price difference: {abs(mirror_sl_price - main_sl_price)}")
                
                # Try to amend the existing SL order
                mirror_order_id = mirror_sl.get('orderId')
                logger.info(f"   Amending SL order {mirror_order_id[:8]}...")
                
                amend_result = await amend_mirror_sl_order(
                    symbol=symbol,
                    order_id=mirror_order_id,
                    new_trigger_price=str(main_sl_price)
                )
                
                if amend_result:
                    logger.info(f"   ✅ SL price synced: {mirror_sl_price} → {main_sl_price}")
                    synced_count += 1
                else:
                    # If amend fails, try cancel and replace
                    logger.info(f"   ⚠️ Amend failed, trying cancel and replace...")
                    
                    # Cancel existing order
                    cancel_result = await cancel_mirror_order(symbol, mirror_order_id)
                    if not cancel_result:
                        logger.error(f"   ❌ Failed to cancel existing SL order")
                        error_count += 1
                        continue
                    
                    # Get current mirror position size for new order
                    mirror_qty = mirror_sl.get('qty', str(mirror_size))
                    
                    # Place new SL order with main price
                    sl_side = "Sell" if side == "Buy" else "Buy"
                    order_link_id = f"MIR_SL_SYNC_{symbol}_{int(time.time())}"
                    
                    sl_result = await mirror_tp_sl_order(
                        symbol=symbol,
                        side=sl_side,
                        qty=mirror_qty,
                        trigger_price=str(main_sl_price),
                        position_idx=0,
                        order_link_id=order_link_id,
                        stop_order_type="StopLoss"
                    )
                    
                    if sl_result and sl_result.get('orderId'):
                        logger.info(f"   ✅ SL replaced with synced price: {main_sl_price}")
                        synced_count += 1
                    else:
                        logger.error(f"   ❌ Failed to place replacement SL order")
                        error_count += 1
                
            except Exception as e:
                logger.error(f"   ❌ Error processing {position_key}: {e}")
                error_count += 1
        
        # Process main positions without mirror positions to check for missing mirrors
        missing_mirrors = []
        for position_key in active_main:
            if position_key not in active_mirror:
                missing_mirrors.append(position_key)
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("✅ Mirror SL Price Sync Complete!")
        logger.info(f"📊 Summary:")
        logger.info(f"   Total mirror positions: {len(active_mirror)}")
        logger.info(f"   Already synced: {already_synced}")
        logger.info(f"   Prices synced: {synced_count}")
        logger.info(f"   SL orders created: {created_count}")
        logger.info(f"   Errors: {error_count}")
        
        if missing_mirrors:
            logger.info(f"\n⚠️ Main positions without mirror: {len(missing_mirrors)}")
            for pos_key in missing_mirrors[:5]:  # Show first 5
                logger.info(f"   - {pos_key}")
            if len(missing_mirrors) > 5:
                logger.info(f"   ... and {len(missing_mirrors) - 5} more")
        
        logger.info("=" * 80)
        
        # Save sync report
        report = {
            'timestamp': time.time(),
            'synced_count': synced_count,
            'created_count': created_count,
            'error_count': error_count,
            'already_synced': already_synced,
            'total_mirror_positions': len(active_mirror),
            'missing_mirrors': missing_mirrors
        }
        
        import json
        with open('mirror_sl_sync_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info("📝 Detailed report saved to mirror_sl_sync_report.json")
        
    except Exception as e:
        logger.error(f"❌ Critical error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(sync_mirror_sl_prices())