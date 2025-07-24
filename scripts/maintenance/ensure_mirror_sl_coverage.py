#!/usr/bin/env python3
"""
Ensure Mirror SL Coverage
This script ensures all mirror positions have proper SL orders with correct prices and quantities
"""

import asyncio
import logging
from decimal import Decimal
import time
import sys
import os
from typing import Dict, List, Optional, Tuple
import pickle

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def ensure_mirror_sl_coverage():
    """Ensure all mirror positions have proper SL coverage"""
    try:
        from clients.bybit_helpers import get_all_positions, get_instrument_info
        from utils.helpers import value_adjusted_to_step
        from execution.mirror_trader import is_mirror_trading_enabled, bybit_client_2, mirror_tp_sl_order
        from clients.bybit_client import bybit_client
        
        if not is_mirror_trading_enabled() or not bybit_client_2:
            logger.error("❌ Mirror trading is not enabled")
            return
        
        logger.info("🛡️ Ensuring Mirror SL Coverage")
        logger.info("=" * 80)
        
        # Load pickle for SL prices
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            pickle_data = pickle.load(f)
        
        monitors = pickle_data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        # Get all positions
        mirror_positions = await get_all_positions(client=bybit_client_2)
        active_positions = [pos for pos in mirror_positions if float(pos.get('size', 0)) > 0]
        
        logger.info(f"📊 Found {len(active_positions)} active mirror positions")
        
        fixed_count = 0
        already_ok_count = 0
        error_count = 0
        
        for position in active_positions:
            try:
                symbol = position['symbol']
                side = position['side']
                position_size = Decimal(str(position.get('size', '0')))
                
                logger.info(f"\n🎯 Checking {symbol} {side}")
                
                # Get current orders
                response = bybit_client_2.get_open_orders(
                    category="linear",
                    symbol=symbol
                )
                
                if response['retCode'] != 0:
                    logger.error(f"   ❌ Failed to get orders")
                    error_count += 1
                    continue
                
                orders = response.get('result', {}).get('list', [])
                
                # Find existing SL
                existing_sl = None
                sl_side = "Sell" if side == "Buy" else "Buy"
                
                for order in orders:
                    if (order.get('stopOrderType') in ['StopLoss', 'Stop'] and
                        order.get('side') == sl_side and
                        order.get('reduceOnly')):
                        existing_sl = order
                        break
                
                # Calculate required coverage (including unfilled limits)
                unfilled_limit_qty = Decimal('0')
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
                
                target_size = position_size + unfilled_limit_qty
                
                # Get SL price from monitors or main account
                sl_price = None
                
                # Try to get from monitors
                for key in [f"{symbol}_{side}", f"{symbol}_{side}_main", f"{symbol}_{side}_mirror"]:
                    if key in monitors:
                        monitor = monitors[key]
                        if monitor.get('sl_order'):
                            sl_price = monitor['sl_order'].get('price')
                            if sl_price:
                                logger.info(f"   Found SL price from monitor: {sl_price}")
                                break
                
                # If no price in monitors, try to get from main account
                if not sl_price:
                    main_response = bybit_client.get_open_orders(
                        category="linear",
                        symbol=symbol
                    )
                    
                    if main_response['retCode'] == 0:
                        main_orders = main_response.get('result', {}).get('list', [])
                        for order in main_orders:
                            if (order.get('stopOrderType') in ['StopLoss', 'Stop'] and
                                order.get('side') == sl_side and
                                order.get('reduceOnly')):
                                sl_price = order.get('triggerPrice')
                                logger.info(f"   Found SL price from main account: {sl_price}")
                                break
                
                if not sl_price:
                    logger.warning(f"   ⚠️ No SL price found - skipping")
                    continue
                
                # Check if we need to fix the SL
                needs_fix = False
                fix_reason = ""
                
                if not existing_sl:
                    needs_fix = True
                    fix_reason = "No SL exists"
                else:
                    existing_qty = Decimal(str(existing_sl.get('qty', '0')))
                    existing_price = Decimal(str(existing_sl.get('triggerPrice', '0')))
                    
                    # Check quantity coverage
                    qty_coverage = existing_qty / target_size if target_size > 0 else 0
                    if qty_coverage < Decimal('0.99'):  # Less than 99% coverage
                        needs_fix = True
                        fix_reason = f"Insufficient coverage: {qty_coverage:.1%}"
                    
                    # Check price match
                    elif existing_price != Decimal(str(sl_price)):
                        needs_fix = True
                        fix_reason = f"Price mismatch: {existing_price} vs {sl_price}"
                
                if not needs_fix:
                    logger.info(f"   ✅ SL is properly configured")
                    already_ok_count += 1
                    continue
                
                logger.info(f"   ⚠️ {fix_reason} - fixing...")
                
                # Cancel existing SL if present
                if existing_sl:
                    try:
                        cancel_response = bybit_client_2.cancel_order(
                            category="linear",
                            symbol=symbol,
                            orderId=existing_sl['orderId']
                        )
                        if cancel_response['retCode'] == 0:
                            logger.info(f"   🧹 Cancelled existing SL")
                    except Exception as e:
                        logger.error(f"   Error cancelling SL: {e}")
                
                # Get instrument info for quantity adjustment
                instrument_info = await get_instrument_info(symbol)
                if instrument_info:
                    lot_size_filter = instrument_info.get('lotSizeFilter', {})
                    qty_step = Decimal(lot_size_filter.get('qtyStep', '1'))
                    adjusted_qty = value_adjusted_to_step(target_size, qty_step)
                else:
                    adjusted_qty = target_size
                
                # Place new SL with full coverage
                order_link_id = f"MIR_SL_FIX_{symbol}_{int(time.time())}"
                
                logger.info(f"   Placing SL: {adjusted_qty} @ {sl_price}")
                
                sl_result = await mirror_tp_sl_order(
                    symbol=symbol,
                    side=sl_side,
                    qty=str(adjusted_qty),
                    trigger_price=str(sl_price),
                    position_idx=0,
                    order_link_id=order_link_id,
                    stop_order_type="StopLoss"
                )
                
                if sl_result and sl_result.get('orderId'):
                    logger.info(f"   ✅ SL fixed: {sl_result['orderId'][:8]}...")
                    logger.info(f"      Coverage: {adjusted_qty} ({(adjusted_qty/position_size*100):.0f}% of current position)")
                    fixed_count += 1
                else:
                    logger.error(f"   ❌ Failed to place SL")
                    error_count += 1
                
            except Exception as e:
                logger.error(f"   ❌ Error processing {position.get('symbol', 'UNKNOWN')}: {e}")
                error_count += 1
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("✅ Mirror SL Coverage Check Complete!")
        logger.info(f"📊 Summary:")
        logger.info(f"   Total positions: {len(active_positions)}")
        logger.info(f"   Already OK: {already_ok_count}")
        logger.info(f"   Fixed: {fixed_count}")
        logger.info(f"   Errors: {error_count}")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Critical error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(ensure_mirror_sl_coverage())