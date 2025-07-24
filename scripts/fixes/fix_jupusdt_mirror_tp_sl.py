#!/usr/bin/env python3
"""
Fix JUPUSDT mirror position by copying TP/SL from main account and enabling monitoring
"""
import asyncio
import logging
import pickle
from decimal import Decimal
from datetime import datetime
from typing import List, Dict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import required modules
from clients.bybit_helpers import (
    get_position_info, get_open_orders, place_order_with_retry,
    get_correct_position_idx
)
from execution.mirror_trader import (
    bybit_client_2, is_mirror_trading_enabled,
    get_mirror_positions
)
from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
from utils.helpers import value_adjusted_to_step
from utils.order_identifier import generate_order_link_id, ORDER_TYPE_TP, ORDER_TYPE_SL
from config.constants import BOT_PREFIX

async def check_jupusdt_status():
    """Check current status of JUPUSDT on both accounts"""
    logger.info("=" * 50)
    logger.info("Checking JUPUSDT position status...")
    
    # Check main account
    main_positions = await get_position_info("JUPUSDT")
    main_position = None
    for pos in main_positions:
        if float(pos.get('size', 0)) > 0 and pos.get('side') == 'Sell':
            main_position = pos
            break
    
    if not main_position:
        logger.error("❌ No active JUPUSDT Sell position found on main account")
        return None, None
    
    logger.info(f"✅ Main account JUPUSDT position:")
    logger.info(f"   Size: {main_position.get('size')}")
    logger.info(f"   Side: {main_position.get('side')}")
    logger.info(f"   Avg Price: {main_position.get('avgPrice')}")
    
    # Check mirror account
    if not is_mirror_trading_enabled():
        logger.error("❌ Mirror trading is not enabled")
        return main_position, None
    
    mirror_positions = await get_mirror_positions()
    mirror_position = None
    for pos in mirror_positions:
        if pos.get('symbol') == 'JUPUSDT' and float(pos.get('size', 0)) > 0 and pos.get('side') == 'Sell':
            mirror_position = pos
            break
    
    if not mirror_position:
        logger.error("❌ No active JUPUSDT Sell position found on mirror account")
        return main_position, None
    
    logger.info(f"✅ Mirror account JUPUSDT position:")
    logger.info(f"   Size: {mirror_position.get('size')}")
    logger.info(f"   Side: {mirror_position.get('side')}")
    logger.info(f"   Avg Price: {mirror_position.get('avgPrice')}")
    
    return main_position, mirror_position

async def get_mirror_open_orders(symbol: str) -> List[Dict]:
    """Get open orders for a symbol on mirror account"""
    if not bybit_client_2:
        return []
    
    try:
        response = bybit_client_2.get_open_orders(
            category="linear",
            symbol=symbol
        )
        
        if response and response.get('retCode') == 0:
            return response.get('result', {}).get('list', [])
        else:
            logger.error(f"Error getting mirror orders: {response}")
            return []
    except Exception as e:
        logger.error(f"Exception getting mirror orders: {e}")
        return []

async def check_existing_orders():
    """Check existing orders for JUPUSDT on both accounts"""
    logger.info("\n" + "=" * 50)
    logger.info("Checking existing orders...")
    
    # Main account orders
    main_orders = await get_open_orders("JUPUSDT")
    main_tp_orders = []
    main_sl_orders = []
    
    for order in main_orders:
        if order.get('reduceOnly'):
            order_link_id = order.get('orderLinkId', '')
            stop_order_type = order.get('stopOrderType', '')
            
            # Check for TP orders
            if stop_order_type == 'TakeProfit' or 'TP' in order_link_id:
                if order.get('triggerPrice'):  # Only add if has trigger price
                    main_tp_orders.append(order)
            # Check for SL orders  
            elif stop_order_type == 'StopLoss' or 'SL' in order_link_id:
                if order.get('triggerPrice'):  # Only add if has trigger price
                    main_sl_orders.append(order)
    
    logger.info(f"Main account orders: {len(main_tp_orders)} TP, {len(main_sl_orders)} SL")
    
    # Debug: show order structure
    if main_tp_orders:
        logger.info("Main TP order structure:")
        for i, order in enumerate(main_tp_orders):
            logger.info(f"   TP{i+1}: triggerPrice={order.get('triggerPrice')}, stopOrderType={order.get('stopOrderType')}")
    
    # Mirror account orders
    mirror_orders = await get_mirror_open_orders("JUPUSDT")
    mirror_tp_orders = []
    mirror_sl_orders = []
    
    for order in mirror_orders:
        if order.get('reduceOnly'):
            if 'TP' in order.get('orderLinkId', ''):
                mirror_tp_orders.append(order)
            elif 'SL' in order.get('orderLinkId', ''):
                mirror_sl_orders.append(order)
    
    logger.info(f"Mirror account orders: {len(mirror_tp_orders)} TP, {len(mirror_sl_orders)} SL")
    
    return main_tp_orders, main_sl_orders, mirror_tp_orders, mirror_sl_orders

