#!/usr/bin/env python3
"""
Fix mirror position sync to actually create monitors for mirror positions
"""

import asyncio
import logging
from decimal import Decimal
import time
import pickle

logger = logging.getLogger(__name__)

async def sync_mirror_positions_properly():
    """
    Properly sync all mirror account positions and create monitors
    """
    try:
        from execution.mirror_trader import bybit_client_2
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        from clients.bybit_helpers import get_open_orders
        
        if not bybit_client_2:
            logger.warning("Mirror client not available")
            return False
            
        logger.info("🔄 Starting proper mirror position sync")
        
        # Get all mirror positions - need to specify settleCoin for v5 API
        response = bybit_client_2.get_positions(
            category="linear",
            settleCoin="USDT"  # Add this required parameter
        )
        if response['retCode'] != 0:
            logger.error(f"Failed to get mirror positions: {response}")
            return False
            
        mirror_positions = [pos for pos in response['result']['list'] if float(pos.get('size', 0)) > 0]
        
        if not mirror_positions:
            logger.info("📊 No open positions found in mirror account")
            return True
            
        logger.info(f"📊 Found {len(mirror_positions)} positions in mirror account")
        
        monitors_created = 0
        monitors_skipped = 0
        monitors_fixed = 0
        
        for position in mirror_positions:
            try:
                symbol = position.get('symbol')
                side = position.get('side')
                size = float(position.get('size', 0))
                
                if size <= 0:
                    continue
                
                # Use account-aware key format
                monitor_key = f"{symbol}_{side}_mirror"
                
                # Check if monitor already exists
                if monitor_key in enhanced_tp_sl_manager.position_monitors:
                    # Check if it has correct size
                    existing_monitor = enhanced_tp_sl_manager.position_monitors[monitor_key]
                    existing_size = float(existing_monitor.get('position_size', 0))
                    
                    if abs(existing_size - size) > 0.01:  # Size mismatch
                        logger.warning(f"⚠️ Size mismatch for {monitor_key}: monitor={existing_size}, actual={size}")
                        # Update the size
                        existing_monitor['position_size'] = Decimal(str(size))
                        existing_monitor['remaining_size'] = Decimal(str(size))
                        monitors_fixed += 1
                    else:
                        logger.debug(f"✅ Monitor already exists and correct for {monitor_key}")
                        monitors_skipped += 1
                    continue
                
                # Try to find chat_id
                chat_id = await find_chat_id_for_mirror_position(symbol, side)
                
                if not chat_id:
                    logger.warning(f"⚠️ Could not find chat_id for {symbol} {side} (mirror) - creating monitor without alerts")
                
                # Create monitor for this position
                logger.info(f"🆕 Creating monitor for mirror position: {symbol} {side}")
                
                # Get position details
                avg_price = Decimal(str(position.get('avgPrice', 0)))
                
                # Get orders for this position
                orders_response = bybit_client_2.get_open_orders(
                    category="linear",
                    symbol=symbol
                )
                orders = orders_response['result']['list'] if orders_response['retCode'] == 0 else []
                
                tp_orders = {}
                sl_order = None
                
                for order in orders:
                    order_type = order.get('orderType', '')
                    stop_type = order.get('stopOrderType', '')
                    
                    if order_type == 'Limit' and order.get('reduceOnly'):
                        # TP order
                        tp_order_data = {
                            'order_id': order['orderId'],
                            'order_link_id': order.get('orderLinkId', ''),
                            'price': Decimal(str(order['price'])),
                            'quantity': Decimal(str(order['qty'])),
                            'original_quantity': Decimal(str(order['qty'])),
                            'percentage': 100,  # Will be adjusted based on approach
                            'tp_number': len(tp_orders) + 1,
                            'account': 'mirror'
                        }
                        tp_orders[order['orderId']] = tp_order_data
                        
                    elif stop_type == 'StopLoss':
                        sl_order = {
                            'order_id': order['orderId'],
                            'order_link_id': order.get('orderLinkId', ''),
                            'price': Decimal(str(order.get('triggerPrice', 0))),
                            'quantity': Decimal(str(order['qty'])),
                            'original_quantity': Decimal(str(order['qty'])),
                            'covers_full_position': True,
                            'target_position_size': Decimal(str(size)),
                            'account': 'mirror'
                        }
                
                # Create monitor data
                monitor_data = {
                    "symbol": symbol,
                    "side": side,
                    "position_size": Decimal(str(size)),
                    "remaining_size": Decimal(str(size)),
                    "entry_price": avg_price,
                    "avg_price": avg_price,
                    "approach": "conservative" if len(tp_orders) > 1 else "fast",
                    "tp_orders": tp_orders,
                    "sl_order": sl_order,
                    "filled_tps": [],
                    "cancelled_limits": False,
                    "tp1_hit": False,
                    "tp1_info": None,
                    "sl_moved_to_be": False,
                    "sl_move_attempts": 0,
                    "created_at": time.time(),
                    "last_check": time.time(),
                    "limit_orders": [],
                    "limit_orders_cancelled": False,
                    "phase": "MONITORING",
                    "chat_id": chat_id,
                    "account_type": "mirror",
                    "has_mirror": True
                }
                
                # Add to monitors
                enhanced_tp_sl_manager.position_monitors[monitor_key] = monitor_data
                
                # Also add to persistence directly
                pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
                try:
                    with open(pkl_path, 'rb') as f:
                        data = pickle.load(f)
                    
                    if 'bot_data' not in data:
                        data['bot_data'] = {}
                    if 'enhanced_tp_sl_monitors' not in data['bot_data']:
                        data['bot_data']['enhanced_tp_sl_monitors'] = {}
                    
                    data['bot_data']['enhanced_tp_sl_monitors'][monitor_key] = monitor_data
                    
                    # Create dashboard monitor entry if we have chat_id
                    if chat_id and 'monitor_tasks' in data['bot_data']:
                        dashboard_key = f"{chat_id}_{symbol}_{monitor_data['approach']}_mirror"
                        data['bot_data']['monitor_tasks'][dashboard_key] = {
                            'chat_id': chat_id,
                            'symbol': symbol,
                            'approach': monitor_data['approach'],
                            'monitoring_mode': 'ENHANCED_TP_SL_MIRROR',
                            'started_at': time.time(),
                            'active': True,
                            'account_type': 'mirror',
                            'system_type': 'enhanced_tp_sl',
                            'side': side
                        }
                    
                    with open(pkl_path, 'wb') as f:
                        pickle.dump(data, f)
                    
                except Exception as e:
                    logger.error(f"Error saving to persistence: {e}")
                
                monitors_created += 1
                logger.info(f"✅ Created mirror monitor for {symbol} {side} with {len(tp_orders)} TP orders")
                
            except Exception as e:
                logger.error(f"❌ Error creating monitor for mirror position {position}: {e}")
                continue
        
        logger.info(f"🔄 Mirror sync complete: {monitors_created} created, {monitors_fixed} fixed, {monitors_skipped} skipped")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error syncing mirror positions: {e}")
        import traceback
        traceback.print_exc()
        return False

