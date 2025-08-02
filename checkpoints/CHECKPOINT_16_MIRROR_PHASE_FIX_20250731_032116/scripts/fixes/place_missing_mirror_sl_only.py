#!/usr/bin/env python3
"""
Place Missing Mirror Account SL Orders Only
This script only places SL orders for positions that don't have any SL
"""

import asyncio
import logging
from decimal import Decimal
import time
import sys
import os
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
DRY_RUN = False  # Set to False to actually place orders
SPECIFIC_SYMBOLS = ['AUCTIONUSDT', 'CRVUSDT', 'ARBUSDT']  # Only process these symbols

async def place_missing_sl_orders():
    """Place SL orders only for positions completely missing them"""
    try:
        from clients.bybit_helpers import get_all_positions, get_instrument_info
        from clients.bybit_client import bybit_client
        from utils.helpers import value_adjusted_to_step
        from execution.mirror_trader import is_mirror_trading_enabled, bybit_client_2, mirror_tp_sl_order
        import pickle
        
        if not is_mirror_trading_enabled() or not bybit_client_2:
            logger.error("❌ Mirror trading is not enabled")
            return
        
        logger.info("🔧 Placing Missing Mirror Account SL Orders")
        logger.info(f"🏃 Mode: {'DRY RUN' if DRY_RUN else 'LIVE'}")
        logger.info(f"🎯 Target symbols: {', '.join(SPECIFIC_SYMBOLS)}")
        logger.info("=" * 80)
        
        # Get positions from both accounts
        logger.info("📊 Fetching positions...")
        main_positions = await get_all_positions(client=bybit_client)
        mirror_positions = await get_all_positions(client=bybit_client_2)
        
        # Create position maps
        main_map = {(pos['symbol'], pos['side']): pos for pos in main_positions if float(pos.get('size', 0)) > 0}
        mirror_map = {(pos['symbol'], pos['side']): pos for pos in mirror_positions if float(pos.get('size', 0)) > 0}
        
        # Load pickle data for monitors
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        # Track results
        placed_count = 0
        error_count = 0
        actions = []
        
        # Process each target symbol
        for symbol in SPECIFIC_SYMBOLS:
            # Check both Buy and Sell sides
            for side in ['Buy', 'Sell']:
                key = (symbol, side)
                
                # Check if mirror position exists
                if key not in mirror_map:
                    continue
                
                mirror_pos = mirror_map[key]
                mirror_size = Decimal(str(mirror_pos.get('size', '0')))
                
                if mirror_size <= 0:
                    continue
                
                logger.info(f"\n{'='*60}")
                logger.info(f"🎯 Processing {symbol} {side}")
                logger.info(f"   Mirror position size: {mirror_size}")
                
                # Check if corresponding main position exists
                if key not in main_map:
                    logger.warning(f"   ⚠️ No corresponding main position - skipping")
                    continue
                
                main_pos = main_map[key]
                logger.info(f"   Main position size: {main_pos.get('size')}")
                
                # Check if SL already exists
                response = bybit_client_2.get_open_orders(
                    category="linear",
                    symbol=symbol
                )
                
                if response['retCode'] != 0:
                    logger.error(f"   ❌ Failed to get open orders")
                    error_count += 1
                    continue
                
                orders = response.get('result', {}).get('list', [])
                
                # Check for existing SL
                has_sl = False
                for order in orders:
                    if order.get('stopOrderType') in ['StopLoss', 'Stop'] and order.get('reduceOnly'):
                        has_sl = True
                        logger.info(f"   ✅ SL order already exists - skipping")
                        break
                
                if has_sl:
                    continue
                
                # Get SL price from main account
                main_sl_price = None
                
                # First check main account orders
                response = bybit_client.get_open_orders(
                    category="linear",
                    symbol=symbol
                )
                
                if response['retCode'] == 0:
                    main_orders = response.get('result', {}).get('list', [])
                    for order in main_orders:
                        if order.get('stopOrderType') in ['StopLoss', 'Stop'] and order.get('reduceOnly'):
                            main_sl_price = Decimal(str(order.get('triggerPrice', '0')))
                            logger.info(f"   Main SL found: {main_sl_price}")
                            break
                
                # If not found in orders, check monitors
                if not main_sl_price:
                    for monitor_key, monitor_data in enhanced_monitors.items():
                        if (monitor_data.get('symbol') == symbol and 
                            monitor_data.get('side') == side and
                            'main' in monitor_key.lower()):
                            if monitor_data.get('sl_order'):
                                main_sl_price = Decimal(str(monitor_data['sl_order'].get('price', '0')))
                                logger.info(f"   Main SL found in monitor: {main_sl_price}")
                                break
                
                if not main_sl_price or main_sl_price == 0:
                    logger.warning(f"   ⚠️ No SL price found on main account - skipping")
                    continue
                
                # Calculate target size (including unfilled limits)
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
                
                target_size = mirror_size + unfilled_limit_qty
                if unfilled_limit_qty > 0:
                    logger.info(f"   Including unfilled limits: {unfilled_limit_qty}")
                
                logger.info(f"   Target SL size: {target_size}")
                
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
                
                if len(order_link_id) > 45:
                    order_link_id = f"MIR_SL_{symbol}_{int(time.time())}"[:45]
                
                logger.info(f"\n   📍 Placing SL order:")
                logger.info(f"      Price: {main_sl_price}")
                logger.info(f"      Quantity: {adjusted_qty}")
                logger.info(f"      Side: {sl_side}")
                
                if not DRY_RUN:
                    try:
                        result = await mirror_tp_sl_order(
                            symbol=symbol,
                            side=sl_side,
                            qty=str(adjusted_qty),
                            trigger_price=str(main_sl_price),
                            position_idx=0,  # Mirror uses One-Way mode
                            order_link_id=order_link_id,
                            stop_order_type="StopLoss"
                        )
                        
                        if result and result.get('orderId'):
                            logger.info(f"   ✅ SL order placed successfully!")
                            logger.info(f"      Order ID: {result['orderId'][:8]}...")
                            placed_count += 1
                            
                            actions.append({
                                'symbol': symbol,
                                'side': side,
                                'sl_price': main_sl_price,
                                'quantity': adjusted_qty,
                                'order_id': result['orderId']
                            })
                            
                            # Update monitor if exists
                            mirror_monitor_key = f"{symbol}_{side}_mirror"
                            if mirror_monitor_key in enhanced_monitors:
                                enhanced_monitors[mirror_monitor_key]['sl_order'] = {
                                    'order_id': result['orderId'],
                                    'order_link_id': order_link_id,
                                    'price': main_sl_price,
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
                        logger.error(f"   ❌ Error placing SL order: {e}")
                        error_count += 1
                else:
                    logger.info(f"   🏃 DRY RUN: Would place SL order")
                    placed_count += 1
                
                # Brief delay between operations
                await asyncio.sleep(0.5)
        
        # Save updated monitors if not dry run
        if not DRY_RUN and placed_count > 0:
            with open(pkl_path, 'wb') as f:
                pickle.dump(data, f)
            logger.info("\n📊 Updated pickle file with new SL orders")
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("📋 SUMMARY")
        logger.info("=" * 80)
        logger.info(f"SL orders placed: {placed_count}")
        logger.info(f"Errors encountered: {error_count}")
        
        if actions:
            logger.info("\n📝 SL Orders Placed:")
            for action in actions:
                logger.info(f"   • {action['symbol']} {action['side']}: SL @ {action['sl_price']} for {action['quantity']} units")
        
        logger.info("\n✅ Operation complete!")
        
    except Exception as e:
        logger.error(f"❌ Critical error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(place_missing_sl_orders())