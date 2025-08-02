#!/usr/bin/env python3
"""
Create Missing Enhanced TP/SL Monitors

The bot shows "Monitoring 24 positions" but you have 28 positions (14 main + 14 mirror).
This means XTZUSDT and BANDUSDT (both main and mirror) are missing Enhanced TP/SL monitors.

This script will create the 4 missing Enhanced TP/SL monitors:
- XTZUSDT_Sell
- BANDUSDT_Sell  
- XTZUSDT_Sell_MIRROR
- BANDUSDT_Sell_MIRROR
"""

import asyncio
import pickle
import logging
import time
from decimal import Decimal
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def get_position_info_for_symbol(symbol: str) -> Dict[str, Any]:
    """Get current position information for a symbol from Bybit"""
    try:
        from clients.bybit_helpers import get_position_info
        positions = await get_position_info(symbol)
        
        if positions:
            for pos in positions:
                if float(pos.get('size', 0)) > 0:
                    return {
                        'symbol': symbol,
                        'side': pos.get('side', ''),
                        'size': Decimal(str(pos.get('size', '0'))),
                        'entry_price': Decimal(str(pos.get('avgPrice', '0'))),
                        'unrealised_pnl': Decimal(str(pos.get('unrealisedPnl', '0'))),
                        'position_idx': pos.get('positionIdx', 0)
                    }
        return None
    except Exception as e:
        logger.error(f"Error getting position info for {symbol}: {e}")
        return None

async def get_orders_for_symbol(symbol: str) -> list:
    """Get current orders for a symbol"""
    try:
        from clients.bybit_helpers import get_open_orders
        orders = await get_open_orders(symbol)
        return orders if orders else []
    except Exception as e:
        logger.error(f"Error getting orders for {symbol}: {e}")
        return []

async def create_enhanced_monitor_entry(symbol: str, side: str, position_info: Dict, orders: list, is_mirror: bool = False) -> Dict[str, Any]:
    """Create Enhanced TP/SL monitor entry"""
    
    # Separate TP and SL orders
    tp_orders = []
    sl_orders = []
    
    for order in orders:
        order_link_id = order.get('orderLinkId', '')
        trigger_price = order.get('triggerPrice', '')
        order_type = order.get('orderType', '')
        stop_order_type = order.get('stopOrderType', '')
        
        if stop_order_type == 'TakeProfit' or 'TP' in order_link_id:
            tp_orders.append({
                'order_id': order.get('orderId', ''),
                'order_link_id': order_link_id,
                'price': Decimal(str(trigger_price or order.get('price', '0'))),
                'quantity': Decimal(str(order.get('qty', '0'))),
                'original_quantity': Decimal(str(order.get('qty', '0'))),
                'tp_number': len(tp_orders) + 1,
                'status': 'ACTIVE'
            })
        elif stop_order_type == 'StopLoss' or 'SL' in order_link_id:
            sl_orders.append({
                'order_id': order.get('orderId', ''),
                'order_link_id': order_link_id,
                'price': Decimal(str(trigger_price or order.get('price', '0'))),
                'quantity': Decimal(str(order.get('qty', '0'))),
                'original_quantity': Decimal(str(order.get('qty', '0'))),
                'status': 'ACTIVE'
            })
    
    # Create monitor data structure
    monitor_data = {
        'symbol': symbol,
        'side': side,
        'position_size': position_info['size'],
        'remaining_size': position_info['size'],
        'current_size': position_info['size'],
        'entry_price': position_info['entry_price'],
        'position_idx': position_info.get('position_idx', 0),
        'tp_orders': tp_orders,
        'sl_orders': sl_orders,
        'sl_order': sl_orders[0] if sl_orders else None,
        'created_at': time.time(),
        'last_check': time.time(),
        'last_update': time.time(),
        'phase': 'PROFIT_TAKING' if tp_orders else 'MONITORING',
        'approach': 'conservative',
        'sl_moved_to_be': False,
        'tp1_hit': False,
        'is_mirror': is_mirror,
        'account_type': 'mirror' if is_mirror else 'main',
        'status': 'ACTIVE',
        'monitoring_active': True,
        'created_by': 'missing_monitor_recovery'
    }
    
    return monitor_data

async def create_missing_enhanced_monitors():
    """Create the missing Enhanced TP/SL monitors"""
    try:
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        backup_path = f'{pkl_path}.backup_enhanced_fix_{int(time.time())}'
        
        # Backup
        logger.info(f"💾 Creating backup: {backup_path}")
        with open(pkl_path, 'rb') as src, open(backup_path, 'wb') as dst:
            dst.write(src.read())
        
        # Load current data
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        logger.info(f"📊 Current Enhanced TP/SL monitors: {len(enhanced_monitors)}")
        
        # Missing symbols
        missing_symbols = ['XTZUSDT', 'BANDUSDT']
        created_count = 0
        
        for symbol in missing_symbols:
            logger.info(f"🔍 Processing {symbol}...")
            
            # Get current position info
            position_info = await get_position_info_for_symbol(symbol)
            if not position_info:
                logger.warning(f"⚠️ No position found for {symbol}")
                continue
            
            # Get current orders
            orders = await get_orders_for_symbol(symbol)
            
            side = position_info['side']
            
            # Create main account monitor
            main_key = f"{symbol}_{side}"
            if main_key not in enhanced_monitors:
                monitor_data = await create_enhanced_monitor_entry(symbol, side, position_info, orders, is_mirror=False)
                enhanced_monitors[main_key] = monitor_data
                created_count += 1
                logger.info(f"✅ Created Enhanced TP/SL monitor: {main_key}")
            else:
                logger.info(f"ℹ️ Enhanced TP/SL monitor already exists: {main_key}")
            
            # Create mirror account monitor
            mirror_key = f"{symbol}_{side}_MIRROR"
            if mirror_key not in enhanced_monitors:
                mirror_monitor_data = await create_enhanced_monitor_entry(symbol, side, position_info, orders, is_mirror=True)
                enhanced_monitors[mirror_key] = mirror_monitor_data
                created_count += 1
                logger.info(f"✅ Created Enhanced TP/SL mirror monitor: {mirror_key}")
            else:
                logger.info(f"ℹ️ Enhanced TP/SL mirror monitor already exists: {mirror_key}")
        
        # Save updated data
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"✅ Created {created_count} missing Enhanced TP/SL monitors")
        logger.info(f"📊 Total Enhanced TP/SL monitors: {len(enhanced_monitors)}")
        
        # Create signal file for hot reload
        signal_file = '/Users/lualakol/bybit-telegram-bot/reload_enhanced_monitors.signal'
        with open(signal_file, 'w') as f:
            f.write(f"Enhanced monitors updated at {time.time()}")
        
        logger.info("🔄 Created reload signal for background monitoring loop")
        
        return created_count > 0
        
    except Exception as e:
        logger.error(f"❌ Error creating missing Enhanced monitors: {e}")
        return False

async def main():
    """Main execution"""
    logger.info("🎯 Creating Missing Enhanced TP/SL Monitors")
    logger.info("=" * 50)
    
    success = await create_missing_enhanced_monitors()
    
    if success:
        logger.info("✅ Missing Enhanced TP/SL monitors created successfully!")
        logger.info("🔄 The monitoring loop will detect the new monitors within 60 seconds")
        logger.info("📊 You should see 'Monitoring 28 positions' in the logs soon")
    else:
        logger.error("❌ Failed to create missing Enhanced monitors")

if __name__ == "__main__":
    asyncio.run(main())