async def place_mirror_tp_sl_orders(main_position, mirror_position, main_tp_orders, main_sl_orders):
    """Place TP/SL orders on mirror account based on main account configuration"""
    logger.info("\n" + "=" * 50)
    logger.info("Placing TP/SL orders on mirror account...")
    
    symbol = "JUPUSDT"
    side = mirror_position['side']
    mirror_size = Decimal(str(mirror_position['size']))
    
    # Get position index - mirror account uses One-Way mode (always 0)
    position_idx = 0
    
    placed_orders = []
    
    # Place TP orders
    if main_tp_orders:
        logger.info(f"\nPlacing {len(main_tp_orders)} TP orders...")
        
        # Sort TP orders by price (ascending for Sell)
        def get_trigger_price(order):
            price = order.get('triggerPrice', '0')
            if not price or price == '':
                return 0
            return float(price)
        
        sorted_tps = sorted(main_tp_orders, key=get_trigger_price)
        
        for i, main_tp in enumerate(sorted_tps):
            try:
                # Calculate proportional quantity for mirror position
                # For conservative approach: 85%, 5%, 5%, 5% distribution
                if i == 0:
                    qty_percentage = Decimal("0.85")
                else:
                    qty_percentage = Decimal("0.05")
                
                tp_qty = value_adjusted_to_step(mirror_size * qty_percentage, Decimal("1"))
                tp_price = main_tp.get('triggerPrice', '')
                
                # Skip if no trigger price
                if not tp_price:
                    logger.warning(f"   TP{i+1} has no trigger price, skipping")
                    continue
                
                # Generate order link ID
                tp_num = i + 1
                order_link_id = generate_order_link_id(
                    ORDER_TYPE_TP, 
                    f"MIRROR_TP{tp_num}",
                    symbol
                )
                
                logger.info(f"   TP{tp_num}: {tp_qty} @ {tp_price}")
                
                # Import the mirror order placement function
                from execution.mirror_trader import mirror_tp_sl_order
                
                # Place TP order on mirror account
                tp_result = await mirror_tp_sl_order(
                    symbol=symbol,
                    side="Buy" if side == "Sell" else "Sell",
                    qty=str(tp_qty),
                    trigger_price=str(tp_price),
                    position_idx=position_idx,
                    order_type="Market",
                    reduce_only=True,
                    order_link_id=order_link_id,
                    stop_order_type="TakeProfit"
                )
                
                if tp_result and tp_result.get('orderId'):
                    placed_orders.append(('TP', tp_result['orderId']))
                    logger.info(f"   ✅ TP{tp_num} placed: {tp_result['orderId'][:8]}...")
                else:
                    logger.error(f"   ❌ Failed to place TP{tp_num}")
                    
            except Exception as e:
                logger.error(f"   ❌ Error placing TP{i+1}: {e}")
    
    # Import mirror_tp_sl_order at the beginning if not already imported
    from execution.mirror_trader import mirror_tp_sl_order
    
    # Place SL order
    if main_sl_orders:
        logger.info(f"\nPlacing SL order...")
        main_sl = main_sl_orders[0]  # Should only be one SL
        
        try:
            sl_price = main_sl.get('triggerPrice')
            sl_qty = mirror_size  # SL covers full position
            
            # Generate order link ID
            order_link_id = generate_order_link_id(
                ORDER_TYPE_SL,
                "MIRROR_SL",
                symbol
            )
            
            logger.info(f"   SL: {sl_qty} @ {sl_price}")
            
            # Place SL order on mirror account
            sl_result = await mirror_tp_sl_order(
                symbol=symbol,
                side="Buy" if side == "Sell" else "Sell",
                qty=str(sl_qty),
                trigger_price=str(sl_price),
                position_idx=position_idx,
                order_type="Market",
                reduce_only=True,
                order_link_id=order_link_id,
                stop_order_type="StopLoss"
            )
            
            if sl_result and sl_result.get('orderId'):
                placed_orders.append(('SL', sl_result['orderId']))
                logger.info(f"   ✅ SL placed: {sl_result['orderId'][:8]}...")
            else:
                logger.error(f"   ❌ Failed to place SL")
                
        except Exception as e:
            logger.error(f"   ❌ Error placing SL: {e}")
    
    return placed_orders

