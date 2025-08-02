#!/usr/bin/env python3
"""
Place Mirror Account SL Orders with Full Coverage
This script places SL orders covering full position including unfilled limit orders
"""

import asyncio
import logging
from decimal import Decimal
import time
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def place_all_mirror_sl_orders():
    """Place SL orders for all mirror positions with full coverage"""
    try:
        from clients.bybit_helpers import get_all_positions, get_instrument_info
        from utils.helpers import value_adjusted_to_step
        from execution.mirror_trader import is_mirror_trading_enabled, bybit_client_2, mirror_tp_sl_order
        import pickle
        
        if not is_mirror_trading_enabled() or not bybit_client_2:
            logger.error("❌ Mirror trading is not enabled")
            return
        
        logger.info("🔧 Placing Mirror Account SL Orders with Full Coverage")
        logger.info("=" * 80)
        
        # Get mirror positions
        mirror_positions = await get_all_positions(client=bybit_client_2)
        active_positions = [pos for pos in mirror_positions if float(pos.get('size', 0)) > 0]
        
        logger.info(f"📊 Found {len(active_positions)} active mirror positions")
        
        placed_count = 0
        error_count = 0
        
        # Load pickle data to get SL prices
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        for position in active_positions:
            try:
                symbol = position.get('symbol')
                side = position.get('side')
                position_size = Decimal(str(position.get('size', '0')))
                
                logger.info(f"\n🎯 Processing {symbol} {side}")
                
                # Find monitor to get SL price
                monitor_key = None
                sl_price = None
                
                # Check different monitor key formats
                for key in [f"{symbol}_{side}", f"{symbol}_{side}_mirror"]:
                    if key in enhanced_monitors:
                        monitor = enhanced_monitors[key]
                        if monitor.get('sl_order'):
                            sl_price = monitor['sl_order'].get('price')
                            monitor_key = key
                            break
                
                if not sl_price:
                    logger.warning(f"   ⚠️ No SL price found in monitors - skipping")
                    continue
                
                logger.info(f"   Found SL price from monitor: {sl_price}")
                
                # Get open orders
                response = bybit_client_2.get_open_orders(
                    category="linear",
                    symbol=symbol
                )
                
                if response['retCode'] != 0:
                    logger.error(f"   ❌ Failed to get open orders")
                    error_count += 1
                    continue
                
                orders = response.get('result', {}).get('list', [])
                
                # Check if SL already exists
                existing_sl = False
                for order in orders:
                    if order.get('stopOrderType') in ['StopLoss', 'Stop']:
                        existing_sl = True
                        logger.info(f"   ℹ️ SL order already exists - skipping")
                        break
                
                if existing_sl:
                    continue
                
                # Calculate unfilled limit orders
                unfilled_limit_qty = Decimal('0')
                for order in orders:
                    if (order.get('orderType') == 'Limit' and 
                        not order.get('reduceOnly') and 
                        order.get('side') == side and
                        order.get('orderStatus') in ['New', 'PartiallyFilled']):
                        
                        if order.get('orderStatus') == 'PartiallyFilled':
                            total_qty = Decimal(str(order.get('qty', '0')))
                            filled_qty = Decimal(str(order.get('cumExecQty', '0')))
                            remaining_qty = total_qty - filled_qty
                            unfilled_limit_qty += remaining_qty
                        else:
                            unfilled_limit_qty += Decimal(str(order.get('qty', '0')))
                
                # Calculate target size
                target_size = position_size + unfilled_limit_qty
                
                logger.info(f"   Current position: {position_size}")
                logger.info(f"   Unfilled limits: {unfilled_limit_qty}")
                logger.info(f"   Target size: {target_size}")
                
                # Get instrument info
                instrument_info = await get_instrument_info(symbol)
                if not instrument_info:
                    logger.error(f"   ❌ Could not get instrument info")
                    error_count += 1
                    continue
                
                lot_size_filter = instrument_info.get('lotSizeFilter', {})
                qty_step = Decimal(lot_size_filter.get('qtyStep', '1'))
                
                # Adjust quantity
                adjusted_qty = value_adjusted_to_step(target_size, qty_step)
                
                # Place SL order
                sl_side = "Sell" if side == "Buy" else "Buy"
                order_link_id = f"MIR_SL_{symbol}_{int(time.time())}"
                
                logger.info(f"   Placing SL: {adjusted_qty} @ {sl_price}")
                
                sl_result = await mirror_tp_sl_order(
                    symbol=symbol,
                    side=sl_side,
                    qty=str(adjusted_qty),
                    trigger_price=str(sl_price),
                    position_idx=0,  # Mirror uses One-Way mode
                    order_link_id=order_link_id,
                    stop_order_type="StopLoss"
                )
                
                if sl_result and sl_result.get('orderId'):
                    logger.info(f"   ✅ SL placed: {sl_result['orderId'][:8]}...")
                    logger.info(f"      Coverage: 100% of target position")
                    placed_count += 1
                    
                    # Update monitor
                    if monitor_key in enhanced_monitors:
                        enhanced_monitors[monitor_key]['sl_order'] = {
                            'order_id': sl_result['orderId'],
                            'order_link_id': order_link_id,
                            'price': sl_price,
                            'quantity': adjusted_qty,
                            'original_quantity': adjusted_qty,
                            'covers_full_position': True,
                            'target_position_size': target_size,
                            'account': 'mirror'
                        }
                else:
                    logger.error(f"   ❌ Failed to place SL order")
                    error_count += 1
                
            except Exception as e:
                logger.error(f"   ❌ Error processing {position.get('symbol', 'UNKNOWN')}: {e}")
                error_count += 1
        
        # Save updated monitors
        if placed_count > 0:
            with open(pkl_path, 'wb') as f:
                pickle.dump(data, f)
            logger.info("   📊 Updated pickle file with new SL orders")
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info(f"✅ Mirror SL Order Placement Complete!")
        logger.info(f"📊 Summary:")
        logger.info(f"   Total positions: {len(active_positions)}")
        logger.info(f"   SL orders placed: {placed_count}")
        logger.info(f"   Errors: {error_count}")
        logger.info(f"   Already had SL: {len(active_positions) - placed_count - error_count}")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Critical error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(place_all_mirror_sl_orders())