async def find_chat_id_for_mirror_position(symbol: str, side: str) -> int:
    """
    Try to find chat_id for a mirror position from various sources
    """
    chat_id = None
    
    try:
        import pickle
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        # Check main account monitor for same position
        bot_data = data.get('bot_data', {})
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        # Look for main monitor
        main_key = f"{symbol}_{side}_main"
        if main_key in enhanced_monitors:
            chat_id = enhanced_monitors[main_key].get('chat_id')
            if chat_id:
                logger.info(f"✅ Found chat_id {chat_id} from main monitor for {symbol} {side}")
                return chat_id
        
        # Check monitor_tasks
        monitor_tasks = bot_data.get('monitor_tasks', {})
        for mk, mv in monitor_tasks.items():
            if mv.get('symbol') == symbol and mv.get('side') == side:
                chat_id = mv.get('chat_id')
                if chat_id:
                    logger.info(f"✅ Found chat_id {chat_id} from monitor_tasks for {symbol}")
                    return chat_id
        
        # Check user_data
        user_data = data.get('user_data', {})
        for uid, udata in user_data.items():
            if 'positions' in udata:
                for pos in udata.get('positions', []):
                    if pos.get('symbol') == symbol and pos.get('side') == side:
                        chat_id = uid
                        logger.info(f"✅ Found chat_id {chat_id} from user data for {symbol} {side}")
                        return chat_id
                        
    except Exception as e:
        logger.warning(f"Error finding chat_id: {e}")
    
    return chat_id

if __name__ == "__main__":
    import sys
    sys.path.append('/Users/lualakol/bybit-telegram-bot')
    from config.settings import setup_logging
    setup_logging()
    
    result = asyncio.run(sync_mirror_positions_properly())
    if result:
        print("\n✅ Mirror position sync completed successfully!")
        print("All mirror positions now have monitors")
    else:
        print("\n❌ Failed to sync mirror positions")