#!/usr/bin/env python3
"""
Fix SL Coverage to 100% for All Positions

This script updates all current stop loss orders to ensure 100% coverage
while preserving the trigger price. It handles both main and mirror accounts.
"""
import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def fix_sl_coverage():
    """Fix SL coverage for all positions to ensure 100% protection"""
    try:
        # Import required modules
        from clients.bybit_helpers import (
            get_all_positions, get_all_open_orders, get_instrument_info,
            cancel_order_with_retry, place_order_with_retry,
            get_correct_position_idx
        )
        from utils.helpers import value_adjusted_to_step
        from clients.bybit_client import bybit_client
        from execution.mirror_trader import is_mirror_trading_enabled, bybit_client_2
        from utils.order_identifier import generate_adjusted_order_link_id
        import pickle
        
        logger.info("🔧 Starting SL Coverage Fix to 100%")
        logger.info("=" * 60)
        
        # Load persistence data to get approach info
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        # Process main account
        logger.info("\n📍 MAIN ACCOUNT")
        logger.info("-" * 40)
        
        main_positions = await get_all_positions()
        main_orders = await get_all_open_orders()
        
        await process_account_positions(
            positions=main_positions,
            orders=main_orders,
            monitors=enhanced_monitors,
            account_type="main",
            client=bybit_client
        )
        
        # Process mirror account if enabled
        if is_mirror_trading_enabled() and bybit_client_2:
            logger.info("\n🪞 MIRROR ACCOUNT")
            logger.info("-" * 40)
            
            mirror_positions = await get_all_positions(client=bybit_client_2)
            mirror_orders = await get_all_open_orders(bybit_client_2)
            
            await process_account_positions(
                positions=mirror_positions,
                orders=mirror_orders,
                monitors=enhanced_monitors,
                account_type="mirror",
                client=bybit_client_2
            )
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ SL Coverage Fix Complete!")
        
    except Exception as e:
        logger.error(f"❌ Error in SL coverage fix: {e}")
        import traceback
        traceback.print_exc()

