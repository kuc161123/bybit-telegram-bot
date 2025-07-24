#!/usr/bin/env python3
"""
Comprehensive fix for all positions
- Create monitors for positions that don't have them
- Fix DOGEUSDT limit order state
- Ensure mirror sync is correct
"""
import asyncio
import logging
from decimal import Decimal
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHAT_ID = 5634913742

async def fix_all_positions():
    """Fix all positions comprehensively"""
    try:
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        from execution.mirror_enhanced_tp_sl import mirror_enhanced_tp_sl_manager
        from clients.bybit_helpers import get_all_positions, get_open_orders
        from execution.mirror_trader import is_mirror_trading_enabled
        
        logger.info("🔧 Comprehensive position fix starting...")
        
        # Get all positions
        positions = await get_all_positions()
        logger.info(f"📊 Found {len(positions)} positions")
        
        # Get all orders
        all_orders = await get_open_orders()
        
        fixed_count = 0
        
        for position in positions:
            symbol = position.get('symbol', '')
            side = position.get('side', '')
            size = Decimal(str(position.get('size', '0')))
            avg_price = Decimal(str(position.get('avgPrice', '0')))
            
            if not symbol or not side or size == 0:
                continue
            
            monitor_key = f"{symbol}_{side}"
            logger.info(f"\n{'='*50}")
            logger.info(f"📊 Processing {symbol} {side}")
            logger.info(f"   Size: {size}")
            logger.info(f"   Entry: ${avg_price}")
            
            # Check if monitor exists
            if monitor_key in enhanced_tp_sl_manager.position_monitors:
                logger.info("✅ Monitor exists")
                monitor_data = enhanced_tp_sl_manager.position_monitors[monitor_key]
                
                # Special fix for DOGEUSDT
                if symbol == 'DOGEUSDT' and side == 'Buy':
                    logger.info("🔧 Applying DOGEUSDT special fix...")
                    monitor_data['limit_orders_filled'] = True
                    monitor_data['phase'] = 'PROFIT_TAKING'
                    monitor_data['position_size'] = size
                    monitor_data['remaining_size'] = size
                    
                    # Reset fill tracker
                    enhanced_tp_sl_manager.fill_tracker[monitor_key] = {
                        "total_filled": Decimal("0"),
                        "target_size": size
                    }
                    logger.info("✅ DOGEUSDT state fixed")
            else:
                logger.info("⚠️ No monitor found, creating one...")
                
                # Get orders for this position
                position_orders = [o for o in all_orders if o.get('symbol') == symbol]
                
                # Separate TP and SL orders
                tp_orders = []
                sl_order = None
                
                for order in position_orders:
                    if not order.get('reduceOnly'):
                        continue
                    
                    order_link_id = order.get('orderLinkId', '')
                    
                    # Check for TP orders
                    if 'TP' in order_link_id and order.get('orderType') == 'Limit':
                        tp_number = 1
                        for i in range(1, 5):
                            if f'TP{i}' in order_link_id:
                                tp_number = i
                                break
                        
                        tp_orders.append({
                            'order_id': order.get('orderId'),
                            'order_link_id': order_link_id,
                            'price': Decimal(str(order.get('price', '0'))),
                            'quantity': Decimal(str(order.get('qty', '0'))),
                            'original_quantity': Decimal(str(order.get('qty', '0'))),
                            'tp_number': tp_number
                        })
                    
                    # Check for SL orders
                    elif 'SL' in order_link_id and order.get('triggerPrice'):
                        sl_order = {
                            'order_id': order.get('orderId'),
                            'order_link_id': order_link_id,
                            'price': Decimal(str(order.get('triggerPrice', '0'))),
                            'quantity': Decimal(str(order.get('qty', '0'))),
                            'original_quantity': Decimal(str(order.get('qty', '0')))
                        }
                
                # Sort TP orders by number
                tp_orders.sort(key=lambda x: x.get('tp_number', 0))
                
                # Determine approach
                approach = 'CONSERVATIVE' if len(tp_orders) >= 3 else 'FAST'
                
                # Check if this position started with limit orders already filled
                # For conservative approach with partial position (like DOGEUSDT at 28.33%)
                limit_orders_filled = False
                if approach == 'CONSERVATIVE' and symbol == 'DOGEUSDT':
                    # DOGEUSDT had limit orders filled (28.33% of target)
                    limit_orders_filled = True
                
                # Create monitor
                monitor_data = {
                    'symbol': symbol,
                    'side': side,
                    'chat_id': CHAT_ID,
                    'approach': approach,
                    'position_size': size,
                    'remaining_size': size,
                    'entry_price': avg_price,
                    'tp_orders': tp_orders,
                    'sl_order': sl_order,
                    'limit_orders': [],
                    'limit_orders_filled': limit_orders_filled or (approach == 'FAST'),
                    'phase': 'PROFIT_TAKING',  # All current positions are in profit-taking
                    'created_at': time.time(),
                    'last_check': time.time(),
                    'account_type': 'main',
                    'sl_moved_to_be': False,
                    'tp1_hit': False,
                    'original_sl_price': sl_order['price'] if sl_order else None,
                    'total_tp_filled': Decimal("0"),
                    'cleanup_completed': False
                }
                
                # Add to monitors
                enhanced_tp_sl_manager.position_monitors[monitor_key] = monitor_data
                
                # Initialize fill tracker
                enhanced_tp_sl_manager.fill_tracker[monitor_key] = {
                    "total_filled": Decimal("0"),
                    "target_size": size
                }
                
                logger.info(f"✅ Created monitor:")
                logger.info(f"   - Approach: {approach}")
                logger.info(f"   - TP Orders: {len(tp_orders)}")
                logger.info(f"   - SL Order: {'Yes' if sl_order else 'No'}")
                logger.info(f"   - Limit Orders Filled: {limit_orders_filled}")
                
                # Start monitoring task
                monitor_task = asyncio.create_task(enhanced_tp_sl_manager._run_monitor_loop(symbol, side))
                monitor_data['monitoring_task'] = monitor_task
                logger.info("   - Started monitoring task")
                
                fixed_count += 1
            
            # Create dashboard monitor entry
            try:
                await enhanced_tp_sl_manager.create_dashboard_monitor_entry(
                    symbol, side, CHAT_ID, 
                    enhanced_tp_sl_manager.position_monitors[monitor_key].get('approach', 'conservative').lower(),
                    'main'
                )
                logger.info("✅ Dashboard monitor entry created/updated")
            except Exception as e:
                logger.error(f"Error creating dashboard entry: {e}")
        
        # Fix mirror sync if enabled
        if is_mirror_trading_enabled() and mirror_enhanced_tp_sl_manager:
            logger.info("\n🪞 Syncing mirror account...")
            
            from execution.mirror_trader import get_mirror_positions
            mirror_positions = await get_mirror_positions()
            
            for position in positions:
                symbol = position.get('symbol', '')
                side = position.get('side', '')
                main_size = Decimal(str(position.get('size', '0')))
                
                if not symbol or not side or main_size == 0:
                    continue
                
                # Find corresponding mirror position
                mirror_pos = None
                for mp in mirror_positions:
                    if mp.get('symbol') == symbol and mp.get('side') == side:
                        mirror_pos = mp
                        break
                
                if mirror_pos:
                    mirror_size = Decimal(str(mirror_pos.get('size', '0')))
                    logger.info(f"\n🪞 {symbol} {side}: Main={main_size}, Mirror={mirror_size}")
                    
                    # Sync mirror orders
                    try:
                        await mirror_enhanced_tp_sl_manager.sync_with_main_position_enhanced(
                            symbol, side, main_size
                        )
                        logger.info("✅ Mirror sync completed")
                    except Exception as e:
                        logger.error(f"Error syncing mirror: {e}")
        
        logger.info(f"\n✅ Comprehensive fix completed!")
        logger.info(f"📊 Summary:")
        logger.info(f"   - Positions processed: {len(positions)}")
        logger.info(f"   - Monitors created/fixed: {fixed_count}")
        logger.info(f"   - Total active monitors: {len(enhanced_tp_sl_manager.position_monitors)}")
        
    except Exception as e:
        logger.error(f"❌ Error in comprehensive fix: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fix_all_positions())