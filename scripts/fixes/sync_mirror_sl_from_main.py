#!/usr/bin/env python3
"""
Sync Mirror Account Stop Loss Orders from Main Account
This script ensures all mirror positions have SL orders matching the main account prices
"""

import asyncio
import logging
from decimal import Decimal
import time
import sys
import os
from typing import Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
DRY_RUN = True  # Set to False to actually place/modify orders
VERIFY_AFTER_PLACEMENT = True
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

async def get_position_sl_info(positions: List[Dict], symbol: str, side: str) -> Tuple[Optional[Decimal], Optional[Dict]]:
    """Extract SL information for a specific position"""
    for pos in positions:
        if pos.get('symbol') == symbol and pos.get('side') == side and float(pos.get('size', 0)) > 0:
            # Position found, now check for SL in stopOrderType or other fields
            sl_price = pos.get('stopLoss')
            if sl_price and sl_price != '0':
                return Decimal(str(sl_price)), pos
            return None, pos
    return None, None

async def get_open_sl_order(client, symbol: str, side: str) -> Optional[Dict]:
    """Get open SL order for a position"""
    try:
        response = client.get_open_orders(
            category="linear",
            symbol=symbol
        )
        
        if response['retCode'] != 0:
            logger.error(f"Failed to get open orders: {response.get('retMsg', 'Unknown error')}")
            return None
        
        orders = response.get('result', {}).get('list', [])
        sl_side = "Sell" if side == "Buy" else "Buy"
        
        for order in orders:
            if (order.get('stopOrderType') in ['StopLoss', 'Stop'] and 
                order.get('side') == sl_side and
                order.get('reduceOnly')):
                return order
                
    except Exception as e:
        logger.error(f"Error getting open SL order: {e}")
    
    return None