async def process_account_positions(
    positions: List[Dict],
    orders: List[Dict],
    monitors: Dict,
    account_type: str,
    client
):
    """Process positions for a specific account"""
    
    from clients.bybit_helpers import (
        get_instrument_info, cancel_order_with_retry, 
        place_order_with_retry, get_correct_position_idx
    )
    from utils.helpers import value_adjusted_to_step
    from utils.order_identifier import generate_adjusted_order_link_id
    
    fixed_count = 0
    checked_count = 0
    
    for position in positions:
        try:
            symbol = position.get('symbol')
            side = position.get('side')
            position_size = Decimal(str(position.get('size', '0')))
            
            if position_size <= 0:
                continue
            
            checked_count += 1
            logger.info(f"\n🔍 Checking {symbol} {side}")
            logger.info(f"   Position size: {position_size}")
            
            # Find monitor data to get approach and target size
            monitor_key = f"{symbol}_{side}"
            monitor_data = monitors.get(monitor_key, {})
            approach = monitor_data.get('approach', 'FAST')  # Default to FAST
            
            # For conservative approach, we need target size (including unfilled limits)
            if approach == "CONSERVATIVE":
                # Try to get target size from monitor data
                target_size = monitor_data.get('position_size', position_size)
                if target_size < position_size:
                    target_size = position_size  # Safety: never less than current
            else:
                # For FAST approach, target is current size
                target_size = position_size
            
            logger.info(f"   Approach: {approach}")
            logger.info(f"   Target size: {target_size}")
            
            # Find SL order for this position
            sl_order = None
            position_orders = [o for o in orders if o.get('symbol') == symbol]
            
            for order in position_orders:
                # Check for stop orders (both 'StopLoss' and 'Stop' types)
                if (order.get('stopOrderType') in ['StopLoss', 'Stop'] and 
                    order.get('orderStatus') in ['New', 'Untriggered'] and
                    order.get('side') != side):  # SL side is opposite of position side
                    # Check if this is a bot SL order
                    order_link_id = order.get('orderLinkId', '')
                    if 'BOT_' in order_link_id or 'SL' in order_link_id:
                        sl_order = order
                        break
            
            if not sl_order:
                logger.warning(f"   ⚠️ No SL order found for {symbol} {side}")
                continue
            
            # Check current SL coverage
            current_sl_qty = Decimal(str(sl_order.get('qty', '0')))
            trigger_price = Decimal(str(sl_order.get('triggerPrice', '0')))
            
            logger.info(f"   Current SL: {current_sl_qty} @ {trigger_price}")
            
            # Calculate required SL quantity for 100% coverage
            required_sl_qty = target_size
            
            # Check if adjustment needed
            if abs(current_sl_qty - required_sl_qty) < Decimal('0.001'):
                logger.info(f"   ✅ Already has 100% coverage")
                continue
            
            # Get instrument info for quantity step
            instrument_info = await get_instrument_info(symbol)
            if not instrument_info:
                logger.error(f"   ❌ Could not get instrument info")
                continue
            
            lot_size_filter = instrument_info.get('lotSizeFilter', {})
            qty_step = Decimal(lot_size_filter.get('qtyStep', '1'))
            
            # Adjust quantity to step
            adjusted_qty = value_adjusted_to_step(required_sl_qty, qty_step)
            
            logger.info(f"   🔧 Adjusting SL: {current_sl_qty} → {adjusted_qty}")
            
            # Cancel existing SL order
            old_order_id = sl_order.get('orderId')
            
            # For mirror account, need to use mirror cancel function
            if account_type == "mirror":
                from execution.mirror_trader import cancel_mirror_order
                cancel_success = await cancel_mirror_order(symbol, old_order_id)
            else:
                cancel_success = await cancel_order_with_retry(symbol, old_order_id)
            
            if not cancel_success:
                logger.error(f"   ❌ Failed to cancel old SL order")
                continue
            
            # Place new SL with 100% coverage
            sl_side = "Sell" if side == "Buy" else "Buy"
            position_idx = await get_correct_position_idx(symbol, side)
            
            # Generate new order link ID
            old_link_id = sl_order.get('orderLinkId', '')
            new_link_id = generate_adjusted_order_link_id(old_link_id, "100PCT")
            
            # Place new SL order
            if account_type == "mirror":
                from execution.mirror_trader import mirror_tp_sl_order
                sl_result = await mirror_tp_sl_order(
                    symbol=symbol,
                    side=sl_side,
                    qty=str(adjusted_qty),
                    trigger_price=str(trigger_price),  # PRESERVE ORIGINAL PRICE
                    position_idx=0,  # Mirror uses One-Way mode
                    order_link_id=new_link_id,
                    stop_order_type="StopLoss"
                )
            else:
                sl_result = await place_order_with_retry(
                    symbol=symbol,
                    side=sl_side,
                    order_type="Market",
                    qty=str(adjusted_qty),
                    trigger_price=str(trigger_price),  # PRESERVE ORIGINAL PRICE
                    reduce_only=True,
                    order_link_id=new_link_id,
                    position_idx=position_idx,
                    stop_order_type="StopLoss"
                )
            
            if sl_result and sl_result.get('orderId'):
                new_order_id = sl_result['orderId']
                logger.info(f"   ✅ New SL placed: {new_order_id[:8]}...")
                logger.info(f"      Quantity: {adjusted_qty} (100% coverage)")
                logger.info(f"      Trigger: {trigger_price} (unchanged)")
                fixed_count += 1
            else:
                logger.error(f"   ❌ Failed to place new SL order")
                
        except Exception as e:
            logger.error(f"   ❌ Error processing {position.get('symbol', 'UNKNOWN')}: {e}")
    
    logger.info(f"\n📊 {account_type.upper()} Summary: {fixed_count}/{checked_count} positions fixed")

if __name__ == "__main__":
    asyncio.run(fix_sl_coverage())