#!/usr/bin/env python3
"""
Emergency TONUSDT Monitor Fix

Fix the Enhanced TP/SL monitor data for TONUSDT to properly track the position
and ensure stop loss monitoring is working correctly.
"""

import pickle
import time
import logging
from decimal import Decimal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_tonusdt_monitor():
    """Fix TONUSDT Enhanced TP/SL monitor data"""
    try:
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        backup_path = f'{pkl_path}.backup_emergency_fix_{int(time.time())}'
        
        # Create backup
        logger.info(f"💾 Creating backup: {backup_path}")
        with open(pkl_path, 'rb') as src, open(backup_path, 'wb') as dst:
            dst.write(src.read())
        
        # Load current data
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        # Current position details from exchange
        current_position_size = Decimal('76')
        current_avg_price = Decimal('2.7836')
        emergency_sl_order_id = '0bc96079-672e-4e8d-92fb-3448d0d4aa26'
        emergency_sl_price = Decimal('2.9228')
        
        # Update main monitor
        main_key = 'TONUSDT_Sell'
        if main_key in enhanced_monitors:
            monitor = enhanced_monitors[main_key]
            
            logger.info(f"🔧 Updating main monitor: {main_key}")
            
            # Update position data to match reality
            monitor['position_size'] = current_position_size
            monitor['current_size'] = current_position_size
            monitor['remaining_size'] = current_position_size
            monitor['entry_price'] = current_avg_price
            monitor['last_check'] = time.time()
            monitor['last_update'] = time.time()
            monitor['phase'] = 'PROFIT_TAKING'  # Since limit orders filled
            
            # Add the emergency SL order data
            monitor['sl_order'] = {
                'order_id': emergency_sl_order_id,
                'order_link_id': f'BOT_EMERGENCY_SL_TONUSDT_{int(time.time())}',
                'price': emergency_sl_price,
                'quantity': current_position_size,
                'original_quantity': current_position_size,
                'status': 'ACTIVE'
            }
            
            # Update TP orders to match current exchange orders
            monitor['tp_orders'] = [
                {
                    'order_id': '9fb34a42',
                    'order_link_id': 'BOT_CONS_TONUSDT_TP1_112542',
                    'price': Decimal('2.6995'),
                    'quantity': Decimal('32.3'),
                    'original_quantity': Decimal('32.3'),
                    'tp_number': 1,
                    'status': 'ACTIVE'
                },
                {
                    'order_id': 'a7130f72',
                    'order_link_id': 'BOT_CONS_TONUSDT_TP2_112542',
                    'price': Decimal('2.6365'),
                    'quantity': Decimal('1.9'),
                    'original_quantity': Decimal('1.9'),
                    'tp_number': 2,
                    'status': 'ACTIVE'
                },
                {
                    'order_id': '85c5836e',
                    'order_link_id': 'BOT_CONS_TONUSDT_TP3_112543',
                    'price': Decimal('2.5735'),
                    'quantity': Decimal('1.9'),
                    'original_quantity': Decimal('1.9'),
                    'tp_number': 3,
                    'status': 'ACTIVE'
                },
                {
                    'order_id': '15682759',
                    'order_link_id': 'BOT_CONS_TONUSDT_TP4_112543',
                    'price': Decimal('2.3846'),
                    'quantity': Decimal('1.9'),
                    'original_quantity': Decimal('1.9'),
                    'tp_number': 4,
                    'status': 'ACTIVE'
                }
            ]
            
            # Mark that we've fixed the monitor
            monitor['emergency_fixed'] = True
            monitor['emergency_fix_time'] = time.time()
            
            logger.info(f"✅ Updated main monitor with:")
            logger.info(f"   Position Size: {current_position_size}")
            logger.info(f"   Entry Price: {current_avg_price}")
            logger.info(f"   SL Order: {emergency_sl_order_id}")
            logger.info(f"   TP Orders: {len(monitor['tp_orders'])}")
        
        # Update mirror monitor if exists
        mirror_key = 'TONUSDT_Sell_MIRROR'
        if mirror_key in enhanced_monitors:
            mirror_monitor = enhanced_monitors[mirror_key]
            logger.info(f"🔧 Updating mirror monitor: {mirror_key}")
            
            # Update mirror monitor similarly but with smaller size
            mirror_size = current_position_size * Decimal('0.6')  # Approximate mirror ratio
            mirror_monitor['position_size'] = mirror_size
            mirror_monitor['current_size'] = mirror_size
            mirror_monitor['remaining_size'] = mirror_size
            mirror_monitor['last_check'] = time.time()
            mirror_monitor['last_update'] = time.time()
            mirror_monitor['phase'] = 'PROFIT_TAKING'
            mirror_monitor['emergency_fixed'] = True
            mirror_monitor['emergency_fix_time'] = time.time()
            
            logger.info(f"✅ Updated mirror monitor with size: {mirror_size}")
        
        # Save updated data
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"✅ Monitor data updated successfully")
        logger.info(f"📊 Total Enhanced TP/SL monitors: {len(enhanced_monitors)}")
        
        # Create signal file for monitor reload
        signal_file = '/Users/lualakol/bybit-telegram-bot/reload_enhanced_monitors.signal'
        with open(signal_file, 'w') as f:
            f.write(f"Emergency TONUSDT fix applied at {time.time()}")
        
        logger.info("🔄 Created reload signal for background monitoring loop")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error fixing TONUSDT monitor: {e}")
        return False

if __name__ == "__main__":
    logger.info("🚨 Emergency TONUSDT Monitor Fix")
    logger.info("=" * 50)
    
    success = fix_tonusdt_monitor()
    
    if success:
        logger.info("✅ Emergency fix applied successfully!")
        logger.info("🔄 Monitor system will reload the data within 60 seconds")
        logger.info("📊 TONUSDT position is now properly tracked and protected")
    else:
        logger.error("❌ Emergency fix failed!")