async def sync_mirror_sl_from_main():
    """Main function to sync mirror SL orders from main account"""
    try:
        from clients.bybit_helpers import get_all_positions, get_instrument_info
        from clients.bybit_client import bybit_client
        from utils.helpers import value_adjusted_to_step
        from execution.mirror_trader import is_mirror_trading_enabled, bybit_client_2
        import pickle
        
        if not is_mirror_trading_enabled() or not bybit_client_2:
            logger.error("❌ Mirror trading is not enabled")
            return
        
        logger.info("🔄 Starting Mirror Account Stop Loss Synchronization")
        logger.info(f"🏃 Mode: {'DRY RUN' if DRY_RUN else 'LIVE'}")
        logger.info("=" * 80)
        
        # Get positions from both accounts
        logger.info("📊 Fetching positions from both accounts...")
        main_positions = await get_all_positions(client=bybit_client)
        mirror_positions = await get_all_positions(client=bybit_client_2)
        
        # Filter active positions only
        active_main = [pos for pos in main_positions if float(pos.get('size', 0)) > 0]
        active_mirror = [pos for pos in mirror_positions if float(pos.get('size', 0)) > 0]
        
        logger.info(f"📈 Found {len(active_main)} active main positions")
        logger.info(f"🔄 Found {len(active_mirror)} active mirror positions")
        
        # Load pickle data for monitors
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        # Track synchronization results
        sync_results = {
            'positions_checked': 0,
            'sl_synced': 0,
            'sl_already_matching': 0,
            'sl_missing_on_main': 0,
            'errors': 0,
            'actions': []
        }
        
        # Process each mirror position
        for mirror_pos in active_mirror:
            symbol = mirror_pos.get('symbol')
            side = mirror_pos.get('side')
            mirror_size = Decimal(str(mirror_pos.get('size', '0')))
            
            if mirror_size <= 0:
                continue
                
            sync_results['positions_checked'] += 1
            
            logger.info(f"\n{'='*60}")
            logger.info(f"🎯 Processing {symbol} {side}")
            logger.info(f"   Mirror position size: {mirror_size}")
            
            # Find corresponding main position
            main_sl_price = None
            main_pos_found = False
            
            for main_pos in active_main:
                if main_pos.get('symbol') == symbol and main_pos.get('side') == side:
                    main_pos_found = True
                    main_size = Decimal(str(main_pos.get('size', '0')))
                    logger.info(f"   Main position size: {main_size}")
                    break
            
            if not main_pos_found:
                logger.warning(f"   ⚠️ No corresponding main position found - skipping")
                continue
            
            # Get SL info from main account
            # First check open orders
            main_sl_order = await get_open_sl_order(bybit_client, symbol, side)
            if main_sl_order:
                main_sl_price = Decimal(str(main_sl_order.get('triggerPrice', '0')))
                logger.info(f"   Main SL found in orders: {main_sl_price}")
            else:
                # Check monitors for SL price
                for monitor_key, monitor_data in enhanced_monitors.items():
                    if (monitor_data.get('symbol') == symbol and 
                        monitor_data.get('side') == side and
                        'main' in monitor_key.lower()):
                        if monitor_data.get('sl_order'):
                            main_sl_price = Decimal(str(monitor_data['sl_order'].get('price', '0')))
                            logger.info(f"   Main SL found in monitor: {main_sl_price}")
                            break
            
            if not main_sl_price or main_sl_price == 0:
                logger.warning(f"   ⚠️ No SL found on main account - skipping")
                sync_results['sl_missing_on_main'] += 1
                continue
            
            # Get mirror SL info
            mirror_sl_order = await get_open_sl_order(bybit_client_2, symbol, side)
            mirror_sl_price = None
            
            if mirror_sl_order:
                mirror_sl_price = Decimal(str(mirror_sl_order.get('triggerPrice', '0')))
                logger.info(f"   Mirror SL found: {mirror_sl_price}")
            else:
                logger.info(f"   ❌ No SL order found on mirror account")
            
            # Determine action needed
            action_needed = None
            if not mirror_sl_order:
                action_needed = 'PLACE'
            elif abs(mirror_sl_price - main_sl_price) > Decimal('0.00001'):
                action_needed = 'UPDATE'
            else:
                logger.info(f"   ✅ SL prices already match")
                sync_results['sl_already_matching'] += 1
                continue
            
            # Calculate target size for mirror SL (including unfilled limits)
            target_size = mirror_size
            
            # Check for unfilled limit orders
            response = bybit_client_2.get_open_orders(
                category="linear",
                symbol=symbol
            )
            
            if response['retCode'] == 0:
                orders = response.get('result', {}).get('list', [])
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
                
                if unfilled_limit_qty > 0:
                    target_size = mirror_size + unfilled_limit_qty
                    logger.info(f"   Including unfilled limits: {unfilled_limit_qty}")
                    logger.info(f"   Target SL size: {target_size}")
            
            # Get instrument info for quantity adjustment
            instrument_info = await get_instrument_info(symbol)
            if not instrument_info:
                logger.error(f"   ❌ Could not get instrument info")
                sync_results['errors'] += 1
                continue
            
            lot_size_filter = instrument_info.get('lotSizeFilter', {})
            qty_step = Decimal(lot_size_filter.get('qtyStep', '1'))
            
            # Adjust quantity
            adjusted_qty = value_adjusted_to_step(target_size, qty_step)
            
            # Prepare order parameters
            sl_side = "Sell" if side == "Buy" else "Buy"
            
            if action_needed == 'PLACE':
                logger.info(f"\n   📍 ACTION: Place new SL order")
                logger.info(f"      Price: {main_sl_price}")
                logger.info(f"      Quantity: {adjusted_qty}")
                
                if not DRY_RUN:
                    try:
                        from execution.mirror_trader import mirror_tp_sl_order
                        
                        order_link_id = f"MIR_SL_SYNC_{symbol}_{int(time.time())}"
                        
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
                            logger.info(f"   ✅ SL order placed successfully: {result['orderId'][:8]}...")
                            sync_results['sl_synced'] += 1
                            
                            action = {
                                'symbol': symbol,
                                'side': side,
                                'action': 'PLACED',
                                'sl_price': main_sl_price,
                                'quantity': adjusted_qty,
                                'order_id': result['orderId']
                            }
                            sync_results['actions'].append(action)
                            
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
                                    'account': 'mirror',
                                    'synced_from_main': True,
                                    'sync_timestamp': time.time()
                                }
                        else:
                            logger.error(f"   ❌ Failed to place SL order")
                            sync_results['errors'] += 1
                            
                    except Exception as e:
                        logger.error(f"   ❌ Error placing SL order: {e}")
                        sync_results['errors'] += 1
                else:
                    logger.info(f"   🏃 DRY RUN: Would place SL order")
                    sync_results['sl_synced'] += 1
                    
            elif action_needed == 'UPDATE':
                logger.info(f"\n   📍 ACTION: Update existing SL order")
                logger.info(f"      Current price: {mirror_sl_price}")
                logger.info(f"      New price: {main_sl_price}")
                logger.info(f"      Quantity: {adjusted_qty}")
                
                if not DRY_RUN:
                    try:
                        # Cancel existing and place new
                        # (Bybit doesn't allow amending trigger price on stop orders)
                        cancel_result = bybit_client_2.cancel_order(
                            category="linear",
                            symbol=symbol,
                            orderId=mirror_sl_order['orderId']
                        )
                        
                        if cancel_result['retCode'] == 0:
                            logger.info(f"   ✅ Existing SL cancelled")
                            
                            # Place new SL
                            from execution.mirror_trader import mirror_tp_sl_order
                            
                            order_link_id = f"MIR_SL_SYNC_{symbol}_{int(time.time())}"
                            
                            result = await mirror_tp_sl_order(
                                symbol=symbol,
                                side=sl_side,
                                qty=str(adjusted_qty),
                                trigger_price=str(main_sl_price),
                                position_idx=0,
                                order_link_id=order_link_id,
                                stop_order_type="StopLoss"
                            )
                            
                            if result and result.get('orderId'):
                                logger.info(f"   ✅ New SL order placed: {result['orderId'][:8]}...")
                                sync_results['sl_synced'] += 1
                                
                                action = {
                                    'symbol': symbol,
                                    'side': side,
                                    'action': 'UPDATED',
                                    'old_price': mirror_sl_price,
                                    'new_price': main_sl_price,
                                    'quantity': adjusted_qty,
                                    'order_id': result['orderId']
                                }
                                sync_results['actions'].append(action)
                            else:
                                logger.error(f"   ❌ Failed to place new SL order")
                                sync_results['errors'] += 1
                        else:
                            logger.error(f"   ❌ Failed to cancel existing SL")
                            sync_results['errors'] += 1
                            
                    except Exception as e:
                        logger.error(f"   ❌ Error updating SL order: {e}")
                        sync_results['errors'] += 1
                else:
                    logger.info(f"   🏃 DRY RUN: Would update SL order")
                    sync_results['sl_synced'] += 1
                    
            # Brief delay between operations
            await asyncio.sleep(0.5)
        
        # Save updated monitors if not dry run
        if not DRY_RUN and sync_results['sl_synced'] > 0:
            with open(pkl_path, 'wb') as f:
                pickle.dump(data, f)
            logger.info("\n📊 Updated pickle file with synced SL orders")
        
        # Generate summary report
        logger.info("\n" + "=" * 80)
        logger.info("📋 SYNCHRONIZATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total positions checked: {sync_results['positions_checked']}")
        logger.info(f"SL orders synced: {sync_results['sl_synced']}")
        logger.info(f"SL already matching: {sync_results['sl_already_matching']}")
        logger.info(f"SL missing on main: {sync_results['sl_missing_on_main']}")
        logger.info(f"Errors encountered: {sync_results['errors']}")
        
        if sync_results['actions']:
            logger.info("\n📝 Actions Taken:")
            for action in sync_results['actions']:
                if action['action'] == 'PLACED':
                    logger.info(f"   • {action['symbol']} {action['side']}: Placed SL @ {action['sl_price']}")
                else:
                    logger.info(f"   • {action['symbol']} {action['side']}: Updated SL {action['old_price']} → {action['new_price']}")
        
        logger.info("\n✅ Synchronization complete!")
        
        # Verification step
        if not DRY_RUN and VERIFY_AFTER_PLACEMENT and sync_results['sl_synced'] > 0:
            logger.info("\n🔍 Verifying synchronization...")
            await asyncio.sleep(3)  # Wait for orders to settle
            
            # Re-check positions
            verify_count = 0
            for action in sync_results['actions']:
                sl_order = await get_open_sl_order(bybit_client_2, action['symbol'], action['side'])
                if sl_order:
                    verify_count += 1
                    logger.info(f"   ✅ Verified: {action['symbol']} {action['side']} SL order exists")
                else:
                    logger.error(f"   ❌ Not verified: {action['symbol']} {action['side']} SL order not found")
            
            logger.info(f"\n📊 Verification: {verify_count}/{sync_results['sl_synced']} orders confirmed")
        
    except Exception as e:
        logger.error(f"❌ Critical error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(sync_mirror_sl_from_main())