#!/usr/bin/env python3
"""
Trigger monitoring for all open positions
This will create monitors for existing positions in the running bot
"""
import asyncio
import logging
from decimal import Decimal
import time
import pickle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHAT_ID = 5634913742

async def trigger_monitoring():
    """Trigger monitoring for all open positions"""
    try:
        from clients.bybit_helpers import get_all_positions, get_open_orders
        from utils.robust_persistence import add_trade_monitor
        
        logger.info("🔧 Triggering monitoring for all open positions...")
        
        # Get all positions
        positions = await get_all_positions()
        logger.info(f"📊 Found {len(positions)} open positions")
        
        # Get all orders
        all_orders = await get_open_orders()
        logger.info(f"📋 Found {len(all_orders)} open orders")
        
        monitors_created = 0
        
        for position in positions:
            symbol = position.get('symbol', '')
            side = position.get('side', '')
            size = Decimal(str(position.get('size', '0')))
            avg_price = Decimal(str(position.get('avgPrice', '0')))
            
            if not symbol or not side or size == 0:
                continue
            
            logger.info(f"\n{'='*50}")
            logger.info(f"📊 Processing {symbol} {side}")
            logger.info(f"   Size: {size}")
            logger.info(f"   Entry: ${avg_price}")
            
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
            approach = 'conservative' if len(tp_orders) >= 3 else 'fast'
            
            # Special handling for DOGEUSDT
            limit_orders_filled = False
            if symbol == 'DOGEUSDT' and side == 'Buy':
                limit_orders_filled = True  # DOGEUSDT had limit orders already filled
            
            logger.info(f"📝 Creating monitor:")
            logger.info(f"   - Approach: {approach}")
            logger.info(f"   - TP Orders: {len(tp_orders)}")
            logger.info(f"   - SL Order: {'Yes' if sl_order else 'No'}")
            logger.info(f"   - Limit Orders Filled: {limit_orders_filled}")
            
            # Create monitor data for robust persistence
            monitor_data = {
                'symbol': symbol,
                'side': side,
                'chat_id': CHAT_ID,
                'approach': approach.lower(),
                'account_type': 'main',
                'dashboard_key': f"{CHAT_ID}_{symbol}_{approach}",
                'entry_price': float(avg_price),
                'stop_loss': float(sl_order['price']) if sl_order else 0,
                'take_profits': [{'price': float(tp['price']), 'quantity': float(tp['quantity'])} for tp in tp_orders],
                'created_at': time.time(),
                'system_type': 'enhanced_tp_sl',
                'position_size': float(size),
                'remaining_size': float(size),
                'limit_orders_filled': limit_orders_filled,
                'phase': 'PROFIT_TAKING',
                'tp1_hit': False,
                'sl_moved_to_be': False
            }
            
            # Add position data for robust persistence
            position_data = {
                'symbol': symbol,
                'side': side,
                'size': str(size),
                'avgPrice': str(avg_price),
                'markPrice': position.get('markPrice', str(avg_price)),
                'unrealisedPnl': position.get('unrealisedPnl', '0'),
                'cumRealisedPnl': position.get('cumRealisedPnl', '0')
            }
            
            # Add monitor using robust persistence
            try:
                await add_trade_monitor(symbol, side, monitor_data, position_data)
                logger.info(f"✅ Monitor created via robust persistence")
                monitors_created += 1
                
                # Also update dashboard monitors
                pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
                
                # Create backup
                import shutil
                backup_path = f"{pkl_path}.backup_{int(time.time())}"
                shutil.copy2(pkl_path, backup_path)
                
                # Load and update
                with open(pkl_path, 'rb') as f:
                    data = pickle.load(f)
                
                if 'bot_data' not in data:
                    data['bot_data'] = {}
                if 'monitor_tasks' not in data['bot_data']:
                    data['bot_data']['monitor_tasks'] = {}
                
                # Add dashboard monitor
                dashboard_key = f"{CHAT_ID}_{symbol}_{approach}"
                data['bot_data']['monitor_tasks'][dashboard_key] = {
                    'symbol': symbol,
                    'side': side,
                    'approach': approach,
                    'chat_id': CHAT_ID,
                    'created_at': time.time(),
                    'account_type': 'main'
                }
                
                # Save
                with open(pkl_path, 'wb') as f:
                    pickle.dump(data, f)
                
                logger.info(f"✅ Dashboard monitor entry created")
                
            except Exception as e:
                logger.error(f"❌ Error creating monitor: {e}")
                import traceback
                traceback.print_exc()
        
        logger.info(f"\n✅ Monitoring triggered for {monitors_created} positions")
        logger.info("🔄 The bot will pick up these monitors in the next monitoring cycle (5-12 seconds)")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(trigger_monitoring())