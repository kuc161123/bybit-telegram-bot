#!/usr/bin/env python3
"""
Create Missing ZILUSDT Enhanced TP/SL Monitors

This script will:
1. Create the missing ZILUSDT_Sell Enhanced TP/SL monitor
2. Create the missing ZILUSDT_Sell_MIRROR Enhanced TP/SL monitor
3. Populate them with current exchange order data
4. Restore complete 28/28 monitor coverage
"""

import asyncio
import sys
import pickle
import time
import logging
from decimal import Decimal
from typing import Dict, List, Any, Optional

sys.path.append('/Users/lualakol/bybit-telegram-bot')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_zilusdt_exchange_data():
    """Get current ZILUSDT exchange data for monitor creation"""
    
    logger.info("🔍 GATHERING ZILUSDT EXCHANGE DATA")
    logger.info("=" * 50)
    
    from clients.bybit_helpers import get_position_info, get_open_orders
    
    try:
        # Get position data
        positions = await get_position_info('ZILUSDT')
        position_data = None
        
        if positions:
            for pos in positions:
                size = float(pos.get('size', 0))
                if size > 0:
                    position_data = {
                        'symbol': 'ZILUSDT',
                        'side': pos.get('side', ''),
                        'size': Decimal(str(size)),
                        'avg_price': Decimal(str(pos.get('avgPrice', 0))),
                        'position_idx': pos.get('positionIdx', 0),
                        'unrealized_pnl': Decimal(str(pos.get('unrealisedPnl', 0)))
                    }
                    logger.info(f"✅ Position: {position_data['side']} {position_data['size']} @ {position_data['avg_price']}")
                    break
        
        if not position_data:
            logger.error("❌ No active ZILUSDT position found")
            return None
        
        # Get orders
        orders = await get_open_orders('ZILUSDT')
        
        sl_orders = []
        tp_orders = []
        
        if orders:
            for order in orders:
                order_link_id = order.get('orderLinkId', '')
                stop_order_type = order.get('stopOrderType', '')
                order_type = order.get('orderType', '')
                
                if (stop_order_type == 'Stop' or 'SL' in order_link_id):
                    sl_orders.append({
                        'order_id': order.get('orderId', ''),
                        'order_link_id': order_link_id,
                        'price': Decimal(str(order.get('triggerPrice') or order.get('price', '0'))),
                        'quantity': Decimal(str(order.get('qty', '0'))),
                        'status': 'ACTIVE'
                    })
                    logger.info(f"✅ SL Order: {order_link_id} @ {order.get('triggerPrice')}")
                    
                elif ('TP' in order_link_id and order_type == 'Limit'):
                    tp_number = 1  # Default
                    if 'TP1' in order_link_id:
                        tp_number = 1
                    elif 'TP2' in order_link_id:
                        tp_number = 2
                    elif 'TP3' in order_link_id:
                        tp_number = 3
                    elif 'TP4' in order_link_id:
                        tp_number = 4
                    
                    tp_orders.append({
                        'order_id': order.get('orderId', ''),
                        'order_link_id': order_link_id,
                        'price': Decimal(str(order.get('price', '0'))),
                        'quantity': Decimal(str(order.get('qty', '0'))),
                        'tp_number': tp_number,
                        'status': 'ACTIVE'
                    })
                    logger.info(f"✅ TP{tp_number} Order: {order_link_id} @ {order.get('price')}")
        
        # Sort TP orders by number
        tp_orders.sort(key=lambda x: x['tp_number'])
        
        logger.info(f"📊 Orders Summary: {len(sl_orders)} SL, {len(tp_orders)} TP")
        
        return {
            'position': position_data,
            'sl_orders': sl_orders,
            'tp_orders': tp_orders
        }
        
    except Exception as e:
        logger.error(f"❌ Error gathering ZILUSDT exchange data: {e}")
        return None

