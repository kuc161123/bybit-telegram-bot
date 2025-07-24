#!/usr/bin/env python3
"""
Fix Missing Mirror Enhanced TP/SL Monitors

Current issue: Mirror positions don't have Enhanced TP/SL monitors
This script creates the missing monitors for LINKUSDT, TIAUSDT, and WIFUSDT on mirror account
"""

import asyncio
import pickle
import logging
import time
from decimal import Decimal
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def create_mirror_enhanced_monitors():
    """Create missing Enhanced TP/SL monitors for mirror positions"""
    try:
        # Import required modules
        from clients.bybit_helpers import get_all_positions_with_client, get_all_open_orders
        from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
        
        if not is_mirror_trading_enabled() or not bybit_client_2:
            logger.error("Mirror trading not enabled")
            return False
            
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        backup_path = f'{pkl_path}.backup_mirror_fix_{int(time.time())}'
        
        # Backup
        logger.info(f"💾 Creating backup: {backup_path}")
        with open(pkl_path, 'rb') as src, open(backup_path, 'wb') as dst:
            dst.write(src.read())
        
        # Load current data
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        logger.info(f"📊 Current Enhanced TP/SL monitors: {len(enhanced_monitors)}")
        
        # Get mirror positions
        mirror_positions = await get_all_positions_with_client(bybit_client_2)
        mirror_orders = await get_all_open_orders(bybit_client_2)
        
        created_count = 0
        
        for pos in mirror_positions:
            if float(pos.get('size', 0)) > 0:
                symbol = pos.get('symbol')
                side = pos.get('side')
                size = Decimal(str(pos.get('size', '0')))
                entry_price = Decimal(str(pos.get('avgPrice', '0')))
                
                logger.info(f"🔍 Processing mirror position: {symbol} {side} size={size}")
                
                # Find orders for this position
                position_orders = [o for o in mirror_orders if o.get('symbol') == symbol]
                
                # Separate TP and SL orders
                tp_orders = []
                sl_order = None
                
                for order in position_orders:
                    order_link_id = order.get('orderLinkId', '')
                    trigger_price = order.get('triggerPrice', '')
                    
                    # Handle empty trigger price
                    if not trigger_price or trigger_price == '':
                        trigger_price = '0'
                    
                    if 'TP' in order_link_id and order.get('reduceOnly'):
                        tp_orders.append({
                            'order_id': order.get('orderId', ''),
                            'order_link_id': order_link_id,
                            'price': Decimal(str(trigger_price)),
                            'quantity': Decimal(str(order.get('qty', '0'))),
                            'original_quantity': Decimal(str(order.get('qty', '0'))),
                            'tp_number': len(tp_orders) + 1,
                            'status': 'ACTIVE'
                        })
                    elif 'SL' in order_link_id and order.get('reduceOnly'):
                        sl_order = {
                            'order_id': order.get('orderId', ''),
                            'order_link_id': order_link_id,
                            'price': Decimal(str(trigger_price)),
                            'quantity': Decimal(str(order.get('qty', '0'))),
                            'original_quantity': Decimal(str(order.get('qty', '0'))),
                            'breakeven': False,
                            'covers_full_position': True,  # 100% coverage
                            'target_position_size': size
                        }
                
                # Sort TP orders by price (descending for Buy, ascending for Sell)
                tp_orders.sort(key=lambda x: x['price'], reverse=(side == 'Buy'))
                
                # Get approach from main monitor
                main_key = f"{symbol}_{side}"
                main_monitor = enhanced_monitors.get(main_key, {})
                approach = main_monitor.get('approach', 'CONSERVATIVE')
                
                # Create mirror monitor key and data
                mirror_key = f"{symbol}_{side}_MIRROR"
                
                if mirror_key not in enhanced_monitors:
                    monitor_data = {
                        'symbol': symbol,
                        'side': side,
                        'position_size': size,
                        'remaining_size': size,
                        'current_size': size,
                        'entry_price': entry_price,
                        'position_idx': 0,  # Mirror uses One-Way mode
                        'tp_orders': tp_orders,
                        'sl_order': sl_order,
                        'created_at': time.time(),
                        'last_check': time.time(),
                        'last_update': time.time(),
                        'phase': 'PROFIT_TAKING' if tp_orders else 'MONITORING',
                        'approach': approach,
                        'sl_moved_to_be': False,
                        'tp1_hit': False,
                        'is_mirror': True,
                        'account_type': 'mirror',
                        'status': 'ACTIVE',
                        'monitoring_active': True,
                        'created_by': 'mirror_monitor_fix',
                        'chat_id': None,  # Will be populated from main monitor
                        'monitor_id': f"ENH_{symbol}_{side}_MIRROR_{int(time.time())}"
                    }
                    
                    # Copy chat_id from main monitor if exists
                    if main_monitor:
                        monitor_data['chat_id'] = main_monitor.get('chat_id')
                        monitor_data['original_size'] = main_monitor.get('original_size', size)
                    
                    enhanced_monitors[mirror_key] = monitor_data
                    created_count += 1
                    logger.info(f"✅ Created Enhanced TP/SL mirror monitor: {mirror_key}")
                    logger.info(f"   - TP orders: {len(tp_orders)}")
                    logger.info(f"   - SL order: {'Yes' if sl_order else 'No'}")
                else:
                    logger.info(f"ℹ️ Enhanced TP/SL mirror monitor already exists: {mirror_key}")
        
        # Save updated data
        bot_data['enhanced_tp_sl_monitors'] = enhanced_monitors
        data['bot_data'] = bot_data
        
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"\n✅ Created {created_count} missing mirror Enhanced TP/SL monitors")
        logger.info(f"📊 Total Enhanced TP/SL monitors: {len(enhanced_monitors)}")
        
        # Show all monitor keys
        logger.info("\n📋 All Enhanced TP/SL monitor keys:")
        for key in sorted(enhanced_monitors.keys()):
            logger.info(f"   {key}")
        
        return created_count > 0
        
    except Exception as e:
        logger.error(f"❌ Error creating mirror Enhanced monitors: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main execution"""
    logger.info("🎯 Fixing Missing Mirror Enhanced TP/SL Monitors")
    logger.info("=" * 50)
    
    success = await create_mirror_enhanced_monitors()
    
    if success:
        logger.info("\n✅ Mirror Enhanced TP/SL monitors created successfully!")
        logger.info("🔄 The monitoring loop will detect the new monitors immediately")
        logger.info("📊 Monitor coverage should now be 100%")
    else:
        logger.info("\nℹ️ No new monitors needed to be created")

if __name__ == "__main__":
    asyncio.run(main())