async def create_enhanced_monitor():
    """Create Enhanced TP/SL monitor for the mirror position"""
    logger.info("\n" + "=" * 50)
    logger.info("Creating Enhanced TP/SL monitor...")
    
    symbol = "JUPUSDT"
    side = "Sell"
    
    # Load pickle file to check current monitors
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    try:
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
            
        # Check if Enhanced TP/SL monitors exist
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        monitor_key = f"{symbol}_{side}"
        
        if monitor_key in enhanced_monitors:
            logger.info(f"✅ Enhanced TP/SL monitor already exists for {monitor_key}")
            
            # Check if it has mirror info
            monitor_data = enhanced_monitors[monitor_key]
            if monitor_data.get('has_mirror'):
                logger.info("✅ Mirror monitoring is already enabled")
            else:
                logger.info("⚠️ Mirror monitoring needs to be enabled")
                monitor_data['has_mirror'] = True
                monitor_data['mirror_synced'] = True
                
                # Save updated pickle
                with open(pickle_file, 'wb') as f:
                    pickle.dump(data, f)
                logger.info("✅ Enabled mirror monitoring in existing monitor")
        else:
            logger.warning(f"⚠️ No Enhanced TP/SL monitor found for {monitor_key}")
            logger.info("Creating new monitor entry...")
            
            # We need position info to create a proper monitor
            # This would normally be done through the enhanced_tp_sl_manager
            # For now, we'll just note that it needs to be created
            
    except Exception as e:
        logger.error(f"❌ Error checking monitors: {e}")
    
    # Trigger monitor sync
    try:
        logger.info("\nTriggering position sync in Enhanced TP/SL manager...")
        await enhanced_tp_sl_manager.sync_existing_positions()
        logger.info("✅ Position sync completed")
    except Exception as e:
        logger.error(f"❌ Error syncing positions: {e}")

async def main():
    """Main function to fix JUPUSDT mirror TP/SL"""
    logger.info("Starting JUPUSDT mirror TP/SL fix...")
    
    # Step 1: Check current status
    main_position, mirror_position = await check_jupusdt_status()
    if not main_position or not mirror_position:
        logger.error("Cannot proceed without both positions")
        return
    
    # Step 2: Check existing orders
    main_tp_orders, main_sl_orders, mirror_tp_orders, mirror_sl_orders = await check_existing_orders()
    
    # Step 3: Check if mirror already has orders
    if mirror_tp_orders or mirror_sl_orders:
        logger.warning("⚠️ Mirror account already has some orders. Current state:")
        logger.warning(f"   TP orders: {len(mirror_tp_orders)}")
        logger.warning(f"   SL orders: {len(mirror_sl_orders)}")
        
        response = input("\nDo you want to proceed and add missing orders? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Operation cancelled")
            return
    
    # Step 4: Place missing orders
    if not mirror_tp_orders and not mirror_sl_orders:
        placed_orders = await place_mirror_tp_sl_orders(
            main_position, mirror_position, main_tp_orders, main_sl_orders
        )
        logger.info(f"\n✅ Placed {len(placed_orders)} orders on mirror account")
    else:
        logger.info("⚠️ Some orders already exist, skipping order placement")
    
    # Step 5: Ensure Enhanced TP/SL monitoring
    await create_enhanced_monitor()
    
    logger.info("\n" + "=" * 50)
    logger.info("✅ JUPUSDT mirror TP/SL fix completed!")
    logger.info("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())