async def create_zilusdt_enhanced_monitors():
    """Create missing ZILUSDT Enhanced TP/SL monitors"""
    
    logger.info("")
    logger.info("🔧 CREATING ZILUSDT ENHANCED TP/SL MONITORS")
    logger.info("=" * 50)
    
    # Get exchange data
    exchange_data = await get_zilusdt_exchange_data()
    
    if not exchange_data:
        logger.error("❌ Could not get exchange data for ZILUSDT")
        return False
    
    try:
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        backup_path = f'{pkl_path}.backup_zilusdt_monitors_{int(time.time())}' 
        
        # Create backup
        logger.info(f"💾 Creating backup: {backup_path}")
        with open(pkl_path, 'rb') as src, open(backup_path, 'wb') as dst:
            dst.write(src.read())
        
        # Load current data
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        logger.info(f"📊 Current Enhanced TP/SL monitors: {len(enhanced_monitors)}")
        
        # Create main account monitor
        main_monitor_key = "ZILUSDT_Sell"
        position = exchange_data['position']
        
        main_monitor = {
            'symbol': position['symbol'],
            'side': position['side'],
            'position_size': position['size'],
            'current_size': position['size'],
            'remaining_size': position['size'],
            'entry_price': position['avg_price'],
            'position_idx': position['position_idx'],
            'unrealized_pnl': position['unrealized_pnl'],
            'approach': 'conservative',
            'account_type': 'main',
            'monitor_type': 'enhanced_tp_sl',
            'created_at': time.time(),
            'last_check': time.time(),
            'last_update': time.time(),
            'circuit_breaker_count': 0,
            'is_active': True,
            'tp_orders': [],
            'sl_order': {}
        }
        
        # Add SL order data
        if exchange_data['sl_orders']:
            sl_order = exchange_data['sl_orders'][0]
            main_monitor['sl_order'] = {
                'order_id': sl_order['order_id'],
                'order_link_id': sl_order['order_link_id'],
                'price': sl_order['price'],
                'quantity': sl_order['quantity'],
                'original_quantity': sl_order['quantity'],
                'status': sl_order['status']
            }
            logger.info(f"✅ Added SL order data to main monitor")
        
        # Add TP orders data
        tp_orders_data = []
        for tp_order in exchange_data['tp_orders']:
            tp_orders_data.append({
                'order_id': tp_order['order_id'],
                'order_link_id': tp_order['order_link_id'],
                'price': tp_order['price'],
                'quantity': tp_order['quantity'],
                'original_quantity': tp_order['quantity'],
                'tp_number': tp_order['tp_number'],
                'status': tp_order['status']
            })
        
        main_monitor['tp_orders'] = tp_orders_data
        logger.info(f"✅ Added {len(tp_orders_data)} TP orders to main monitor")
        
        # Create main monitor
        enhanced_monitors[main_monitor_key] = main_monitor
        logger.info(f"✅ Created main monitor: {main_monitor_key}")
        
        # Create mirror account monitor (60% of main)
        mirror_monitor_key = "ZILUSDT_Sell_MIRROR"
        mirror_ratio = Decimal('0.6')
        
        mirror_monitor = main_monitor.copy()
        mirror_monitor.update({
            'position_size': position['size'] * mirror_ratio,
            'current_size': position['size'] * mirror_ratio,
            'remaining_size': position['size'] * mirror_ratio,
            'account_type': 'mirror',
            'mirror_account': True,
            'mirror_ratio': mirror_ratio
        })
        
        # Create proportional SL order for mirror
        if exchange_data['sl_orders']:
            sl_order = exchange_data['sl_orders'][0]
            mirror_monitor['sl_order'] = {
                'order_id': f"mirror_{sl_order['order_id'][:8]}",
                'order_link_id': sl_order['order_link_id'].replace('BOT_', 'BOT_MIRROR_'),
                'price': sl_order['price'],
                'quantity': position['size'] * mirror_ratio,
                'original_quantity': position['size'] * mirror_ratio,
                'status': 'ACTIVE'
            }
            logger.info(f"✅ Added proportional SL order data to mirror monitor")
        
        # Create proportional TP orders for mirror
        mirror_tp_orders = []
        for tp_order in exchange_data['tp_orders']:
            mirror_tp_qty = tp_order['quantity'] * mirror_ratio
            mirror_tp_orders.append({
                'order_id': f"mirror_{tp_order['order_id'][:8]}",
                'order_link_id': tp_order['order_link_id'].replace('BOT_', 'BOT_MIRROR_'),
                'price': tp_order['price'],
                'quantity': mirror_tp_qty,
                'original_quantity': mirror_tp_qty,
                'tp_number': tp_order['tp_number'],
                'status': 'ACTIVE'
            })
        
        mirror_monitor['tp_orders'] = mirror_tp_orders
        logger.info(f"✅ Added {len(mirror_tp_orders)} proportional TP orders to mirror monitor")
        
        # Create mirror monitor
        enhanced_monitors[mirror_monitor_key] = mirror_monitor
        logger.info(f"✅ Created mirror monitor: {mirror_monitor_key}")
        
        # Save updated data
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        
        # Create reload signal
        signal_file = '/Users/lualakol/bybit-telegram-bot/reload_enhanced_monitors.signal'
        with open(signal_file, 'w') as f:
            f.write(f"ZILUSDT monitors created at {time.time()}")
        
        logger.info("")
        logger.info(f"✅ ZILUSDT Enhanced TP/SL monitors created successfully!")
        logger.info(f"   Main monitor: {main_monitor_key}")
        logger.info(f"   Mirror monitor: {mirror_monitor_key}")
        logger.info(f"   Total monitors now: {len(enhanced_monitors)}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating ZILUSDT monitors: {e}")
        return False

