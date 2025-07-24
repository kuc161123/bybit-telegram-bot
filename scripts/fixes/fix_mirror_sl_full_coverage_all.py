#!/usr/bin/env python3
"""
Fix Mirror Account SL Coverage to Include Unfilled Limit Orders
This script updates all mirror account stop loss orders to cover 100% including unfilled limit orders
Can be run without restarting the bot
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional
import time
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def fix_all_mirror_sl_coverage():
    """Fix SL coverage for all mirror positions to include unfilled limit orders"""
    try:
        # Import required modules
        from clients.bybit_helpers import get_all_positions, get_instrument_info
        from utils.helpers import value_adjusted_to_step
        from execution.mirror_trader import is_mirror_trading_enabled, bybit_client_2, cancel_mirror_order, mirror_tp_sl_order
        from utils.order_identifier import generate_adjusted_order_link_id
        import pickle
        
        # Check if mirror trading is enabled
        if not is_mirror_trading_enabled() or not bybit_client_2:
            logger.error("❌ Mirror trading is not enabled or client not available")
            return
        
        logger.info("🔧 Starting Mirror Account SL Full Coverage Fix")
        logger.info("=" * 80)
        logger.info("📌 This will update ALL mirror positions to have 100% SL coverage")
        logger.info("📌 Including protection for unfilled limit orders")
        logger.info("📌 Bot does NOT need to be restarted")
        logger.info("=" * 80)
        
        # Get mirror positions
        mirror_positions = await get_all_positions(client=bybit_client_2)
        
        # Filter active positions
        active_positions = []
        for pos in mirror_positions:
            if float(pos.get('size', 0)) > 0:
                active_positions.append(pos)
        
        logger.info(f"\n📊 Found {len(active_positions)} active mirror positions")
        
        fixed_count = 0
        error_count = 0
        
        # Process each position
        for position in active_positions:
            try:
                symbol = position.get('symbol')
                side = position.get('side')
                position_size = Decimal(str(position.get('size', '0')))
                
                logger.info(f"\n🎯 Processing {symbol} {side}")
                logger.info(f"   Current position: {position_size}")
                
                # Get open orders for this symbol
                response = bybit_client_2.get_open_orders(
                    category="linear",
                    symbol=symbol
                )
                
                if response['retCode'] != 0:
                    logger.error(f"   ❌ Failed to get open orders: {response.get('retMsg')}")
                    error_count += 1
                    continue
                
                orders = response.get('result', {}).get('list', [])
                
                # Find unfilled limit orders and current SL
                unfilled_limit_qty = Decimal('0')
                limit_orders = []
                sl_order = None
                
                for order in orders:
                    order_type = order.get('orderType', '')
                    order_link_id = order.get('orderLinkId', '')
                    
                    # Check if this is an unfilled entry limit order
                    if (order_type == 'Limit' and 
                        not order.get('reduceOnly') and 
                        order.get('side') == side and
                        order.get('orderStatus') in ['New', 'PartiallyFilled'] and
                        ('BOT_' in order_link_id or 'MIR_' in order_link_id)):
                        
                        # For partially filled orders, only count the remaining qty
                        if order.get('orderStatus') == 'PartiallyFilled':
                            total_qty = Decimal(str(order.get('qty', '0')))
                            filled_qty = Decimal(str(order.get('cumExecQty', '0')))
                            remaining_qty = total_qty - filled_qty
                            unfilled_limit_qty += remaining_qty
                        else:
                            qty = Decimal(str(order.get('qty', '0')))
                            unfilled_limit_qty += qty
                            limit_orders.append({
                                'id': order.get('orderId')[:8] + '...',
                                'qty': qty,
                                'price': order.get('price')
                            })
                    
                    # Find SL order
                    if (order.get('stopOrderType') in ['StopLoss', 'Stop'] and
                        order.get('orderStatus') in ['New', 'Untriggered'] and
                        order.get('side') != side):
                        sl_order = order
                
                if not sl_order:
                    logger.warning(f"   ⚠️ No SL order found - skipping")
                    continue
                
                # Calculate target size
                target_size = position_size + unfilled_limit_qty
                
                # Log unfilled limit orders
                if limit_orders:
                    logger.info(f"   Unfilled limit orders: {len(limit_orders)}")
                    for lo in limit_orders[:3]:  # Show first 3
                        logger.info(f"      - {lo['qty']} @ {lo['price']}")
                    if len(limit_orders) > 3:
                        logger.info(f"      - ... and {len(limit_orders) - 3} more")
                    logger.info(f"   Total unfilled quantity: {unfilled_limit_qty}")
                
                logger.info(f"   Target size (including unfilled): {target_size}")
                
                # Check current SL coverage
                current_sl_qty = Decimal(str(sl_order.get('qty', '0')))
                trigger_price = sl_order.get('triggerPrice')
                
                logger.info(f"   Current SL: {current_sl_qty} @ {trigger_price}")
                
                # Check if adjustment is needed
                if abs(current_sl_qty - target_size) < Decimal('0.001'):
                    logger.info(f"   ✅ Already has 100% coverage including limits")
                    continue
                
                # Calculate coverage percentage
                coverage_pct = (current_sl_qty / target_size * 100) if target_size > 0 else 0
                logger.info(f"   ⚠️ Current coverage: {coverage_pct:.1f}% - needs adjustment")
                
                # Get instrument info for quantity step
                instrument_info = await get_instrument_info(symbol)
                if not instrument_info:
                    logger.error(f"   ❌ Could not get instrument info")
                    error_count += 1
                    continue
                
                lot_size_filter = instrument_info.get('lotSizeFilter', {})
                qty_step = Decimal(lot_size_filter.get('qtyStep', '1'))
                
                # Adjust quantity to step
                adjusted_qty = value_adjusted_to_step(target_size, qty_step)
                
                logger.info(f"   🔧 Adjusting SL: {current_sl_qty} → {adjusted_qty}")
                
                # Cancel existing SL order
                old_order_id = sl_order.get('orderId')
                cancel_success = await cancel_mirror_order(symbol, old_order_id)
                
                if not cancel_success:
                    logger.error(f"   ❌ Failed to cancel old SL order")
                    error_count += 1
                    continue
                
                await asyncio.sleep(0.5)  # Brief pause after cancel
                
                # Place new SL with full coverage
                sl_side = "Sell" if side == "Buy" else "Buy"
                
                # Generate new order link ID (max 45 chars)
                old_link_id = sl_order.get('orderLinkId', '')
                # Shorten the link ID to fit within 45 character limit
                if len(old_link_id) > 35:
                    # Take the prefix and add timestamp
                    prefix = old_link_id[:20] if old_link_id.startswith('BOT_') or old_link_id.startswith('MIR_') else 'MIR_SL'
                    new_link_id = f"{prefix}_FULL_{int(time.time())}"
                elif 'FULL' not in old_link_id:
                    new_link_id = f"{old_link_id}_FULL"
                else:
                    new_link_id = old_link_id  # Already has FULL marker
                
                # Ensure it's not too long
                if len(new_link_id) > 45:
                    new_link_id = f"MIR_SL_{symbol}_{int(time.time())}"
                
                # Place new SL order
                sl_result = await mirror_tp_sl_order(
                    symbol=symbol,
                    side=sl_side,
                    qty=str(adjusted_qty),
                    trigger_price=str(trigger_price),  # PRESERVE ORIGINAL PRICE
                    position_idx=0,  # Mirror uses One-Way mode
                    order_link_id=new_link_id,
                    stop_order_type="StopLoss"
                )
                
                if sl_result and sl_result.get('orderId'):
                    new_order_id = sl_result['orderId']
                    logger.info(f"   ✅ New SL placed: {new_order_id[:8]}...")
                    logger.info(f"      Quantity: {adjusted_qty} (includes {unfilled_limit_qty} unfilled)")
                    logger.info(f"      Trigger: {trigger_price} (unchanged)")
                    logger.info(f"      Coverage: 100% of target position")
                    fixed_count += 1
                    
                    # Update Enhanced TP/SL monitor if exists
                    await update_enhanced_monitor(symbol, side, position_size, target_size)
                else:
                    logger.error(f"   ❌ Failed to place new SL order")
                    error_count += 1
                
            except Exception as e:
                logger.error(f"   ❌ Error processing {position.get('symbol', 'UNKNOWN')}: {e}")
                error_count += 1
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info(f"✅ Mirror SL Coverage Fix Complete!")
        logger.info(f"📊 Summary:")
        logger.info(f"   Total positions: {len(active_positions)}")
        logger.info(f"   Fixed: {fixed_count}")
        logger.info(f"   Errors: {error_count}")
        logger.info(f"   Already correct: {len(active_positions) - fixed_count - error_count}")
        logger.info("=" * 80)
        
        # Trigger position sync
        try:
            from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
            if enhanced_tp_sl_manager:
                await enhanced_tp_sl_manager.sync_existing_positions()
                logger.info("✅ Triggered Enhanced TP/SL position sync")
        except Exception as e:
            logger.warning(f"⚠️ Could not trigger position sync: {e}")
        
    except Exception as e:
        logger.error(f"❌ Critical error in fix script: {e}")
        import traceback
        traceback.print_exc()

async def update_enhanced_monitor(symbol: str, side: str, current_size: Decimal, target_size: Decimal):
    """Update Enhanced TP/SL monitor with target size information"""
    try:
        import pickle
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        # Check both possible monitor keys
        monitor_keys = [
            f"{symbol}_{side}_mirror",
            f"{symbol}_{side}"
        ]
        
        monitor_updated = False
        for monitor_key in monitor_keys:
            if monitor_key in enhanced_monitors:
                monitor_data = enhanced_monitors[monitor_key]
                if monitor_data.get('has_mirror') or 'mirror' in monitor_key.lower():
                    # Update monitor with target size
                    monitor_data['target_size'] = str(target_size)
                    monitor_data['current_size'] = str(current_size)
                    monitor_data['position_size'] = str(target_size)  # Full intended size
                    monitor_data['remaining_size'] = str(current_size)  # Current filled size
                    monitor_data['last_update'] = time.time()
                    monitor_updated = True
                    logger.info(f"   📊 Updated Enhanced monitor {monitor_key} with target size: {target_size}")
                    break
        
        if monitor_updated:
            with open(pkl_path, 'wb') as f:
                pickle.dump(data, f)
        else:
            logger.debug(f"   ℹ️ No mirror Enhanced monitor found for {symbol} {side}")
            
    except Exception as e:
        logger.warning(f"   ⚠️ Could not update Enhanced monitor: {e}")

if __name__ == "__main__":
    asyncio.run(fix_all_mirror_sl_coverage())