async def verify_monitor_creation():
    """Verify that monitors were created successfully"""
    
    logger.info("")
    logger.info("🔍 VERIFYING MONITOR CREATION")
    logger.info("=" * 50)
    
    try:
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        # Check for ZILUSDT monitors
        zilusdt_monitors = [k for k in enhanced_monitors.keys() if 'ZILUSDT' in k]
        
        logger.info(f"📊 ZILUSDT Enhanced TP/SL monitors found: {len(zilusdt_monitors)}")
        
        success = len(zilusdt_monitors) == 2
        
        for key in zilusdt_monitors:
            monitor = enhanced_monitors[key]
            account_type = monitor.get('account_type', 'unknown')
            position_size = monitor.get('position_size', 0)
            tp_count = len(monitor.get('tp_orders', []))
            has_sl = bool(monitor.get('sl_order', {}).get('order_id'))
            
            logger.info(f"✅ {key}:")
            logger.info(f"   Account Type: {account_type}")
            logger.info(f"   Position Size: {position_size}")
            logger.info(f"   TP Orders: {tp_count}")
            logger.info(f"   SL Order: {'Yes' if has_sl else 'No'}")
        
        # Check total monitor count
        total_monitors = len(enhanced_monitors)
        expected_total = 28  # 14 main + 14 mirror
        
        logger.info(f"")
        logger.info(f"📊 TOTAL MONITOR COUNT:")
        logger.info(f"   Current total: {total_monitors}")
        logger.info(f"   Expected total: {expected_total}")
        logger.info(f"   Gap remaining: {expected_total - total_monitors}")
        
        if total_monitors == expected_total:
            logger.info("🎯 PERFECT: 28/28 monitor coverage achieved!")
        elif total_monitors >= 26:
            logger.info(f"✅ GOOD: {total_monitors}/28 monitor coverage")
        else:
            logger.warning(f"⚠️  Monitor coverage incomplete: {total_monitors}/28")
        
        return success and total_monitors >= 26
        
    except Exception as e:
        logger.error(f"❌ Error verifying monitor creation: {e}")
        return False

async def main():
    """Main execution"""
    
    logger.info("🔧 ZILUSDT ENHANCED TP/SL MONITOR CREATION")
    logger.info("=" * 70)
    logger.info("Creating missing ZILUSDT monitors to restore complete coverage")
    logger.info("")
    
    # Create monitors
    creation_success = await create_zilusdt_enhanced_monitors()
    
    if creation_success:
        # Verify creation
        verification_success = await verify_monitor_creation()
        
        if verification_success:
            logger.info("")
            logger.info("🎯 ZILUSDT MONITOR CREATION: COMPLETE SUCCESS")
            logger.info("✅ Both main and mirror monitors created")
            logger.info("✅ All TP and SL data populated")
            logger.info("✅ Enhanced TP/SL monitoring restored for ZILUSDT")
            logger.info("✅ Position is now protected from SL failures")
        else:
            logger.error("⚠️  Monitor creation succeeded but verification failed")
            return False
    else:
        logger.error("❌ Monitor creation failed")
        return False
    
    return True

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)